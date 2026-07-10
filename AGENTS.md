# AGENTS.md

This repo's full engineering guide lives in **`CLAUDE.md`** (project root) — **read it first**; it is the source of truth for the architecture, the pipeline, conventions, and gotchas. Then skim:

- `ARCHITECTURE.md` — deep reference for the LangGraph consensus pipeline (researcher → 2 analysts → judge → compiler).
- `docs/KNOWN_ISSUES.md` — open bugs / tech debt, plus a "Fixed" trail.
- `docs/UI_PLAN.md` — the planned report + market-map + graphics UI.
- `docs/QUALITY_RUBRIC.md` — a scored rubric (out of 24) for grading the platform's output against top-fund quality.

## Quick orientation
A LangGraph multi-agent pipeline that turns one market prompt into an institutional-grade VC **sector analysis + scored market map**. Stack: FastAPI + Celery/Redis backend (`backend/app/`), Next.js frontend (`frontend/src/`). The real IP is the prompts in `backend/app/graph/prompts.py` and the scoring/extraction code in `backend/app/graph/nodes.py`. Token-free unit tests are in `backend/tests/`.

## How to run / test
- Stack: `docker compose up -d --build` (redis :6379, backend :8000, frontend :3000).
- Backend tests (no API tokens): run all nine suites in `backend/tests/` — `test_focal.py`, `test_ingest.py`, `test_scope.py`, `test_structured_artifacts.py`, `test_filters_sliders.py`, `test_repositioning.py`, `test_freshness.py`, `test_gradesheet.py`, `test_trust.py` (each is a standalone `python3 backend/tests/<file>` script; see CLAUDE.md §7).
- The backend image bakes source (`COPY . .`, no live mount) — **rebuild to pick up code changes**.

## Conventions
- When the code and an older comment/doc disagree, the **code wins** (see `CLAUDE.md` §9).
- Scoring/weighting is computed **in code** (not by an LLM) — `nodes._extract_resolved_scores` + `_compute_weighted_scores`.
- Keep `CLAUDE.md`, `ARCHITECTURE.md`, and the `docs/*` files in sync with code changes.
