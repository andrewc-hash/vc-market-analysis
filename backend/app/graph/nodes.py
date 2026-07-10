"""LangGraph node functions for the 3-Phase Consensus Pipeline.

Nodes:
  - researcher_node  : Gemini 2.5 Pro (data gathering with tools)
  - analyst_a_node   : Gemini 2.5 Pro (independent analyst, no tools)
  - analyst_b_node   : Claude Sonnet (independent analyst, no tools)
  - judge_node       : GPT-4.1 (Arbitrator)
  - compile_report   : Gemini 2.5 Pro (single-pass merger)
  - analysts_fanout  : No-op pass-through for parallel fan-out
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import get_settings
from app.graph.prompts import (
    ANALYST_A_SYSTEM,
    ANALYST_B_SYSTEM,
    CLAIM_AUDIT_SYSTEM,
    CLAIM_EXTRACTION_SYSTEM,
    COMPILE_SYSTEM_PROMPT,
    FOUNDER_REPOSITIONING_SECTION,
    RESEARCHER_SYSTEM,
    RESOLVE_SCORES_SYSTEM,
    SCOPE_INFERENCE_SYSTEM,
    STRUCTURED_ARTIFACTS_SYSTEM,
    get_judge_system_prompt,
)
from app.graph.state import ResearchState
from app.graph.tools import RESEARCH_TOOLS

logger = logging.getLogger(__name__)


DIMENSION_KEYS = [
    "financial_health",
    "defensibility",
    "market_urgency",
    "founder_market_fit",
    "regulatory_alignment",
]

# a16z's four measurable moat sub-types. Defensibility is set = their mean IN CODE (R10),
# so the §7 dimension can never disagree with the sub-scores shown beside it.
MOAT_KEYS = [
    "economies_of_scale",
    "differentiated_technology",
    "network_effects",
    "brand_power",
]

# Human-readable labels for LLM-facing text (weights block, founder §0.5 weak-spot anchors).
DIMENSION_LABELS = {
    "financial_health": "Financial Health & Capital Efficiency",
    "defensibility": "Defensibility & IP Moat",
    "market_urgency": "Market Urgency & TRL",
    "founder_market_fit": "Founder-Market Fit",
    "regulatory_alignment": "Regulatory Alignment",
}
MOAT_LABELS = {
    "economies_of_scale": "Economies of Scale",
    "differentiated_technology": "Differentiated Technology",
    "network_effects": "Network Effects",
    "brand_power": "Brand/Direct Power",
}

# Letter-grade bands for the gradesheet — computed IN CODE from the reconciled 0-100
# scores (never LLM-graded), so the visual gradesheet can't disagree with the scorecard.
# VC-calibrated (harsher than academic): A is genuinely strong, F is a real fail.
# (threshold, letter), highest first. Tunable — this constant IS the grading rubric.
GRADE_BANDS = [
    (90, "A+"), (85, "A"), (80, "A-"),
    (75, "B+"), (70, "B"), (65, "B-"),
    (60, "C+"), (55, "C"), (50, "C-"),
    (45, "D+"), (40, "D"), (35, "D-"),
]

# Appended to EVERY compiled report in code (never left to the LLM to remember):
# the tool emits investment-adjacent output, so the liability boundary must be
# deterministic. Do not remove — fund compliance gates on exactly this.
REPORT_DISCLAIMER = (
    "\n\n---\n\n"
    "*Decision-support only — NOT investment advice. This report is AI-generated "
    "preliminary research: figures are drawn from public web sources and may be "
    "incomplete, stale, or wrong. Verify every material figure against a primary "
    "source before acting on it. Scores, rankings, and return ranges are computed "
    "heuristics — not the opinion of a licensed investment adviser. Return figures "
    "are scenario-derived multiples: gross unless explicitly labeled net, and the "
    "net figures reflect only a coarse stage-banded dilution assumption — all "
    "before fees, taxes, and time-value.*\n"
)

# Default dimension weights (research-informed: Defensibility > Financial Health).
# Mirror app.models.schemas.DimensionWeights — keep both in sync.
DEFAULT_WEIGHTS = {
    "financial_health": 20,
    "defensibility": 30,
    "market_urgency": 20,
    "founder_market_fit": 15,
    "regulatory_alignment": 15,
}


def _normalize_weights(weights: dict | None) -> dict[str, float]:
    """Return the dimension weights as fractions that sum to 1.0.

    Robust to any positive integers (the UI does not enforce sum=100): the
    weights are treated as RELATIVE and normalized here. Degenerate input
    (all non-positive) falls back to equal weighting.
    """
    raw = {k: float((weights or {}).get(k, DEFAULT_WEIGHTS[k])) for k in DIMENSION_KEYS}
    total = sum(v for v in raw.values() if v > 0)
    if total <= 0:
        return {k: 1.0 / len(DIMENSION_KEYS) for k in DIMENSION_KEYS}
    return {k: (v if v > 0 else 0.0) / total for k, v in raw.items()}


def _as_score(v):
    """Coerce an LLM-emitted dimension score to float. Accepts int/float and
    numeric strings (LLMs often quote numbers in JSON); rejects bools, non-numeric
    values, and non-finite floats (NaN/inf — which JSON can't represent safely)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _parse_money(v) -> float | None:
    """Parse an LLM money/number string ('$850M', '1.2B', '30', '110%') to a float.

    Money magnitudes are normalized to $M: 'B' scales x1000, 'K' scales /1000, so
    both ratios (valuation / ARR) and sums (field_stats disclosed-capital) are
    unit-consistent even when rows mix '$1.2B' with '$800K'.
    None if there is no parseable number (e.g. 'Not Disclosed').
    """
    if isinstance(v, bool):
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
    # Scale by the unit ATTACHED to the number, not a letter anywhere in the string
    # ("45 (weak)" must not read as billions just because 'b' appears somewhere).
    suffix = s[m.end():].lstrip(" ")
    if suffix[:1] == "b":  # b / bn / billion -> millions
        num *= 1000.0
    elif suffix[:1] == "k" or suffix.startswith("thousand"):  # thousands -> millions
        num /= 1000.0
    return num if math.isfinite(num) else None


def _norm_name(s) -> str:
    """Lowercased, punctuation-light key for matching company names across sections."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _compute_weighted_scores(resolved_scores: dict | None, weights: dict | None):
    """Deterministically compute the Weighted Underwriting Index + ranking.

    The slider weights act HERE, in code — not via LLM arithmetic — so they have
    an exact, reproducible effect on the final ranking. Renormalizes over the
    dimensions the judge actually scored, so a partial scorecard still ranks.

    resolved_scores: {startup: {dimension: 0-100, ...}}
    returns: ({startup: {**raw_dims, "weighted_score": float|None}}, ranking[best..worst])
    """
    norm = _normalize_weights(weights)
    out: dict[str, dict] = {}
    for name, dims in (resolved_scores or {}).items():
        if not isinstance(dims, dict):
            continue
        wsum = 0.0
        present = 0.0
        for k in DIMENSION_KEYS:
            v = _as_score(dims.get(k))
            if v is not None:
                wsum += norm[k] * v
                present += norm[k]
        entry = {k: dims.get(k) for k in DIMENSION_KEYS}
        # Round to 1 decimal: the inputs are 0-100 integers under ±30-40% data
        # uncertainty, so 2 decimals (e.g. 70.75 vs 70.8) is false precision.
        entry["weighted_score"] = round(wsum / present, 1) if present > 0 else None
        if entry["weighted_score"] is None:
            logger.warning("No usable dimension scores for '%s' — dropped from ranking", name)
        out[name] = entry
    ranking = sorted(
        [n for n, e in out.items() if e["weighted_score"] is not None],
        key=lambda n: out[n]["weighted_score"],
        reverse=True,
    )
    return out, ranking


def _validate_resolved_scores(raw, incumbents=None, pre_pmf=None, protect="") -> dict:
    """Coerce reconciled scores into {startup: {dimension: 0-100 float}}; drop malformed.

    The authoritative per-dimension scores now come from reconciling the two analysts in
    code (not the judge), so this gates what _compute_weighted_scores consumes.

    R1 guard: any startup matching `incumbents` (big-tech / EHR / platform players) is dropped
    here in code. R13 guard: any startup matching `pre_pmf` (pre-product-market-fit / pre-launch)
    is also dropped — it is watchlist-only and cannot be underwritten yet. The prompts ask for
    both exclusions; this enforces them so an LLM slip can't leak one into the ranking.

    EXCEPTION: a `protect` name (the user's focal startup) is NEVER dropped — the user explicitly
    asked for it, so it is scored even if early-stage and even if the LLM mislabels it.
    """
    out: dict[str, dict] = {}
    if not isinstance(raw, dict):
        return out
    keep = _norm_name(protect) if str(protect).strip() else None
    blocked = {_norm_name(x) for x in (incumbents or []) if str(x).strip()} - ({keep} if keep else set())
    watchlist = {_norm_name(x) for x in (pre_pmf or []) if str(x).strip()} - ({keep} if keep else set())
    for name, dims in raw.items():
        if not isinstance(dims, dict):
            continue
        n = str(name).strip()
        if not n:
            continue
        if _norm_name(n) in blocked:
            logger.info("Dropped incumbent '%s' from investable scorecard (R1 guard)", n)
            continue
        if _norm_name(n) in watchlist:
            logger.info("Dropped pre-PMF '%s' from investable scorecard (R13 guard)", n)
            continue
        row = {}
        for k in DIMENSION_KEYS:
            v = _as_score(dims.get(k))
            if v is not None:
                row[k] = round(max(0.0, min(100.0, v)), 1)
        if row:
            out[n] = row
    return out


def _validate_moat_subscores(raw, valid_names) -> dict:
    """Coerce the four a16z moat sub-scores into {startup: {moat_key: 0-100}}.

    Only kept for startups that survived scoring (`valid_names`), so a dropped incumbent /
    pre-PMF name can't sneak back in via the moat channel.
    """
    out: dict[str, dict] = {}
    if not isinstance(raw, dict):
        return out
    allowed = {_norm_name(n) for n in valid_names}
    for name, subs in raw.items():
        if not isinstance(subs, dict) or _norm_name(name) not in allowed:
            continue
        row = {}
        for k in MOAT_KEYS:
            v = _as_score(subs.get(k))
            if v is not None:
                row[k] = round(max(0.0, min(100.0, v)), 1)
        if row:
            out[str(name).strip()] = row
    return out


def _apply_moat_reconciliation(resolved_scores: dict, moat_subscores: dict) -> None:
    """R10: set Defensibility = mean of the four moat sub-scores, IN CODE.

    Mutates resolved_scores in place so the §7 Defensibility dimension can never disagree
    with the moat sub-scores shown next to it (the prior incoherence Codex flagged).
    """
    by_norm = {_norm_name(n): n for n in resolved_scores}
    for name, subs in (moat_subscores or {}).items():
        target = by_norm.get(_norm_name(name))
        present = [subs[k] for k in MOAT_KEYS if k in subs]
        if target and present:
            resolved_scores[target]["defensibility"] = round(sum(present) / len(present), 1)


# ------------------------------------------------------------------ #
#  Probability-weighted return — computed in CODE (R6), not asserted
#  by the LLM. Mirrors the weighting-in-code philosophy: the analysts
#  supply scenario probabilities + return multiples, we do the arithmetic.
# ------------------------------------------------------------------ #

def _validate_scenarios(raw) -> dict | None:
    """Coerce the recommended startup's outcome scenarios into a checkable shape.

    Returns {"startup": str|None, "scenarios": [{label, probability(0-1),
    multiple_low, multiple_high}], "expected_return": float|None} or None.
    """
    if not isinstance(raw, dict):
        return None
    rows_in = raw.get("scenarios")
    if not isinstance(rows_in, list):
        return None
    # Entry post-money ($M) — enables exit-dollar-derived multiples (exit ÷ entry, in code),
    # which are harder to inflate than a hand-asserted "50-100x".
    entry_post = _parse_money(raw.get("entry_post_money_musd"))
    if entry_post is not None and entry_post <= 0:
        entry_post = None
    scenarios = []
    for r in rows_in if isinstance(rows_in, list) else []:
        if not isinstance(r, dict):
            continue
        label = str(r.get("label", "")).strip()
        prob = _as_score(r.get("probability"))
        lo = _parse_money(r.get("multiple_low", r.get("multiple")))
        hi = _parse_money(r.get("multiple_high", r.get("multiple")))
        # Exit dollar values ($M), sanitized: non-negative, low<=high, singleton fills.
        ex_lo = _parse_money(r.get("exit_value_low_musd"))
        ex_hi = _parse_money(r.get("exit_value_high_musd"))
        ex_lo = ex_lo if (ex_lo is not None and ex_lo >= 0) else None
        ex_hi = ex_hi if (ex_hi is not None and ex_hi >= 0) else None
        if ex_lo is None and ex_hi is not None:
            ex_lo = ex_hi
        if ex_hi is None and ex_lo is not None:
            ex_hi = ex_lo
        if ex_lo is not None and ex_hi is not None and ex_lo > ex_hi:
            ex_lo, ex_hi = ex_hi, ex_lo
        # Derive multiples from exit dollars when possible. Policy: fill when the stated
        # multiple is missing; OVERRIDE when both exist and disagree by >25% (the dollar
        # figure is comp-anchored and unit-checked; the bare multiple is the inflatable one).
        multiple_source = "stated"
        if entry_post is not None and ex_lo is not None:
            d_lo, d_hi = ex_lo / entry_post, ex_hi / entry_post
            if lo is None and hi is None:
                lo, hi, multiple_source = round(d_lo, 2), round(d_hi, 2), "exit-derived"
            else:
                _s_lo = lo if lo is not None else hi
                _s_hi = hi if hi is not None else lo
                s_mid = (_s_lo + _s_hi) / 2
                d_mid = (d_lo + d_hi) / 2
                if s_mid > 0 and abs(d_mid - s_mid) / s_mid > 0.25:
                    lo, hi, multiple_source = round(d_lo, 2), round(d_hi, 2), "exit-derived"
        if prob is None or (lo is None and hi is None):
            continue
        # probabilities may arrive as 0-1 or 0-100; normalize a >1 value as a percent
        p = prob / 100.0 if prob > 1 else prob
        row = {
            "label": label or "scenario",
            "probability": round(max(0.0, min(1.0, p)), 4),
            "multiple_low": lo if lo is not None else hi,
            "multiple_high": hi if hi is not None else lo,
            "multiple_source": multiple_source,
            # One-phrase outcome path (who buys / what happens) — judgment, carried verbatim.
            # `or ""` (not a .get default): the LLM emits "path": null despite the omit rule,
            # and str(None) would render a literal "None" in the UI/export path column.
            "path": str(r.get("path") or "").strip()[:200],
        }
        if ex_lo is not None:
            row["exit_value_low_musd"] = round(ex_lo, 1)
            row["exit_value_high_musd"] = round(ex_hi, 1)
        scenarios.append(row)
    if not scenarios:
        return None
    name = str(raw.get("startup", raw.get("recommended_startup", ""))).strip() or None
    low, high = _expected_return_range(scenarios)
    out = {
        "startup": name,
        "scenarios": scenarios,
        "expected_return": _compute_expected_return(scenarios),
        # Honest bounds: EV over the low vs high multiples. A single point estimate on
        # ranged scenarios is false precision (KNOWN_ISSUES R6') — report the range.
        "expected_return_low": low,
        "expected_return_high": high,
    }
    if entry_post is not None:
        out["entry_post_money_musd"] = round(entry_post, 2)
    return out


def _compute_expected_return(scenarios) -> float | None:
    """Σ probability × midpoint(multiple_low, multiple_high), in code.

    Renormalizes probabilities if they don't sum to 1 (e.g. 25/60/15 -> /100 already
    handled, but 30/60/15 = 1.05 gets rescaled) so the expected value is always
    internally consistent with the stated scenarios. None if nothing usable.
    """
    if not scenarios:
        return None
    rows = [s for s in scenarios if isinstance(s, dict)]
    psum = sum((s.get("probability") or 0) for s in rows)
    if psum <= 0:
        return None
    ev = 0.0
    for s in rows:
        lo, hi = s.get("multiple_low"), s.get("multiple_high")
        mids = [m for m in (lo, hi) if isinstance(m, (int, float))]
        if not mids:
            continue
        mid = sum(mids) / len(mids)
        ev += ((s.get("probability") or 0) / psum) * mid
    return round(ev, 2) if math.isfinite(ev) else None


# Ownership retention from entry to exit (1 - expected future dilution), stage-banded.
# Coarse, clearly-labeled assumptions — the point is honest net-of-dilution math instead
# of a gross multiple masquerading as an investor outcome (KNOWN_ISSUES R6').
_STAGE_RETENTION = [
    ("pre-seed", 0.60), ("seed", 0.65), ("series a", 0.70),
    ("series b", 0.75), ("series c", 0.80), ("growth", 0.85), ("scale", 0.85),
]
_DEFAULT_RETENTION = 0.70


def _stage_retention(stage: str | None) -> float:
    s = str(stage or "").lower()
    return next((r for key, r in _STAGE_RETENTION if key in s), _DEFAULT_RETENTION)


def _scenario_dominance(scenarios) -> tuple[str, int] | None:
    """(label, % of the expected value contributed) for the scenario that dominates the
    EV — pure arithmetic, handed to the compiler so 'the math is dominated by the base
    case' is a computed statement, never an assertion. None when nothing usable."""
    if not scenarios:
        return None
    rows = [s for s in scenarios if isinstance(s, dict)]
    psum = sum((s.get("probability") or 0) for s in rows)
    if psum <= 0:
        return None
    contribs: list[tuple[str, float]] = []
    for s in rows:
        lo, hi = s.get("multiple_low"), s.get("multiple_high")
        mids = [m for m in (lo, hi) if isinstance(m, (int, float))]
        if not mids:
            continue
        contribs.append((str(s.get("label", "scenario")),
                         ((s.get("probability") or 0) / psum) * (sum(mids) / len(mids))))
    total = sum(c for _, c in contribs)
    if not contribs or total <= 0 or not math.isfinite(total):
        return None
    label, best = max(contribs, key=lambda t: t[1])
    return label, round(best / total * 100)


def _expected_return_range(scenarios) -> tuple[float | None, float | None]:
    """(EV over the LOW multiples, EV over the HIGH multiples) — the honest bounds
    around the midpoint expected return. Same renormalization as
    _compute_expected_return; (None, None) when nothing is usable."""
    if not scenarios:
        return None, None
    rows = [s for s in scenarios if isinstance(s, dict)]
    psum = sum((s.get("probability") or 0) for s in rows)
    if psum <= 0:
        return None, None
    ev_lo = ev_hi = 0.0
    any_row = False
    for s in rows:
        lo, hi = s.get("multiple_low"), s.get("multiple_high")
        if not isinstance(lo, (int, float)) and not isinstance(hi, (int, float)):
            continue
        lo = lo if isinstance(lo, (int, float)) else hi
        hi = hi if isinstance(hi, (int, float)) else lo
        w = (s.get("probability") or 0) / psum
        ev_lo += w * min(lo, hi)
        ev_hi += w * max(lo, hi)
        any_row = True
    if not any_row or not (math.isfinite(ev_lo) and math.isfinite(ev_hi)):
        return None, None
    return round(ev_lo, 2), round(ev_hi, 2)


# ------------------------------------------------------------------ #
#  Fund-math engine — "does THIS deal return MY fund?"
#  Pure functions over numeric inputs (determinism-in-code): the compiler
#  LLM only renders the code-computed strings, asserts NO numbers. Extends
#  the shipped scenario/net-of-dilution machinery WITHOUT contradicting it —
#  because retention rho is constant across scenarios, E[net_MoIC] =
#  rho x E[gross_MoIC] = rho x expected_return, i.e. exactly the shipped
#  expected_return_net_* midpoint, monetized through ownership and dollars.
#  Designed + adversarially verified by an expert panel (8 worked test
#  vectors pin every output — see backend/tests/test_fund_math.py).
# ------------------------------------------------------------------ #

# Typical post-money by stage ($M) — used ONLY to infer a missing entry post
# (flag 'post_inferred'; CALIBRATION-PENDING — a wrong seed post shifts the
# required-exit ~1.7x). And typical hold-to-exit by stage (years).
_STAGE_POST = [
    ("pre-seed", 8.0), ("seed", 20.0), ("series a", 60.0),
    ("series b", 150.0), ("series c", 400.0), ("growth", 1000.0), ("scale", 1000.0),
]
_STAGE_HOLD = [
    ("pre-seed", 8.0), ("seed", 7.0), ("series a", 6.0),
    ("series b", 5.0), ("series c", 4.0), ("growth", 3.0), ("scale", 3.0),
]
_DEFAULT_HOLD = 6.0
_UNIT_SUSPECT_MUSD = 5000.0  # >$5B entered in $M is implausible (likely raw dollars)


def _fin(v):
    """Finite float or None (JSON-safe; rejects bools/NaN/inf/non-numeric strings)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _stage_post(stage: str | None) -> float | None:
    s = str(stage or "").lower()
    return next((p for key, p in _STAGE_POST if key in s), None)


def _stage_hold(stage: str | None) -> float:
    s = str(stage or "").lower()
    return next((h for key, h in _STAGE_HOLD if key in s), _DEFAULT_HOLD)


def _net_irr(net_moic, years) -> float | None:
    """Annualized IRR (%) from a NET MoIC and a single bullet horizon.
    None when years<=0 or 0<years<0.25 (annualization explodes sub-quarter);
    the total-loss floor (-100%) is applied BEFORE the power op so a
    non-positive base never reaches ** (which would yield a complex number)."""
    y = _fin(years)
    if y is None or y < 0.25:
        return None
    m = _fin(net_moic)
    if m is None:
        return None
    if m <= 0:
        return -100.0
    try:
        v = (m ** (1.0 / y) - 1.0) * 100.0
    except (ValueError, OverflowError):
        return None
    return round(v, 2) if math.isfinite(v) else None


def _fund_scenario_row(s: dict, check: float, post: float | None, own_true: float | None,
                       retention: float, fund_size: float, years, returner_frac: float,
                       target_mult: float) -> dict | None:
    """One scenario's fund-level outcome. None when the scenario carries no usable
    multiple (skip + renormalize, exactly as _compute_expected_return)."""
    lo, hi = s.get("multiple_low"), s.get("multiple_high")
    mids = [m for m in (lo, hi) if isinstance(m, (int, float))]
    if not mids:
        return None
    g = sum(mids) / len(mids)  # gross MoIC = midpoint (== _compute_expected_return)
    net_moic = g * retention
    net_proceeds = check * g * retention  # = gross_proceeds x rho = own_at_exit x implied_exit
    gross_proceeds = check * g
    net_turns = net_proceeds / fund_size
    return {
        "label": str(s.get("label", "scenario")),
        "probability": round(float(s.get("probability") or 0), 4),
        "gross_MoIC": round(g, 4),
        "net_MoIC": round(net_moic, 4),
        "implied_exit_value_musd": round(g * post, 2) if post is not None else None,
        "gross_proceeds_musd": round(gross_proceeds, 4),
        "net_proceeds_musd": round(net_proceeds, 4),
        "gross_turns": round(gross_proceeds / fund_size, 4),
        "net_turns": round(net_turns, 4),
        "net_irr_pct": _net_irr(net_moic, years),
        "returns_fund": net_proceeds >= returner_frac * fund_size,
        "is_fund_maker": net_turns >= target_mult,
    }


def _compute_fund_math(scenarios, fund_econ, stage, retention, *,
                       mode: str = "vc", scen_is_focal: bool = True) -> dict | None:
    """final_report['fund_math'] or None. Master-gated on fund_size. Optional-degrades:
    absent fund inputs suppress the block and the shipped gross/net ranges render unchanged."""
    rows_in = scenarios.get("scenarios") if isinstance(scenarios, dict) else scenarios
    if not isinstance(rows_in, list) or not rows_in:
        return None
    fe = fund_econ or {}
    fund_size = _fin(fe.get("fund_size_musd"))
    if fund_size is None or fund_size <= 0:      # MASTER GATE
        return None
    # Founder mode where the modelled scenarios are a COMPETITOR's: fund-math on the
    # focal's headline would be meaningless — suppress (mirrors the return_note branch).
    if mode == "founder" and not scen_is_focal:
        return None

    flags: list[str] = []
    if fund_size > _UNIT_SUSPECT_MUSD:
        flags.append("unit_suspect")

    check = _fin(fe.get("check_size_musd"))
    post = _fin(fe.get("entry_post_money_musd"))
    own_pct = _fin(fe.get("target_ownership_pct"))
    if own_pct is not None and not (0 < own_pct <= 100):
        flags.append("ownership_input_ignored")
        own_pct = None

    # Derive a missing check or post from target ownership; infer post from stage.
    if check is None and own_pct is not None and post is not None:
        check = (own_pct / 100.0) * post
    if post is None and check is not None and own_pct is not None:
        post = check / (own_pct / 100.0)
    if post is None:
        inferred = _stage_post(stage)
        if inferred is not None and check is not None:
            post, _ = inferred, flags.append("post_inferred")
    if check is None:                            # no ownership path at all
        return None
    if check <= 0:
        return None
    if check > _UNIT_SUSPECT_MUSD or (post is not None and post > _UNIT_SUSPECT_MUSD):
        if "unit_suspect" not in flags:
            flags.append("unit_suspect")

    # Entry ownership: TRUE (unclamped) drives all math; DISPLAY is clamped to 100%.
    own_true = (check / post) if (post is not None and post > 0) else None
    own_display = None
    if own_true is not None:
        if own_true > 1.0:
            flags.append("ownership_infeasible")
        own_display = min(own_true, 1.0)
        if own_pct is not None and abs(own_true - own_pct / 100.0) > 0.01:
            flags.append("ownership_mismatch")
    own_at_exit_true = own_true * retention if own_true is not None else None

    if 0 < fund_size <= check:
        flags.append("check_exceeds_fund")
    if not any(k in str(stage or "").lower() for k, _ in _STAGE_RETENTION):
        flags.append("retention_defaulted")

    # Holding horizon (single, v1): request override else stage default.
    years = _fin(fe.get("holding_years"))
    if years is None:
        years = _stage_hold(stage)
    elif 0 < years < 0.25:
        flags.append("holding_too_short")
    returner_frac = _fin(fe.get("fund_returner_fraction"))
    if returner_frac is None or returner_frac <= 0:
        returner_frac = 1.0
    if returner_frac < 0.1:
        flags.append("unusual_returner_bar")
    target_mult = _fin(fe.get("target_fund_multiple"))
    if target_mult is None or target_mult < 1.0:
        target_mult = 3.0

    rows = [r for r in (_fund_scenario_row(s, check, post, own_true, retention, fund_size,
                                           years, returner_frac, target_mult)
                        for s in rows_in if isinstance(s, dict)) if r]
    if not rows:
        return None

    # Expected (renormalized over psum, exactly as _compute_expected_return).
    psum = sum(r["probability"] for r in rows)
    exp = {}
    if psum > 0:
        e_gross = sum(r["probability"] / psum * r["gross_MoIC"] for r in rows)
        e_net_moic = e_gross * retention
        e_net_proceeds = check * e_gross * retention
        irrs = [r["net_irr_pct"] for r in rows]
        exp = {
            "expected_gross_MoIC": round(e_gross, 4),
            "expected_net_MoIC": round(e_net_moic, 4),
            "expected_gross_proceeds_musd": round(check * e_gross, 4),
            "expected_net_proceeds_musd": round(e_net_proceeds, 4),
            "expected_net_turns": round(e_net_proceeds / fund_size, 4),
            # PRIMARY: IRR of the expected multiple (approximation, Jensen upper bound).
            "expected_net_irr_pct": _net_irr(e_net_moic, years),
            # SECONDARY (disclosed): prob-weighted mean of per-scenario IRRs.
            "expected_net_irr_pw_pct": (
                round(sum(r["probability"] / psum * i for r, i in zip(rows, irrs)), 2)
                if all(i is not None for i in irrs) else None),
        }

    # Requirements: the exit / multiples needed to return `returner_frac` of the fund.
    req_net_moic = returner_frac * fund_size / check
    requirements = {
        "required_exit_value_musd": (round(returner_frac * fund_size / own_at_exit_true, 2)
                                     if own_at_exit_true else None),
        "required_net_MoIC": round(req_net_moic, 2),
        "required_gross_MoIC": round(req_net_moic / retention, 2) if retention > 0 else None,
        "preserved_ownership_ref_musd": (round(returner_frac * fund_size / own_true, 2)
                                         if own_true else None),
        "fund_returner_fraction": round(returner_frac, 4),
        "target_fund_multiple": round(target_mult, 4),
    }

    verdicts = {
        "can_return_fund": any(r["returns_fund"] for r in rows),
        "best_case_net_turns": round(max(r["net_turns"] for r in rows), 4),
        "expected_returns_fund": bool(exp) and exp["expected_net_proceeds_musd"] >= returner_frac * fund_size,
        "is_fund_maker": any(r["is_fund_maker"] for r in rows),
    }

    return {
        "scenarios": rows,
        "expected": exp or None,
        "requirements": requirements,
        "verdicts": verdicts,
        "assumptions": {
            "fund_size_musd": round(fund_size, 4),
            "check_size_musd": round(check, 4),
            "entry_post_money_musd": round(post, 4) if post is not None else None,
            "entry_ownership_pct": round(own_display * 100, 2) if own_display is not None else None,
            "ownership_at_exit_pct": round(own_at_exit_true * 100, 2) if own_at_exit_true is not None else None,
            "retention": round(retention, 4),
            "holding_years": round(years, 4) if years is not None else None,
            "stage": stage or "",
        },
        "flags": flags,
    }


def _musd_str(v) -> str:
    """Compact $M/$B string for a millions-USD figure ($769M, $1.2B)."""
    if v is None:
        return "n/a"
    return f"${v / 1000:.1f}B" if v >= 1000 else f"${round(v)}M"


_FUND_FLAG_NOTES = {
    "post_inferred": "entry post-money inferred from stage — calibration-pending",
    "ownership_infeasible": "check exceeds post-money — entry ownership clamped to 100%",
    "retention_defaulted": "stage unknown — 0.70 dilution retention assumed",
    "ownership_mismatch": "stated ownership disagrees with check/post — check/post used",
    "ownership_input_ignored": "target ownership out of range — ignored",
    "unit_suspect": "a dollar input looks implausibly large — check it is in $M, not raw dollars",
    "holding_too_short": "holding period under a quarter — IRR suppressed",
    "unusual_returner_bar": "return-the-fund bar set unusually low",
    "check_exceeds_fund": "check is larger than the whole fund",
    "post_from_cap_table": "entry post-money taken from the uploaded cap table",
}


def _fund_math_note(fm: dict | None, subject: str) -> str:
    """Compiler-facing '## Fund Fit' block — every number CODE-COMPUTED and rendered
    VERBATIM (the LLM asserts no fund figures), same contract as return_note. '' when
    no fund_math (the block simply does not appear)."""
    if not fm:
        return ""
    a = fm["assumptions"]; ver = fm["verdicts"]; req = fm["requirements"]; exp = fm.get("expected")
    who = subject or "this deal"
    lines = []
    # (1) header
    if a.get("entry_ownership_pct") is not None and a.get("ownership_at_exit_pct") is not None:
        lines.append(
            f"For a {_musd_str(a['fund_size_musd'])} fund, a {_musd_str(a['check_size_musd'])} check "
            f"at {_musd_str(a['entry_post_money_musd'])} post = {a['entry_ownership_pct']:g}% entry → "
            f"{a['ownership_at_exit_pct']:g}% at exit (after {round((1 - a['retention']) * 100)}% "
            f"dilution to exit).")
    else:
        lines.append(
            f"For a {_musd_str(a['fund_size_musd'])} fund, a {_musd_str(a['check_size_musd'])} check "
            f"(entry post-money not given, so ownership %/required-exit are omitted).")
    # (2) scenario table
    tbl = ["| Scenario | Prob | Gross MoIC | Net MoIC | Net proceeds | Net turns | Net IRR |",
           "|---|---|---|---|---|---|---|"]
    for r in fm["scenarios"]:
        irr = "n/a" if r["net_irr_pct"] is None else f"{r['net_irr_pct']:+.1f}%"
        tbl.append(f"| {r['label']} | {round(r['probability'] * 100):g}% | {r['gross_MoIC']:g}x | "
                   f"{r['net_MoIC']:g}x | {_musd_str(r['net_proceeds_musd'])} | {r['net_turns']:g}x | {irr} |")
    lines.append("\n".join(tbl))
    # (3) three verdict one-liners
    if req.get("required_exit_value_musd") is not None:
        lines.append(f"Required to return the fund: ~{_musd_str(req['required_exit_value_musd'])} exit "
                     f"({req['required_net_MoIC']:g}x net / {req['required_gross_MoIC']:g}x gross on the check).")
    else:
        lines.append(f"Required to return the fund: {req['required_net_MoIC']:g}x net on the check "
                     f"({req['required_gross_MoIC']:g}x gross).")
    n_ret = sum(1 for r in fm["scenarios"] if r["returns_fund"])
    lines.append(f"Best modelled case returns {ver['best_case_net_turns']:g}x of the fund — "
                 f"returns the fund in {n_ret}/{len(fm['scenarios'])} scenarios "
                 f"({'YES' if ver['can_return_fund'] else 'NO'} — any path returns it).")
    lines.append(f"Fund-maker (≥{req['target_fund_multiple']:g}x the fund in one position): "
                 f"{'YES' if ver['is_fund_maker'] else 'NO'}.")
    # (4) expected line
    if exp:
        eirr = "n/a" if exp["expected_net_irr_pct"] is None else f"{exp['expected_net_irr_pct']:+.1f}% net IRR"
        hy = a.get("holding_years")
        lines.append(f"Expected (probability-weighted): {exp['expected_net_MoIC']:g}x net / "
                     f"{exp['expected_net_turns']:g}x of the fund / {eirr}"
                     + (f" ({hy:g}y)" if hy is not None else "") + ".")
    foot = [f"_{_FUND_FLAG_NOTES[f]}_" for f in fm.get("flags", []) if f in _FUND_FLAG_NOTES]
    block = "\n".join(lines) + ("\n" + "; ".join(foot) if foot else "")
    return (
        f"\n\nFUND-FIT BLOCK (SYSTEM-COMPUTED — render VERBATIM as a '### Fund Fit — Does this "
        f"return the fund?' subsection inside Section 12, for {who}; assert NONE of these numbers "
        f"yourself, they are computed in code from the scenario table and the fund inputs; net = "
        f"gross × the same stage dilution retention used above; turns-of-fund are GROSS of fund "
        f"fees/carry; do NOT recompute):\n{block}"
    )


# ------------------------------------------------------------------ #
#  Structured artifact validators (market_map + financial_ledger)
#  The LLM emits these as JSON; we coerce/clamp them in code so the UI
#  always receives a well-formed shape (or null) — never raw LLM output.
# ------------------------------------------------------------------ #

def _clamp_position(v):
    """Coerce a 0-100 scored position; clamp into range, or None if unusable."""
    n = _as_score(v)
    if n is None:
        return None
    return round(max(0.0, min(100.0, n)), 1)


def _coerce_axis(ax) -> dict | None:
    if not isinstance(ax, dict):
        return None
    label = str(ax.get("label", "")).strip()
    low = str(ax.get("low", "")).strip()
    high = str(ax.get("high", "")).strip()
    if not label and not (low and high):
        return None
    return {"label": label, "low": low, "high": high}


def _validate_market_map(raw, weighted_scores: dict | None = None,
                         incumbents=None, canonical=None) -> dict | None:
    """Coerce the LLM's market_map into a render-safe shape, or None if unusable.

    Requires both axes and at least one positioned company. Clamps x/y to [0,100],
    backfills each company's weighted_score from the AUTHORITATIVE code-computed
    weighted_scores when available, and drops malformed company entries.

    R1: is_incumbent is forced from the authoritative `incumbents` list (an incumbent
    can never be styled as an investable dot). R3: logs ranked startups the map omitted.
    """
    if not isinstance(raw, dict):
        return None
    axes = raw.get("axes")
    x = _coerce_axis(axes.get("x")) if isinstance(axes, dict) else None
    y = _coerce_axis(axes.get("y")) if isinstance(axes, dict) else None
    if not x or not y:
        return None

    ws = weighted_scores if isinstance(weighted_scores, dict) else {}
    inc_keys = {_norm_name(v) for v in (incumbents or []) if str(v).strip()}
    raw_companies = raw.get("companies")
    companies = []
    placed = set()
    for c in raw_companies if isinstance(raw_companies, list) else []:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name", "")).strip()
        cx, cy = _clamp_position(c.get("x")), _clamp_position(c.get("y"))
        if not name or cx is None or cy is None:
            continue  # a dot needs a name AND a position
        is_incumbent = bool(c.get("is_incumbent")) or _norm_name(name) in inc_keys
        # An incumbent is reference-only — it must not carry an investable weighted score.
        wscore = None if is_incumbent else (
            ws.get(name, {}).get("weighted_score") if isinstance(ws.get(name), dict) else None
        )
        if wscore is None and not is_incumbent:
            wscore = _as_score(c.get("weighted_score"))
        companies.append({
            "name": name,
            "x": cx,
            "y": cy,
            "segment": str(c.get("segment", "")).strip() or None,
            "stage": str(c.get("stage", "")).strip() or None,
            "raised_usd_m": _as_score(c.get("raised_usd_m")),
            "weighted_score": wscore,
            "is_incumbent": is_incumbent,
            "rationale": str(c.get("rationale", "")).strip() or None,
        })
        placed.add(_norm_name(name))
    if not companies:
        return None

    # R3: surface coverage gaps (can't synthesize a position, but don't hide the omission).
    missing = [n for n in (canonical or []) if _norm_name(n) not in placed]
    if missing:
        logger.info("Market map omitted ranked startups %s (R3 coverage gap)", missing)

    raw_quadrants = raw.get("quadrants")
    quadrants = [
        {
            "name": str(q.get("name")).strip(),
            "x": "high" if str(q.get("x", "")).strip().lower() == "high" else "low",
            "y": "high" if str(q.get("y", "")).strip().lower() == "high" else "low",
        }
        for q in (raw_quadrants if isinstance(raw_quadrants, list) else [])
        if isinstance(q, dict) and str(q.get("name", "")).strip()
    ]
    white_space = None
    w = raw.get("white_space")
    if isinstance(w, dict):
        wx, wy = _clamp_position(w.get("x")), _clamp_position(w.get("y"))
        # Reject the degenerate (0,0) default — that means the LLM didn't actually place it.
        if wx is not None and wy is not None and not (wx == 0 and wy == 0):
            white_space = {"x": wx, "y": wy, "label": str(w.get("label", "Investable white space")).strip()}

    return {"axes": {"x": x, "y": y}, "quadrants": quadrants, "white_space": white_space, "companies": companies}


_LEDGER_COLS = [
    "startup", "stage", "total_raised", "valuation", "arr",
    "implied_arr_multiple", "yoy_growth", "ltv_cac", "nrr", "burn_multiple", "rule_of_40",
]
_FLAG_VALUES = {"ok", "warn", "bad"}


def _validate_financial_ledger(raw, canonical=None, incumbents=None) -> dict | None:
    """Coerce the LLM's financial_ledger into a render-safe table, or None if empty.

    Missing values become "Not Disclosed"; flags are filtered to ok/warn/bad on
    known columns; rows without a startup name are dropped.

    R7: `implied_arr_multiple` (= valuation / ARR) is computed HERE in code, not trusted
    from the prose, so the BLUF/§6/§12 can never disagree on it.
    R3: `canonical` (the investable ranking set) reconciles coverage — every ranked startup
    gets a row (synthesized as "Not Disclosed" if the LLM dropped it), and rows are split
    into investable startups (is_incumbent=False) first, incumbents last.
    """
    if isinstance(raw, list):
        rows_in = raw
    elif isinstance(raw, dict):
        rows_in = raw.get("rows", [])
    else:
        rows_in = []
    if not isinstance(rows_in, list):
        rows_in = []

    inc_keys = {_norm_name(x) for x in (incumbents or []) if str(x).strip()}
    rows = []
    seen = set()
    for r in rows_in:
        if not isinstance(r, dict):
            continue
        name = str(r.get("startup", r.get("name", ""))).strip()
        if not name:
            continue
        row = {"startup": name}
        for col in _LEDGER_COLS[1:]:
            if col == "implied_arr_multiple":
                continue  # computed below, never read from the LLM
            v = r.get(col)
            row[col] = str(v).strip() if v not in (None, "") else "Not Disclosed"
        # R7: derive the valuation/ARR multiple in code so it is internally consistent.
        val, arr = _parse_money(r.get("valuation")), _parse_money(r.get("arr"))
        row["implied_arr_multiple"] = f"{round(val / arr, 1)}x" if val and arr else "Not Disclosed"
        flags = {}
        raw_flags = r.get("flags")
        if isinstance(raw_flags, dict):
            for k, fv in raw_flags.items():
                if k in _LEDGER_COLS and str(fv).lower() in _FLAG_VALUES:
                    flags[k] = str(fv).lower()
        row["flags"] = flags
        row["is_incumbent"] = bool(r.get("is_incumbent")) or _norm_name(name) in inc_keys
        rows.append(row)
        seen.add(_norm_name(name))

    # R3: backfill any canonical (ranked, investable) startup the LLM dropped from the table.
    for cname in (canonical or []):
        if _norm_name(cname) in seen or _norm_name(cname) in inc_keys:
            continue
        logger.info("Ledger missing ranked startup '%s' — backfilled as Not Disclosed (R3)", cname)
        row = {"startup": str(cname).strip()}
        for col in _LEDGER_COLS[1:]:
            row[col] = "Not Disclosed"
        row["flags"] = {}
        row["is_incumbent"] = False
        rows.append(row)
        seen.add(_norm_name(cname))

    if not rows:
        return None
    # Investable startups first, incumbents (reference rows) last.
    rows.sort(key=lambda r: r["is_incumbent"])
    return {"columns": _LEDGER_COLS, "rows": rows, "stage_banded": True}


def _format_weights_block(weights: dict | None) -> str:
    """Human-readable normalized weights, for injecting into LLM context."""
    norm = _normalize_weights(weights)
    return "\n".join(f"  - {DIMENSION_LABELS[k]}: {round(norm[k] * 100)}%" for k in DIMENSION_KEYS)


# ------------------------------------------------------------------ #
#  Gradesheet – letter grades computed IN CODE from the reconciled data
# ------------------------------------------------------------------ #

def _to_grade(score) -> str | None:
    """0-100 score -> letter grade via GRADE_BANDS (the coded rubric). None if unscored."""
    v = _as_score(score)
    if v is None:
        return None
    v = max(0.0, min(100.0, v))
    for lo, letter in GRADE_BANDS:
        if v >= lo:
            return letter
    return "F"


def _grade_cell(score, note_suffix: str = "/100") -> dict:
    """A gradesheet cell: {letter, score, note}. 'NR' (not rated) when unscored — NEVER
    'F', which would unfairly punish an undisclosed metric rather than a bad one."""
    v = _as_score(score)
    letter = _to_grade(v)
    if letter is None:
        return {"letter": "NR", "score": None, "note": "not scored"}
    return {"letter": letter, "score": round(v, 1), "note": f"{round(v)}{note_suffix}"}


def _capital_efficiency_score(row: dict | None) -> float | None:
    """0-100 capital-efficiency score from the ledger row, computed in code:
    Rule of 40 (>=40 -> full marks) + burn-multiple bands, averaged over whatever is
    disclosed. None when neither is disclosed (-> folds away / 'NR', not 'F')."""
    if not isinstance(row, dict):
        return None
    comps: list[float] = []
    r40 = _parse_money(row.get("rule_of_40"))
    if r40 is not None:
        comps.append(max(0.0, min(100.0, (r40 / 40.0) * 100.0)))
    burn = _parse_money(row.get("burn_multiple"))
    if burn is not None:
        # Lower burn multiple is better (net burn per net-new ARR).
        comps.append(100.0 if burn <= 1.0 else 80.0 if burn <= 1.5 else
                     60.0 if burn <= 2.5 else 40.0 if burn <= 3.5 else 20.0)
    if not comps:
        return None
    return sum(comps) / len(comps)


def _financial_health_grade(dims: dict | None, row: dict | None) -> dict:
    """Gradesheet 'Financial Health & Capital Efficiency' cell = mean of the reconciled
    Financial Health dimension and the coded ledger capital-efficiency score, over
    whichever is available. Honestly REPLACES the repo-only 'Engineering quality' card
    (coverage/tests/ADRs have no per-startup web source). Degrades to the reconciled
    dimension when the ledger is undisclosed; NR only if both are absent."""
    comps: list[float] = []
    fh = _as_score((dims or {}).get("financial_health"))
    if fh is not None:
        comps.append(fh)
    eff = _capital_efficiency_score(row)
    if eff is not None:
        comps.append(eff)
    if not comps:
        return {"letter": "NR", "score": None, "note": "financials undisclosed"}
    return _grade_cell(sum(comps) / len(comps), "/100 (health+R40/burn)")


# Undisclosed traction -> NR (can't prove zero from silence); affirmatively-disclosed
# zero/pre-revenue -> F. This regex detects the affirmative-zero case.
_PRE_REVENUE_RE = re.compile(r"pre[- ]?revenue|pre[- ]?launch|pre[- ]?pmf|no revenue|zero revenue", re.I)
# Stage-normalized YoY growth targets (a value that is elite at seed is death at scale).
_STAGE_GROWTH_TARGET = [
    ("series a", 175.0), ("series b", 100.0), ("series c", 75.0), ("series d", 75.0),
    ("growth", 75.0), ("scale", 75.0), ("seed", 200.0),
]


def _traction_score(row: dict | None) -> tuple[float | None, bool]:
    """(0-100 traction score | None, disclosed_zero) from the ledger, computed in code:
    stage-adjusted YoY growth + NRR bands + LTV/CAC bands + revenue-exists, averaged over
    whatever is disclosed. Returns disclosed_zero=True when ARR is affirmatively 0 /
    pre-revenue (-> an honest F), vs None (-> NR) when traction is merely undisclosed."""
    if not isinstance(row, dict):
        return None, False
    stage = str(row.get("stage", "")).lower()
    arr_raw = str(row.get("arr", ""))
    arr = _parse_money(arr_raw)
    disclosed_zero = arr == 0.0 or bool(_PRE_REVENUE_RE.search(f"{stage} {arr_raw}"))
    if disclosed_zero:
        return None, True

    target = next((t for key, t in _STAGE_GROWTH_TARGET if key in stage), 100.0)
    comps: list[float] = []
    g = _parse_money(row.get("yoy_growth"))
    if g is not None:
        comps.append(max(0.0, min(100.0, (g / target) * 100.0)))
    n = _parse_money(row.get("nrr"))
    if n is not None:
        comps.append(100.0 if n >= 120 else 80.0 if n >= 110 else
                     60.0 if n >= 100 else 40.0 if n >= 90 else 20.0)
    lc = _parse_money(row.get("ltv_cac"))
    if lc is not None:
        comps.append(100.0 if lc >= 3 else 70.0 if lc >= 2 else 40.0 if lc >= 1 else 20.0)
    if arr is not None and arr > 0:
        comps.append(100.0)  # revenue-exists
    if not comps:
        return None, False
    return sum(comps) / len(comps), False


# The gradesheet card criteria — 6 cards matching the reference screenshot, but honestly
# sourced (some renamed/replaced where the repo-derived original has no per-startup web
# signal). Overall is the per-startup header, not a card. Order = display order.
GRADESHEET_CRITERIA = [
    {"key": "market_urgency", "label": "Market & Timing",
     "calculation": "Reconciled Market Urgency & TRL dimension (0-100), averaged from both analysts, mapped to a letter. Grades the market's timing/why-now, not a startup's timing edge, so competitors often cluster."},
    {"key": "product_depth", "label": "Product & Tech Depth",
     "calculation": "The a16z Differentiated-Technology moat sub-score (0-100): how novel / hard-to-replicate the technology is. NOT a code/feature/package audit (no repo) and not the 4-moat mean. NR when unscored."},
    {"key": "regulatory_alignment", "label": "Regulatory & Compliance",
     "calculation": "Reconciled Regulatory Alignment dimension (0-100): compliance readiness (HIPAA/SOC2/GDPR/sector rules). NOT an adversarial security / pen-test grade. NR when unscored."},
    {"key": "financial_health", "label": "Financial Health & Capital Efficiency",
     "calculation": "Mean of the reconciled Financial Health dimension and the coded ledger Capital-Efficiency score (Rule-of-40 >=40 = full + burn-multiple bands), over whichever is disclosed. Honestly replaces 'Engineering quality' (coverage/tests are repo-only)."},
    {"key": "traction_gtm", "label": "Traction & GTM",
     "calculation": "Coded stage-adjusted blend of disclosed ledger traction: YoY growth vs the stage benchmark, NRR bands, LTV/CAC bands, revenue-exists. F only when zero/pre-revenue is affirmatively disclosed; NR when all traction is undisclosed."},
    {"key": "founder_market_fit", "label": "Founder-Market Fit",
     "calculation": "Reconciled Founder-Market Fit dimension (0-100): founder domain fit / pedigree / unfair insight. Team continuity & key-person risk are out of scope (that signal was repo-only). NR when unscored."},
]


def _compute_gradesheet(resolved_scores, moat_subscores, weighted_scores,
                        financial_ledger, ranking, focal: str = "") -> dict:
    """Per-startup letter gradesheet — 100% computed in code from the already-reconciled
    scores + ledger (no LLM grading), so it can never disagree with the scorecard.
    Six cards matching the reference screenshot (some renamed/replaced where the original
    was repo-derived — see GRADESHEET_CRITERIA). Incumbents (unscored) are excluded."""
    ledger_by_name: dict[str, dict] = {}
    if isinstance(financial_ledger, dict):
        for row in financial_ledger.get("rows", []) or []:
            if isinstance(row, dict) and not row.get("is_incumbent"):
                ledger_by_name[_norm_name(row.get("startup"))] = row

    # Ranked order first, then any scored startup missing from the ranking.
    ordered = list(ranking or [])
    for n in resolved_scores or {}:
        if n not in ordered:
            ordered.append(n)

    fkey = _norm_name(focal)
    startups = []
    for name in ordered:
        dims = (resolved_scores or {}).get(name)
        if not isinstance(dims, dict):
            continue
        wrow = (weighted_scores or {}).get(name) or {}
        subs = (moat_subscores or {}).get(name)
        row = ledger_by_name.get(_norm_name(name))

        cells = {
            "market_urgency": _grade_cell(dims.get("market_urgency")),
            "product_depth": _grade_cell((subs or {}).get("differentiated_technology"), "/100 diff-tech moat"),
            "regulatory_alignment": _grade_cell(dims.get("regulatory_alignment")),
            "financial_health": _financial_health_grade(dims, row),
            "founder_market_fit": _grade_cell(dims.get("founder_market_fit")),
        }
        tscore, tzero = _traction_score(row)
        cells["traction_gtm"] = (
            {"letter": "F", "score": 0.0, "note": "disclosed zero / pre-revenue"} if tzero
            else {"letter": "NR", "score": None, "note": "traction undisclosed"} if tscore is None
            else _grade_cell(tscore, "/100 (stage-adj.)"))

        startups.append({
            "name": name,
            "is_focal": bool(fkey) and _norm_name(name) == fkey,
            "overall": _grade_cell(wrow.get("weighted_score"), "/100 index"),
            "cells": cells,
        })

    return {"criteria": GRADESHEET_CRITERIA, "startups": startups}


def _today_note(role: str) -> str:
    """Date-grounding line for every fact-asserting/arbitrating agent. Without it the
    LLMs default to their training-cutoff sense of 'now' and present stale figures
    (old funding rounds, dead competitors) as current — the freshness bug. As-of dates
    are demanded only WHERE A SOURCE PROVIDES ONE — an unconditional demand pressures
    the model into inventing dates (general-topic Tavily results are often undated)."""
    today = datetime.now().strftime("%Y-%m-%d")
    if role == "researcher":
        return (
            f"**Today's date: {today}.** Your training knowledge predates this — every "
            f"time-sensitive figure (funding, valuation, ARR, product status, headcount) MUST "
            f"come from your search results, NOT from memory. Carry each source's publication "
            f"date onto its facts as an as-of date where one is available; if no source states "
            f"a date, mark the fact \"(date not stated)\" — NEVER invent a date. When two "
            f"sources conflict, the most RECENT wins — report the newer figure and note the "
            f"older one with its date.\n\n"
        )
    if role == "compiler":
        return (
            f"**Today's date: {today}.** The two analyst reports' sourced, dated figures are "
            f"your ONLY current source — your training knowledge is stale. When the reports "
            f"carry conflicting values for the same metric, use the most RECENT (by as-of / "
            f"publication date) and note the older figure and its date (in prose — never "
            f"inside table cells).\n\n"
        )
    if role == "judge":
        return (
            f"**Today's date: {today}.** When the analysts disagree on a time-sensitive "
            f"figure, the position backed by the more RECENT as-of/publication date in the "
            f"research data is presumptively correct — instruct the trailing analyst to "
            f"re-check the dated sources. NEVER arbitrate a figure from your own training "
            f"memory.\n\n"
        )
    return (
        f"**Today's date: {today}.** Treat the research data as the only current source — "
        f"your training knowledge is stale. When the research data gives conflicting values "
        f"for the same metric, use the most RECENT (by as-of / publication date) and note "
        f"the older figure and its date in parentheses (in prose — never inside table cells).\n\n"
    )


def _focal_weak_spots(resolved_scores: dict | None, moat_subscores: dict | None, focal: str) -> str:
    """The focal startup's 2 weakest dimensions + 2 weakest moat sub-scores as a
    compiler-ready phrase — computed IN CODE from the reconciled scorecard (not
    LLM-asserted), so the founder §0.5 anchors can't contradict the §7 scorecard.
    Scores are rendered VERBATIM (same 1-decimal precision as the stored values) so
    the anchor can't disagree with the resolved-scores JSON in the same message.
    Empty string when the focal has no usable entry — broader than
    weighting_unavailable: the focal alone may be missing from a good scorecard.
    """
    key = _norm_name(focal)
    if not key:
        return ""
    dims = next((v for n, v in (resolved_scores or {}).items()
                 if _norm_name(n) == key and isinstance(v, dict)), {})
    moats = next((v for n, v in (moat_subscores or {}).items()
                  if _norm_name(n) == key and isinstance(v, dict)), {})
    scored_dims = sorted(
        ((k, _as_score(dims.get(k))) for k in DIMENSION_KEYS if _as_score(dims.get(k)) is not None),
        key=lambda kv: kv[1],
    )
    if not scored_dims:
        return ""
    parts = ["weakest dimensions: " + ", ".join(
        f"{DIMENSION_LABELS[k]} ({v:g}/100)" for k, v in scored_dims[:2])]
    scored_moats = sorted(
        ((k, _as_score(moats.get(k))) for k in MOAT_KEYS if _as_score(moats.get(k)) is not None),
        key=lambda kv: kv[1],
    )
    if scored_moats:
        parts.append("weakest moat sub-scores: " + ", ".join(
            f"{MOAT_LABELS[k]} ({v:g}/100)" for k, v in scored_moats[:2]))
    return "; ".join(parts)


def _focal_field_position(resolved_scores: dict | None, weighted_scores: dict | None,
                          ranking: list | None, moat_subscores: dict | None,
                          focal: str, pick: str) -> str:
    """VC-focal anchor: the focal deal's rank in the field + the largest per-dimension
    deficits vs the field leader — computed IN CODE so §0/§7/§12 can't disagree with the
    scorecard. Empty string when the focal has no usable ranked entry (same degrade
    contract as _focal_weak_spots). When the focal IS the pick, only the rank line."""
    fkey = _norm_name(focal)
    if not fkey or not ranking:
        return ""
    idx = next((i for i, n in enumerate(ranking) if _norm_name(n) == fkey
                or fkey in _norm_name(n) or _norm_name(n) in fkey), None)
    if idx is None:
        return ""
    def _ws(name: str):
        v = (weighted_scores or {}).get(name) or next(
            (d for n, d in (weighted_scores or {}).items() if _norm_name(n) == _norm_name(name)), None)
        return _as_score((v or {}).get("weighted_score")) if isinstance(v, dict) else None
    fscore = _ws(ranking[idx])
    rank_line = f"{focal} ranks #{idx + 1} of {len(ranking)} on the weighted index"
    if fscore is not None:
        rank_line += f" (weighted {fscore:g})"
    # Focal is the field leader / the pick itself → no self-comparison.
    if _norm_name(pick) == fkey or fkey in _norm_name(pick) or _norm_name(pick) in fkey:
        return rank_line + "."
    pscore = _ws(pick)
    fdims = next((v for n, v in (resolved_scores or {}).items()
                  if _norm_name(n) == fkey and isinstance(v, dict)), {})
    pdims = next((v for n, v in (resolved_scores or {}).items()
                  if _norm_name(n) == _norm_name(pick) and isinstance(v, dict)), {})
    deltas = []
    for k in DIMENSION_KEYS:
        fv, pv = _as_score(fdims.get(k)), _as_score(pdims.get(k))
        if fv is not None and pv is not None and pv - fv > 0:
            deltas.append((k, fv, pv, pv - fv))
    deltas.sort(key=lambda t: t[3], reverse=True)
    parts = [rank_line]
    if pscore is not None and fscore is not None:
        parts.append(f"gap to {pick} is {round(pscore - fscore, 1):g} points")
    if deltas:
        parts.append("driven by " + ", ".join(
            f"{DIMENSION_LABELS[k]} ({fv:g} vs {pv:g}, −{round(d, 1):g})" for k, fv, pv, d in deltas[:3]))
    return "; ".join(parts) + "."


def _normalize_content(content) -> str:
    """Normalize LLM .content to a plain string.

    Some providers (especially Anthropic/Claude) return .content as a list
    of content blocks like [{"type": "text", "text": "..."}] instead of a
    plain string. This ensures we always get a string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


# ------------------------------------------------------------------ #
#  Helper: multi-provider LLM factory
# ------------------------------------------------------------------ #

def _make_llm(model: str, temperature: float = 0.2, max_tokens: int = 8192):
    """Create an LLM instance based on model ID prefix."""
    settings = get_settings()

    if model.startswith("gemini"):
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
    elif model.startswith("claude"):
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif model.startswith("gpt") or model.startswith("o"):
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        # Fallback to Groq for Llama / other models
        return ChatGroq(
            model=model,
            api_key=settings.groq_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# ------------------------------------------------------------------ #
#  Retry helpers
# ------------------------------------------------------------------ #

def _extract_retry_seconds(err_str: str) -> int | None:
    """Extract the retry wait time from a rate limit error message."""
    match = re.search(r"try again in (\d+)m(\d+)", err_str)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.search(r"try again in (\d+)s", err_str)
    if match:
        return int(match.group(1))
    return None


# LangGraph's default recursion_limit is 25 supersteps ≈ 12 sequential tool rounds — far
# below the ≥20-call research protocol (a compliant researcher needs ~24-33 calls). 100
# covers ~49 sequential rounds with headroom; without it a compliant run dies mid-research
# with GraphRecursionError (which is NOT retryable below).
AGENT_RECURSION_LIMIT = 100


def _run_agent_with_retry(agent, messages, max_retries=8):
    """Run a LangGraph agent with retry logic for rate limit and tool_use_failed errors."""
    config = {"recursion_limit": AGENT_RECURSION_LIMIT}
    for attempt in range(max_retries):
        try:
            return agent.invoke(messages, config=config)
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                suggested = _extract_retry_seconds(err_str)
                wait = min(suggested + 10, 900) if suggested else 30 * (attempt + 1)
                logger.warning("Rate limited (attempt %d/%d), waiting %ds...", attempt + 1, max_retries, wait)
                time.sleep(wait)
            elif "tool_use_failed" in err_str or "failed to call a function" in err_str:
                wait = 5 * (attempt + 1)
                logger.warning("Tool call failed (attempt %d/%d), retrying in %ds...", attempt + 1, max_retries, wait)
                time.sleep(wait)
            else:
                raise
    return agent.invoke(messages, config=config)


def _invoke_llm_with_retry(llm, messages, max_retries=8):
    """Invoke an LLM directly with retry logic for rate limit errors."""
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                suggested = _extract_retry_seconds(err_str)
                wait = min(suggested + 10, 900) if suggested else 30 * (attempt + 1)
                logger.warning("Rate limited (attempt %d/%d), waiting %ds...", attempt + 1, max_retries, wait)
                time.sleep(wait)
            else:
                raise
    return llm.invoke(messages)


# ------------------------------------------------------------------ #
#  User message builders
# ------------------------------------------------------------------ #

def _build_researcher_user_message(state: ResearchState) -> str:
    """Construct the researcher prompt from shared state."""
    stage = state.get("stage", "All Stages")
    geography = state.get("geography", "Global")
    scope_lines = []
    if stage and stage != "All Stages":
        scope_lines.append(
            f"- SCOPE BY STAGE: weave \"{stage}\" into your search queries (e.g. "
            f"\"{stage} stage <sector> startups\") and prioritize {stage}-stage companies."
        )
    if geography and geography != "Global":
        scope_lines.append(
            f"- SCOPE BY GEOGRAPHY: weave \"{geography}\" into your search queries and "
            f"prioritize companies/HQ in {geography}."
        )
    scope = ("\n**Search-scoping requirements:**\n" + "\n".join(scope_lines) + "\n") if scope_lines else ""
    return (
        f"## Research Assignment\n\n"
        f"{_today_note('researcher')}"
        f"**Market Prompt:** {state['market_prompt']}\n"
        f"**Sector:** {state.get('sector', 'Not specified')}\n"
        f"**Investment Stage Filter:** {stage}\n"
        f"**Geography:** {geography}\n"
        f"{scope}\n"
        f"{_focal_research_block(state)}"
        f"Also gather, where available: a credible TOP-DOWN market-size anchor for "
        f"this sector (to triangulate against bottom-up sizing), founder/team "
        f"backgrounds and cap-table/ownership signals, and each startup's last "
        f"round / valuation terms.\n\n"
        f"Perform exhaustive research using your search tools. You MUST make "
        f"at least 20 tool calls (including one search_latest_news call per "
        f"deep-dived startup — the freshness pass). Identify and profile AT LEAST "
        f"6-8 startups in this sector. Output ALL raw facts, data, source URLs, "
        f"and each fact's as-of date. Do NOT form opinions or assign scores."
    )


def _focal_research_block(state: ResearchState) -> str:
    """Researcher instructions for a user-supplied focal startup (+ uploaded materials)."""
    focal = (state.get("focal_startup") or "").strip()
    materials = (state.get("focal_materials") or "").strip()
    if not focal and not materials:
        return ""
    mode = (state.get("analysis_mode") or "vc").lower()
    name = focal or "the focal startup"
    lines = ["\n**FOCAL STARTUP (must be included):**"]
    if mode == "founder":
        lines.append(
            f"- This run is centered on **{name}**. Research the MARKET it is entering "
            f"exhaustively (competitors, sizing, incumbents, why-now) so it can be positioned "
            f"and stress-tested against the field. {name} MUST be researched and profiled."
        )
    else:
        lines.append(
            f"- GUARANTEE **{name}** is researched, profiled, and deep-dived alongside the "
            f"other startups (it is a required member of the competitive field)."
        )
    lines.append(
        f"- Search specifically for {name} (funding, team, product, traction). If little is "
        f"public (stealth / very early), say so explicitly and rely on the provided materials below."
    )
    if materials:
        # Cap injected materials so a huge deck can't blow the researcher context budget.
        clip = materials[:24000]
        if len(materials) > 24000:
            clip += "\n…[materials truncated]"
        lines.append(
            "- PROVIDED MATERIALS for the focal startup (user-uploaded — treat as PRIMARY SOURCE "
            "for this company; quote concrete figures and facts from it):\n"
            f"\n=== BEGIN FOCAL MATERIALS ===\n{clip}\n=== END FOCAL MATERIALS ===\n"
        )
    claims = state.get("call_claims") or []
    if claims:
        # Phase-0 claim audit gains the call channel: each spoken claim gets ONE
        # verification search; a call-vs-public contradiction is a headline finding.
        rows = "\n".join(
            f"  {i + 1}. {c.get('claim', '')}"
            + (f" (said at {c['timestamp']})" if c.get("timestamp") else "")
            for i, c in enumerate(claims) if isinstance(c, dict)
        )
        lines.append(
            f"- FOUNDER-CALL CLAIMS TO VERIFY (extracted from an uploaded call recording/"
            f"transcript — spoken testimony, NOT evidence). Per the Phase 0 protocol, run ONE "
            f"verification call for each VERIFIABLE claim below and report a per-claim verdict "
            f"(VERIFIED-INDEPENDENT / CONTRADICTED with the conflicting public fact + source + "
            f"date / VENDOR-ONLY / UNVERIFIABLE) in your brief under a heading "
            f"'FOUNDER-CALL CLAIM VERIFICATION':\n{rows}"
        )
    return "\n".join(lines) + "\n\n"


def _focal_materials_digest(state: ResearchState, cap: int = 12000) -> str:
    """The founder-uploaded deck/materials, formatted for the analysts + compiler.

    Root-cause fix for the "stealth = black box" failure: the parsed deck used to reach
    ONLY the researcher (_focal_research_block). For a stealth company the researcher finds
    nothing public, so the analysts and compiler that write §0/§0.5/§7/§8/§9 saw only
    "Not Disclosed" and treated the founder as unknown. Threading the materials here lets
    those agents judge the founder on what the deck actually states. Founder-mode only.
    """
    focal = (state.get("focal_startup") or "").strip()
    materials = (state.get("focal_materials") or "").strip()
    if not focal or not materials:
        return ""
    if (state.get("analysis_mode") or "vc").lower() != "founder":
        return ""
    clip = materials[:cap]
    if len(materials) > cap:
        clip += "\n…[materials truncated]"
    return (
        f"\n---\n\n## FOUNDER-PROVIDED MATERIALS (primary source for {focal})\n\n"
        f"The founder uploaded these materials for **{focal}**. This is a PRIMARY SOURCE on "
        f"the focal — extract its team/founder background, architecture, product, traction, and "
        f"GTM, and use them wherever you assess {focal} (Sections 6-9, and the §0.5 repositioning). "
        f"Tag facts drawn from here \"(per founder materials)\". Do NOT write \"unknown\", "
        f"\"undisclosed\", or \"opaque\" for anything the materials actually state — that is the "
        f"single most common failure on stealth companies. Only genuinely absent facts are "
        f"\"Not Disclosed\". These materials are self-reported (founder-authored) — weigh them as "
        f"such, but they are the best available signal on {focal}.\n\n"
        f"CRITICAL SOURCING BOUNDARY: \"(per founder materials)\" is a valid source ONLY for "
        f"COMPANY-INTERNAL facts about {focal} (its team, architecture, product, traction, GTM). "
        f"MARKET-LEVEL claims — market size, breach statistics, adoption ratios, regulatory "
        f"status/deadlines, competitor rounds or moves — may NEVER rest on the deck alone: they "
        f"require an independent research source, or they must be tagged \"(unverified — founder "
        f"claim)\". A pitch deck is not evidence for the size of its own market or the maturity of "
        f"a standard it cites.\n\n"
        f"=== BEGIN FOUNDER MATERIALS ===\n{clip}\n=== END FOUNDER MATERIALS ===\n"
    )


def _build_analyst_user_message(state: ResearchState) -> str:
    """Construct the analyst prompt from shared state, including research data."""
    weights = state.get("dimension_weights", {})
    critique = state.get("judge_critique", "")
    iteration = state.get("iterations", 0)
    research_data = state.get("research_data", "")

    msg = (
        f"## Research Data (from Researcher Agent)\n\n"
        f"{research_data}\n\n"
        f"---\n\n"
        f"## Your Assignment\n\n"
        f"{_today_note('analyst')}"
        f"**Market Prompt:** {state['market_prompt']}\n"
        f"**Sector:** {state.get('sector', 'Not specified')}\n"
        f"**Investment Stage Filter:** {state.get('stage', 'All Stages')}\n"
        f"**Geography:** {state.get('geography', 'Global')}\n"
        f"**Thesis Bias:** {state.get('thesis_bias', 'Base')}\n\n"
        f"**Dimension Weights (normalized, for context — the PLATFORM applies these "
        f"in code to compute the official Weighted Index; do NOT compute the weighted "
        f"total yourself):**\n"
        f"{_format_weights_block(weights)}\n\n"
        f"Using the research data above, form your INDEPENDENT analysis. "
        f"Score every startup across all 5 dimensions as a RAW 0-100 score per "
        f"dimension, interpreting financial/efficiency benchmarks against the "
        f"target investment stage above (a metric that is excellent at one stage "
        f"can be poor at another). Present a clear per-startup, per-dimension "
        f"scorecard so each raw score is unambiguous. "
        f"Structure your output using the full section framework with multi-paragraph "
        f"depth per section. Include the complete Financial Ledger and raw Scorecard "
        f"tables, detailed startup profiles (3-4 paragraphs each), team/founder "
        f"assessment, risk factors with mitigants, and an ASCII coordinate market map.\n"
    )

    # Founder mode: the framework gains §0.5 (Strategic Repositioning). The analysts are
    # not otherwise mode-aware — the compiler does the verdict framing — so this block
    # establishes only the minimum: the mode, the focal startup, and the extra section.
    focal = (state.get("focal_startup") or "").strip()
    if focal and (state.get("analysis_mode") or "vc").lower() == "founder":
        msg += (
            f"\n---\n\n## FOUNDER MODE — ADDITIONAL REQUIRED SECTION (0.5)\n\n"
            f"This run is FOUNDER MODE: the user is the founder of **{focal}**. The market field "
            f"above is its competitive backdrop, and the final compiled document renders a "
            f"build/pass verdict on {focal}. YOUR report keeps the standard framework (Section 0 "
            f"remains the field-level Investment Take) — but for this run ONLY it gains ONE extra "
            f"section, `## 0.5`, per the SECTION 0.5 SPEC below. Every other section is unchanged.\n\n"
            f"Ground rules for YOUR Section 0.5:\n\n"
            f"- {focal} must appear in your ledger, scorecard, profiles, and map like any other "
            f"scored startup. It is NEVER an incumbent, and the PRE-PMF/WATCHLIST exclusion does "
            f"NOT apply to it — score it even if early; flag data thinness in prose instead.\n"
            f"- In YOUR draft, write Section 0.5 LAST — after your scorecard and profiles exist "
            f"(placing it right after Section 0 is the Compiler's job). Anchor every move to the "
            f"weakest dimensions / a16z moat sub-scores in YOUR OWN Section 7 scorecard for "
            f"{focal} — name the dimension inside the move; a 0.5 whose targets don't match your "
            f"own scorecard is invalid.\n"
            f"- Every move needs NAMED evidence from the research data (a competitor's gap, a "
            f"benchmark band, a regulatory item, or the Section 4 white space) — apply the PASTE "
            f"TEST from the spec. Zero generic startup advice survives.\n"
            f"- Your 0.5 will be synthesized with the other analyst's — take real positions; a "
            f"hedged 0.5 contributes nothing. When a judge critique arrives, revise your 0.5 "
            f"alongside your scores.\n"
            f"{_focal_materials_digest(state)}"
            f"{FOUNDER_REPOSITIONING_SECTION.format(focal=focal)}"
        )
    elif focal:
        # VC-focal mode: a specific deal is on the table. Get BOTH analysts (and the judge loop)
        # to actually debate the focal AS the deal, so the compiler's deal-centered §0/§12 has
        # analyst-level scenarios to reconcile — not just a field-leader take. Mirrors the
        # founder gate's mechanism. Must not contain the literal "0.5" (VC mode has no §0.5).
        msg += (
            f"\n---\n\n## VC-FOCAL MODE — {focal} IS THE DEAL UNDER EVALUATION\n\n"
            f"This run attaches **{focal}** as the specific deal the reader is evaluating "
            f"(INVEST / WATCH / PASS), with the discovered field as context.\n\n"
            f"- {focal} MUST appear in your ledger, scorecard, profiles, and map like any other "
            f"scored startup. It is NEVER an incumbent, and the PRE-PMF / WATCHLIST exclusion does "
            f"NOT apply to it — score it even if early; flag data thinness in prose instead.\n"
            f"- In Section 12, model {focal}'s OWN probability-weighted outcome scenarios "
            f"(downside / base / outlier — each with a probability, a return-multiple range, and a "
            f"one-phrase exit path) at its last-round post-money, ALONGSIDE the field top pick's — "
            f"so the deal can be underwritten on its own terms, not only the leader's.\n"
            f"- State YOUR explicit INVEST / WATCH / PASS on {focal} at a price in Section 12, and "
            f"where {focal} sits vs the field leader on price-adjusted return. Take a real position; "
            f"when a judge critique arrives, revise it alongside your scores.\n"
        )

    if critique and iteration > 0:
        msg += (
            f"\n---\n## DISAGREEMENTS THE JUDGE FLAGGED (ROUND {iteration})\n"
            f"The Judge compared your report with the other analyst's and flagged these "
            f"specific disagreement points. Re-examine the research data and RECONSIDER each "
            f"one — adjust your scores/claims where the evidence warrants, or defend them:\n\n{critique}\n"
        )

    return msg


# ------------------------------------------------------------------ #
#  Scope inference – derive {sector, market_prompt} from a focal startup
# ------------------------------------------------------------------ #

def derive_scope(focal_startup: str, context_text: str, settings) -> dict | None:
    """Infer {sector, market_prompt, rationale} for a focal startup from CONTEXT
    (uploaded materials and/or web-search snippets), via one structured LLM call.
    Returns None on failure or when nothing usable is produced.
    """
    focal = (focal_startup or "").strip()
    ctx = (context_text or "").strip()
    if not focal and not ctx:
        return None
    user_message = (
        f"Startup: {focal or '(unnamed)'}\n\n"
        f"Context about the startup:\n{ctx[:16000] or '(no context available)'}\n\n"
        f"Infer the MARKET to analyze. JSON ONLY."
    )
    try:
        llm = _make_llm(settings.judge_model, temperature=0.2, max_tokens=1024)
        result = _invoke_llm_with_retry(llm, [
            ("system", SCOPE_INFERENCE_SYSTEM),
            ("user", user_message),
        ])
        raw = _last_balanced_json(_normalize_content(result.content)) or {}
        # Only accept a real STRING prompt — a JSON null/object would otherwise str()-coerce
        # into a truthy garbage value ("None") and bypass the downstream 10-char floor.
        prompt = raw.get("market_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return None
        _s = lambda v: v.strip() if isinstance(v, str) else ""
        return {
            "sector": _s(raw.get("sector")),
            "market_prompt": prompt.strip(),
            "rationale": _s(raw.get("rationale")),
        }
    except Exception as e:  # noqa: BLE001 - scope inference is best-effort
        logger.error("Scope inference failed: %s", e)
        return None


# ------------------------------------------------------------------ #
#  Founder-call claim audit — extract claims from an uploaded call
#  recording/transcript, then cross-examine them against the research
#  brief + the deck. The verdicts are validated IN CODE; contradiction
#  is a first-class finding (deck vs call vs public record).
# ------------------------------------------------------------------ #

_CLAIM_CATEGORIES = {"financial", "traction", "team", "product", "market", "other"}
_CLAIM_STATUSES = {"verified", "contradicted", "unsupported", "vendor-only"}
_MAX_CLAIMS = 12


def _validate_call_claims(raw) -> list[dict]:
    """Coerce the extraction LLM's claims into render-safe rows (capped, typed)."""
    rows_in = (raw or {}).get("claims") if isinstance(raw, dict) else None
    if not isinstance(rows_in, list):
        return []
    out: list[dict] = []
    for r in rows_in:
        if len(out) >= _MAX_CLAIMS:  # cap VALID rows — garbage rows don't consume slots
            break
        if not isinstance(r, dict):
            continue
        claim = str(r.get("claim") or "").strip()
        if not claim:
            continue
        cat = str(r.get("category") or "other").strip().lower()
        out.append({
            "claim": claim[:300],
            "quote": str(r.get("quote") or "").strip()[:300],
            "timestamp": str(r.get("timestamp") or "").strip()[:12],
            "category": cat if cat in _CLAIM_CATEGORIES else "other",
        })
    return out


def _extract_call_claims(transcripts: str, focal: str, settings) -> list[dict]:
    """One structured LLM call: transcript -> the founder's falsifiable claims."""
    clip = transcripts[:28000]
    user_message = (
        f"Startup on the call: {focal or '(unnamed)'}\n\n"
        f"## Call transcript(s)\n\n{clip}\n\n"
        f"Extract the founder's falsifiable factual claims. JSON ONLY."
    )
    llm = _make_llm(settings.judge_model, temperature=0.1, max_tokens=2048)
    result = _invoke_llm_with_retry(llm, [
        ("system", CLAIM_EXTRACTION_SYSTEM),
        ("user", user_message),
    ])
    return _validate_call_claims(_last_balanced_json(_normalize_content(result.content)) or {})


def _validate_claim_audit(raw, claims: list[dict]) -> dict | None:
    """Coerce the audit LLM's verdicts into {claims: rows, counts: {...}}, joining back
    onto the ORIGINAL extracted claims by order/text so a hallucinated claim can't enter
    and every real claim keeps its quote/timestamp. Counts are computed in code."""
    rows_in = (raw or {}).get("claims") if isinstance(raw, dict) else None
    if not isinstance(rows_in, list) or not claims:
        return None
    by_text = {c["claim"].strip().lower(): c for c in claims}
    out: list[dict] = []
    used: set = set()
    for i, r in enumerate(rows_in[:_MAX_CLAIMS]):
        if not isinstance(r, dict):
            continue
        text = str(r.get("claim") or "").strip()
        src = by_text.get(text.strip().lower())
        if src is None and i < len(claims):
            src = claims[i]  # order fallback: the audit graded in input order
        if src is None or id(src) in used:
            continue
        used.add(id(src))
        status = str(r.get("status") or "").strip().lower()
        out.append({
            **src,
            "status": status if status in _CLAIM_STATUSES else "unsupported",
            "evidence": str(r.get("evidence") or "").strip()[:300],
            "deck_conflict": str(r.get("deck_conflict") or "").strip()[:300],
        })
    if not out:
        return None
    counts = {s: sum(1 for c in out if c["status"] == s) for s in sorted(_CLAIM_STATUSES)}
    counts["deck_conflicts"] = sum(1 for c in out if c["deck_conflict"])
    return {"claims": out, "counts": counts}


def _audit_call_claims(claims: list[dict], research_data: str, focal_materials: str,
                       focal: str, settings) -> dict | None:
    """One structured LLM call: claims + research brief (+ deck) -> per-claim verdicts.
    Best-effort; None on any failure (the UI/PDF then simply omit the audit)."""
    if not claims:
        return None
    try:
        from app.services.ingest import split_transcripts
        _calls, docs = split_transcripts(focal_materials or "")
        claims_block = "\n".join(
            f"{i + 1}. {c['claim']}"
            + (f" (said at {c['timestamp']})" if c.get("timestamp") else "")
            for i, c in enumerate(claims)
        )
        user_message = (
            f"Startup: {focal or '(unnamed)'}\n\n"
            f"## Founder-call claims to grade (grade ALL, in order)\n\n{claims_block}\n\n"
            f"---\n\n## Uploaded materials (deck/docs — check for call-vs-deck conflicts)\n\n"
            f"{(docs or '(none uploaded)')[:12000]}\n\n"
            f"---\n\n## Independent research brief\n\n{(research_data or '')[:24000]}\n\n"
            f"Grade each claim. JSON ONLY."
        )
        llm = _make_llm(settings.judge_model, temperature=0.1, max_tokens=2048)
        result = _invoke_llm_with_retry(llm, [
            ("system", CLAIM_AUDIT_SYSTEM),
            ("user", user_message),
        ])
        return _validate_claim_audit(_last_balanced_json(_normalize_content(result.content)) or {}, claims)
    except Exception as e:  # noqa: BLE001 - the audit is best-effort, never fails a run
        logger.error("Call-claim audit failed: %s", e)
        return None


# ------------------------------------------------------------------ #
#  Ingest Node – parse uploaded focal-startup materials (runs first)
# ------------------------------------------------------------------ #

def ingest_focal_materials(state: ResearchState) -> dict[str, Any]:
    """Extract text from the focal startup's uploaded files into `focal_materials`,
    plus the two structured side-channels: `call_claims` (factual claims extracted from
    any uploaded call recording/transcript — fact-checked downstream) and `cap_table`
    (a parsed round-history CSV — grounds the fund-math entry post in real terms).

    Pure pass-through when there is no focal startup / no upload. Failures degrade to
    empty materials (the researcher then relies on public search) — never crash the run.
    """
    focal = (state.get("focal_startup") or "").strip()
    upload_id = (state.get("focal_upload_id") or "").strip()
    if not focal and not upload_id:
        return {}

    materials = ""
    cap_table = None
    call_claims: list = []
    if upload_id:
        settings = get_settings()
        updir = os.path.join(settings.uploads_dir, upload_id)
        logger.info("▶ Ingesting focal materials (upload_id=%s) for '%s'", upload_id, focal or "?")
        try:
            from app.services.ingest import extract_materials_cached
            materials = extract_materials_cached(updir)
        except Exception as e:  # noqa: BLE001 - ingest is best-effort
            logger.error("Focal material ingest failed: %s", e)
            materials = ""
        try:
            from app.services.captable import find_cap_table
            cap_table = find_cap_table(updir)
        except Exception as e:  # noqa: BLE001 - cap table is best-effort
            logger.error("Cap-table ingest failed: %s", e)
        # Founder-call claim extraction: only when a transcript chunk exists.
        try:
            from app.services.ingest import split_transcripts
            transcripts, _docs = split_transcripts(materials)
            if transcripts.strip():
                call_claims = _extract_call_claims(transcripts, focal, settings)
        except Exception as e:  # noqa: BLE001 - claim extraction is best-effort
            logger.error("Call-claim extraction failed: %s", e)

    out: dict[str, Any] = {"focal_materials": materials, "agent_logs": []}
    if cap_table:
        out["cap_table"] = cap_table
    if call_claims:
        out["call_claims"] = call_claims
    if upload_id:
        out["agent_logs"].append(
            f"[Ingest] Focal '{focal or upload_id}': extracted {len(materials)} chars from uploaded files."
        )
        if cap_table:
            out["agent_logs"].append(
                f"[Ingest] Cap table parsed ({cap_table.get('source_file')}): "
                f"{len(cap_table.get('rounds') or [])} round(s), latest post "
                f"{cap_table.get('latest_post_money_musd')}M."
            )
        if call_claims:
            out["agent_logs"].append(
                f"[Ingest] Call transcript detected: extracted {len(call_claims)} founder claims for fact-check."
            )
    else:
        out["agent_logs"].append(
            f"[Ingest] Focal startup '{focal}' flagged for guaranteed inclusion (public research)."
        )

    # Self-heal: if the caller supplied NO market prompt (e.g. a direct API call that
    # relied on auto-derivation), infer the sector + prompt here so the pipeline still
    # runs. The confirm-first UI normally fills these before submit, so this is a fallback.
    if not (state.get("market_prompt") or "").strip() and focal:
        try:
            from app.services.scope import infer_scope
            scope = infer_scope(focal, upload_id)
            if scope.get("market_prompt"):
                out["market_prompt"] = scope["market_prompt"]
                out["sector"] = scope.get("sector", "")
                out["scope_autoderived"] = True
                out["agent_logs"].append(f"[Scope] Auto-identified market: {scope.get('sector') or '?'}")
        except Exception as e:  # noqa: BLE001 - derivation is best-effort
            logger.error("In-pipeline scope derivation failed: %s", e)

    return out


def _research_manifest(messages: list) -> dict:
    """Compact audit of the researcher's tool usage, built from the ReAct transcript
    (which is otherwise discarded). Duck-typed — no langchain message imports — so the
    token-free tests can feed plain namespaces. Answers 'did the protocol actually run?':
    total calls, per-tool counts, and how many searches failed/hit quota."""
    calls: list[dict] = []
    failed = 0
    for m in messages or []:
        for tc in getattr(m, "tool_calls", None) or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            if name:
                calls.append({
                    "tool": str(name),
                    "args": {k: str(v)[:200] for k, v in (args or {}).items()},
                })
        if getattr(m, "type", "") == "tool":
            content = str(getattr(m, "content", ""))
            if "[Search failed" in content or "QUOTA EXHAUSTED" in content or "[Grounded search failed" in content:
                failed += 1
    by_tool: dict[str, int] = {}
    for c in calls:
        by_tool[c["tool"]] = by_tool.get(c["tool"], 0) + 1
    return {"total": len(calls), "by_tool": by_tool, "failed": failed, "calls": calls}


_MD_LINK_RE = re.compile(r"\[([^\]\n]{1,120})\]\((https?://[^)\s]+)\)")

# Source-quality tiers, classified in code by domain so weak evidence is LABELED rather
# than silently blended with strong evidence (a VC discounts an SEO market-report mill;
# the pipeline must let them). Heuristic and conservative: unknown domains are "unverified".
_TIER_OFFICIAL = (
    ".gov", "sec.gov", "europa.eu", "eur-lex", "businesswire.com", "prnewswire.com",
    "globenewswire.com", "newswire.", "accesswire.com", "accessnewswire.com",
)
_TIER_PRESS = (
    "techcrunch.com", "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "forbes.com", "axios.com", "theinformation.com", "fortune.com", "businessinsider.com",
    "venturebeat.com", "crunchbase.com", "globes.co.il", "calcalistech.com",
    "securityweek.com", "darkreading.com", "wired.com", "economist.com", "cyberscoop.com",
    "fiercehealthcare.com", "fiercebiotech.com", "statnews.com", "techcompanynews.com",
)
_TIER_MILL = (
    "marketintelo", "fortunebusinessinsights", "marketsandmarkets", "grandviewresearch",
    "mordorintelligence", "verifiedmarketresearch", "precedenceresearch", "gminsights",
    "futuremarketinsights", "polarismarketresearch", "getlatka", "growjo", "zoominfo",
    "tracxn",
)


def _canonical_pick(scen_startup: str | None, ranking: list | None, focal: str, mode: str) -> str:
    """The name the 'Top pick' badge/History may carry — validated in code:
    - FOUNDER mode: the pick is the SUBJECT (the report's §0 verdict is about the focal;
      naming the competitor field leader would recreate the R11 header contradiction).
    - Otherwise the modelled scenarios' startup, but ONLY if it resolves (norm-name
      equality/containment) to a RANKED name — the resolve LLM can emit an incumbent or
      a variant spelling; the canonical ranked spelling is returned so UI string
      comparisons work. Falls back to ranking[0]."""
    if mode == "founder" and str(focal).strip():
        return str(focal).strip()
    ranked = [str(r) for r in (ranking or [])]
    sk = _norm_name(scen_startup or "")
    if sk:
        for name in ranked:
            nk = _norm_name(name)
            if nk == sk or nk in sk or sk in nk:
                return name
    return ranked[0] if ranked else ""


def _ledger_confidence(financial_ledger: dict | None, canonical: list | None = None) -> dict[str, str]:
    """{startup: 'low'|'medium'|'high'} from how many ledger metrics are actually
    disclosed (parseable), computed in code. Feeds the UI so decimal-precise scores are
    never displayed at face precision on mostly-'Not Disclosed' rows — the false-precision
    trust failure. Counts 8 DISCLOSED metrics only (implied_arr_multiple is code-derived
    from two of them — counting it would double-credit disclosure). low: <=2, medium:
    3-5, high: >=6. Keys are re-mapped to the canonical ranked names (the ledger keeps
    the LLM's raw spelling, e.g. 'Abridge, Inc.') so UI lookups by ranking name hit."""
    out: dict[str, str] = {}
    if not isinstance(financial_ledger, dict):
        return out
    metric_cols = ("total_raised", "valuation", "arr",
                   "yoy_growth", "ltv_cac", "nrr", "burn_multiple", "rule_of_40")
    canon = {_norm_name(c): str(c) for c in (canonical or [])}
    for row in financial_ledger.get("rows", []) or []:
        if not isinstance(row, dict) or row.get("is_incumbent"):
            continue
        name = str(row.get("startup") or "").strip()
        if not name:
            continue
        nk = _norm_name(name)
        key = canon.get(nk) or next(
            (v for k, v in canon.items() if k in nk or nk in k), name)
        disclosed = sum(1 for c in metric_cols if _parse_money(row.get(c)) is not None)
        out[key] = "low" if disclosed <= 2 else "medium" if disclosed <= 5 else "high"
    return out


def _source_tier(url: str) -> str:
    """'official/wire' | 'press' | 'report-mill' | 'unverified' — by HOSTNAME (not full
    URL: a ?ref=sec.gov query string must not launder a mill link into 'official')."""
    from urllib.parse import urlsplit
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        host = ""
    if not host:
        return "unverified"

    def _host_match(entry: str) -> bool:
        e = entry.lower()
        if e.startswith("."):  # suffix entry like ".gov"
            return host.endswith(e)
        if e.endswith("."):  # prefix keyword like "newswire."
            return e[:-1] in host
        if "." in e:  # domain entry: exact or subdomain
            return host == e or host.endswith("." + e)
        return e in host  # bare keyword (the mill list)

    if any(_host_match(d) for d in _TIER_MILL):
        return "report-mill"
    if any(_host_match(d) for d in _TIER_OFFICIAL):
        return "official/wire"
    if any(_host_match(d) for d in _TIER_PRESS):
        return "press"
    return "unverified"


_PLACEHOLDER_CITE_RE = re.compile(
    r"(?im)^(\s*(?:\[)?\d+(?:\])?[\.\)]?\s+).*?"
    r"(?:unspecified source|unspecified,|from analyst [ab]'?s? report|analyst [ab] report|"
    r"source unavailable|no url|url not available|internal analysis)\.?\s*$"
)


def _sanitize_citations(md: str) -> str:
    """Rewrite placeholder Works Cited entries ('[34] Unspecified source from Analyst B
    report.') into an honest unverified marker, KEEPING the number so in-text [n] still
    resolves. The compiler is told never to emit these (prompt-level), but the failure was
    observed live (26 of ~50 dead footnotes reading as real citations), so this is the
    deterministic backstop — an honest 'unverified' beats a numbered link to nothing. We do
    NOT fuzzy-match a real URL in (attaching the WRONG source is worse than admitting none)."""
    if not md:
        return md
    return _PLACEHOLDER_CITE_RE.sub(
        r"\1(analyst estimate — unverified; no source URL in the research transcript)", md
    )


# "A × B = C" product claims (sizing bridges: accounts × ACV = SAM, SAM × penetration = SOM).
# Token = money/count/percent form ("~$380M", "50,000", "40k", "15%"). The lookbehind and
# lookahead refuse digits/dashes/$ on either edge so neither half of a range ("$1M-$1.5M")
# nor the tail of another number can bind as a factor. Up to two unit words may sit between
# the first factor and the operator ("50,000 accounts × ..."). A bare ASCII "x" only counts
# as the operator when it stands alone ("5 x 6" yes, "5x return" no).
_ARITH_TOKEN = r"(?<![\w.$\-–—])[~≈>]{0,2}\s?\$?\s?[\d,]+(?:\.\d+)?\s*[kKmMbB%]?(?![\d\-–—])"
_ARITH_RE = re.compile(
    rf"({_ARITH_TOKEN})(?:\s+[A-Za-z][\w/()'%-]*){{0,2}}\s*(?:[×*]|\bx\b)\s*({_ARITH_TOKEN})"
    rf"([^=\n]{{0,60}}?)=\s*({_ARITH_TOKEN})"
)


def _arith_val(tok: str) -> float | None:
    """Token value in product-consistent units: money normalizes to $M (via _parse_money's
    K/B scaling), counts stay raw, percents become fractions (50% -> 0.5)."""
    t = str(tok or "").strip()
    if not t:
        return None
    pct = t.rstrip().endswith("%")
    v = _parse_money(t)
    if v is None:
        return None
    return v / 100.0 if pct else v


def _section_span(md: str, n: int) -> tuple[int, int] | None:
    """(start, end) byte span of canonical section `## n.` including its header line."""
    m = re.search(rf"(?m)^##\s+{n}\.(?!\d).*$", md or "")
    if not m:
        return None
    nxt = re.search(r"(?m)^##\s+\d+\.(?!\d)", md[m.end():])
    end = m.end() + nxt.start() if nxt else len(md)
    return m.start(), end


def _lint_arithmetic(md: str, cap: int = 5) -> list[dict]:
    """Deterministic check of every stated 'A × B = C' product in the compiled prose.
    Returns mismatches [{section, expr, computed, stated}] — tolerance 2% on exact '='
    claims, 15% when the expression is hedged (~/≈). Pure code; no LLM judgment."""
    if not md:
        return []
    spans = {n: _section_span(md, n) for n in _report_sections(md)}
    out: list[dict] = []
    for m in _ARITH_RE.finditer(md):
        a, b, _mid, c = m.group(1), m.group(2), m.group(3), m.group(4)
        va, vb, vc = _arith_val(a), _arith_val(b), _arith_val(c)
        if va is None or vb is None or vc is None or vc == 0:
            continue
        computed = va * vb
        if computed == 0 or not math.isfinite(computed):
            continue
        tol = 0.15 if ("~" in m.group(0) or "≈" in m.group(0)) else 0.02
        if abs(computed - vc) / abs(vc) <= tol:
            continue
        sec = next((n for n, sp in spans.items() if sp and sp[0] <= m.start() < sp[1]), None)
        out.append({"section": sec, "expr": m.group(0).strip(),
                    "computed": round(computed, 4), "stated": vc})
        if len(out) >= cap:
            break
    return out


def _repair_arithmetic(md: str, settings) -> str:
    """One-round, section-scoped repair of failed product claims — the deterministic
    backstop behind the prompt-level ARITHMETIC SELF-CHECK (same pattern as
    _sanitize_citations: prompt rule + code backstop). At most 2 sections repaired;
    a repair that fails re-lint, drops citations, changes the header, or resizes the
    section beyond 0.5-2.0x is DISCARDED and the original kept."""
    flags = _lint_arithmetic(md)
    if not flags:
        return md
    by_sec: dict[int, list[dict]] = {}
    for f in flags:
        if f["section"] is not None:
            by_sec.setdefault(f["section"], []).append(f)
    for sec in sorted(by_sec)[:2]:
        span = _section_span(md, sec)
        if not span:
            continue
        original = md[span[0]:span[1]]
        issues = "\n".join(
            f"- \"{f['expr']}\" — the product computes to ~{f['computed']:g} (in the same "
            f"units), but the text states {f['stated']:g}."
            for f in by_sec[sec]
        )
        try:
            llm = _make_llm(settings.compiler_model, temperature=0.1, max_tokens=8192)
            result = _invoke_llm_with_retry(llm, [
                ("system",
                 "You repair arithmetic in one section of a compiled investment report. "
                 "The stated products below do not compute. Fix ONLY what is needed to make "
                 "the arithmetic internally consistent — either recompute the product from "
                 "its inputs, or correct the inputs if the product is the externally-sourced "
                 "figure (prefer whichever preserves cited sources). Change nothing else: "
                 "keep the exact section header, every citation, every other figure, and the "
                 "same overall length. Return the FULL corrected section markdown and "
                 "NOTHING else — no preamble, no fences."),
                ("user", f"FAILED PRODUCTS:\n{issues}\n\nSECTION:\n{original}"),
            ])
            fixed = _normalize_content(result.content).strip()
        except Exception as e:  # noqa: BLE001 - repair is best-effort
            logger.error("Arithmetic repair call failed for §%s: %s", sec, e)
            continue
        # Invariants — any failure keeps the original section untouched.
        if not re.match(rf"^##\s+{sec}\.(?!\d)", fixed):
            continue
        if _lint_arithmetic(fixed):
            continue
        if fixed.count("](") < original.count("]("):
            continue
        ratio = len(fixed) / max(len(original), 1)
        if not (0.5 <= ratio <= 2.0):
            continue
        tail = md[span[1]:].lstrip("\n")
        md = md[:span[0]] + fixed.rstrip("\n") + ("\n\n" + tail if tail else "\n")
        logger.info("▶ Arithmetic repair applied to §%s (%d issue(s))", sec, len(by_sec[sec]))
    return md


def _harvest_source_index(messages: list, limit: int = 100) -> str:
    """Pull the real source URLs out of the tool transcripts into a numbered index
    appended to research_data — deterministic bookkeeping (R-series rule), so the
    analysts/compiler cite REAL links instead of reconstructing them from memory
    (the fabricated-Works-Cited failure observed live on 2026-07-02)."""
    seen: dict[str, str] = {}
    for m in messages or []:
        if getattr(m, "type", "") != "tool":
            continue
        for title, url in _MD_LINK_RE.findall(str(getattr(m, "content", ""))):
            if url not in seen:
                seen[url] = title.strip()
            if len(seen) >= limit:
                break
        if len(seen) >= limit:
            break
    if not seen:
        return ""
    lines = [f"{i}. [{t}]({u}) — tier: {_source_tier(u)}" for i, (u, t) in enumerate(seen.items(), 1)]
    return (
        "\n\n## Source Index (auto-generated from the search transcript — cite THESE "
        "exact URLs; do not invent or reconstruct links)\n"
        "Source tiers are classified in code: official/wire > press > unverified > "
        "report-mill. Base material figures on official/wire or press sources where "
        "available; a figure supported ONLY by a report-mill or unverified source must "
        "be labeled \"(weak source)\" where it is used — never silently blended.\n"
        + "\n".join(lines)
    )


# Month-year ("March 2026", "Mar. 2026"), ISO ("2026-03[-19]") and quarter ("Q2 2026")
# mentions — bare years are deliberately excluded (predictions like "by 2027" would
# poison the freshness signal).
_DATE_MENTION_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(20\d{2})\b"
    r"|\b(20\d{2})-(\d{2})(?:-\d{2})?\b"
    r"|\bQ([1-4])\s+(20\d{2})\b"
)
_MONTH_NUM = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
              "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _data_freshness(md: str) -> dict | None:
    """In-code freshness audit of the compiled report: how recent is the evidence it
    cites? Scans dated mentions (month-year / ISO / quarter), returns the newest and
    oldest plus a lag-vs-today — a computed number instead of a vibe. None when the
    report carries no dated mentions at all (itself a freshness red flag)."""
    stamps: list[tuple[int, int]] = []
    for m in _DATE_MENTION_RE.finditer(md or ""):
        if m.group(1):  # month-year
            stamps.append((int(m.group(2)), _MONTH_NUM[m.group(1)]))
        elif m.group(3):  # ISO year-month
            month = int(m.group(4))
            if 1 <= month <= 12:
                stamps.append((int(m.group(3)), month))
        else:  # quarter
            stamps.append((int(m.group(6)), int(m.group(5)) * 3 - 2))
    now = datetime.now()
    # Future-dated mentions are predictions/deadlines ("by October 2027", "Aug 2026
    # enforcement"), not evidence — they must not count toward evidence recency.
    stamps = [s for s in stamps if 2000 <= s[0] <= 2100 and s <= (now.year, now.month)]
    if not stamps:
        return None
    newest, oldest = max(stamps), min(stamps)
    months_lag = max(0, (now.year - newest[0]) * 12 + (now.month - newest[1]))
    return {
        "report_date": now.strftime("%Y-%m-%d"),
        "newest_dated_mention": f"{newest[0]}-{newest[1]:02d}",
        "oldest_dated_mention": f"{oldest[0]}-{oldest[1]:02d}",
        "dated_mentions": len(stamps),
        "months_since_newest": months_lag,
    }


# ------------------------------------------------------------------ #
#  Researcher Node – Gemini 2.5 Pro (ReAct agent with all tools)
# ------------------------------------------------------------------ #

def researcher_node(state: ResearchState) -> dict[str, Any]:
    """Run the Researcher agent to gather all data via search tools."""
    settings = get_settings()
    logger.info("▶ Researcher (Gemini) starting")

    # Large output budget so the 6-8 startup research brief isn't truncated.
    # The factory default (8192) was a likely cause of under-profiled reports,
    # since this brief is the sole input both analysts depend on.
    # 65536 matches the compiler on the same model: the ≥20-call protocol produces a much
    # larger brief, and a truncated brief starves the analysts (a documented prior failure).
    llm = _make_llm(settings.researcher_model, max_tokens=65536)

    agent = create_react_agent(
        model=llm,
        tools=RESEARCH_TOOLS,
        prompt=RESEARCHER_SYSTEM,
    )

    user_message = _build_researcher_user_message(state)
    result = _run_agent_with_retry(agent, {"messages": [("user", user_message)]})

    messages = result["messages"]
    research_output = _normalize_content(messages[-1].content)

    # Audit the (otherwise discarded) transcript: protocol compliance + real source URLs.
    manifest = _research_manifest(messages)
    urls_in_brief = research_output.count("http")
    manifest["urls_in_brief"] = urls_in_brief
    source_index = _harvest_source_index(messages)
    if source_index:
        research_output += source_index

    latest_news = manifest["by_tool"].get("search_latest_news", 0)
    grounded = manifest["by_tool"].get("search_google_live", 0)
    shortfalls = []
    if manifest["total"] < 20:
        shortfalls.append(f"only {manifest['total']} calls (<20)")
    if latest_news == 0:
        shortfalls.append("no latest-news freshness pass")
    if grounded == 0:
        shortfalls.append("no grounded precision checks")
    if urls_in_brief == 0:
        shortfalls.append("brief carries no source URLs")
    log = (
        f"[Researcher] {manifest['total']} searches ({latest_news} latest-news, "
        f"{grounded} grounded, {manifest['failed']} failed) → brief {len(research_output)} chars, "
        f"{urls_in_brief} URLs in prose, {source_index.count('](') if source_index else 0} in the Source Index"
    )
    if shortfalls:
        log += " — PROTOCOL SHORTFALL: " + "; ".join(shortfalls)

    return {
        "research_data": research_output,
        "research_manifest": manifest,
        "agent_logs": [log],
    }


# ------------------------------------------------------------------ #
#  Fan-out node for parallel analyst execution
# ------------------------------------------------------------------ #

def analysts_fanout(state: ResearchState) -> dict[str, Any]:
    """No-op pass-through node for parallel fan-out to both analysts."""
    return {}


# ------------------------------------------------------------------ #
#  Analyst A – Gemini 2.5 Pro (full-spectrum analyst, NO tools)
# ------------------------------------------------------------------ #

def analyst_a_node(state: ResearchState) -> dict[str, Any]:
    """Run Analyst Agent A — direct LLM call, no tools."""
    settings = get_settings()
    logger.info("▶ Analyst A (Gemini) starting — iteration %s", state.get("iterations", 0))

    llm = _make_llm(settings.analyst_a_model, max_tokens=16384)

    user_message = _build_analyst_user_message(state)
    result = _invoke_llm_with_retry(llm, [
        ("system", ANALYST_A_SYSTEM),
        ("user", user_message),
    ])

    report = _normalize_content(result.content)
    return {
        "agent_a_report": report,
        "agent_logs": [f"[Analyst A · Round {state.get('iterations', 0) + 1}] Completed analysis ({len(report)} chars)"],
    }


# ------------------------------------------------------------------ #
#  Analyst B – Claude Sonnet (full-spectrum analyst, NO tools)
# ------------------------------------------------------------------ #

def analyst_b_node(state: ResearchState) -> dict[str, Any]:
    """Run Analyst Agent B — direct LLM call, no tools."""
    settings = get_settings()
    logger.info("▶ Analyst B (Claude) starting — iteration %s", state.get("iterations", 0))

    llm = _make_llm(settings.analyst_b_model, max_tokens=16384)

    user_message = _build_analyst_user_message(state)
    result = _invoke_llm_with_retry(llm, [
        ("system", ANALYST_B_SYSTEM),
        ("user", user_message),
    ])

    report = _normalize_content(result.content)
    return {
        "agent_b_report": report,
        "agent_logs": [f"[Analyst B · Round {state.get('iterations', 0) + 1}] Completed analysis ({len(report)} chars)"],
    }


# ------------------------------------------------------------------ #
#  Judge Agent – GPT-4.1 (Arbitrator)
# ------------------------------------------------------------------ #

def _format_disagreements(disagreements: list) -> str:
    """Render the judge's disagreement list into a critique the analysts act on."""
    if not disagreements:
        return ""
    lines = ["The Judge flagged these disagreements between the two analysts:"]
    for i, d in enumerate(disagreements, 1):
        if not isinstance(d, dict):
            continue
        lines.append(
            f"{i}. {d.get('point', '')} — A: {d.get('analyst_a', '')}; B: {d.get('analyst_b', '')}. "
            f"Reconsider: {d.get('reconsider', '')}"
        )
    return "\n".join(lines)


def judge_node(state: ResearchState) -> dict[str, Any]:
    """Disagreement arbiter: PINPOINT where the two analysts diverge and route those
    points back for reconsideration. It does NOT score and does NOT build final_report —
    the platform reconciles the analysts' scores in code at compile time (compile_report).
    """
    settings = get_settings()
    iteration = state.get("iterations", 0) + 1
    is_final = iteration >= settings.max_debate_iterations
    logger.info("▶ Judge (disagreement arbiter) — iteration %s (final=%s)", iteration, is_final)

    llm = _make_llm(settings.judge_model, temperature=0.1, max_tokens=4096)
    system_prompt = get_judge_system_prompt(state.get("thesis_bias", "Base"))
    user_message = (
        f"## Analyst A Report\n\n{state.get('agent_a_report', '[No report]')}\n\n"
        f"---\n\n## Analyst B Report\n\n{state.get('agent_b_report', '[No report]')}\n\n"
        f"---\n\n**Dimension Weights (prioritize disagreements on high-weight dimensions):**\n"
        f"{_format_weights_block(state.get('dimension_weights'))}\n\n"
        f"**Current Iteration:** {iteration} of {settings.max_debate_iterations}\n\n"
        f"{_today_note('judge')}"
    )
    # Founder mode: both analysts write a §0.5 with deliberately independent repositioning
    # proposals — synthesis material for the compiler, not a disagreement to converge on.
    focal = (state.get("focal_startup") or "").strip()
    if focal and (state.get("analysis_mode") or "vc").lower() == "founder":
        user_message += (
            f"\n**FOUNDER MODE NOTE:** both reports include a Section 0.5 with repositioning "
            f"proposals for {focal}. Divergent 0.5 PROPOSALS are expected (the compiler "
            f"synthesizes them) — flag a 0.5 point ONLY if the analysts contradict each other "
            f"on a fact or on a score underlying it.\n"
        )
    if is_final:
        user_message += (
            '\n**FINAL ITERATION** — set "converged": true regardless; the analysts will '
            "not revise again. Still list any remaining disagreements for the record.\n"
        )

    result = _invoke_llm_with_retry(llm, [("system", system_prompt), ("user", user_message)])
    verdict = _last_balanced_json(_normalize_content(result.content)) or {}

    disagreements = verdict.get("disagreements")
    if not isinstance(disagreements, list):
        disagreements = []
    converged = bool(verdict.get("converged")) or is_final
    log = "converged" if converged else f"{len(disagreements)} disagreement(s) — looping"
    return {
        "iterations": iteration,
        "judge_agreed": converged,
        "judge_critique": "" if converged else _format_disagreements(disagreements),
        "agent_logs": [f"[Judge · Round {iteration}] {log}"],
    }


def _last_balanced_json(text: str) -> dict | None:
    """Return the last TOP-LEVEL JSON object in `text`, or None.

    Uses ``json.JSONDecoder().raw_decode`` so it is STRING-AWARE — braces inside a
    string value (e.g. judge synthesis/critique prose) don't corrupt parsing — and
    keeps nested objects whole. Tolerates prose/markdown around the JSON. Shared by
    the judge verdict and the structured-artifact extraction.
    """
    decoder = json.JSONDecoder()
    result: dict | None = None
    idx = 0
    n = len(text)
    while idx < n:
        brace = text.find("{", idx)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            idx = brace + 1
            continue
        if isinstance(obj, dict):
            result = obj  # keep the LAST successfully-decoded top-level object
        idx = max(end, brace + 1)  # skip past this object (don't descend into nesting)
    return result


def _report_sections(md: str) -> dict[int, str]:
    """Split a compiled report into {section_number: body} on `## N.` headings.
    `(?!\\d)` keeps the founder-only `## 0.5` heading from being keyed as section 0."""
    out: dict[int, str] = {}
    parts = re.split(r"(?m)^##\s+(\d+)\.(?!\d)", md or "")
    for i in range(1, len(parts) - 1, 2):
        try:
            out[int(parts[i])] = parts[i + 1]
        except (ValueError, IndexError):
            continue
    return out


def _extract_resolved_scores(analyst_a: str, analyst_b: str, settings, focal: str = ""):
    """Reconcile the analysts into ONE authoritative scoring set + side artifacts, via a
    focused JSON extraction validated in code.

    Returns (resolved_scores{startup:{5 dims}}, incumbents[names], scenarios|None,
    moat_subscores{startup:{4 subs}}, pre_pmf[names], focal_confidence:str).
    The `focal` startup (if any) is force-kept in the scorecard and gets a data-confidence tag.
    This is the source of truth for scoring (replaces the judge's unreliable scores) and
    also pulls the incumbent list (R1), the recommended startup's outcome scenarios (R6),
    the four moat sub-scores (R10), and pre-PMF watchlist names (R13).
    Slices each analyst report to sections 6-8 (scores) + 12 (scenarios) to stay cheap.
    """
    def slice_scores(rep: str) -> str:
        secs = _report_sections(rep or "")
        # §3 included for the exit tape (acquisitions are often named there, not §12).
        return "\n\n".join(f"## {n}.{secs[n]}" for n in (3, 6, 7, 8, 12) if n in secs) or (rep or "")

    focal_note = (
        f"\n\nFOCAL STARTUP = \"{focal}\". It MUST appear in resolved_scores (the user requires it) "
        f"even if early-stage — do NOT put it in incumbents or pre_pmf. Also return "
        f"\"focal_confidence\": \"low|medium|high\" reflecting how much hard data backs its scores."
        if str(focal).strip() else ""
    )
    user_message = (
        f"## Analyst A (sections 6-8, 12)\n\n{slice_scores(analyst_a)}\n\n"
        f"---\n\n## Analyst B (sections 6-8, 12)\n\n{slice_scores(analyst_b)}\n\n"
        f"---\n\nReconcile the two analysts' per-startup, per-dimension RAW scores into ONE set "
        f"(average where they differ; include EVERY investable startup either scored, EXCLUDE "
        f"incumbents AND pre-PMF/pre-launch names). Give each scored startup's four a16z moat "
        f"sub-scores. List the incumbents and the pre-PMF names you excluded, and extract the "
        f"recommended startup's outcome scenarios with probabilities and return multiples "
        f"(plus entry post-money and per-scenario exit dollar values where the analysts stated "
        f"them), and the exit_tape of named sector acquisitions. JSON ONLY."
        f"{focal_note}"
    )
    try:
        llm = _make_llm(settings.judge_model, temperature=0.1, max_tokens=6144)
        result = _invoke_llm_with_retry(llm, [
            ("system", RESOLVE_SCORES_SYSTEM),
            ("user", user_message),
        ])
        raw = _last_balanced_json(_normalize_content(result.content)) or {}

        def _name_list(key):
            v = raw.get(key)
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

        incumbents = _name_list("incumbents")
        pre_pmf = _name_list("pre_pmf")
        if str(focal).strip():
            # FOCAL EXCEPTION (R1/R13) applies to the NAME lists too, not just the drop-sets:
            # if the resolve LLM mislabels the focal, an unfiltered list would tell the
            # compiler/map/ledger it is both scored and excluded in the same message.
            fkey = _norm_name(focal)
            incumbents = [x for x in incumbents if _norm_name(x) != fkey]
            pre_pmf = [x for x in pre_pmf if _norm_name(x) != fkey]
        resolved = _validate_resolved_scores(raw.get("resolved_scores"), incumbents, pre_pmf, protect=focal)
        moat_subscores = _validate_moat_subscores(raw.get("moat_subscores"), resolved.keys())
        _apply_moat_reconciliation(resolved, moat_subscores)  # R10: defensibility = mean(subs)
        scenarios = _validate_scenarios(raw.get("scenarios"))
        fc = str(raw.get("focal_confidence", "")).strip().lower()
        focal_confidence = fc if fc in {"low", "medium", "high"} else ""
        # PRE-compile exit tape (the post-compile acquisitions artifact can't inform §12 —
        # it is extracted AFTER the compiler runs). Best-effort; never drops other keys.
        exit_tape = _validate_acquisitions(raw.get("exit_tape"))
        return resolved, incumbents, scenarios, moat_subscores, pre_pmf, focal_confidence, exit_tape
    except Exception as e:  # noqa: BLE001 - scoring is best-effort; degrade gracefully
        logger.error("Resolved-scores extraction failed: %s", e)
        return {}, [], None, {}, [], "", None


def _acq_multiple_on_capital(value, raised) -> float | None:
    """Deal value ÷ target's total capital raised — the multiple-on-capital the exit
    tape is read on. None when either side doesn't parse or raised <= 0."""
    v, r = _parse_money(value), _parse_money(raised)
    if v is None or r is None or r <= 0 or v <= 0:
        return None
    m = v / r
    return round(m, 1) if math.isfinite(m) else None


def _validate_acquisitions(raw) -> list[dict] | None:
    """Coerce the acquisitions artifact into render-safe rows (exit-precedent table).
    Rows need at least target + acquirer; other fields default to 'Not Disclosed'.
    multiple_on_capital is computed IN CODE (value ÷ raised) — never LLM-asserted.
    None when nothing usable — never raw LLM output."""
    if not isinstance(raw, list):
        return None
    rows: list[dict] = []
    for r in raw[:12]:
        if not isinstance(r, dict):
            continue
        target = str(r.get("target") or "").strip()
        acquirer = str(r.get("acquirer") or "").strip()
        if not target or not acquirer:
            continue
        value = str(r.get("value") or "Not Disclosed").strip()[:40]
        raised = str(r.get("target_total_raised") or "Not Disclosed").strip()[:40]
        rows.append({
            "target": target[:80],
            "acquirer": acquirer[:80],
            "announced": str(r.get("announced") or "Not Disclosed").strip()[:40],
            "value": value,
            "target_total_raised": raised,
            "multiple_on_capital": _acq_multiple_on_capital(value, raised),
        })
    return rows or None


def _extract_structured_artifacts(merged_report: str, weighted_scores: dict, settings,
                                  canonical=None, incumbents=None):
    """Dedicated JSON pass over the finished report -> (market_map, financial_ledger,
    acquisitions), each validated/coerced in code. Any may be None on failure; the UI
    then degrades to prose-only. Slices to the relevant sections to keep the call cheap.

    `canonical` (the ranked investable set) and `incumbents` are threaded into the
    validators so coverage is reconciled (R3) and incumbents are marked authoritatively (R1).
    """
    secs = _report_sections(merged_report)
    relevant = "\n\n".join(f"## {n}.{secs[n]}" for n in (3, 5, 6, 8, 12, 13) if n in secs)
    source = relevant or merged_report  # fall back to full report if heading split failed

    user_message = (
        f"## Final Report (extract from THIS)\n\n{source}\n\n"
        f"---\n\n## Authoritative weighted scores (copy each weighted_score VERBATIM)\n"
        f"```json\n{json.dumps(weighted_scores, indent=2)}\n```\n\n"
        f"Extract the Section 5 axes, the Section 13 market-map company placements, the "
        f"Section 6 Financial Ledger, and the acquisition precedents named in Sections 3/8/12 "
        f"into the JSON object from the system instructions, using the Section 8 profiles for "
        f"each company's stage / segment / capital raised. JSON ONLY."
    )
    try:
        llm = _make_llm(settings.compiler_model, temperature=0.1, max_tokens=8192)
        result = _invoke_llm_with_retry(llm, [
            ("system", STRUCTURED_ARTIFACTS_SYSTEM),
            ("user", user_message),
        ])
        raw = _last_balanced_json(_normalize_content(result.content)) or {}
        # Validate INSIDE the try so a malformed shape can never crash compile_report.
        market_map = _validate_market_map(raw.get("market_map"), weighted_scores, incumbents, canonical)
        financial_ledger = _validate_financial_ledger(raw.get("financial_ledger"), canonical, incumbents)
        acquisitions = _validate_acquisitions(raw.get("acquisitions"))
        return market_map, financial_ledger, acquisitions
    except Exception as e:  # noqa: BLE001 - structured artifacts are optional UI sugar
        logger.error("Structured-artifact extraction failed: %s", e)
        return None, None, None


_TIER_TAG_RE = re.compile(r"— tier: (official/wire|press|unverified|report-mill)")


def _methodology_section(state: ResearchState, settings, data_freshness: dict | None,
                         financial_ledger: dict | None) -> str:
    """'What we diligenced — and what we did NOT': generated DETERMINISTICALLY from the
    pipeline's own telemetry (manifest, source tiers, freshness, debate rounds, upload
    presence) — never written by the LLMs, so it can't inflate the apparatus. The negative
    scope is what makes the confident claims elsewhere trustworthy."""
    lines = [
        "\n\n## Methodology & Scope",
        "",
        "*Generated deterministically from the pipeline's own telemetry — not written by "
        "the language models.*",
        "",
    ]
    mf = state.get("research_manifest") or {}
    if mf.get("total"):
        by = mf.get("by_tool") or {}
        lines.append(
            f"- **Research:** {mf['total']} web searches "
            f"({by.get('search_latest_news', 0)} latest-news freshness checks, "
            f"{by.get('search_google_live', 0)} Google-grounded precision checks, "
            f"{mf.get('failed', 0)} failed)."
        )
    tiers = {}
    for m in _TIER_TAG_RE.finditer(state.get("research_data") or ""):
        tiers[m.group(1)] = tiers.get(m.group(1), 0) + 1
    if tiers:
        total_src = sum(tiers.values())
        lines.append(
            f"- **Sources:** {total_src} indexed — "
            f"{tiers.get('official/wire', 0)} official/wire, {tiers.get('press', 0)} press, "
            f"{tiers.get('unverified', 0)} unverified, {tiers.get('report-mill', 0)} report-mill. "
            f"Material figures should rest on the first two tiers; weak-tier figures are flagged in text."
        )
    if data_freshness:
        lines.append(
            f"- **Evidence freshness:** newest dated mention {data_freshness.get('newest_dated_mention')}, "
            f"oldest {data_freshness.get('oldest_dated_mention')} (run date {data_freshness.get('report_date')})."
        )
    rounds = state.get("iterations", 0)
    lines.append(
        f"- **Analysis:** two independent analysts on different model platforms "
        f"({settings.analyst_a_model} and {settings.analyst_b_model}) debated for {rounds} "
        f"round(s), arbitrated by a {settings.judge_model} judge; scores, weighted index, "
        f"grades, and return math are computed in code from the reconciled outputs."
    )
    if (state.get("analysis_mode") or "vc").lower() == "founder" or state.get("focal_startup"):
        has_deck = bool((state.get("focal_materials") or "").strip())
        lines.append(
            f"- **Focal materials:** {'founder-provided documents were parsed and used as a primary source on the focal startup (self-reported).' if has_deck else 'none uploaded — the focal startup is assessed from public information only.'}"
        )
    if isinstance(financial_ledger, dict):
        rows = [r for r in financial_ledger.get("rows", []) or []
                if isinstance(r, dict) and not r.get("is_incumbent")]
        if rows:
            arr_n = sum(1 for r in rows if _parse_money(r.get("arr")) is not None)
            thin = " — willingness-to-pay evidence is thin category-wide" if arr_n <= max(1, len(rows) // 4) else ""
            lines.append(f"- **Category disclosure:** {arr_n} of {len(rows)} scored startups disclose ARR{thin}.")
    lines.append(
        "- **NOT diligenced:** founder references, cap tables, legal, private financials, "
        "and source code — all figures are outside-in web research at the tiers above, and "
        "any proposed terms are the platform's own framing, not a company ask."
    )
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ #
#  Final Report Compiler – Gemini 2.5 Pro (single-pass, 65K output)
# ------------------------------------------------------------------ #

def compile_report(state: ResearchState) -> dict[str, Any]:
    """Reconcile the analysts' scores in code, compute the weighted index, compile the
    final report, and emit the structured UI artifacts. The judge no longer scores or
    builds final_report — this node assembles the whole thing.
    """
    logger.info("▶ Compiling final report")
    settings = get_settings()
    analyst_a = state.get("agent_a_report", "")
    analyst_b = state.get("agent_b_report", "")
    weights = state.get("dimension_weights")
    focal = (state.get("focal_startup") or "").strip()
    mode = (state.get("analysis_mode") or "vc").lower()

    # 1) Authoritative scores: reconcile the two (converged) analysts IN CODE — this
    #    replaces the judge's unreliable resolved_scores (the prior failure mode).
    #    Also returns the excluded incumbents (R1) and the recommended startup's
    #    outcome scenarios, from which we compute the expected return in code (R6).
    #    The focal startup (if any) is force-kept and tagged with a data confidence.
    resolved_scores, incumbents, scenarios, moat_subscores, pre_pmf, focal_confidence, exit_tape = _extract_resolved_scores(analyst_a, analyst_b, settings, focal)  # noqa: E501
    weighted_scores, ranking = _compute_weighted_scores(resolved_scores, weights)
    weighting_unavailable = not ranking
    if weighting_unavailable:
        logger.warning("No usable analyst scores to reconcile — weighted index unavailable")
    applied = {k: round(v, 4) for k, v in _normalize_weights(weights).items()}

    # R6: probability-weighted return is arithmetic — compute it in code from the analysts'
    # scenarios, then hand the compiler BOTH the exact figure AND the exact scenario rows that
    # produced it, so §0, §12, and the §12 table all reconcile (the headline can't drift from
    # the table the compiler renders — the prior residual).
    expected_return = scenarios.get("expected_return") if isinstance(scenarios, dict) else None
    er_low = scenarios.get("expected_return_low") if isinstance(scenarios, dict) else None
    er_high = scenarios.get("expected_return_high") if isinstance(scenarios, dict) else None
    # Range presentation kills the false-precision failure (a bare "6.05x" reads as more
    # rigorous than ranged scenario inputs support). Falls back to the midpoint alone.
    _is_range = er_low is not None and er_high is not None and er_low != er_high
    if _is_range:
        er_text = f"{er_low}x–{er_high}x (midpoint {expected_return}x)"
        er_presentation = "Present it as this RANGE verbatim"
    else:
        er_text = f"{expected_return}x"
        er_presentation = "Present it as this single expected multiple (the scenario inputs carried no ranges)"
    _ASSUMPTIONS = (
        "State its assumptions wherever it appears: a GROSS multiple on today's scenario "
        "ranges — before dilution, ownership, fees, and time-value (no IRR)."
    )
    _scen_startup = scenarios.get("startup") if isinstance(scenarios, dict) else None
    # Whether the field's return scenarios describe the focal itself (VC mode where the focal
    # is the top pick) or a competitor (the usual founder-mode case — the field leader).
    # Tolerant match: the resolve LLM may return "NeuroScribe, Inc." for focal "NeuroScribe".
    # Containment either way avoids a self-contradictory "focal is its own competitor" note.
    _fk, _sk = _norm_name(focal), _norm_name(_scen_startup or "")
    _scen_is_focal = bool(_fk) and bool(_sk) and (_fk == _sk or _fk in _sk or _sk in _fk)
    # Net-of-dilution (R6'): gross multiple × stage-banded ownership retention to exit —
    # computed in code so the "investor outcome" figure is never a gross multiple in disguise.
    retention = _stage_retention(state.get("stage"))
    er_net_low = round(er_low * retention, 2) if er_low is not None else None
    er_net_high = round(er_high * retention, 2) if er_high is not None else None
    dominance = _scenario_dominance(scenarios.get("scenarios")) if isinstance(scenarios, dict) else None
    if expected_return is not None and isinstance(scenarios, dict):
        _rows = scenarios.get("scenarios", [])
        # Render probabilities at one-decimal precision when non-integral: rounding 52.5%→52%
        # in the printed table makes it impossible for a reader to reproduce the code-computed
        # EV from the visible rows (critique: table can't reproduce its own headline).
        _tbl = "\n".join(
            f"  - {s['label']}: probability {round(s['probability'] * 100, 1):g}%, "
            f"return {s['multiple_low']}x"
            + ("" if s["multiple_low"] == s["multiple_high"] else f"–{s['multiple_high']}x")
            + (f" — path: {s['path']}" if s.get("path") else "")
            for s in _rows
        )
        if er_net_low is not None and er_net_high is not None:
            # Degenerate ranges (low == high) must not read as "the same range is 3.9x–3.9x"
            # right after er_presentation said the inputs carried no ranges.
            _net_val = (f"the same range is {er_net_low}x–{er_net_high}x"
                        if er_net_low != er_net_high else f"the same figure is ≈{er_net_low}x")
            _net_note = (
                f" NET of estimated future dilution (stage-banded assumption: ~{round((1 - retention) * 100)}% "
                f"additional dilution to exit, i.e. ×{retention} ownership retention), {_net_val} "
                f"on today's entry — present BOTH gross and net, each with its label."
            )
        else:
            _net_note = ""
        # When the EV is dominated by a NON-base (tail) case, a blended-EV headline overstates the
        # modal outcome — lead with the base case and label the blend tail-dominated (critique fix).
        _tail_dom = bool(dominance) and dominance[0].lower() not in ("base", "base case") and dominance[1] > 50
        _dom_note = (
            f" SYSTEM-COMPUTED: the expected value is dominated by the {dominance[0]} case "
            f"({dominance[1]}% of EV) — close the scenario table by naming the single belief that "
            f"case requires, citing a researched acquisition precedent where one exists."
            + (f" Because {dominance[1]}% of the EV sits in the {dominance[0]} (tail) case, do NOT "
               f"headline the blended EV as the expected outcome: LEAD Section 0/12 with the BASE-case "
               f"multiple as the modal outcome, present the blended range SECOND explicitly labeled "
               f"'tail-dominated', and add one 'what must be true' sentence for the tail case. "
               f"DEFEND the tail dominance against the stage outcome base rate you cited (per the "
               f"BASE-RATE ANCHOR rule): a tail-dominated EV is the exception that needs the "
               f"strongest named evidence, never the default."
               if _tail_dom else "")
            if dominance else ""
        )
        if mode == "founder" and not _scen_is_focal:
            # Founder mode: §12 must be about the FOUNDER's fundraise, not a competitor's MoIC.
            # The computed figure is the FIELD LEADER's — allow it only as labeled exit context,
            # never as the focal's headline return.
            return_note = (
                f"\n\nSYSTEM-COMPUTED probability-weighted return of {er_text} is for "
                f"**{_scen_startup or 'the field leader'}** — a COMPETITOR, NOT {focal or 'the focal'}. "
                f"In FOUNDER MODE, Section 12 is about {focal}'s own path, NOT a competitor's MoIC: "
                f"do NOT headline it as {focal}'s return in Section 0 or 12. You MAY "
                f"cite it ONCE inside Section 12 as exit-comp context, explicitly labeled as the field "
                f"leader's and presented as the RANGE {er_text}. {_ASSUMPTIONS} Use exactly these rows:\n{_tbl}"
            )
        else:
            # VC mode, or founder mode where the focal IS the modelled pick: the figure is the
            # focal's own — the original verbatim-in-§0/§12 contract holds, as a RANGE.
            # Market-overview runs (VC, no focal): §0 carries the sector call, not a deal
            # multiple — the pick's return figure renders in §12 only (overview_note below).
            _er_sections = ("in Section 12 ONLY — Section 0 carries the sector verdict, never a "
                            "single deal's multiple" if not focal else "in Sections 0 and 12")
            return_note = (
                f"\n\nSYSTEM-COMPUTED probability-weighted return for {_scen_startup or 'the top pick'}: "
                f"{er_text}. {er_presentation} {_er_sections} (do NOT recompute"
                + (", and do NOT present the midpoint alone as a precise forecast" if _is_range else "")
                + f"). {_ASSUMPTIONS}{_net_note}{_dom_note} "
                f"Render the Section 12 scenario table with EXACTLY these rows (keep each PATH) — do "
                f"NOT change the probabilities or return multiples, because they are what produce "
                f"this figure:\n{_tbl}"
            )
    else:
        return_note = ""

    # The pick is canonicalized ONCE here and reused for the bridge note + final_report.
    recommended = _canonical_pick(_scen_startup, ranking, focal, mode)
    # Fund-math engine ("does THIS deal return MY fund?") — computed in code from the SAME
    # scenarios + the same stage retention, so it cannot contradict the shipped net range.
    # None (whole block suppressed) unless fund_size was provided. The note hands the compiler
    # code-computed display strings to render verbatim (no LLM-asserted fund numbers).
    # Entry-post precedence: the user's fund_economics wins; the resolve-emitted modelled
    # entry post (scenarios.entry_post_money_musd) fills it only when the user gave none.
    _fund_econ = dict(state.get("fund_economics") or {})
    _scen_entry = (scenarios or {}).get("entry_post_money_musd") if isinstance(scenarios, dict) else None
    # Entry-post precedence: user input > uploaded CAP TABLE (real terms, focal-only —
    # gated on the scenarios actually describing the focal, so a competitor's scenarios
    # can never be priced at the focal's post) > resolve-emitted modelled post > stage.
    _cap = state.get("cap_table") or {}
    _post_from_cap = False
    if (_fin(_fund_econ.get("entry_post_money_musd")) is None and _scen_is_focal
            and _fin(_cap.get("latest_post_money_musd")) is not None):
        _fund_econ["entry_post_money_musd"] = _cap["latest_post_money_musd"]
        _post_from_cap = True
    if _fin(_fund_econ.get("entry_post_money_musd")) is None and _fin(_scen_entry) is not None:
        _fund_econ["entry_post_money_musd"] = _scen_entry
    fund_math = _compute_fund_math(scenarios, _fund_econ, state.get("stage"),
                                   retention, mode=mode, scen_is_focal=_scen_is_focal)
    if fund_math and _post_from_cap:
        # Cap-table-grounded post is a strength, not a caveat — but disclose the source
        # (and it supersedes the stage-inference flag, which cannot have fired).
        fund_math.setdefault("flags", []).append("post_from_cap_table")
    fund_note = _fund_math_note(fund_math, recommended or focal or _scen_startup or "")
    # PRE-compile exit tape with code-computed multiples-on-capital — the §12 both-ways
    # tape reading cites these verbatim (the post-compile acquisitions artifact arrives
    # too late to inform the compiler).
    tape_note = ""
    if exit_tape:
        _tr = []
        for a in exit_tape:
            mc = a.get("multiple_on_capital")
            line = f"  - {a['target']} ← {a['acquirer']}: {a['value']}"
            if a["announced"] != "Not Disclosed":
                line += f" ({a['announced']})"
            if mc is not None:
                line += f" — {mc:g}x on {a['target_total_raised']} raised (computed in code)"
            elif a["target_total_raised"] != "Not Disclosed":
                line += f" — raised {a['target_total_raised']}"
            _tr.append(line)
        tape_note = (
            "\n\nSYSTEM-COMPUTED EXIT TAPE (multiples on invested capital computed in code — "
            "cite these rows VERBATIM in Section 12's both-ways tape reading; do NOT recompute "
            "or invent deals):\n" + "\n".join(_tr)
        )
    # D/F-grade bridge (memo lesson): a pick carrying failing grades must have §0 classify
    # each as buyable-with-the-round or structural — the failing list is computed in code.
    # Tolerant lookup: in founder mode `recommended` is the raw focal string while the
    # resolve LLM may key it as a variant ("Fidea, Inc." for "Fidea") — same containment
    # matching as _canonical_pick/_scen_is_focal.
    _by_norm = {_norm_name(n): d for n, d in (resolved_scores or {}).items()}
    _rk = _norm_name(recommended)
    _pick_dims = (_by_norm.get(_rk)
                  or next((d for k, d in _by_norm.items() if _rk and (_rk in k or k in _rk)), None)
                  or {})
    _failing = [DIMENSION_LABELS[k] for k in DIMENSION_KEYS
                if (_v := _as_score(_pick_dims.get(k))) is not None and _v < 35]
    # In market-overview runs the pick's full underwrite lives in §12 (§0 is a sector call),
    # so the bridge sentences attach there; otherwise §0.
    _bridge_section = "Section 12" if not focal else "Section 0"
    bridge_note = (
        f"\n\nGRADE BRIDGE (system-computed): the pick ({recommended}) carries failing-grade "
        f"dimensions: {', '.join(_failing)}. {_bridge_section} MUST contain one bridge sentence "
        f"per failing dimension classifying it as BUYABLE-with-the-round (money/conditions fix "
        f"it) or STRUCTURAL — and if structural, why the verdict survives it."
        if _failing and recommended else ""
    )

    # Focal-startup framing: VC mode = ensure it's in the ranked field; Founder mode = center
    # the whole report on it with an explicit verdict. Confidence badge in either case.
    focal_note = ""
    if focal:
        conf = f" Data confidence on {focal} is **{focal_confidence}** — state this caveat where you present its scores." if focal_confidence else ""
        if focal_confidence == "low":
            # §7 stealth banding: low scores driven by non-disclosure are not comparable
            # to funded peers' scored weaknesses — present them as disclosure-limited.
            conf += (
                f" Wherever {focal}'s scores appear (Sections 0, 0.5, 7, and any bridge sentence), "
                f"present them as approximate (≈) and round to whole numbers — NEVER show decimal "
                f"precision (e.g. '43.4/100') on a disclosure-limited focal, which falsely implies "
                f"measurement it doesn't have. In Section 7, present {focal}'s row as "
                f"'disclosure-limited — not directly comparable to funded peers', separating REAL "
                f"closable gaps (no shipped product, unknown team) from pure non-disclosure artifacts."
            )
        if mode == "founder":
            # §0.5 anchors are computed in code from the reconciled scorecard (same
            # determinism-in-code rule as the weighted index) — with a fallback parallel
            # to weighting_note when reconciliation produced nothing usable.
            weak_spots = _focal_weak_spots(resolved_scores, moat_subscores, focal)
            if weak_spots:
                anchor = (
                    f"ANCHOR it to the SYSTEM-COMPUTED weak spots for {focal} (authoritative — "
                    f"computed in code from the reconciled scorecard): {weak_spots}. Every move "
                    f"MUST target one of those named dimensions/sub-scores — do NOT substitute a "
                    f"weakness of your own choosing. Every listed weak DIMENSION must be addressed "
                    f"by at least one move (the listed moat sub-scores are targeting detail for a "
                    f"Defensibility move, not separate obligations); if no analyst proposal targets "
                    f"a listed weak dimension, RE-ANCHOR the best-evidenced proposal to it — do not "
                    f"fabricate new evidence. "
                )
            elif ranking:
                # The scorecard reconciled fine — only the focal is missing from it. Saying
                # "the scorecard was unavailable" would be false in the same message that
                # carries the authoritative scores block.
                anchor = (
                    f"The reconciled scorecard has no usable entry for {focal} — anchor the moves "
                    f"to the weaknesses BOTH analysts agree on for {focal}, and flag that "
                    f"{focal}'s Section 7 scores are analyst-asserted, not system-reconciled. "
                )
            else:
                anchor = (
                    f"No system-computed weak spots are available for this run — anchor the moves "
                    f"to the weaknesses BOTH analysts agree on for {focal}, and say plainly that "
                    f"the reconciled scorecard was unavailable. "
                )
            # Section 12 wording depends on whether the modelled scenarios are the focal's own
            # (analysts picked the focal as field leader) or a competitor's (the usual case).
            # Shared founder §12 discipline appended to BOTH branches (critique: the fundraise
            # math was incoherent — 43% implied dilution, missing ownership line, comp anchored
            # to a mislabeled round size with a dead citation, and the deal-verdict devices
            # silently vanished with no founder-shaped replacement).
            _founder_s12_close = (
                f"\n\nFUNDRAISE DISCIPLINE (mandatory, {focal}): "
                f"(a) State the round's IMPLIED DILUTION = raise ÷ post-money as a %, and the "
                f"resulting founder ownership, labeled '(illustrative)'. The dilution MUST land in "
                f"the 15–25% seed norm — reconcile the ask and post-money so they do, or state "
                f"explicitly why not. A $5–8M raise on a $12–18M post (≈43% dilution) is INCOHERENT "
                f"and must be corrected, never printed. "
                f"(a2) RUNWAY-TO-MILESTONE check: from the use-of-proceeds (headcount + programs) "
                f"estimate an implied monthly burn, then state whether the raise ÷ burn buys enough "
                f"months to actually reach the next-round milestones in (d) BEFORE cash-out — a raise "
                f"that doesn't fund its own milestones is the real risk. Round to whole months. "
                f"(b) Any raise size or post-money the founder materials do not disclose carries "
                f"'(assumed; no formal ask)'. "
                f"(c) Benchmark the post-money ONLY to a named Section 6 ledger comp OR a named "
                f"deal from the acquisitions table — say which — and NEVER to a figure whose source "
                f"is below press tier or reads 'Unspecified'. NEVER treat an amount RAISED as a "
                f"valuation. "
                f"(d) CONDITIONS TO CLOSE: the 3–4 milestones ARE the conditions a lead will require "
                f"— render them as **Conditions to close the round**, each with a measurable metric, "
                f"a DEADLINE, and how a lead verifies it. Mandatory when any Section 11 risk is "
                f"EXISTENTIAL or {focal}'s data confidence is low. "
                f"(e) Close Section 12 with **Why not stop — and why not raise more**: grant every "
                f"fact in the strongest STOP/PIVOT case, tag each PRICED-BY-STAGE / CONDITIONED (a "
                f"milestone answers it) / CUTS-BOTH-WAYS, then resolve on the ONE question that "
                f"decides whether {focal} raises now. "
                f"(f) The template's WHAT-WE-MUST-BELIEVE ledger and NEXT-DILIGENCE-STEPS blocks "
                f"apply here in FOUNDER voice: the beliefs are what a LEAD INVESTOR must believe to "
                f"write the check, and the diligence steps are what that lead will verify — so the "
                f"founder can pre-empt each one (prepare the reference list, the pipeline audit, the "
                f"threat model) before the partner meeting."
            )
            if _scen_is_focal:
                s12_note = (
                    f"SECTION 12 (Return Math) is about {focal}. The system-computed "
                    f"probability-weighted return IS {focal}'s own (see the return note) — you MAY "
                    f"headline it. ALSO give {focal}'s fundraise path: recommended next round "
                    f"(stage + raise-size range), target post-money BENCHMARKED to named Section 6 "
                    f"comps, realistic dilution / founder ownership, and the 3-4 milestones that "
                    f"unlock the round." + _founder_s12_close
                )
            else:
                s12_note = (
                    f"SECTION 12 (Return Math) IS ABOUT {focal}'s FUNDRAISE, not a competitor's "
                    f"MoIC. PRIMARY content, in this order: (1) {focal}'s recommended next round "
                    f"(stage + raise-size range); (2) target post-money BENCHMARKED to named "
                    f"Section 6 comps (state which comps and their multiples — do NOT state a "
                    f"post-money that conflicts with the Section 6 ledger; label ownership figures "
                    f"'(illustrative)'); (3) realistic dilution / founder ownership after the round; "
                    f"(4) the 3-4 concrete milestones that unlock the round. The field leader's "
                    f"probability-weighted MoIC may appear AFTERWARD as a clearly-labeled, "
                    f"SUBORDINATE 'Exit comparable' block (max 2 sentences + the table) — NEVER in "
                    f"Section 0, and never as {focal}'s headline return." + _founder_s12_close
                )
            focal_note = (
                f"\n\n=== FOUNDER MODE — THESE INSTRUCTIONS OVERRIDE YOUR FRAMEWORK ===\n"
                f"For THIS run, the Section 0 and Section 12 instructions below REPLACE the Section 0 "
                f"(top pick / recommendation-at-a-price) and Section 12 (headline the top pick's "
                f"probability-weighted return) instructions in your system template AND in COMPILATION "
                f"INSTRUCTION 2 — where they conflict, THIS message wins. The two analyst reports you "
                f"are merging both take a FIELD-LEVEL view (they name a competitor top pick); you MUST "
                f"re-frame Sections 0 and 12 around {focal}, not merge those competitor takes verbatim.\n"
                f"\nThe SUBJECT of this report is **{focal}**. Frame the whole document around it: "
                f"position {focal} against each competitor throughout, name its sharpest wedge and its "
                f"most likely failure mode, and end with the concrete bar it must clear to be "
                f"venture-scale. {focal} MUST be profiled (Section 8) and scored (Section 7).{conf}"
                f"\n\nSECTION 0 (BLUF) IS ABOUT {focal}, NOT THE FIELD. The FIRST LINE under the "
                f"`## 0` header is the **Investor check (today):** line — NO preamble sentence "
                f"before it. Render THREE explicitly labeled lines: (1) **Investor check (today):** "
                f"is {focal} fundable for a check right now — yes / not-yet — and why; (2) **Founder "
                f"call:** BUILD / KEEP GOING / PIVOT / STOP, with one sentence on whether {focal}'s "
                f"low stealth/early-stage scores are STAGE-NORMAL (expected for its stage) or "
                f"genuinely alarming; (3) **Binary variable:** the single factor {focal}'s BUILD/"
                f"PIVOT/STOP call actually turns on, in {focal}'s own kill-condition voice ('if X is "
                f"not true, stop building') — about {focal}, with ONE metric and ONE deadline, never "
                f"a competitor. Section 0 must contain NO buy/INVEST recommendation, "
                f"NO entry/indicative valuation, and NO MoIC/return multiple for ANY company other "
                f"than {focal} — the field ranking lives in Section 7 only. You may name the field "
                f"leader ONCE as {focal}'s benchmark, with zero recommendation language.\n"
                f"\n\nTRIPWIRE COHERENCE (one causal chain, not three tripwires): the phrase "
                f"'binary variable' appears EXACTLY TWICE in the report — in Section 0 (line 3 above) "
                f"and on Section 11's top-severity (EXISTENTIAL) risk, which MUST restate Section 0's "
                f"binary VERBATIM (same metric, same deadline). Never label any other risk 'the binary "
                f"variable'. Section 0.5's 'Fastest signal to quit' must be the cheapest self-runnable "
                f"TEST of that SAME variable (it may be an earlier rung of the same ladder — e.g. "
                f"signed LOIs before paying design partners — but must name the same underlying gate). "
                f"Order Section 11 by threat-to-{focal} and mark each mitigant IN {focal}'s CONTROL or "
                f"OUTSIDE IT.\n"
                f"\n\nMECHANISM RED-TEAM (inside {focal}'s Section 8 profile — a bounded sub-block, "
                f"NOT a new section; applies when {focal}'s differentiation rests on specific "
                f"technical/architectural mechanisms, which for an infra/security product it does): "
                f"enumerate the 3-5 load-bearing MECHANISMS the materials claim (one dense paragraph "
                f"each) and for each state (a) its OWN attack surface and error modes; (b) any "
                f"CONTRADICTION between two of the materials' claims (e.g. a feature that requires "
                f"inspecting content vs a privacy claim of never seeing it) — deck-internal "
                f"contradictions are the highest-value finding; (c) its concentration/blast-radius "
                f"cost; (d) the missing evidence a buyer's staff engineer will demand — phrased as "
                f"the SECOND-MEETING OBJECTION and paired with the pre-emptive artifact {focal} "
                f"should publish (a p99 latency benchmark, a fail-open/fail-closed policy matrix, a "
                f"threat model). This block OWNS claim-level skepticism; Section 8's Failure Mode "
                f"and Section 11 reference it rather than repeating it. If the differentiation is "
                f"genuinely not mechanism-based, say so in one line and skip the block.\n"
                f"\nIP PROVENANCE: when {focal}'s moat is claimed as an architecture the founders "
                f"built at a prior employer, flag the trade-secret/IP diligence question a lead will "
                f"raise as a NAMED Section 11 risk or Section 12 condition (with the one-sentence "
                f"reframe: 'the same principles, re-derived' — never 'the same architecture') — this "
                f"is a legal-hygiene flag, not an Honest-caveats line.\n"
                f"\nONE-TELLING RULE: each load-bearing fact about {focal} (a founder's provenance, "
                f"a flagship architecture claim, a marquee stat) is told ONCE in full, in the section "
                f"that owns it — every later mention is a one-clause reference. Repeating the same "
                f"credential card in Sections 0, 3, 8, 9, and 12 reads as padding and dilutes it.\n"
                f"\nDECK-AS-ARTIFACT: where the research brief carries per-claim verdicts on the "
                f"materials' market stats (verified-independent / vendor-origin / unverifiable), "
                f"carry the tags where those stats are used, and treat presentation gaps in the "
                f"materials (an unstated ask, a missing traction slide, an incomplete competitor "
                f"set) as REPOSITIONING material for Section 0.5 — fixes to the fundraise ARTIFACT "
                f"are among the cheapest, fastest moves a founder can make.\n"
                f"\n\n{s12_note}\n"
                f"\n\nAdditionally, render `## 0.5 Strategic Repositioning — What to Change, What to "
                f"Keep` IMMEDIATELY after Section 0 and BEFORE Section 1, per the SECTION 0.5 SPEC "
                f"below. {anchor}Treat both analysts' 0.5 proposals as RAW MATERIAL (they may "
                f"conflict): keep only moves whose evidence survives the paste test, merge "
                f"duplicates, and where they genuinely conflict keep the better-evidenced move AND "
                f"SAY WHY — synthesize down to 2-4 moves plus exactly ONE 'What NOT to change' (the "
                f"wedge {focal}'s verdict rests on). Directional claims only in 0.5 — no new "
                f"scores or weighted totals; if you cite a score, use the system-supplied figure "
                f"VERBATIM.\n"
                f"{_focal_materials_digest(state, cap=10000)}"
                f"{FOUNDER_REPOSITIONING_SECTION.format(focal=focal)}"
            )
        else:
            # VC-focal mode: a specific DEAL is on the table. Re-center §0/§12's verdict devices
            # on the focal (INVEST/WATCH/PASS on {focal} at a price), with the field leader as the
            # opportunity-cost benchmark — rather than headlining the field's best asset with the
            # deal as a footnote. Field position + weak spots are computed in code (same rule as
            # the founder anchors) so §0/§7/§12 can't contradict the scorecard.
            field_pos = _focal_field_position(resolved_scores, weighted_scores, ranking,
                                              moat_subscores, focal, recommended)
            weak_ref = _focal_weak_spots(resolved_scores, moat_subscores, focal) \
                or "the focal's weakest scored dimensions"
            pos_note = (f" SYSTEM-COMPUTED field position (authoritative — state verbatim in "
                        f"Sections 0 and 7): {field_pos}" if field_pos else "")
            focal_note = (
                f"\n\n=== VC-FOCAL MODE — THESE INSTRUCTIONS OVERRIDE YOUR FRAMEWORK ===\n"
                f"The user REQUIRES **{focal}** in this analysis: it MUST appear in the Section 6 "
                f"ledger, the Section 7 scorecard + ranking, the Section 8 profiles, and the Section 13 "
                f"map — alongside the discovered competitors.{conf} {focal} is the DEAL UNDER "
                f"EVALUATION: the reader is deciding INVEST / WATCH / PASS on {focal} specifically, "
                f"with the field as context. Where these instructions conflict with the system "
                f"template's Section 0 / Section 12 (which headline the field's best pick), THIS "
                f"message wins.\n"
                f"\nSECTION 0 renders TWO labeled lines: (1) **Field take:** one sentence on the "
                f"field's best asset (the top pick), as context; (2) **Deal verdict: {focal}** — "
                f"INVEST / WATCH / PASS at/below a stated valuation, price-conditional and anchored to "
                f"{focal}'s last-round post-money from the Section 6 ledger — tag '(assumed; no formal "
                f"ask)' when the post is undisclosed.{pos_note}\n"
                f"\nSECTION 12's PRICE-CONDITIONAL VERDICT, CONDITIONS PRECEDENT, and WHY NOT PASS — "
                f"AND WHY NOT MORE devices apply to {focal} (the DEAL), NOT the field leader. The "
                f"field leader appears as the structural COMPARABLE / opportunity-cost benchmark "
                f"('the alternative use of this check'), stating {focal}'s parity / discount / premium "
                f"vs its marks. When the recommended field pick is NOT {focal}, Section 12 MUST carry "
                f"the explicit quality-rank-vs-price bridge: why {focal} is (or is not) the better "
                f"INVESTMENT than the higher-ranked name on price-adjusted return, not just quality "
                f"score.\n"
                f"\nDEAL PATH: when the verdict on {focal} is WATCH or PASS, Section 12 MUST close "
                f"with **Deal Path for {focal} — what would change our answer**: 3-5 conditions, each "
                f"a MEASURABLE metric with a DEADLINE and how we verify it, each tied to a named "
                f"Section 11 risk or a system-computed weak dimension ({weak_ref}); PLUS the valuation "
                f"band at/below which today's evidence WOULD clear ('re-engage at/below $X'); PLUS the "
                f"single tripwire that converts WATCH to PASS permanently."
            )

    # Market-overview mode (VC, no focal startup): the reader is deciding WHERE to hunt, not
    # whether to close a deal. The shared template's §0/§12 are deal-verdict machinery (name a
    # pick, price it, condition its closing); with no deal on the table that reads as a deal
    # teaser, not a sector call. This note repoints §0/§12 to SECTOR-level devices. Same
    # override mechanism founder mode uses. Gated purely on no-focal (mode is 'vc' by default).
    overview_note = ""
    if not focal:
        # #1-vs-#3 weighted-index gap, computed in code (a concentration signal for the
        # basket-vs-concentrate dialectic) — never asked of the LLM.
        _gap_note = ""
        if ranking and len(ranking) >= 3:
            _s1 = (weighted_scores.get(ranking[0]) or {}).get("weighted_score")
            _s3 = (weighted_scores.get(ranking[2]) or {}).get("weighted_score")
            if isinstance(_s1, (int, float)) and isinstance(_s3, (int, float)):
                _gap_note = (
                    f" SYSTEM-COMPUTED: the weighted-index gap between #1 ({ranking[0]}) and #3 "
                    f"({ranking[2]}) is {round(_s1 - _s3, 1)} points — cite this verbatim when "
                    f"resolving concentrate-vs-basket (a tight gap argues for a basket)."
                )
        overview_note = (
            "\n\n=== MARKET-OVERVIEW MODE — THESE INSTRUCTIONS OVERRIDE YOUR FRAMEWORK ===\n"
            "No focal startup is attached: the reader is a partner deciding WHERE to hunt, not "
            "whether to close a specific deal. For THIS run the Section 0 and Section 12 "
            "instructions below REPLACE the deal-verdict instructions in your system template "
            "AND in COMPILATION INSTRUCTIONS 0 and 2 (lead with the top pick + recommendation at "
            "a price; use that figure in Sections 0 and 12) — where they conflict, THIS message "
            "wins.\n"
            "\nSECTION 0 IS A SECTOR CALL, NOT A DEAL TEASER. Its FIRST sentence is the sector "
            "verdict: **ENTER / WATCH / AVOID**, naming the specific SUB-SEGMENT (located on the "
            "Section 5 axes) and the STAGE BAND where the white space is investable, plus ONE "
            "entry-discipline clause (the Val/ARR band above which the fund does not engage, "
            "anchored to the Section 6 ledger multiples). Restate the BINARY VARIABLE at SECTOR "
            "level ('if X is not true, we do not build a position in this sector'). The top pick "
            "is demoted to ONE sentence naming the 'best current asset in the field' — its full "
            "underwrite lives in Section 12, and NO single company's return multiple appears in "
            "Section 0.\n"
            "\nSECTION 12 REPOINTS ITS DEAL DEVICES TO SECTOR-ENTRY DEVICES:\n"
            "(a) CATEGORY PRICING DISCIPLINE (replaces the price-conditional verdict): per stage "
            "band, the Val/ARR range at which this sector clears the bar vs where the same team "
            "should pass, from the Section 6 ledger dispersion + the stage benchmarks, naming "
            "WHICH Section 11 risks justify the discount — then applied to the best asset as ONE "
            "worked example (tag any assumed terms '(assumed; no formal ask)').\n"
            "(b) ENTRY TRIGGERS (replace conditions precedent): 3-5 measurable, dated, verifiable "
            "events that would flip a WATCH sector to ENTER (or that the first meeting with the "
            "leading asset must verify) — REQUIRED whenever the sector verdict is WATCH.\n"
            "(c) SECTOR/BASKET DIALECTIC (replaces why-not-pass / why-not-more): 'why not skip "
            "this sector entirely' (grant the bear case, tag each PRICED / CONDITIONED / "
            "CUTS-BOTH-WAYS) and 'why not go wider' — a basket of 2-3 checks across different "
            "Section 5 cells vs a preemptive move on the leading asset priced against its "
            "Section 6 marks, resolved on the computed evidence." + _gap_note + " Close on the "
            "ONE question that decides sector-entry posture.\n"
            "\nSECTION 8: every NON-pick startup profile ENDS with one bolded '**Watch trigger:**' "
            "line — a single observable, dated-where-possible event (metric threshold, priced "
            "round, a named incumbent shipping/not-shipping by a quarter, design-partner count) "
            "that graduates the name to take-the-meeting; a genuinely-not-ripe name gets 'no "
            "trigger within 12 months — revisit at next raise.' Every pre-PMF watchlist entry "
            "gets a '**Re-engage when:**' line in the same format."
        )

    weighting_note = (
        ""
        if ranking
        else "\n\n**NOTE:** the weighted index could not be computed for this run. In "
        "Section 7, state plainly that the Weighted Underwriting Index is unavailable and "
        "present the qualitative ranking from the analyst reports — do NOT fabricate numbers."
    )

    # Cap table (user-uploaded, parsed in code): the authoritative funding history for
    # the focal — grounds its §6 ledger row and any §12 entry-price statement.
    cap_note = ""
    if _cap and (focal or _cap.get("rounds")):
        _who = focal or "the focal startup"
        _rounds = _cap.get("rounds") or []
        _rtxt = "; ".join(
            f"{r.get('round')}"
            + (f" ({r['date']})" if r.get("date") else "")
            + (f" raised ${r['raised_musd']:g}M" if r.get("raised_musd") is not None else "")
            + (f" at ${r['post_money_musd']:g}M post" if r.get("post_money_musd") is not None else "")
            for r in _rounds
        )
        cap_note = (
            f"\n\nCAP TABLE (user-uploaded round history, parsed in code — the PRIMARY SOURCE for "
            f"{_who}'s funding terms): {_rtxt or 'no parseable rounds'}."
            + (f" Total raised ${_cap['total_raised_musd']:g}M." if _cap.get("total_raised_musd") is not None else "")
            + (f" Latest post-money ${_cap['latest_post_money_musd']:g}M ({_cap.get('latest_round') or 'latest round'})."
               if _cap.get("latest_post_money_musd") is not None else "")
            + f" Ground {_who}'s Section 6 ledger row (total raised, valuation) and any Section 12 "
            f"entry-price statement on THESE figures, tagged '(per cap table)' — they override "
            f"conflicting web figures for {_who}. Never extend them to other companies."
        )

    # Founder-call claim audit: cross-examine the call claims against the research brief
    # + the deck (one structured LLM call, verdicts validated in code) BEFORE compiling,
    # so the compiler can cite the verdicts rather than re-litigate them.
    call_audit = None
    _claims = state.get("call_claims") or []
    if _claims:
        call_audit = _audit_call_claims(
            [c for c in _claims if isinstance(c, dict)],
            state.get("research_data", ""), state.get("focal_materials", ""), focal, settings)
    claims_note = ""
    if call_audit:
        _crows = "\n".join(
            f"  - [{c['status'].upper()}] {c['claim']}"
            + (f" (said at {c['timestamp']})" if c.get("timestamp") else "")
            + (f" — {c['evidence']}" if c.get("evidence") else "")
            + (f" — DECK CONFLICT: {c['deck_conflict']}" if c.get("deck_conflict") else "")
            for c in call_audit["claims"]
        )
        _cc = call_audit["counts"]
        claims_note = (
            f"\n\nFOUNDER-CALL CLAIM AUDIT (system-validated: the founder's spoken claims from an "
            f"uploaded call, cross-examined against the public record and the deck — "
            f"{_cc.get('verified', 0)} verified, {_cc.get('contradicted', 0)} contradicted, "
            f"{_cc.get('vendor-only', 0)} vendor-only, {_cc.get('unsupported', 0)} unsupported, "
            f"{_cc.get('deck_conflicts', 0)} deck-conflicts):\n{_crows}\n"
            f"Use these verdicts VERBATIM — do NOT re-grade, soften, or omit them. Weave the "
            f"CONTRADICTED and DECK-CONFLICT findings into Section 9's founder credibility read "
            f"(each is among the highest-signal facts this report holds), and when one is material "
            f"to the thesis, into a Section 11 risk. Wherever a figure rests only on a call claim, "
            f"tag it '(founder-call claim — {{status}})'. Verified claims may be cited as "
            f"independently confirmed."
        )

    user_message = (
        f"{_today_note('compiler')}"
        f"## Analyst A Report\n\n{analyst_a}\n\n"
        f"---\n\n## Analyst B Report\n\n{analyst_b}\n\n"
        f"---\n\n## AUTHORITATIVE scores (system-reconciled from BOTH analysts; use these "
        f"EXACT numbers and ranking in Section 7 — do NOT recompute or invent your own)\n\n"
        f"Applied (normalized) weights:\n```json\n{json.dumps(applied, indent=2)}\n```\n\n"
        f"Resolved RAW per-dimension scores:\n```json\n{json.dumps(resolved_scores, indent=2)}\n```\n\n"
        f"Defensibility moat sub-scores (Section 7 must SHOW these; Defensibility above already "
        f"equals their mean — do NOT print a different Defensibility):\n```json\n"
        f"{json.dumps(moat_subscores, indent=2)}\n```\n\n"
        f"Weighted scores per startup:\n```json\n{json.dumps(weighted_scores, indent=2)}\n```\n\n"
        f"Final ranking (best to worst): {', '.join(ranking) if ranking else '[none computed]'}\n\n"
        + (f"PRE-PMF / watchlist (profile in Section 8 ONLY — NOT in the scorecard or ranking): "
           f"{', '.join(pre_pmf)}\n\n" if pre_pmf else "")
        + f"---\n\n"
        f"Write the COMPLETE final merged report covering EVERY section of the framework, "
        f"with full multi-paragraph depth. Include the stage-banded Financial Ledger (point "
        f"estimates, NOT ranges), the Weighted Underwriting Scorecard (using the authoritative "
        f"scores + ranking above), detailed startup profiles, Team & Founder assessment, Risk "
        f"Factors with mitigants and 'what would make us wrong' triggers, Return Math & exit "
        f"pathways, regulatory mapping, and the ASCII coordinate market map. End with a Works "
        f"Cited section with numbered references and source URLs — take the URLs from the "
        f"analysts' citations and the Source Index; NEVER invent or reconstruct a URL. "
        f"Close Section 0 with the line: *Research data as of "
        f"{datetime.now().strftime('%Y-%m-%d')}.*"
        f"{weighting_note}"
        f"{return_note}"
        f"{tape_note}"
        f"{bridge_note}"
        f"{cap_note}"
        f"{claims_note}"
        f"{focal_note}"
        f"{overview_note}"
        f"{fund_note}"
    )

    compile_ok = False
    try:
        llm = _make_llm(settings.compiler_model, temperature=0.15, max_tokens=65536)
        result = _invoke_llm_with_retry(llm, [
            ("system", COMPILE_SYSTEM_PROMPT),
            ("user", user_message),
        ])
        merged_report = _normalize_content(result.content)
        merged_report = _sanitize_citations(merged_report)
        try:
            # Deterministic product-claim lint (accounts × ACV = SAM etc.) + bounded repair —
            # generation-time arithmetic self-verification is unreliable in-model; this is
            # the code backstop behind the prompt-level ARITHMETIC SELF-CHECK.
            merged_report = _repair_arithmetic(merged_report, settings)
        except Exception as e:  # noqa: BLE001 - lint/repair must never kill a compile
            logger.error("Arithmetic lint/repair pass failed: %s", e)
        compile_ok = True
        logger.info("▶ Compiled merged report (%d chars)", len(merged_report))
    except Exception as e:
        logger.error("Failed to compile merged report via LLM: %s", e)
        merged_report = (
            f"# VC Market Analysis Report\n\n"
            f"*Automated compilation failed. Showing the analyst reports below.*\n\n"
            f"## Analyst A Report\n\n{analyst_a}\n\n"
            f"## Analyst B Report\n\n{analyst_b}"
        )

    if compile_ok:
        market_map, financial_ledger, acquisitions = _extract_structured_artifacts(
            merged_report, weighted_scores, settings, canonical=ranking, incumbents=incumbents
        )
    else:
        market_map, financial_ledger, acquisitions = None, None, None

    # Cap-table grounding of the focal's ledger row (in code): fill ONLY missing cells —
    # never overwrite a figure the report itself disclosed.
    if isinstance(financial_ledger, dict) and _cap and focal:
        _fk2 = _norm_name(focal)
        for _row in financial_ledger.get("rows", []) or []:
            if not isinstance(_row, dict):
                continue
            _rk2 = _norm_name(_row.get("startup"))
            if not (_rk2 == _fk2 or (_fk2 and (_fk2 in _rk2 or _rk2 in _fk2))):
                continue
            if _parse_money(_row.get("total_raised")) is None and _cap.get("total_raised_musd") is not None:
                _row["total_raised"] = _musd_str(_cap["total_raised_musd"])
            if _parse_money(_row.get("valuation")) is None and _cap.get("latest_post_money_musd") is not None:
                _row["valuation"] = _musd_str(_cap["latest_post_money_musd"])
            break

    # Freshness is computed BEFORE the telemetry sections are appended — the methodology
    # block quotes dates and must not feed back into its own freshness audit.
    data_freshness = _data_freshness(merged_report)
    methodology_md = _methodology_section(state, settings, data_freshness, financial_ledger)
    # Deterministic telemetry + liability boundary on BOTH paths — never left to LLM compliance.
    merged_report += methodology_md + REPORT_DISCLAIMER

    # Deterministic field stats for the UI hero cards (ledger-derived, no LLM).
    field_stats = None
    if isinstance(financial_ledger, dict):
        _frows = [r for r in financial_ledger.get("rows", []) or []
                  if isinstance(r, dict) and not r.get("is_incumbent")]
        if _frows:
            _raised = [m for r in _frows if (m := _parse_money(r.get("total_raised"))) is not None]
            field_stats = {
                "startups": len(_frows),
                "incumbents": len(incumbents),
                "total_raised_musd": round(sum(_raised)) if _raised else None,
                "arr_disclosed": sum(1 for r in _frows if _parse_money(r.get("arr")) is not None),
            }

    final_report = {
        "merged_report": merged_report,
        "research_data": state.get("research_data", ""),
        "research_manifest": state.get("research_manifest"),
        "data_freshness": data_freshness,
        "methodology": methodology_md,
        "analyst_a_report": analyst_a,
        "analyst_b_report": analyst_b,
        "resolved_scores": resolved_scores,
        "weighted_scores": weighted_scores,
        "ranking": ranking,
        "applied_weights": applied,
        "weighting_unavailable": weighting_unavailable,
        "incumbents": incumbents,
        "pre_pmf": pre_pmf,
        "moat_subscores": moat_subscores,
        "scenarios": scenarios,
        "expected_return": expected_return,
        "expected_return_low": er_low,
        "expected_return_high": er_high,
        # Net-of-dilution bounds (gross × stage-banded ownership retention) + the coded
        # dominance readout — the memo-grade return math, computed, never asserted (R6').
        "expected_return_net_low": er_net_low,
        "expected_return_net_high": er_net_high,
        "return_assumptions": {
            "retention": retention,
            "note": "net = gross scenario multiples × stage-banded ownership retention to exit",
        },
        "return_dominance": ({"label": dominance[0], "share_pct": dominance[1]} if dominance else None),
        # The §0/§12 recommendation — the UI's "Top pick" badge uses THIS, so the header
        # can never contradict the report's own pick (R11). Canonicalized against the
        # ranked universe (an incumbent/variant name from the resolve LLM must never
        # become the headline); founder mode's pick is the SUBJECT, not the field leader.
        "recommended_pick": recommended,
        "acquisitions": acquisitions,
        "field_stats": field_stats,
        # Fund-math engine output (None unless fund_size provided). Reconciles by construction
        # with expected_return_net_* (same retention haircut, monetized through ownership).
        "fund_math": fund_math,
        # Uploaded round-history CSV, parsed in code (grounds the fund-math entry post +
        # the focal's ledger row). None when no cap table was uploaded.
        "cap_table": (_cap or None),
        # Founder-call claim audit: spoken claims cross-examined against the public record
        # + the deck, verdicts validated in code. None when no call transcript was uploaded.
        "call_claims_audit": call_audit,
        "analysis_mode": mode,
        "focal_startup": focal,
        "focal_confidence": focal_confidence,
        # The focal deal's rank in the field (VC-focal mode), computed in code by norm-name
        # containment — lets the UI/History headline answer "how did MY deal place?" without
        # masquerading as the field pick (which stays recommended_pick). None when no focal /
        # focal absent from the ranking.
        "focal_rank": (
            next((i + 1 for i, n in enumerate(ranking)
                  if focal and (_norm_name(n) == _norm_name(focal)
                                or _norm_name(focal) in _norm_name(n)
                                or _norm_name(n) in _norm_name(focal))), None)
            if focal and ranking else None
        ),
        "sector": state.get("sector", ""),
        "scope_autoderived": bool(state.get("scope_autoderived", False)),
        "market_map": market_map,
        "financial_ledger": financial_ledger,
        "gradesheet": _compute_gradesheet(
            resolved_scores, moat_subscores, weighted_scores, financial_ledger, ranking, focal),
        # Per-startup score confidence from ledger disclosure (in code) — the UI bands
        # or de-precisions scores for low-disclosure startups instead of showing 71.9.
        "score_confidence": _ledger_confidence(financial_ledger, canonical=ranking),
        "iterations_to_consensus": state.get("iterations", 0),
        "thesis_bias": state.get("thesis_bias", "Base"),
        "status": "completed",
    }

    log = (
        f"[Compiler] Report compiled ({len(merged_report)} chars) · "
        f"scores={'ok' if ranking else 'none'} · map={'ok' if market_map else 'none'} · "
        f"ledger={'ok' if financial_ledger else 'none'} · "
        f"E[return]={f'{expected_return}x' if expected_return is not None else 'n/a'} · "
        f"incumbents={len(incumbents)}"
    )
    return {"final_report": final_report, "agent_logs": [log]}
