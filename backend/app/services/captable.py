"""Cap-table / round-history CSV ingest.

Parses an uploaded funding-round CSV into structured round data so the fund-math
engine runs on the company's REAL entry post-money instead of the stage-banded
inference (`_STAGE_POST`), and the ledger's focal row is grounded instead of
"Not Disclosed". Pure code — no LLM, fully unit-testable.

Expected shape (flexible headers, case-insensitive, extra columns ignored):
    round/stage, date, raised/amount, pre-money, post-money/valuation, investors
One data row per round. Amounts may be "$5M", "5,000,000", "5000000", "1.2B", "750K".
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Header aliases -> canonical field. First alias hit wins; matching is substring-based
# on the lowercased header cell ("Post-Money Valuation ($)" matches "post").
_COLUMN_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    # Order matters: "pre" must be tested before the bare "money"/"valuation" catch-alls.
    ("round", ("round", "stage", "series", "financing")),
    ("date", ("date", "close", "year")),
    ("pre_money", ("pre-money", "pre money", "premoney")),
    ("post_money", ("post-money", "post money", "postmoney", "post_money", "valuation", "post")),
    ("raised", ("raised", "amount", "investment", "size", "capital")),
    ("investors", ("investor", "lead", "participant")),
]

_MAX_ROUNDS = 20


def _money_musd(v) -> float | None:
    """Parse a money cell to $M. Suffix-aware ('5M', '1.2B', '750K'); bare numbers
    >= 50,000 are treated as raw dollars (a $5,000,000 cell), smaller bare numbers
    as already-in-$M (a '5' cell). None when unparseable."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
    else:
        s = str(v).strip().lower().replace(",", "").replace("$", "").replace("~", "")
        if not s:
            return None
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        f = float(m.group(0))
        suffix = s[m.end():].lstrip(" ")
        if suffix[:1] == "b" or suffix.startswith("billion"):
            f *= 1000.0
        elif suffix[:1] == "k" or suffix.startswith("thousand"):
            f /= 1000.0
        elif suffix[:1] == "m" or suffix.startswith("million"):
            pass  # already $M
        elif f >= 50_000:
            f /= 1_000_000.0  # bare raw-dollar cell
    if not math.isfinite(f) or f <= 0:
        return None
    return round(f, 4)


def _map_columns(header: list[str]) -> dict[str, int]:
    """Map canonical field -> column index from a flexible header row."""
    out: dict[str, int] = {}
    lowered = [str(h or "").strip().lower() for h in header]
    for field, aliases in _COLUMN_ALIASES:
        for i, cell in enumerate(lowered):
            if i in out.values():
                continue
            if any(a in cell for a in aliases):
                out[field] = i
                break
    return out


def is_cap_table_csv(text: str) -> bool:
    """Cheap sniff: the first non-empty row must map a round-ish column AND a
    money-ish column (raised or post) — separates a cap table from an arbitrary CSV."""
    try:
        for row in csv.reader(io.StringIO(text or "")):
            if not any(str(c).strip() for c in row):
                continue
            cols = _map_columns(row)
            return "round" in cols and ("raised" in cols or "post_money" in cols)
    except Exception:  # noqa: BLE001
        return False
    return False


def parse_cap_table_csv(text: str, source_file: str = "") -> dict | None:
    """Parse a round-history CSV into the cap_table dict, or None when not one.

    Returns {"rounds": [{round, date, raised_musd, pre_money_musd, post_money_musd,
    investors}], "total_raised_musd", "latest_post_money_musd", "latest_round",
    "source_file"} — every amount normalized to $M in code.
    """
    try:
        rows = [r for r in csv.reader(io.StringIO(text or "")) if any(str(c).strip() for c in r)]
    except Exception as e:  # noqa: BLE001
        logger.warning("Cap-table CSV parse failed: %s", e)
        return None
    if len(rows) < 2:
        return None
    cols = _map_columns(rows[0])
    if "round" not in cols or ("raised" not in cols and "post_money" not in cols):
        return None

    def cell(row: list[str], field: str) -> str:
        i = cols.get(field)
        return str(row[i]).strip() if i is not None and i < len(row) else ""

    rounds: list[dict] = []
    for row in rows[1:][:_MAX_ROUNDS]:
        name = cell(row, "round")
        raised = _money_musd(cell(row, "raised"))
        post = _money_musd(cell(row, "post_money"))
        pre = _money_musd(cell(row, "pre_money"))
        if not name and raised is None and post is None:
            continue
        # Post-money coherence: when pre and raised exist but post is absent, derive it
        # (post = pre + raised) — arithmetic belongs in code, never asserted downstream.
        if post is None and pre is not None and raised is not None:
            post = round(pre + raised, 4)
        rounds.append({
            "round": name[:40] or "round",
            "date": cell(row, "date")[:20],
            "raised_musd": raised,
            "pre_money_musd": pre,
            "post_money_musd": post,
            "investors": cell(row, "investors")[:120],
        })
    if not rounds:
        return None

    raised_vals = [r["raised_musd"] for r in rounds if r["raised_musd"] is not None]
    # Latest round = last data row carrying a post (CSV convention: chronological order);
    # falls back to the last row with any money signal.
    latest = next((r for r in reversed(rounds) if r["post_money_musd"] is not None), None) \
        or next((r for r in reversed(rounds) if r["raised_musd"] is not None), rounds[-1])
    return {
        "rounds": rounds,
        "total_raised_musd": round(sum(raised_vals), 2) if raised_vals else None,
        "latest_post_money_musd": latest.get("post_money_musd"),
        "latest_round": latest.get("round") or "",
        "source_file": source_file[:120],
    }


def find_cap_table(upload_dir: str | Path) -> dict | None:
    """Scan an upload dir for the first CSV that parses as a cap table."""
    p = Path(upload_dir)
    if not p.is_dir():
        return None
    for fp in sorted(p.iterdir()):
        if not fp.is_file() or fp.name.startswith("_") or fp.suffix.lower() != ".csv":
            continue
        try:
            text = fp.read_text(errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        if not is_cap_table_csv(text):
            continue
        parsed = parse_cap_table_csv(text, source_file=fp.name)
        if parsed:
            return parsed
    return None
