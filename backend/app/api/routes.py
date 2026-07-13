"""FastAPI route definitions for the research pipeline API.

Auth: pilot-grade API keys (services/auth.py). With `API_KEYS` unset, every dependency
resolves to owner=None and behavior is identical to the pre-auth app (local dev).
With keys configured, all /api endpoints require `X-API-Key` (except GET /api/config,
which the UI needs before it has a key) and History is filtered per owner.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.config import get_settings
from app.models.schemas import (
    ReportMetaUpdate,
    ReportSummary,
    ResearchRequest,
    ScopeRequest,
    ScopeResponse,
    TaskCreatedResponse,
    TaskStatusResponse,
    UploadResponse,
)
from app.services.auth import resolve_owner
from app.services.clerk_auth import clerk_enabled, verify_clerk_token
from app.worker.tasks import run_research_pipeline
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["research"])

# File types the ingest service can parse (mirror app.services.ingest):
# documents/images + call transcripts (.vtt/.srt), meeting recordings (audio →
# whisper transcription; the OpenAI API caps audio files at ~25MB), and a
# round-history .csv (cap table → grounded fund math).
_ALLOWED_EXTS = {
    ".pdf", ".docx", ".txt", ".md", ".markdown",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
    ".vtt", ".srt", ".mp3", ".m4a", ".wav", ".webm",
    ".csv",
}
_MAX_FILES = 12
_READ_CHUNK = 1024 * 1024  # stream uploads in 1MB chunks so the cap aborts early
_AGGREGATE_FILES_FACTOR = 4  # per-request total cap = max_upload_mb * this


def require_owner(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> str | None:
    """None = auth disabled (single-operator mode); str = authenticated owner; 401 otherwise.

    Hosted multi-user mode (Clerk) takes precedence when configured: a valid
    `Authorization: Bearer <jwt>` is REQUIRED and its verified subject is the owner.
    Otherwise the static X-API-Key pilot auth applies (empty api_keys = disabled).
    """
    settings = get_settings()
    if clerk_enabled(settings):
        token = ""
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        try:
            return verify_clerk_token(token, settings)
        except PermissionError:
            raise HTTPException(status_code=401, detail="Invalid or missing bearer token (Authorization header).")
    try:
        return resolve_owner(settings.api_keys, x_api_key)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Invalid or missing API key (X-API-Key header).")


def _safe_filename(name: str) -> str:
    """Strip path components and unsafe chars so an upload can't escape its dir.
    Self-contained: '.'/'..' are rewritten even though the extension gate would
    also reject them — safety must not depend on the caller's other checks."""
    base = os.path.basename(name or "").strip().replace("\x00", "")
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if base in {"", ".", ".."}:
        base = "file"
    return base[:120]


@router.get("/config")
async def get_public_config():
    """Deployment flags the UI needs BEFORE authenticating. No sensitive data."""
    settings = get_settings()
    return {
        "auth_required": bool(settings.api_keys.strip()),
        "uploads_enabled": bool(settings.uploads_enabled),
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_focal_materials(
    files: list[UploadFile] = File(...),
    owner: str | None = Depends(require_owner),
):
    """Store uploaded focal-startup files on the shared volume; return an upload_id.

    Streaming size enforcement: each file is written in bounded chunks with a running
    per-file AND per-request total, so an oversized body is aborted early instead of
    being read fully into memory. Any rejection cleans up the whole upload dir.
    """
    settings = get_settings()
    if not settings.uploads_enabled:
        raise HTTPException(
            status_code=403,
            detail="Uploads are disabled on this deployment (public-data mode). "
            "Run the analysis from a market prompt / startup name instead.",
        )
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > _MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files (max {_MAX_FILES}).")

    # Validate every extension BEFORE writing anything (no orphaned partial uploads).
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in _ALLOWED_EXTS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or '(none)'}")

    upload_id = uuid.uuid4().hex
    dest = Path(settings.uploads_dir) / upload_id
    dest.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    max_total = max_bytes * _AGGREGATE_FILES_FACTOR

    saved: list[str] = []
    total = 0
    try:
        for i, f in enumerate(files, 1):
            # Index prefix: guarantees unique stored names (two originals can sanitize to
            # the same string) and that no stored file starts with "_" (the ingest service
            # skips underscore-prefixed files and reserves _extracted.txt as its cache).
            out = dest / f"{i:02d}_{_safe_filename(f.filename or 'file')}"
            written = 0
            with out.open("wb") as fh:
                while chunk := await f.read(_READ_CHUNK):
                    written += len(chunk)
                    total += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(
                            status_code=400,
                            detail=f"{f.filename} exceeds {settings.max_upload_mb}MB.")
                    if total > max_total:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Upload exceeds the {max_total // (1024 * 1024)}MB request total.")
                    fh.write(chunk)
            saved.append(out.name)
    except BaseException:
        # ANY failure (cap 400s, disk-full OSError, client disconnect, cancellation)
        # must never leave partial confidential uploads behind.
        shutil.rmtree(dest, ignore_errors=True)
        raise

    logger.info("Stored %d focal file(s) under upload_id=%s", len(saved), upload_id)
    return UploadResponse(upload_id=upload_id, files=saved)


@router.post("/derive-scope", response_model=ScopeResponse)
async def derive_scope_endpoint(request: ScopeRequest, owner: str | None = Depends(require_owner)):
    """Infer the sector + market-analysis prompt from a focal startup (confirm-first UX).

    Fast, interactive step run BEFORE the heavy pipeline: from uploaded materials if present,
    otherwise grounded with a couple of web searches on the startup name. The UI shows the
    result for the user to review/edit before launching the full analysis.
    """
    from app.services.scope import infer_scope
    try:
        res = infer_scope(request.focal_startup, request.focal_upload_id)
    except Exception as exc:  # noqa: BLE001 - never 500 an interactive derive; degrade gracefully
        logger.warning("Scope derivation failed: %s", exc)
        res = {"market_prompt": "", "sector": "", "rationale": "", "autoderived": False, "source": "none"}
    return ScopeResponse(**res)


@router.post("/research", response_model=TaskCreatedResponse, status_code=202)
async def create_research_task(request: ResearchRequest, owner: str | None = Depends(require_owner)):
    """Accept research parameters, enqueue the Celery task, return task_id.

    Stale-result hygiene is handled by Celery's `result_expires` TTL (celery_app.py) —
    the old wipe-all purge clobbered concurrent in-flight runs.
    """
    task = run_research_pipeline.delay(
        market_prompt=request.market_prompt,
        sector=request.sector,
        stage=request.stage.value,
        geography=request.geography.value,
        thesis_bias=request.thesis_bias.value,
        dimension_weights=request.dimension_weights.model_dump(),
        analysis_mode=request.analysis_mode.value,
        focal_startup=request.focal_startup,
        focal_upload_id=request.focal_upload_id,
        scope_autoderived=request.scope_autoderived,
        fund_economics=request.fund_economics.model_dump() if request.fund_economics else None,
        owner=owner or "",
    )
    return TaskCreatedResponse(task_id=task.id)


@router.get("/research/{task_id}", response_model=TaskStatusResponse)
async def get_research_status(task_id: str, owner: str | None = Depends(require_owner)):
    """Poll for the status and results of a research task."""
    try:
        result = celery_app.AsyncResult(task_id)
        status = result.status
    except Exception as exc:
        logger.warning("Failed to read task %s: %s", task_id, exc)
        return TaskStatusResponse(
            task_id=task_id,
            status="FAILURE",
            error=f"Task state is corrupted or unreadable: {exc}",
        )

    response = TaskStatusResponse(
        task_id=task_id,
        status=status,
    )

    def _owned(data: dict) -> bool:
        """Per-owner visibility on task state (mirrors store._visible_to): auth
        disabled or legacy/ownerless tasks are visible; otherwise owners must match.
        Without this, any valid key could read any tenant's full report for the
        3-day result-TTL window via a leaked task_id."""
        if owner is None:
            return True
        task_owner = str((data or {}).get("owner") or "")
        return task_owner == "" or task_owner == owner

    try:
        if status == "STARTED" and result.info:
            meta = result.info
            if not _owned(meta):
                raise HTTPException(status_code=404, detail="Task not found")
            response.current_phase = meta.get("current_phase")
            response.iterations_completed = meta.get("iterations_completed", 0)
            response.agent_logs = meta.get("agent_logs", [])

        elif status == "SUCCESS" and result.result:
            data = result.result
            if not _owned(data):
                raise HTTPException(status_code=404, detail="Task not found")
            response.final_report = data.get("final_report")
            response.agent_logs = data.get("agent_logs", [])
            response.iterations_completed = data.get("iterations_completed", 0)

        elif status == "FAILURE":
            response.error = str(result.info) if result.info else "Unknown error"
    except HTTPException:
        raise  # owner-visibility 404 must not be swallowed into a FAILURE payload
    except Exception as exc:
        logger.warning("Failed to read task result %s: %s", task_id, exc)
        response.status = "FAILURE"
        response.error = f"Failed to read task result: {exc}"

    return response


# ------------------------------------------------------------------ #
#  Analysis history (durable report store)
# ------------------------------------------------------------------ #

@router.get("/reports", response_model=list[ReportSummary])
async def list_reports_endpoint(owner: str | None = Depends(require_owner)):
    """List saved analyses visible to this owner (light meta), starred then newest first."""
    from app.services.store import list_reports
    return list_reports(owner=owner)


@router.get("/reports/{report_id}")
async def get_report_endpoint(report_id: str, owner: str | None = Depends(require_owner)):
    """Return one saved analysis in full (including final_report) to render in the UI."""
    from app.services.store import get_report
    rec = get_report(report_id, owner=owner)
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    return rec


def _can_mutate(rec: dict | None, owner: str | None) -> bool:
    """Mutation is stricter than visibility: legacy (ownerless) records are READABLE by
    every authed user but only mutable in single-operator mode — otherwise any pilot
    key could rename/delete the operator's entire pre-auth history."""
    if not rec:
        return False
    if owner is None:
        return True
    return str(rec.get("owner") or "") == owner


@router.patch("/reports/{report_id}", response_model=ReportSummary)
async def update_report_endpoint(
    report_id: str, update: ReportMetaUpdate, owner: str | None = Depends(require_owner)
):
    """Rename (label) and/or star a saved analysis (own reports only when auth is on)."""
    from app.services.store import get_report, update_meta
    rec = get_report(report_id, owner=owner)
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    if not _can_mutate(rec, owner):
        raise HTTPException(status_code=403, detail="Read-only: this report belongs to another owner.")
    meta = update_meta(report_id, label=update.label, starred=update.starred)
    if not meta:
        raise HTTPException(status_code=404, detail="Report not found")
    return meta


@router.post("/reports/{report_id}/rerun", response_model=TaskCreatedResponse, status_code=202)
async def rerun_report_endpoint(report_id: str, owner: str | None = Depends(require_owner)):
    """Re-execute a saved analysis on its ORIGINAL parameters, diffing against it.

    The new run re-researches the same market today; the worker then computes the
    run delta in code (ranking moves, valuation changes, EV shift) and grades the
    baseline report's own dated predictions against the fresh evidence.
    """
    from app.services.store import get_report
    rec = get_report(report_id, owner=owner)
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    params = rec.get("request_params") or {}
    if not str(params.get("market_prompt") or "").strip() and not str(params.get("focal_startup") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="This report predates re-run support (no stored request parameters).")
    task = run_research_pipeline.delay(
        market_prompt=str(params.get("market_prompt") or ""),
        sector=str(params.get("sector") or ""),
        stage=str(params.get("stage") or "All Stages"),
        geography=str(params.get("geography") or "Global"),
        thesis_bias=str(params.get("thesis_bias") or "Base"),
        dimension_weights=params.get("dimension_weights") or {},
        analysis_mode=str(params.get("analysis_mode") or "vc"),
        focal_startup=str(params.get("focal_startup") or ""),
        focal_upload_id=str(params.get("focal_upload_id") or ""),
        scope_autoderived=bool(params.get("scope_autoderived")),
        fund_economics=params.get("fund_economics"),
        owner=owner or "",
        baseline_report_id=rec.get("id") or report_id,
    )
    return TaskCreatedResponse(task_id=task.id, message="Re-run enqueued against baseline.")


@router.delete("/reports/{report_id}")
async def delete_report_endpoint(report_id: str, owner: str | None = Depends(require_owner)):
    """Delete a saved analysis (own reports only when auth is on)."""
    from app.services.store import delete_report, get_report
    rec = get_report(report_id, owner=owner)
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    if not _can_mutate(rec, owner):
        raise HTTPException(status_code=403, detail="Read-only: this report belongs to another owner.")
    if not delete_report(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": report_id}
