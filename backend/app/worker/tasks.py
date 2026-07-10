"""Celery tasks wrapping the LangGraph consensus pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.graph.pipeline import compile_pipeline
from app.graph.state import ResearchState

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_research_pipeline")
def run_research_pipeline(
    self,
    market_prompt: str,
    sector: str,
    stage: str,
    geography: str,
    thesis_bias: str,
    dimension_weights: dict,
    analysis_mode: str = "vc",
    focal_startup: str = "",
    focal_upload_id: str = "",
    scope_autoderived: bool = False,
    fund_economics: dict | None = None,  # optional fund-profile inputs → fund-math engine
    owner: str = "",  # API-key owner (empty when auth is disabled) — tags the History record
    baseline_report_id: str = "",  # History id this run RE-EXECUTES (longitudinal diff + prediction grading)
) -> dict:
    """Execute the full 3-Phase Consensus Pipeline as a Celery task."""
    logger.info("Starting research pipeline for: %s", market_prompt[:80])

    # The exact inputs, persisted with the report so any run can be re-executed later
    # on identical parameters (the longitudinal re-run feature).
    request_params = {
        "market_prompt": market_prompt,
        "sector": sector,
        "stage": stage,
        "geography": geography,
        "thesis_bias": thesis_bias,
        "dimension_weights": dimension_weights,
        "analysis_mode": analysis_mode,
        "focal_startup": focal_startup,
        "focal_upload_id": focal_upload_id,
        "scope_autoderived": scope_autoderived,
        "fund_economics": fund_economics,
    }

    self.update_state(
        state="STARTED",
        meta={
            "current_phase": "initializing",
            "iterations_completed": 0,
            "agent_logs": [],
            "owner": owner,
        },
    )

    initial_state: ResearchState = {
        "market_prompt": market_prompt,
        "sector": sector,
        "stage": stage,
        "geography": geography,
        "thesis_bias": thesis_bias,
        "dimension_weights": dimension_weights,
        "analysis_mode": analysis_mode,
        "focal_startup": focal_startup,
        "focal_upload_id": focal_upload_id,
        "focal_materials": "",
        "focal_confidence": "",
        "scope_autoderived": scope_autoderived,
        "fund_economics": fund_economics or {},
        "agent_a_report": "",
        "agent_b_report": "",
        "judge_critique": "",
        "judge_agreed": False,
        "iterations": 0,
        "final_report": {},
        "agent_logs": [],
    }

    pipeline = compile_pipeline()

    try:
        # Track accumulated state from stream updates
        accumulated_logs: list[str] = []
        accumulated_iterations: int = 0
        accumulated_report: dict = {}

        for step_output in pipeline.stream(initial_state, stream_mode="updates"):
            for node_name, state_update in step_output.items():
                # Some nodes (e.g. fan-out) can emit None
                if state_update is None:
                    continue

                # Accumulate logs
                new_logs = state_update.get("agent_logs", [])
                if new_logs:
                    accumulated_logs.extend(new_logs)

                # Track iterations
                if "iterations" in state_update:
                    accumulated_iterations = state_update["iterations"]

                # Capture final report when it appears
                if "final_report" in state_update and state_update["final_report"]:
                    accumulated_report = state_update["final_report"]

                self.update_state(
                    state="STARTED",
                    meta={
                        "current_phase": node_name,
                        "iterations_completed": accumulated_iterations,
                        "agent_logs": accumulated_logs[-20:],
                        "owner": owner,
                    },
                )

        # Longitudinal re-run: diff against the baseline (pure code) + grade the
        # baseline's own dated predictions against the new evidence (one LLM call).
        # Both best-effort — a broken baseline can never fail the fresh run.
        if baseline_report_id and accumulated_report:
            try:
                from app.config import get_settings
                from app.services.delta import compute_run_delta, grade_predictions
                from app.services.store import get_report as load_baseline
                baseline = load_baseline(baseline_report_id) or {}
                baseline_fr = baseline.get("final_report") or {}
                if baseline_fr:
                    accumulated_report["baseline_id"] = baseline_report_id
                    accumulated_report["baseline_created_at"] = baseline.get("created_at") or ""
                    accumulated_report["run_delta"] = compute_run_delta(baseline_fr, accumulated_report)
                    accumulated_report["prediction_audit"] = grade_predictions(
                        baseline_fr, accumulated_report, get_settings())
                    self.update_state(state="STARTED", meta={
                        "current_phase": "compile_report",
                        "iterations_completed": accumulated_iterations,
                        "agent_logs": (accumulated_logs + ["[Delta] Compared against baseline run; predictions graded."])[-20:],
                        "owner": owner,
                    })
            except Exception as exc:  # noqa: BLE001 - the diff is best-effort
                logger.warning("Baseline delta/prediction grading failed: %s", exc)

        # Persist the finished report to the durable history store (best-effort).
        if accumulated_report:
            try:
                from app.services.store import save_report
                save_report(self.request.id, accumulated_report,
                            datetime.now(timezone.utc).isoformat(), owner=owner,
                            request_params=request_params)
            except Exception as exc:  # noqa: BLE001 - history is best-effort, never fail the run
                logger.warning("Failed to persist report to history: %s", exc)

        return {
            "status": "completed",
            "final_report": accumulated_report,
            "agent_logs": accumulated_logs,
            "iterations_completed": accumulated_iterations,
            "owner": owner,
        }

    except Exception:
        logger.exception("Pipeline failed")
        # Let Celery handle the failure state natively — do NOT call
        # self.update_state(state="FAILURE") with custom meta, as it
        # corrupts the result backend serialization.
        raise
