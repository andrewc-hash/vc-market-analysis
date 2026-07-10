"""Shared LangGraph state definition for the 3-Phase Consensus Pipeline."""

from __future__ import annotations

from typing import Annotated, TypedDict


def add(existing: list, new: list) -> list:
    """Reducer that merges lists by concatenation (parallel-safe)."""
    return existing + new


class DimensionWeightsDict(TypedDict, total=False):
    financial_health: int
    defensibility: int
    market_urgency: int
    founder_market_fit: int
    regulatory_alignment: int


class ResearchState(TypedDict, total=False):
    """Shared mutable state flowing through every node in the graph."""

    # --- User-defined configuration packet ---
    market_prompt: str
    sector: str
    stage: str
    geography: str
    thesis_bias: str  # "Bear" | "Base" | "Bull"
    dimension_weights: DimensionWeightsDict

    # --- Focal startup (optional; force-included in the analysis) ---
    analysis_mode: str  # "vc" (focal ranked in field) | "founder" (focal is the subject)
    focal_startup: str
    focal_upload_id: str
    focal_materials: str  # text extracted from uploaded files by the ingest node
    focal_confidence: str  # "low" | "medium" | "high" — data confidence on the focal startup
    scope_autoderived: bool  # True if sector/market_prompt were auto-derived from the focal startup

    # --- Fund economics (optional; powers the deterministic fund-math engine) ---
    fund_economics: dict  # {fund_size_musd, check_size_musd, entry_post_money_musd, ...} or absent

    # --- Call-transcript claim audit (optional; from uploaded recordings/transcripts) ---
    call_claims: list  # [{claim, quote, timestamp, category}] extracted by the ingest node

    # --- Cap table (optional; parsed from an uploaded round-history CSV) ---
    cap_table: dict  # {rounds, total_raised_musd, latest_post_money_musd, ...} or absent

    # --- Longitudinal re-run (optional; set by POST /api/reports/{id}/rerun) ---
    baseline_report_id: str  # History id of the run this one re-executes and diffs against

    # --- Researcher output (shared data for both analysts) ---
    research_data: str
    research_manifest: dict  # tool-call audit built from the ReAct transcript (protocol compliance)

    # --- Agent outputs (populated during execution) ---
    agent_a_report: str
    agent_b_report: str

    # --- Judge outputs ---
    judge_critique: str
    judge_agreed: bool

    # --- Iteration tracking ---
    iterations: int

    # --- Final consolidated report ---
    final_report: dict

    # --- Streaming logs (parallel-safe via add reducer) ---
    agent_logs: Annotated[list[str], add]
