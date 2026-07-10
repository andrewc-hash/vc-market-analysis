from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Enums ---------- #

class ThesisBias(str, Enum):
    BEAR = "Bear"
    BASE = "Base"
    BULL = "Bull"


class InvestmentStage(str, Enum):
    PRE_SEED = "Pre-Seed"
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    GROWTH = "Growth"
    ALL = "All Stages"


class Geography(str, Enum):
    GLOBAL = "Global"
    US_ONLY = "US-Only"
    EU_ONLY = "EU-Only"
    ASIA_PACIFIC = "Asia-Pacific"
    ISRAEL = "Israel"


class AnalysisMode(str, Enum):
    # VC: the focal startup is force-included in the ranked field of competitors.
    # FOUNDER: the report is centered on the focal startup (subject), with the
    # market as backdrop and an explicit build/pass verdict.
    VC = "vc"
    FOUNDER = "founder"


# ---------- Request / Response ---------- #

class DimensionWeights(BaseModel):
    # Research-informed defaults: Defensibility outweighs Financial Health
    # (a16z: moats are the root driver; margins are downstream). Weights are
    # treated as RELATIVE and normalized in code, so they need not sum to 100.
    financial_health: int = Field(default=20, ge=1, le=100)
    defensibility: int = Field(default=30, ge=1, le=100)
    market_urgency: int = Field(default=20, ge=1, le=100)
    founder_market_fit: int = Field(default=15, ge=1, le=100)
    regulatory_alignment: int = Field(default=15, ge=1, le=100)


class FundEconomics(BaseModel):
    """Optional fund-profile inputs powering the deterministic fund-math engine
    ("does THIS deal return MY fund?"). All optional — absent fund_size suppresses
    the whole fund-math block and the existing gross/net MoIC ranges render unchanged.
    Amounts are in $M (millions USD); the math is unit-consistent in $M throughout."""
    fund_size_musd: Optional[float] = Field(default=None, gt=0, description="Total fund size ($M). MASTER GATE — absent = no fund-math.")
    check_size_musd: Optional[float] = Field(default=None, gt=0, description="This deal's check ($M).")
    entry_post_money_musd: Optional[float] = Field(default=None, gt=0, description="Entry post-money valuation ($M); inferred from stage if absent.")
    target_ownership_pct: Optional[float] = Field(default=None, gt=0, le=100, description="Target ownership %; only fills a missing check or post.")
    holding_years: Optional[float] = Field(default=None, gt=0, description="Years to exit (for IRR); stage-defaulted if absent.")
    fund_returner_fraction: Optional[float] = Field(default=None, gt=0, description="Bar for 'returns the fund' (turns of fund; default 1.0).")
    target_fund_multiple: Optional[float] = Field(default=None, ge=1, description="Bar for 'fund-maker' (turns of fund; default 3.0).")


class ResearchRequest(BaseModel):
    market_prompt: str = Field(
        default="",
        description="The sector / market prompt. Required UNLESS a focal_startup is provided "
        "(then it may be auto-derived from the startup).",
    )
    sector: str = Field(default="", description="Optional sector label.")
    stage: InvestmentStage = InvestmentStage.ALL
    geography: Geography = Geography.GLOBAL
    thesis_bias: ThesisBias = ThesisBias.BASE
    dimension_weights: DimensionWeights = Field(default_factory=DimensionWeights)

    # --- Focal startup (optional) ---
    analysis_mode: AnalysisMode = AnalysisMode.VC
    focal_startup: str = Field(
        default="",
        max_length=200,
        description="A specific startup to GUARANTEE in the analysis (the user's own, or a target).",
    )
    focal_upload_id: str = Field(
        default="",
        description="Id returned by POST /api/upload; its files become the focal startup's source material.",
    )
    scope_autoderived: bool = Field(
        default=False,
        description="True if market_prompt/sector were auto-derived from the focal startup (for the report header).",
    )

    # --- Fund economics (optional; powers the fund-math engine) ---
    fund_economics: Optional[FundEconomics] = Field(
        default=None,
        description="Optional fund-profile inputs. When fund_size is provided, the report gains "
        "the deterministic fund-math block ('does this return my fund?'); otherwise unchanged.",
    )

    @model_validator(mode="after")
    def _require_prompt_or_focal(self):
        # The market prompt is required for a plain sector run, but may be omitted when a
        # focal startup (by name OR uploaded materials) is attached — the pipeline / derive
        # endpoint fills it in from the startup.
        has_focal = bool((self.focal_startup or "").strip() or (self.focal_upload_id or "").strip())
        if len((self.market_prompt or "").strip()) < 10 and not has_focal:
            raise ValueError("market_prompt must be at least 10 chars unless a focal startup is provided")
        # Founder mode centers the report on a named startup — every founder-mode surface
        # (verdict framing, §0.5, judge note) gates on the name, so an unnamed founder run
        # would silently degrade to a plain sector report. Reject it instead.
        if self.analysis_mode == AnalysisMode.FOUNDER and not (self.focal_startup or "").strip():
            raise ValueError("founder mode requires the startup's name (focal_startup)")
        return self


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # PENDING | STARTED | SUCCESS | FAILURE
    current_phase: Optional[str] = None
    iterations_completed: int = 0
    agent_logs: list[str] = Field(default_factory=list)
    final_report: Optional[dict] = None
    error: Optional[str] = None


class TaskCreatedResponse(BaseModel):
    task_id: str
    message: str = "Research task enqueued."


class UploadResponse(BaseModel):
    upload_id: str
    files: list[str] = Field(default_factory=list)
    message: str = "Files uploaded."


class ScopeRequest(BaseModel):
    focal_startup: str = Field(default="", max_length=200)
    focal_upload_id: str = Field(default="")

    @model_validator(mode="after")
    def _need_something(self):
        if not (self.focal_startup or "").strip() and not (self.focal_upload_id or "").strip():
            raise ValueError("Provide focal_startup and/or focal_upload_id to derive scope.")
        return self


class ScopeResponse(BaseModel):
    market_prompt: str = ""
    sector: str = ""
    rationale: str = ""
    autoderived: bool = False
    source: Literal["materials", "search", "none"] = "none"


class ReportSummary(BaseModel):
    id: str
    created_at: str = ""
    sector: str = ""
    analysis_mode: str = "vc"
    focal_startup: str = ""
    top_pick: str = ""
    thesis_bias: str = ""
    label: str = ""
    starred: bool = False


class ReportMetaUpdate(BaseModel):
    label: Optional[str] = None
    starred: Optional[bool] = None
