"""Durable file-based store for completed analyses (the History feature).

Each finished run is written to `<reports_dir>/<id>.json` (full report + light meta) on a
shared volume, so history survives restarts and the Redis result purge. Listing returns
only the meta so the drawer stays fast; `get` returns the full record (with final_report).

Simple by design (one JSON file per run) — fine for a single-user portfolio deployment;
swap for SQLite/Postgres if it ever needs multi-user or thousands of rows.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

# Light fields returned in list/patch responses (everything except the big final_report).
META_FIELDS = (
    "id", "created_at", "sector", "analysis_mode",
    "focal_startup", "top_pick", "thesis_bias", "label", "starred",
)

# Defaults applied when a stored record is missing/nulls a meta field — one legacy or
# hand-edited JSON must degrade to defaults, never 500 the whole history list.
_META_DEFAULTS = {
    "id": "", "created_at": "", "sector": "", "analysis_mode": "vc",
    "focal_startup": "", "top_pick": "", "thesis_bias": "", "label": "", "starred": False,
}


def _dir() -> Path:
    p = Path(get_settings().reports_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_id(rid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(rid or ""))[:80]


def _path(rid: str) -> Path:
    return _dir() / f"{_safe_id(rid)}.json"


def _read(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001 - a corrupt file must not break the list
        return None


def _meta(rec: dict) -> dict:
    # None-safe: missing or explicit-null fields fall back to defaults so a single
    # malformed record can't fail response-model validation for the entire list.
    return {k: (rec.get(k) if rec.get(k) is not None else _META_DEFAULTS[k]) for k in META_FIELDS}


def _write_atomic(p: Path, text: str) -> None:
    """tmp-file + os.replace so a crash mid-write can never leave truncated JSON
    (which _read would then silently drop — losing the report)."""
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


def save_report(report_id: str, final_report: dict, created_at: str, owner: str = "",
                request_params: dict | None = None) -> dict:
    """Persist a finished report. Returns its meta (or {} on failure).

    `request_params` is the ORIGINAL run request (market_prompt, weights, focal, …) —
    stored so the run can be RE-EXECUTED later on identical inputs (the longitudinal
    re-run feature). Legacy records without it simply can't be re-run.
    """
    fr = final_report or {}
    ranking = fr.get("ranking") or []
    rec = {
        "id": _safe_id(report_id),
        "created_at": created_at,
        "sector": fr.get("sector") or "",
        "analysis_mode": fr.get("analysis_mode") or "vc",
        "focal_startup": fr.get("focal_startup") or "",
        # The report's own §0/§12 recommendation, so the History card can never
        # contradict the document (R11); quality-rank #1 is the fallback.
        "top_pick": fr.get("recommended_pick") or (ranking[0] if ranking else ""),
        "thesis_bias": fr.get("thesis_bias") or "",
        "label": "",
        "starred": False,
        "owner": owner or "",
        "request_params": request_params or {},
        "final_report": fr,
    }
    try:
        _write_atomic(_path(report_id), json.dumps(rec))
        logger.info("Saved report %s to history", rec["id"])
    except Exception as e:  # noqa: BLE001 - persistence is best-effort
        logger.error("Failed to save report %s: %s", report_id, e)
        return {}
    return _meta(rec)


def _visible_to(rec: dict, owner: str | None) -> bool:
    """Owner filter for multi-key deployments. owner=None => auth disabled, everything
    visible (single-operator mode). Legacy records with no owner stay visible to every
    authenticated user (they predate auth; don't strand existing history)."""
    if owner is None:
        return True
    rec_owner = str(rec.get("owner") or "")
    return rec_owner == "" or rec_owner == owner


def list_reports(owner: str | None = None) -> list[dict]:
    """Visible reports' meta, starred first then newest first."""
    out = []
    for p in _dir().glob("*.json"):
        rec = _read(p)
        if rec and rec.get("id") and _visible_to(rec, owner):
            out.append(_meta(rec))
    out.sort(key=lambda r: (bool(r.get("starred")), r.get("created_at") or ""), reverse=True)
    return out


def get_report(rid: str, owner: str | None = None) -> dict | None:
    """Full record including final_report, or None (missing OR not visible to owner)."""
    rec = _read(_path(rid))
    if rec and not _visible_to(rec, owner):
        return None
    return rec


def update_meta(rid: str, label=None, starred=None) -> dict | None:
    """Rename (label) and/or star a report. Returns updated meta or None if missing."""
    rec = _read(_path(rid))
    if not rec:
        return None
    if label is not None:
        rec["label"] = str(label)[:120]
    if starred is not None:
        rec["starred"] = bool(starred)
    try:
        _write_atomic(_path(rid), json.dumps(rec))
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to update report %s: %s", rid, e)
        return None
    return _meta(rec)


def delete_report(rid: str) -> bool:
    p = _path(rid)
    if p.exists():
        try:
            p.unlink()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to delete report %s: %s", rid, e)
    return False
