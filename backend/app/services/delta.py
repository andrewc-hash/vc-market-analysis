"""Longitudinal run comparison — "what changed since the last run?".

Two halves, per the R-series philosophy:
  - compute_run_delta(): PURE CODE diff of two final_report dicts (ranking moves,
    weighted-score deltas, valuation/raised changes, EV change, pick change, new
    acquisitions). Deterministic, unit-testable, no LLM.
  - grade_predictions(): ONE LLM call that extracts the BASELINE report's dated,
    falsifiable predictions (§0 binary variable, §4 dated prediction, §11 kill
    criteria, §12 conditions/triggers) and grades each against the NEW run's
    evidence — then code enforces the deadline logic (a future deadline can never
    be "unresolved"/"broken"; it is "pending").

Deliberately standalone: local money/name parsers (no import of app.graph.nodes at
module scope) so the pure half imports clean in token-free tests.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import date

logger = logging.getLogger(__name__)

_STATUSES = {"validated", "broken", "pending", "unresolved"}
_MAX_PREDICTIONS = 10


def _norm_name(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _money(v) -> float | None:
    """'$850M' / '1.2B' / '30' -> float $M (mirrors nodes._parse_money semantics)."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    if not isinstance(v, str):
        return None
    s = v.strip().lower().replace(",", "").replace("$", "").replace("~", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    num = float(m.group(0))
    suffix = s[m.end():].lstrip(" ")
    if suffix[:1] == "b":
        num *= 1000.0
    elif suffix[:1] == "k" or suffix.startswith("thousand"):
        num /= 1000.0
    return num if math.isfinite(num) else None


def _fin(v) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    return None


def _lookup(k: str, table: dict):
    """Norm-name lookup with the codebase's containment fallback ('freedai' matches
    'freedaiinc'), guarded to >=4 chars so a short fragment can't false-match."""
    if k in table:
        return table[k]
    if len(k) >= 4:
        for pk, v in table.items():
            if len(pk) >= 4 and (k in pk or pk in k):
                return v
    return None


def _ledger_by_name(fr: dict) -> dict[str, dict]:
    rows = ((fr.get("financial_ledger") or {}).get("rows")) or []
    return {_norm_name(r.get("startup")): r for r in rows
            if isinstance(r, dict) and str(r.get("startup") or "").strip()}


def compute_run_delta(prev: dict, new: dict) -> dict | None:
    """Deterministic diff of two final_report dicts. None when either side is unusable."""
    if not isinstance(prev, dict) or not isinstance(new, dict):
        return None
    prev_rank = [str(n) for n in (prev.get("ranking") or [])]
    new_rank = [str(n) for n in (new.get("ranking") or [])]
    if not prev_rank and not new_rank:
        return None

    prev_pos = {_norm_name(n): i + 1 for i, n in enumerate(prev_rank)}
    new_pos = {_norm_name(n): i + 1 for i, n in enumerate(new_rank)}

    entered = [n for n in new_rank if _lookup(_norm_name(n), prev_pos) is None]
    exited = [n for n in prev_rank if _lookup(_norm_name(n), new_pos) is None]

    prev_ws = prev.get("weighted_scores") or {}
    new_ws = new.get("weighted_scores") or {}
    prev_score = {_norm_name(n): _fin((d or {}).get("weighted_score")) for n, d in prev_ws.items()}

    movers: list[dict] = []
    for n in new_rank:
        k = _norm_name(n)
        prev_rank_n = _lookup(k, prev_pos)
        if prev_rank_n is None:
            continue
        row: dict = {"startup": n, "prev_rank": prev_rank_n, "new_rank": new_pos[k]}
        ps, ns = _lookup(k, prev_score), _fin((new_ws.get(n) or {}).get("weighted_score"))
        if ps is not None and ns is not None:
            row["score_delta"] = round(ns - ps, 1)
        if row["prev_rank"] != row["new_rank"] or row.get("score_delta"):
            movers.append(row)
    # Biggest absolute score move first; rank-only moves after.
    movers.sort(key=lambda r: abs(r.get("score_delta") or 0), reverse=True)

    # Ledger money deltas (valuation / total raised) for names present in both runs.
    prev_led, new_led = _ledger_by_name(prev), _ledger_by_name(new)
    ledger_changes: list[dict] = []
    for k, nrow in new_led.items():
        prow = _lookup(k, prev_led)
        if not prow:
            continue
        for field in ("valuation", "total_raised"):
            pv, nv = _money(prow.get(field)), _money(nrow.get(field))
            if pv is not None and nv is not None and abs(nv - pv) > max(0.5, 0.02 * pv):
                ledger_changes.append({
                    "startup": str(nrow.get("startup")),
                    "field": field,
                    "prev_musd": round(pv, 1),
                    "new_musd": round(nv, 1),
                })

    # New exit precedents (acquisitions present now, absent in the baseline).
    def _acq_keys(fr: dict) -> set[tuple[str, str]]:
        return {(_norm_name(a.get("target")), _norm_name(a.get("acquirer")))
                for a in (fr.get("acquisitions") or []) if isinstance(a, dict)}
    new_acqs = [a for a in (new.get("acquisitions") or [])
                if isinstance(a, dict)
                and (_norm_name(a.get("target")), _norm_name(a.get("acquirer"))) not in _acq_keys(prev)]

    prev_pick, new_pick = str(prev.get("recommended_pick") or ""), str(new.get("recommended_pick") or "")
    delta = {
        "entered": entered,
        "exited": exited,
        "movers": movers[:8],
        "ledger_changes": ledger_changes[:10],
        "new_acquisitions": new_acqs[:6],
        "pick_changed": bool(prev_pick and new_pick and _norm_name(prev_pick) != _norm_name(new_pick)),
        "prev_pick": prev_pick,
        "new_pick": new_pick,
        "prev_expected_return": _fin(prev.get("expected_return")),
        "new_expected_return": _fin(new.get("expected_return")),
    }
    return delta


# ------------------------------------------------------------------ #
#  Prediction self-grading (one LLM call + code-enforced deadline logic)
# ------------------------------------------------------------------ #

_DEADLINE_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _deadline_passed(deadline: str, today: date) -> bool | None:
    """True/False for a parseable YYYY-MM deadline (passed = strictly before this
    month), None when the string isn't a deadline."""
    m = _DEADLINE_RE.match(str(deadline or "").strip())
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    if not 1 <= mo <= 12:
        return None
    return (y, mo) < (today.year, today.month)


def validate_prediction_audit(raw, today: date) -> list[dict] | None:
    """Coerce the grading LLM's output into render-safe rows, enforcing the deadline
    logic IN CODE: a future/absent deadline can never be 'broken' or 'unresolved' by
    time alone — an ungraded future prediction is 'pending'."""
    rows_in = (raw or {}).get("predictions") if isinstance(raw, dict) else None
    if not isinstance(rows_in, list):
        return None
    out: list[dict] = []
    for r in rows_in[:_MAX_PREDICTIONS]:
        if not isinstance(r, dict):
            continue
        pred = str(r.get("prediction") or "").strip()
        if not pred:
            continue
        status = str(r.get("status") or "").strip().lower()
        if status not in _STATUSES:
            status = "unresolved"
        deadline = str(r.get("deadline") or "").strip()
        passed = _deadline_passed(deadline, today)
        # Code overrides: time-based statuses must agree with the actual calendar.
        if passed is False and status in {"broken", "unresolved"}:
            status = "pending"
        if passed is True and status == "pending":
            status = "unresolved"
        out.append({
            "prediction": pred[:300],
            "metric": str(r.get("metric") or "").strip()[:120],
            "deadline": deadline[:10] if passed is not None else deadline[:20],
            "status": status,
            "evidence": str(r.get("evidence") or "").strip()[:300],
        })
    return out or None


def _slice_sections(md: str, wanted: tuple[int, ...]) -> str:
    parts = re.split(r"(?m)^##\s+(\d+)\.(?!\d)", md or "")
    out = []
    for i in range(1, len(parts) - 1, 2):
        try:
            n = int(parts[i])
        except ValueError:
            continue
        if n in wanted:
            out.append(f"## {n}.{parts[i + 1]}")
    return "\n\n".join(out)


def grade_predictions(baseline_report: dict, new_report: dict, settings, today: date | None = None) -> list[dict] | None:
    """Extract + grade the baseline's dated predictions against the new run. One LLM
    call (judge model); validated in code. None on any failure — strictly best-effort."""
    today = today or date.today()
    base_md = str((baseline_report or {}).get("merged_report") or "")
    if not base_md.strip():
        return None
    base_slice = _slice_sections(base_md, (0, 4, 11, 12)) or base_md[:16000]
    new_md = str((new_report or {}).get("merged_report") or "")
    new_slice = _slice_sections(new_md, (0, 2, 3, 12)) or new_md[:10000]
    research = str((new_report or {}).get("research_data") or "")[:20000]

    user_message = (
        f"Today's date: {today.isoformat()}.\n\n"
        f"## BASELINE report (grade ITS predictions) — key sections\n\n{base_slice[:24000]}\n\n"
        f"---\n\n## NEW evidence (run today) — fresh research brief\n\n{research}\n\n"
        f"---\n\n## NEW evidence — fresh report key sections\n\n{new_slice[:12000]}\n\n"
        f"---\n\nExtract the baseline's dated, falsifiable predictions and grade each against "
        f"the NEW evidence only. JSON ONLY."
    )
    try:
        from app.graph.nodes import (  # lazy: pulls langchain — worker has it, tests stub it
            _invoke_llm_with_retry, _last_balanced_json, _make_llm, _normalize_content,
        )
        from app.graph.prompts import PREDICTION_GRADING_SYSTEM
        llm = _make_llm(settings.judge_model, temperature=0.1, max_tokens=2048)
        result = _invoke_llm_with_retry(llm, [
            ("system", PREDICTION_GRADING_SYSTEM),
            ("user", user_message),
        ])
        raw = _last_balanced_json(_normalize_content(result.content)) or {}
        return validate_prediction_audit(raw, today)
    except Exception as e:  # noqa: BLE001 - self-grading is best-effort, never fails a run
        logger.error("Prediction grading failed: %s", e)
        return None
