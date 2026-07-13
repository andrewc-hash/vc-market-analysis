# VC Market Analysis Engine — Project Guide

> **Read me first.** This file is auto-loaded into every Claude Code session that opens this repo. It is the single source of truth for *how this app actually works today*. When the code and a comment/old doc disagree, the code wins — see **§9 Stale references & traps** for the specific places older comments lie.

---

## 1. What this is

A **LangGraph multi-agent pipeline** that turns one free-text market prompt into an **institutional-grade, 13-section VC market-analysis report** (a "market map"). It orchestrates 5 LLM roles across 3 providers, has two independent analysts debate through a neutral judge until they reach consensus (max 3 rounds), then compiles everything into one long markdown document.

On top of the sector pipeline it also supports a **focal (target) startup** in two modes — **VC** (rank a named startup inside the discovered field) and **Founder** (center the whole report on your own startup with a build/pass verdict) — with **document upload** (deck/financials/idea → parsed, incl. vision for image decks), **auto-scope** (derive the sector + market prompt from the startup), a persistent **History** of past runs, a **Download** menu (PDF-with-visuals / Markdown / JSON), and a public backend-free **/demo**.

- **Backend:** FastAPI (HTTP) + Celery worker (runs the pipeline) + Redis (broker + result store).
- **Pipeline:** LangGraph `StateGraph` (in `backend/app/graph/`).
- **Frontend:** Next.js 14 (App Router, all client-side) that submits a request and polls for progress + the final report.
- **Deploy:** Docker Compose, 4 services + 2 named volumes (`uploads`, `reports`). Local/dev only — no auth, dev-mode servers.

The complexity is in the *prompts*, the *graph control flow*, and the *in-code scoring/coherence guarantees* — not the plumbing.

> **Project intent: this is a PORTFOLIO PIECE**, not a company being raised for. Priorities: the public `/demo` (done), a Vercel deployment (frontend is backend-free at `/demo`), and a case-study README. Don't optimize for moat/ICP/traction — optimize for a clickable live demo + a great writeup + demonstrable engineering judgment (multi-model consensus, determinism-in-code, the adversarial eval loop).

---

## 2. The pipeline (3-phase consensus)

```
START
  │
  ▼
INGEST_FOCAL (ingest_focal_materials — runs FIRST; pass-through when no focal startup)
  │  parses uploaded focal-startup files → focal_materials (PyMuPDF text + vision fallback,
  │  .docx, .txt/.md, images; cached to <uploaddir>/_extracted.txt).
  │  SELF-HEAL: if market_prompt is empty but a focal startup is set, derives sector +
  │  market_prompt via services.scope.infer_scope and writes them into state.
  ▼
RESEARCHER (gemini-2.5-pro, ReAct agent + 7 search tools: 6 Tavily + search_google_live)
  │  ≥20 search calls (phases sum ~30-38) incl. per-startup latest-news FRESHNESS pass
  │  (news topic, past 365 days, publication dates) + per-startup Google-grounded
  │  PRECISION CHECK (exact round/valuation/M&A status) + a Phase-4 consolidation
  │  sweep; date-grounded ("Today's date: …"); newest/grounded source wins conflicts.
  │  Identifies 6–8 startups, raw facts only (no scores)
  │  → research_data
  ▼
ANALYSTS_FANOUT (no-op pass-through; exists only to fan out, and is the loop-back target)
  ├──────────────────────────┬──────────────────────────┐
  ▼                          ▼                            
ANALYST A (gemini-2.5-pro)   ANALYST B (claude-sonnet-4-6)
  no tools, full-spectrum     no tools, full-spectrum
  → agent_a_report            → agent_b_report
  └──────────────┬───────────┘
                 ▼  (fan-in: judge waits for both)
JUDGE (gpt-4.1) — reads both reports, emits a JSON verdict
  │  iterations += 1
  ├─ agreed=true  OR  iterations ≥ 3  ─────────────►  COMPILER
  └─ agreed=false AND iterations < 3  ──(loop back)──►  ANALYSTS_FANOUT
                                                         (researcher does NOT re-run —
                                                          research_data is unchanged;
                                                          judge_critique is injected into
                                                          both analysts' next prompt)
COMPILER (gemini-2.5-pro, max_tokens=65536) — single-pass merge → merged_report
  │  scoring is reconciled IN CODE here (see §6): _extract_resolved_scores +
  │  _compute_weighted_scores + _compute_expected_return + structured-artifact validators.
  ▼
END  → the worker then persists the finished report to the History store (save-on-completion).
```

Graph wiring is in `pipeline.py`: `START → ingest_focal → researcher → analysts_fanout → [analyst_a, analyst_b] → judge → (loop to analysts_fanout OR compile_report) → END`.

**Key design decision (current):** Both analysts are **full-spectrum (quant + qual)** and run the *byte-for-byte identical* system prompt — they differ **only by the underlying model** (Gemini vs Claude). Disagreement comes from two different LLM platforms interpreting the same `research_data`. The old "Analyst A = Quantitative Challenger / Analyst B = Qualitative Auditor" split was **removed** — any comment/diagram still saying that is stale (see §9).

**The judge is NOT strictly neutral:** `get_judge_system_prompt(thesis_bias)` injects a persona based on the user's `thesis_bias`:
- `Bear` → hyper-skeptical red-team auditor
- `Base` → objective institutional partner (default)
- `Bull` → high-conviction optimist

It *is* on a neutral third platform (GPT-4.1) and outputs JSON, but it argues the user's chosen stance.

---

## 3. Model assignments

**Source of truth: `backend/app/config.py`** (env-overridable, but these are the defaults). Do not rely on any other file for model IDs.

| Role | Model ID | Provider | Tokens / temp | Tools? |
|------|----------|----------|---------------|--------|
| Researcher | `gemini-2.5-pro` | Google | 65536 / 0.2 | ✅ 7 tools (6 Tavily + Google-grounded live search) |
| Analyst A | `gemini-2.5-pro` | Google | 16384 / 0.2 | ❌ |
| Analyst B | `claude-sonnet-4-6` | Anthropic | 16384 / 0.2 | ❌ |
| Judge | `gpt-4.1` | OpenAI | 4096 / 0.1 | ❌ |
| Compiler | `gemini-2.5-pro` | Google | 65536 / 0.15 | ❌ |

`_make_llm(model, …)` in `nodes.py` routes by model-ID **prefix**: `gemini*`→`ChatGoogleGenerativeAI`, `claude*`→`ChatAnthropic`, `gpt*`/`o*`→`ChatOpenAI`, anything else → `ChatGroq` fallback (this is why `GROQ_API_KEY` is required even though no role defaults to Groq).

More LLM touchpoints not in the table: **vision ingest** of image / image-only PDF pages uses `settings.vision_model` (default `gemini-2.5-pro`, in `services/ingest.py`); **audio transcription** of uploaded meeting recordings uses OpenAI `whisper-1` (`_transcribe_audio` in `services/ingest.py`; ≤25MB per file — the OpenAI API cap); **scope inference** (`derive_scope`), **call-claim extraction/audit** (`_extract_call_claims`/`_audit_call_claims` in `nodes.py`), and **prediction grading** (`services/delta.py grade_predictions`) all use `settings.judge_model`.

> When working with the Anthropic/Claude side of this app, check the `claude-api` skill for current model IDs/pricing rather than assuming.

---

## 4. Repo layout

```
vc-market-analysis/
├── CLAUDE.md                    ← you are here (auto-loaded session guide)
├── ARCHITECTURE.md              ← deep pipeline reference (kept in sync with code)
├── docs/KNOWN_ISSUES.md         ← running bug / tech-debt tracker (R1–R14 trail)
├── docs/UI_PLAN.md              ← planned report+map+graphics UI (design only)
├── docs/QUALITY_RUBRIC.md       ← scored rubric for grading output vs. top-fund quality (/24)
├── AGENTS.md                    ← Codex entrypoint (points at this file + docs)
├── docker-compose.yml           ← 4 services + volumes: uploads, reports
├── scripts/                     ← report exporters (CLI): format_report.py (report JSON → clean MD
│                                   + appendix tables), report_to_html.py (MD → light print HTML;
│                                   + Chrome headless --print-to-pdf ⇒ PDF)
├── reports/                     ← exported/saved reports on the host (gitignore-worthy)
├── backend/
│   ├── Dockerfile               ← python:3.12-slim; image shared by backend + worker
│   ├── requirements.txt         ← + pymupdf, python-docx, python-multipart
│   ├── .env / .env.example      ← secrets (gitignored) / template
│   ├── tests/                   ← TOKEN-FREE unit tests (stub LLM deps in sys.modules):
│   │     test_focal.py (27) · test_ingest.py (8) · test_scope.py (16)
│   │     test_structured_artifacts.py (103) · test_filters_sliders.py (27) · test_fund_math.py (53)
│   │     test_repositioning.py (71) · test_freshness.py (65) · test_gradesheet.py (45) · test_trust.py (76)
│   │     test_captable.py (30) · test_call_claims.py (26) · test_delta.py (29) — 576 total; run from REPO ROOT
│   └── app/
│       ├── config.py            ← Settings: model IDs, keys, Redis URLs, uploads_dir, reports_dir, vision_model, max_upload_mb
│       ├── main.py              ← FastAPI factory; CORS→localhost:3000; GET /health
│       ├── api/routes.py        ← research + upload + derive-scope + reports (History) endpoints
│       ├── models/schemas.py    ← Pydantic requests/responses + enums (AnalysisMode, Scope*, Report*)
│       ├── services/            ← ingest.py (doc parsing + vision), scope.py (auto-scope), store.py (History store)
│       ├── worker/
│       │   ├── celery_app.py    ← Celery app; time limits 5400/6000s
│       │   └── tasks.py         ← run_research_pipeline: streams the graph, pushes progress, save-on-completion
│       └── graph/
│           ├── state.py         ← ResearchState TypedDict (+ focal/scope fields) + `add` reducer
│           ├── pipeline.py      ← build_research_graph / compile_pipeline (+ ingest_focal first) + _should_loop
│           ├── nodes.py         ← all node fns + ingest_focal_materials + derive_scope + in-code scoring/validators + _make_llm
│           ├── prompts.py       ← all system prompts + 13-section framework + SCOPE_INFERENCE_SYSTEM + STAGE_BENCHMARKS (the real IP)
│           └── tools.py         ← 7 researcher search tools: 6 Tavily (incl. search_latest_news freshness + published-date tagging) + search_google_live (Gemini server-side Google grounding, nested call, redirect-resolved sources)
└── frontend/
    ├── Dockerfile               ← node:20-alpine; CMD npm run dev (no lockfile copied)
    ├── tailwind.config.ts       ← THEME: brand=azure, gray ramp = cool slate
    ├── package.json             ← next 14, react-markdown + remark-gfm
    └── src/
        ├── app/{layout,page,globals.css}   ← page = 2×2 dashboard + History + footer; globals.css has @media print
        ├── app/demo/page.tsx    ← public backend-free showcase (3 baked real reports)
        ├── app/preview/page.tsx ← single-fixture dev preview
        ├── lib/api.ts           ← all fetch fns + TS types (research, upload, deriveScope, reports/History)
        ├── lib/viz.ts           ← colorblind-safe palette + score/size scales
        ├── lib/exportReport.ts  ← toMarkdown / downloadFile / reportSlug (client-side download)
        ├── fixtures/            ← reportGolden.ts + demoScenarios.ts + demo/*.json (baked real runs)
        └── components/
            ├── ResearchForm.tsx        ← 2×2 dashboard grid; confirm-first auto-scope flow
            ├── FocalStartupPanel.tsx    ← "Target Startup Details": on/off switch, VC/Founder toggle, name, upload dropzone
            ├── DimensionWeights.tsx     ← 5 sliders (boxed % values)
            ├── ThesisBiasToggle.tsx     ← Bear / Base / Bull (semantic rose/amber/emerald)
            ├── ResearchStatus.tsx       ← 3s polling, stepper, agent-log panel
            ├── HistoryDrawer.tsx        ← left drawer: search, star, rename, delete, reopen
            ├── ReportViewer.tsx         ← two-column report ⟷ graphics tabs (Map · Scores · **Grades** · Financials · Raw JSON) + Download menu
            ├── PrintableReport.tsx      ← print-only light memo layout (PDF export, incl. market map)
            └── report/                  ← ReportSections, MarketMap (SVG 2×2), Leaderboard, Scorecard, FinancialLedger
```

---

## 5. Request → report data flow

1. **Frontend** `POST /api/research` with `ResearchRequest` (`sector`, `stage`, `geography`, `thesis_bias`, `dimension_weights`, and the focal fields `analysis_mode`/`focal_startup`/`focal_upload_id`/`scope_autoderived`). **`market_prompt` is now OPTIONAL** — a `model_validator` requires it (≥10 chars) *only when no focal startup is attached*; with a focal startup it may be blank and auto-derived.
   - **Other endpoints:** `POST /api/upload` (multipart → `uploads` volume → `upload_id`; accepts docs/images + `.vtt/.srt` transcripts, audio `.mp3/.m4a/.wav/.webm`, and cap-table `.csv`); `POST /api/derive-scope` (`ScopeRequest → ScopeResponse`, the confirm-first auto-scope); History CRUD `GET /api/reports`, `GET/PATCH/DELETE /api/reports/{id}`; **`POST /api/reports/{id}/rerun`** (202 — re-executes a saved run on its stored `request_params`, then the worker diffs vs the baseline + grades its predictions).
2. **`routes.py`** purges stale `celery-task-meta-*` Redis keys, then `run_research_pipeline.delay(...)`. Returns **202** + `task_id`.
3. **Celery worker** seeds `ResearchState` and streams the compiled LangGraph with `stream_mode="updates"`. After each node it calls `self.update_state("STARTED", meta={current_phase, iterations_completed, agent_logs[-20:]})`.
4. **Frontend** polls `GET /api/research/{task_id}` every **3s**. While running it reads `result.info` (live progress, last 20 logs); on `SUCCESS` it reads `result.result` (full `final_report` + all logs). **There is no websocket/SSE — progress is poll-only.**
5. **`compile_report`** assembles the entire `final_report` dict with keys the UI reads directly:
   `merged_report` (the final doc), `research_data`, `analyst_a_report`, `analyst_b_report`, `resolved_scores`, `weighted_scores`, `ranking`, `applied_weights`, `weighting_unavailable`, `market_map`, `financial_ledger`, `iterations_to_consensus`, `thesis_bias`, `status`, **plus the newer keys** `sector`, `analysis_mode`, `focal_startup`, `focal_confidence`, `scope_autoderived`, `incumbents`, `pre_pmf`, `moat_subscores`, `scenarios`, `expected_return`, `research_manifest` (tool-call audit from the ReAct transcript), `data_freshness` (in-code evidence-recency audit; UI "Data as of" badge), `gradesheet` (per-startup letter grades, computed in code; UI **Grades** tab), `expected_return_low`/`_high` (honest EV bounds — presented as a RANGE, never a lone point estimate), `recommended_pick` (the report's own §0/§12 pick; UI badges + History `top_pick` use THIS — R11), `score_confidence` (ledger-disclosure bands; low-disclosure startups render ≈approximate scores), **plus the memo-adoption keys (2026-07-06)** `expected_return_net_low`/`_high` + `return_assumptions` (net of stage-banded dilution-to-exit, `_stage_retention`), `return_dominance` (which scenario carries the EV), `methodology` (code-built "Methodology & Scope" section, also appended to `merged_report`), `acquisitions` (research-sourced exit-precedent deals, `_validate_acquisitions`), `field_stats` (hero-card counts: startups/incumbents/disclosed capital/ARR disclosure); scenario rows carry a `path` field ("who buys / what happens"). Scoring happens here (see §6): `_extract_resolved_scores` returns `(resolved_scores, incumbents, scenarios, moat_subscores, pre_pmf, focal_confidence)`; `_compute_weighted_scores` → `weighted_scores`/`ranking`/`applied_weights`; `_compute_expected_return` from the scenarios. `market_map`/`financial_ledger` are structured JSON from a dedicated extraction call, **validated/coerced in code** (`_validate_market_map`/`_validate_financial_ledger`) — the UI gets a render-safe shape or `null`, never raw LLM output.

`ResearchState` is `total=False`. Only `agent_logs` has a reducer (`Annotated[list[str], add]`, concatenation) so the two analysts writing logs in the same superstep don't clobber each other. Everything else is last-write-wins (safe only because distinct nodes write distinct keys).

---

## 6. Domain concepts you need to know

- **Report framework (§0 + 13 sections)** — defined in `prompts.py` as `REPORT_TEMPLATE_INSTRUCTIONS`, appended to analyst A, analyst B, and compiler prompts (NOT the researcher or judge). Sections: **0 Investment Take (BLUF — leads the report)**, 1 Sector Narrative (+ consensus-vs-variant view), 2 Market Inflection & Bottoms-Up Sizing (TAM/SAM/SOM + top-down anchor + penetration-derived SOM + venture-scale threshold + "why hasn't this been built before now"), 3 Competitive/Incumbent Encroachment (+ plan-to-win), 4 Investable White Space & Thesis (+ a **dated falsifiable prediction**), 5 Market Segmentation & Capability Map (axes are sector-adaptive/illustrative, **not** hard-coded cyber), 6 Financial Health & Valuation Stress-Test (**stage-banded** ledger, point estimates), 7 Weighted Underwriting Index & Scorecard, 8 Startup Profiles (+ company-specific wedge), 9 Team & Founder Assessment, 10 Regulatory Conformance (conditional), 11 Risk Factors + Mitigants + "what would make us wrong", 12 Return Math & Exit Pathways (**probability-weighted scenarios** + explicit invest/pass), 13 Visual Coordinate Market Map. Analysts steel-man the **bear case first** (`_ANALYST_BODY`); the compiler has anti-slop instructions. These are tuned to `docs/QUALITY_RUBRIC.md`. A `STAGE_BENCHMARKS` constant (2025-vintage, calibratable) bands burn-multiple/growth/NRR/ARR-multiple by stage.
- **VC-readiness trust + security layer (added 2026-07-06).** Built so the tool can be piloted by outside users on public data: (1) **liability boundary** — `REPORT_DISCLAIMER` is appended to every `merged_report` IN CODE (both compile paths), a "decision-support, not investment advice" banner + `/terms` page in the UI; (2) **honest return math** — `expected_return_low/high` (EV over low/high scenario bounds) presented as a RANGE with stated assumptions (gross, pre-dilution), never a lone point estimate; (3) **R11 header consistency** — `recommended_pick` (the modelled §0/§12 pick) drives the UI/History "Top pick", plus compiler rules requiring the quality-vs-price bridge and §4↔§12 reconciliation; (4) **source-quality tiering** — `_source_tier` labels every Source Index URL (official/wire > press > unverified > report-mill) with a weak-source discipline rule; (5) **confidence banding** — `_ledger_confidence` bands startups by ledger disclosure; low-disclosure startups render ≈approximate scores (UI + compiler rule; low-confidence focal rows are "disclosure-limited"); (6) **pilot auth** — `API_KEYS` env ("alice:k1,bob:k2") gates all /api endpoints via X-API-Key (`services/auth.py`; empty = disabled = pre-auth behavior), reports are owner-tagged + filtered (legacy ownerless visible to all authed); (7) **upload gating** — `UPLOADS_ENABLED=false` = public-data mode (403 + hidden dropzone via `GET /api/config`); uploads are streamed with per-file AND per-request caps + full cleanup on rejection.
- **Fund-math engine (added 2026-07-07).** Answers "does THIS deal return MY fund?" — the question every IC asks that the tool couldn't. Optional fund-profile inputs on the form (`FundEconomics`: fund size, check, entry post-money, target ownership %, hold years — all $M) → `_compute_fund_math` (pure functions, determinism-in-code; the compiler LLM renders code-computed strings and asserts NO fund numbers) computes entry ownership, ownership-at-exit (via the SAME `_stage_retention` haircut), per-scenario gross/net proceeds, turns-of-fund, the **required exit value to return the fund**, `can_return_fund` / `is_fund_maker` booleans, and net IRR (per-scenario + expected). **Reconciles with the shipped net range by construction**: because retention ρ is constant across scenarios, `E[net_MoIC] = ρ × expected_return` = the existing `expected_return_net_*` midpoint — it's the same haircut monetized through ownership and dollars, so it cannot contradict it. `final_report.fund_math` (None unless fund_size given → whole block + UI panel suppressed). Designed + adversarially verified by an expert-agent panel (8 hand-cross-checked worked test vectors pin every output — `test_fund_math.py`). v1 caveats surfaced in-code (flags: post_inferred, ownership_infeasible, retention_defaulted, holding_too_short, …); gross of fund fees/carry, reserves/follow-on not modelled (v2). Renders as a "Fund Fit" panel in the Financials tab + a §12 subsection. **Substantially closes R6′.**
- **Memo-grade underwriting layer (added 2026-07-06).** The 12 adoption items from a side-by-side against an institutional IC memo (FideaAnalysis.pdf): §12 verdicts are **price-conditional** (invest at/below a stated valuation; "(assumed; no formal ask)" when none is public) with 3–5 measurable+dated **CONDITIONS PRECEDENT** and a **WHY NOT PASS — AND WHY NOT MORE** dialectic; §0 is capped at three sentences and names **the binary variable**; §11 risks carry severity tags (EXISTENTIAL/HIGH/MEDIUM) + RESIDUAL lines; §12's downside must cite the **weakest named comparable acquisition** (the `acquisitions` artifact); section headers carry verdict clauses (canonical `## N. Name` prefix preserved). In code: net-of-dilution return range (`_stage_retention`), EV dominance (`_scenario_dominance`), scenario `path`s, the deterministic `_methodology_section` (incl. an explicit NOT-diligenced list), `field_stats` hero cards, and a GRADE BRIDGE rule when the pick has failing dimensions. See `docs/KNOWN_ISSUES.md` "Added — 2026-07-06 (memo-grade underwriting layer)".
- **Gradesheet (visual Grades tab, added 2026-07-05).** A per-startup letter-grade view (A+…F, plus **NR** = not rated when a metric is undisclosed — never punished as F), **computed 100% in code** from the already-reconciled scores + ledger (`_compute_gradesheet` in `nodes.py`, `GRADE_BANDS` is the coded rubric; NOT LLM-graded, so it can't disagree with the scorecard). **Six cards matching a reference screenshot, honestly sourced** (repo-derived originals renamed/replaced since git ingestion was dropped): Market & Timing (`market_urgency`), Product & Tech Depth (`differentiated_technology` moat sub), Regulatory & Compliance (`regulatory_alignment`; NOT a security-audit grade), Financial Health & Capital Efficiency (mean of the FH dim + coded Rule-of-40/burn — replaces the repo-only 'Engineering quality'), Traction & GTM (stage-adjusted ledger rubric: growth-vs-benchmark + NRR + LTV/CAC + revenue-exists — the ONLY absence→F card, and only when zero/pre-revenue is affirmatively disclosed), Founder-Market Fit (`founder_market_fit`; continuity/key-person is out of scope). Plus an **Overall** header from the weighted index; the focal is flagged. Rendered by `report/Gradesheet.tsx` in the **Grades** ReportViewer tab (`viz.gradeColor`), each card showing its coded calculation. Incumbents excluded. `final_report.gradesheet`.
- **5 scoring dimensions** (relative weights, **normalized in code** — need not sum to 100; defaults Defensibility-heavy per a16z): Financial Health **20**, Defensibility **30**, Market Urgency & TRL **20**, Founder-Market Fit **15**, Regulatory Alignment **15**. Defaults live in `schemas.py DimensionWeights` and `nodes.py DEFAULT_WEIGHTS` (keep in sync).
- **Weighting is deterministic & in code, not the LLM.** The two analysts emit **raw 0–100 per-dimension scores**; the judge does NOT score. `compile_report` reconciles the analysts in code (`_extract_resolved_scores` averages A & B → `resolved_scores`), then `_compute_weighted_scores(resolved_scores, dimension_weights)` computes the official Weighted Index + ranking (normalizing the weights, renormalizing over present dims, coercing numeric strings). The slider weights therefore have an **exact, reproducible** effect on the ranking. If the analysts' scores can't be reconciled, `final_report.weighting_unavailable=True` and the compiler is told to say so rather than fabricate.
- **In-code coherence guarantees (the "R-series" — anything arithmetic/bookkeeping is done in code, not asserted by the LLM).** `_extract_resolved_scores` returns `(resolved_scores, incumbents, scenarios, moat_subscores, pre_pmf, focal_confidence)`; `compile_report` then enforces:
  - **R1 — incumbents never scored/ranked.** `_validate_resolved_scores(protect=focal)` drops any startup in the emitted `incumbents` list from the scorecard/ranking; `_validate_market_map`/`_validate_financial_ledger` force `is_incumbent` (reference-only, no weighted score, sorted last). A **focal startup is force-kept** even if the LLM mislabels it incumbent/pre-PMF.
  - **R13 — pre-PMF/pre-launch startups aren't underwritten.** Dropped from scoring (watchlist-only); the focal startup is exempt.
  - **R10 — Defensibility = mean of the 4 a16z moat sub-scores** (`_apply_moat_reconciliation`), so §7's Defensibility can't disagree with the sub-scores shown next to it.
  - **R6 — probability-weighted return computed in code.** `_compute_expected_return` = `Σ probability × midpoint(multiple)` from the recommended startup's scenarios; the exact figure is fed to the compiler so §0/§12 + the scenario table reconcile. *(Known limitation R6′: it's a false-precise point estimate ignoring dilution — see `docs/KNOWN_ISSUES.md`.)*
  - **R7 — `implied_arr_multiple` = valuation/ARR** derived in `_validate_financial_ledger`; **R3** backfills any ranked startup missing from the ledger so the company universe matches across §6/§7/§8/§13.
  - **Finite guards:** `_as_score`/`_parse_money`/`_compute_expected_return` reject NaN/inf (JSON-safe).
- **F_score** (financial sub-score, used by the LLM as a *guide* for the raw Financial Health score, normalized against the stage band): `0.35·YoY + 0.30·NRR + 0.20·(LTV/CAC) − 0.15·BurnMultiple`.
- **Research protocol** (`TOOL_CHOREOGRAPHY_INSTRUCTIONS`, researcher only): ≥20 Tavily calls in 4 phases (market+sizing → per-startup financials/moat **+ a mandatory `search_latest_news` freshness pass per startup** → regulatory+founders → exit/M&A), enforce **≥6 (ideally 8) startups** + name 2–3 **incumbents** as map reference, widen to adjacent stages when <6 pure-plays exist (and say so), mark missing data "Not Disclosed", never fabricate.
- **Freshness layer (anti-staleness, added 2026-07-02).** All three fact-asserting agents are **date-grounded** (`_today_note` injects "Today's date: …" into the researcher/analyst/compiler user messages — without it the LLMs treat their training cutoff as "now"). `_tavily_search` tags every source with its **publication date** when Tavily returns one; `search_latest_news` (news topic, past 365 days, query incl. acquisition/merger terms) re-checks each startup for its newest round/valuation/M&A status; `search_startup_financials` fetches **page-body excerpts** (`include_raw_content`, capped 2.5K chars/source) because paragraph-level terms like "post-money ~$700M" never survive into snippets. Recency arbitration everywhere: **newest source wins**, older figure noted with its date, figures-from-memory banned (RECENCY DISCIPLINE in the choreography + RECENCY rule in the shared sourcing block).
- **Research observability + freshness audit (added 2026-07-02).** `researcher_node` no longer discards the ReAct transcript blindly: `_research_manifest` counts every tool call (total / by-tool / failed) → `final_report.research_manifest` + a rich agent log with a **PROTOCOL SHORTFALL** flag; `_harvest_source_index` pulls the REAL source URLs out of the tool transcripts into an auto-generated "Source Index" appended to `research_data` (kills compiler-fabricated Works Cited links — observed live 2026-07-02); `_data_freshness` audits the compiled report's dated mentions (newest/oldest/lag) → `final_report.data_freshness` + a "Data as of" badge in `ReportViewer` (amber when newest evidence >6 months old); every Tavily/grounded call is now logged (live tail during the researcher phase). The compiler is told to close §0 with "*Research data as of <date>*" and to never invent URLs.
- **Google-grounded precision search (added 2026-07-02).** `search_google_live` (tools.py) = Gemini's server-side **Grounding with Google Search**, wrapped as a researcher tool via a NESTED standalone LLM call (the API doesn't mix the built-in google_search tool with client-side function tools in one request — do not bind it directly on the ReAct agent). Used for per-startup PRECISION CHECKS (exact round / post-money valuation / M&A status) + the Phase-4 consolidation sweep + one per-incumbent acquisition sweep; grounded answers WIN recency conflicts vs Tavily snippets. Sources arrive as Google redirect URLs — `_resolve_redirect` follows them (3s timeout, falls back to the redirect) so Works Cited gets real URLs. Gated by `GROUNDED_SEARCH` + a Gemini-researcher check; degrades to a note like the Tavily tools.
- **Judge = disagreement-finder** (`get_judge_system_prompt`; parsed via `_last_balanced_json`) — it does NOT score. It returns `{converged: bool, disagreements: [{point, analyst_a, analyst_b, reconsider}]}`. `judge_node` sets `judge_agreed = converged` (forced `true` on the final round) and `judge_critique` = the formatted disagreements (the analysts revise against them). `_should_loop` routes to `compile_report` when `judge_agreed` OR `iterations ≥ max_debate_iterations` (3); else loops back to `analysts_fanout`. Scoring is done later in `compile_report` (see the weighting bullet) — **not** by the judge.

---

## 6A. Focal startup · auto-scope · uploads · history · demo · download

The features layered on top of the sector pipeline. Backends live in `backend/app/services/`, endpoints in `routes.py`, UI in `frontend/src`.

- **Focal (target) startup + modes.** `analysis_mode` = `vc` (rank the named startup inside the discovered field) or `founder` (center the report on the startup, market as backdrop, explicit build/pass verdict). Threaded through `ResearchState` (`focal_startup`, `focal_upload_id`, `focal_materials`, `focal_confidence`, `analysis_mode`). The compiler prompt branches on mode; the focal startup is force-included and force-scored (R1/R13 exempt) with a data-**confidence** tag (low/med/high) surfaced in prose + the UI badge. UI: `FocalStartupPanel.tsx` ("Target Startup Details") with an **on/off switch**, VC/Founder toggle, name field, and a drag-drop upload dropzone.
- **Founder mode is focal-centric (deepened 2026-07-03).** Three changes made founder mode about the founder's own company rather than a sector memo with the focal bolted on: (A) **the uploaded deck reaches the analysts + compiler**, not just the researcher — `_focal_materials_digest` injects `focal_materials` (founder-mode-gated) so stealth companies aren't treated as "unknown"/"Not Disclosed" black boxes; (B) **§0 leads with the founder verdict** (a two-line "Investor check (today)" + "Founder call: BUILD/KEEP GOING/PIVOT/STOP", stage-normal note) and **NEVER headlines a competitor as top-pick**; **§12 gives the focal's own fundraise** (round size, target post-money benchmarked to §6 comps, dilution/ownership, milestones) — a competitor's probability-weighted MoIC is relabeled as exit-comp context, never the focal's headline return (the `return_note` branches on whether the modelled scenarios describe the focal or a competitor via `_norm_name`); (C) **§0.5 gained a Sequenced 90-day plan** (do-first/defer, cost, cross-move conflict flag) **and a "Fastest signal to quit"** self-runnable kill-gate.
- **Founder-mode §0.5 Strategic Repositioning.** In founder mode ONLY, the report gains `## 0.5 Strategic Repositioning — What to Change, What to Keep` immediately after the Investment Take: 2–4 repositioning moves (each must name a weakest scoring dimension/moat sub-score as TARGET, cite NAMED research evidence, state a DIRECTIONAL fundability effect + the partner objection it removes, and give its COST & FALSIFIER) plus exactly ONE "What NOT to change" (the wedge to preserve), then a sequenced 90-day plan and a fastest-signal-to-quit gate. Spec = `FOUNDER_REPOSITIONING_SECTION` (prompts.py), injected founder-only into both analysts' user message and the compiler note — deliberately NOT in the shared template so VC mode can't leak it. Anti-slop guard = the PASTE TEST + banned-phrase list. The compiler's anchors are **computed in code** (`_focal_weak_spots`: the focal's 2 weakest dims + 2 weakest moat sub-scores from the reconciled scorecard, with a fallback when reconciliation fails); the judge is told mere §0.5 proposal divergence is synthesis material, NOT a disagreement (it still flags §0.5 points when the analysts contradict each other on an underlying fact or score). Founder mode **requires the startup name** (`schemas.py` validator + form gating) — every founder surface keys on it. No new scores/totals — the section reads the scorecard, never edits it.
- **Document upload + ingest.** `POST /api/upload` (multipart, `python-multipart`) stores files on the `uploads` volume → `upload_id`. `services/ingest.py` parses them (called from the `ingest_focal` node): **PyMuPDF** text, with a **vision fallback** (`vision_model`) for image / image-only PDF pages; `.docx` (`python-docx`); `.txt/.md`; images. Cached to `<uploaddir>/_extracted.txt` (files starting with `_` are skipped so the cache isn't re-ingested). Allowed types + 25 MB cap enforced in the route.
- **Auto-scope (confirm-first).** When a startup is attached but the market prompt is blank, the UI calls `POST /api/derive-scope` → `services/scope.py infer_scope`: uploaded **materials** are the PRIMARY context when present, **plus 1–2 quick Tavily searches on the name** appended as a labeled SECONDARY block (freshness/reality check; the label tells the LLM to ignore snippets describing a same-name different company — `source: "materials+search"`); with no materials the searches are the only grounding (`source: "search"`). Then `derive_scope` (LLM, `SCOPE_INFERENCE_SYSTEM`) → `{sector, market_prompt, rationale, autoderived, source}`. The form **prefills the editable prompt+sector** for the user to review, then Launch. The pipeline also **self-heals** the same way in `ingest_focal` if a request arrives with no prompt.
- **History (durable store).** Every finished run is persisted by the worker (save-on-completion in `tasks.py`) to `services/store.py` on the `reports` volume (`<reports_dir>/<id>.json` = light meta + full `final_report`). Survives restarts and the Redis purge. CRUD: `GET /api/reports` (light list, starred-first-then-newest), `GET /api/reports/{id}` (full), `PATCH` (label/star), `DELETE`. UI: `HistoryDrawer.tsx` — a left slide-out (☰ History top-left) with **search**, **star favorites**, **rename/label**, **delete**, and **click-to-reopen** a past run in `ReportViewer`.
- **Differentiation batch (added 2026-07-09 — the three "a chat AI can't do this" features).**
  (1) **Founder-call claim audit**: upload a call recording (audio → `whisper-1` with [mm:ss] segment stamps) or `.vtt/.srt`/named-transcript file → ingest tags it `[CALL TRANSCRIPT]` (`split_transcripts`) → `_extract_call_claims` (judge model, validated by `_validate_call_claims`, ≤12) → the researcher's Phase-0 audit verifies each claim (choreography extended) → `_audit_call_claims` cross-examines claims vs the research brief AND the deck (statuses verified/contradicted/vendor-only/unsupported + `deck_conflict`; joined back onto the real claims in code, counts computed in code) → `final_report.call_claims_audit`, a **Claims** tab, PDF Appendix D, and a compiler note weaving contradictions into §9/§11.
  (2) **Cap-table CSV ingest**: `services/captable.py` (flexible headers; money normalized to $M in code; post = pre + raised derived when absent) → `state.cap_table` → entry-post precedence becomes user > cap table (only when the scenarios describe the focal; flag `post_from_cap_table`) > resolve-emitted > stage; the focal's ledger row backfills missing raised/valuation from it; `final_report.cap_table` renders in the Financials tab + PDF.
  (3) **Longitudinal re-run + self-grading**: History records now store `request_params`; `POST /api/reports/{id}/rerun` re-executes them with `baseline_report_id`; after compile the worker computes `run_delta` IN CODE (`services/delta.py compute_run_delta`: entered/exited, rank+score movers, ledger money deltas, new acquisitions, pick/EV change — containment name-matching) and grades the baseline's own dated predictions vs the fresh evidence (`grade_predictions`, one judge-model call; deadline logic enforced in code by `validate_prediction_audit`: future ≠ broken, passed-pending → unresolved) → `final_report.run_delta`/`prediction_audit`, a "What changed" panel, a ↻ re-run button per History row, PDF Appendix E.
- **Public demo (`/demo`, backend-free).** `app/demo/page.tsx` + `fixtures/demoScenarios.ts` render **three baked, real** reports: VC sector (`reportGolden` cyber), VC + target (sim6 medical scribes w/ Abridge focal), Founder (Fidea/NeuroScribe). No API keys, no run. Home header links to it. This is the primary portfolio artifact (deploy the frontend alone to Vercel).
- **Download.** `ReportViewer` has a Download menu: **PDF-with-visuals** (`window.print()` renders the print-only `PrintableReport.tsx` — a light memo layout with the market-map SVG in a **light print palette** (`MarketMap light` prop) **plus Appendices A–C rendering every graphics tab for paper**: weighted index + moat sub-scores, financial ledger + scenarios + exit precedents + fund fit, and the gradesheet; see `@media print` in `globals.css`), a **one-page tear sheet**, **Markdown** (`lib/exportReport.ts toMarkdown`), **JSON**. All screen chrome on `/` and `/demo` is `no-print`-tagged so printed PDFs contain only the memo. CLI equivalents in `scripts/` (`format_report.py`, `report_to_html.py` + Chrome headless `--print-to-pdf`). Note: CLI/file exports are text+tables only (no map) — that's fast-follow **B-mapfile** in KNOWN_ISSUES.
- **Theme + layout (redesigned 2026-07-08 — "dark console + paper memo").** Azure + Slate dark app chrome (`tailwind.config.ts`: `brand`=azure, `gray`=cool-slate ramp) with a **real top nav bar** (wordmark · History · Examples · API-key icon; the old floating pills, gradient hero title, and body glow are gone). Typography via **next/font** in `layout.tsx`: Inter (app, `tabular-nums` for figures) + Source Serif 4 (memo prose). Emoji chrome replaced by a tiny local inline-SVG set (`components/icons.tsx` — not a dependency). `ResearchForm` keeps the **2×2 dashboard** of cards, now with `01·Scope`-style step kickers. `ResearchStatus` = vertical stepper **with per-step model attributions** + a quiet activity feed (no "Polls: N" debug chrome; poll count lives in the Elapsed tooltip). `ReportViewer` = verdict-first masthead (kicker/serif title/Top pick + gross return range) + divided stat strip + underline tabs; the report body renders on a **white "paper sheet"** (`shadow-sheet ring-1`) with light serif `.report-prose` — the screen matches the printed memo. Score colors stay semantic green→amber→red (`viz.ts`, still dark-panel-tuned — the graphics panel stays dark); the thesis toggle is semantic rose/amber/emerald. The **Sources tab was removed** (sources live at the bottom of the report).

---

## 7. Running it

```bash
# from repo root
docker compose up --build
# redis :6379 (internal) · backend :8000 · frontend :3000
# open http://localhost:3000
```

Requires `backend/.env` (copy from `backend/.env.example`, fill all 5 API keys). **`.env.example` lists the per-role `*_MODEL` overrides commented out** — they default in `config.py`; uncomment only to change a model.

- **API:** `GET /health` → `{"status":"ok"}` · `POST /api/research` (202) · `GET /api/research/{task_id}`.
- **Worker:** `celery -A app.worker.celery_app:celery_app worker --concurrency=2` (concurrency set in the compose command, not in `celery_app.py`).
- **Redis DBs:** broker = DB 0, result backend = DB 1. No persistence volume — a redis restart wipes in-flight tasks (completed reports survive on the `reports` volume).
- **Volumes:** `uploads` (focal-startup files) and `reports` (History store) mounted at `/data/uploads` and `/data/reports` on **both** backend and worker. Source is still baked (`COPY . .`, no live mount) → **rebuild to pick up code changes**.
- A full run is slow (multi-agent + rate-limit retries). Celery limits: **soft 5400s / hard 6000s** (raised 2026-07-13 after a 65-min kill under concurrent-run rate-limit contention + a laptop-sleep kill; a healthy solo run is ~25-35 min — keep the Mac awake, e.g. `caffeinate`, during runs).
- **Tests (token-free, no API keys):** `python3 backend/tests/test_focal.py` (+ `test_ingest`, `test_scope`, `test_structured_artifacts`, `test_filters_sliders`, `test_repositioning`, `test_freshness`, `test_gradesheet`, `test_trust`). They stub the LLM deps in `sys.modules` and exercise the real validators/nodes. Run these after any backend change to `nodes.py`/`services/`/`schemas.py`. **Rebuild the image before any live UI run** (source is baked).

---

## 8. Config & environment (`backend/.env`)

| Var | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | Judge (gpt-4.1) |
| `ANTHROPIC_API_KEY` | Analyst B (claude-sonnet-4-6) |
| `GOOGLE_API_KEY` | Researcher / Analyst A / Compiler (gemini-2.5-pro) |
| `GROQ_API_KEY` | `_make_llm` fallback provider (required even if unused by defaults) |
| `TAVILY_API_KEY` | The 6 search tools (free tier ≈ 1,000 CREDITS/mo; advanced search = 2 credits, basic = 1 → a run burns ~35-50 credits ≈ 20-28 runs/mo) |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Compose repoints these to `redis://redis:6379/{0,0,1}` |
| `MAX_DEBATE_ITERATIONS` | Hard cap on debate rounds (default **3**) |
| `UPLOADS_DIR` / `REPORTS_DIR` | Volume mount points (default `/data/uploads`, `/data/reports`) |
| `VISION_MODEL` | Multimodal model for image / image-PDF ingest (default `gemini-2.5-pro`) |
| `MAX_UPLOAD_MB` | Per-file upload cap (default **25**) |
| `GROUNDED_SEARCH` | Enable the researcher's `search_google_live` Gemini-grounded tool (default **true**; Gemini researcher only — burns Gemini grounding quota, not Tavily credits) |
| `API_KEYS` | Pilot auth: `"alice:key1,bob:key2"` requires `X-API-Key` on all /api endpoints + per-owner History (default **empty = auth disabled**) |
| `UPLOADS_ENABLED` | `false` = public-data mode: uploads 403 + UI dropzone hidden (default **true**) |
| `LOG_LEVEL` | default `INFO` |

`config.py` loads `.env` from an **absolute** path (`Path(__file__).resolve().parent.parent/.env`) so it resolves correctly inside Docker. `redis_url` is defined but effectively dead config (Celery uses the broker/backend URLs).

---

## 9. History — stale references that were fixed (2026-06-26)

A batch of code-vs-doc traps were cleaned up on **2026-06-26** (all adversarially reviewed; no live pipeline run yet). Noted here only so you don't reintroduce them:

- `nodes.py` analyst comments no longer say *"Quantitative Challenger / Qualitative Auditor"* — both analysts are **full-spectrum**, run the identical prompt, and differ only by model.
- `tools.py` docstring now correctly says the search tools are **researcher-only** (not shared by the analysts).
- Frontend `ResearchStatus.tsx` now shows the **real** model names (Gemini 2.5 Pro / Claude Sonnet 4.6 / GPT-4.1, not *"Gemini Flash"*) and includes the **researcher** phase in a 6-step stepper.
- The `$`-as-LaTeX rendering bug is fixed by **removing** `remark-math`/`rehype-katex` — `$` renders literally now. Do **not** re-add a math pipeline; the prompts forbid LaTeX and require formulas in backticks.
- Researcher `max_tokens` is now `65536` (was the 8192 default) to stop truncating the 6–8-startup brief.
- `_extract_json_verdict`'s no-parse fallback now returns `agreed: false` (debate loops) instead of faking a consensus.
- The old root `ARCHITECTURE.md` (quant/qual split, "Claude Sonnet 4") was rewritten to match the current design.

Still: if you change a model ID, update the frontend model attributions too — they're hard-coded in the `STEPS` array in `ResearchStatus.tsx` (the stepper's per-step model sub-labels), not sourced from `config.py`, so they can drift.

**Open** issues (output-quality + infra) with file pointers live in **`docs/KNOWN_ISSUES.md`** — start there, and update it as you fix things.

---

## 10. Known output-quality issues

**`docs/KNOWN_ISSUES.md` is the source of truth** (R1–R14 trail + an "Added — 2026-07-01" §0.5 section + a "Fixed 2026-07-01" section). Summary of *current* state:

1. ✅ **The whole coherence-bug layer is fixed in code and validated live** (sim4/5/6 + the Fidea founder run): LaTeX `$` (R-latex), incumbents-in-ranking (R1), cross-section coverage (R3), ASCII-map/§5 axes + size legend (R4/R5), return-math drift (R6/R7/R8), Defensibility=mean-of-moats (R10), pre-PMF scored (R13), startup breadth ≥6 (R2). Codex grades runs **16–18/24** ("competent, not top-fund").
2. 🟡 **Underwriting depth (the biggest remaining gap, rubric dims 2/3)** — the return-math gap (R6′) was substantially narrowed 2026-07-06 (range + net-of-dilution + paths + dominance + conditions precedent); still open: check-size→ownership math, IRR/time-value, fund-returner framing; sources are secondary. This is the top lever to push a run toward 20+.
3. 🟡 **A few prose-level coherence contradictions** the code can't catch (R9 §4-vs-§12 exit value, R11 recommended≠top-ranked with no valuation bridge, R12 map-vs-profile) — prompt-hardening candidates.
4. ❌ **Analyst debate tension still doesn't surface** in the final report (only `judge_critique` loops back; no "Points of Contention" in the merged doc). The judge is now a disagreement-finder, so the raw material exists — it just isn't threaded into `final_report`.

---

## 11. Conventions & how to work in this repo

- **Models are config-driven.** Change a model in `config.py` (or `.env` `*_MODEL`), never hard-code IDs in nodes/frontend. If you touch a model ID, also fix the frontend `phaseLabel` strings (§9.3) so the UI doesn't lie.
- **Prompts are the product.** The real logic lives in `prompts.py`. Changing report structure/scoring = editing those strings, not Python control flow.
- **The graph loops back to `analysts_fanout`, never `researcher`.** Research is gathered once; debate re-runs only the analysts with `judge_critique` injected.
- **Progress is poll-based**, capped to the last 20 logs while running; the full log + report only exist on `SUCCESS`.
- **Stale Redis results expire via TTL** (`result_expires=3d` in `celery_app.py`) — the old wipe-all `_purge_stale_results` was removed 2026-07-06, so concurrent in-flight runs no longer clobber each other. Ack semantics are explicit (`task_acks_late=False`, `worker_prefetch_multiplier=1`, visibility_timeout > hard limit) so a crashed/killed run is never silently redelivered.
- **Retries:** `_run_agent_with_retry` / `_invoke_llm_with_retry` do up to 8 attempts on rate-limit/quota errors with backoff up to 900s; non-rate-limit errors re-raise immediately.
- **Anything arithmetic goes in code, not the LLM.** Scores, weights, expected return, valuation multiples, moat means, coverage reconciliation are computed/validated in `nodes.py` (the R-series, §6) so sections can't disagree. When adding an LLM-asserted number that should be consistent across the report, compute it in code and feed it to the compiler instead.
- **There ARE token-free tests now** (`backend/tests/`, 491 checks). Run them after backend changes (they stub LLM deps — no keys/cost). But there's still **no `.git`** and no live-run CI — for behavior/quality, also run the stack and exercise a real request. **Rebuild the image after code changes** (source is baked).
- **New backend service work** goes in `backend/app/services/` (ingest/scope/store), imported lazily inside functions/nodes to avoid import cycles (`nodes` ⇄ `services.scope`).
- **Keep these docs in sync.** If you change architecture, models, endpoints, or a coherence guarantee, update this file, `ARCHITECTURE.md`, and `docs/KNOWN_ISSUES.md` in the same change.
