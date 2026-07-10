# Pipeline Architecture

> Deep technical reference for the LangGraph consensus pipeline. Kept in sync with the code in `backend/app/graph/` + `backend/app/services/`. For a fast orientation read `CLAUDE.md`; for the bug/tech-debt list read `docs/KNOWN_ISSUES.md`.
>
> **History of design shifts:**
> - The old "Quantitative Challenger / Qualitative Auditor" analyst split was removed — both analysts are now identical full-spectrum prompts differing only by model.
> - The judge no longer scores. It is a **disagreement-finder**; all scoring/weighting is now **reconciled in code inside `compile_report`** (see *In-code invariants*).
> - A **focal-startup** layer was added: an `ingest_focal` node runs first, two product modes (VC / Founder), document upload + vision, auto-scope, and a durable History store.

## Graph topology

```
                                    +---------------------------+
                                    |          START            |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    |       INGEST_FOCAL         |   (new first node)
                                    |  ingest_focal_materials    |
                                    |                            |
                                    |  - pure pass-through when   |
                                    |    no focal startup         |
                                    |  - else parse uploaded      |
                                    |    files -> focal_materials  |
                                    |    (services/ingest.py)     |
                                    |  - self-heal: if no          |
                                    |    market_prompt, derive     |
                                    |    sector+prompt from the    |
                                    |    startup (services/scope)  |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    |       RESEARCHER          |
                                    |     (gemini-2.5-pro)      |
                                    |   create_react_agent      |
                                    |                           |
                                    |  - 7 tools: 6 Tavily +    |
                                    |    search_google_live      |
                                    |    (Gemini-grounded)       |
                                    |  - >=20 tool calls         |
                                    |  - date-grounded; per-     |
                                    |    startup latest-news     |
                                    |    FRESHNESS pass (news,   |
                                    |    365d, published dates)  |
                                    |  - name 8-12 candidates,   |
                                    |    deep-dive >=6 startups   |
                                    |  - FORCE-INCLUDE the focal  |
                                    |    startup (+materials)     |
                                    |  - raw facts only, newest   |
                                    |    source wins conflicts    |
                                    +------------+--------------+
                                                 |
                                          research_data
                                                 v
                                    +---------------------------+
                                    |    ANALYSTS_FANOUT        |
                                    |   (no-op pass-through;    |
                                    |    also the loop target)  |
                                    +-----+-------------+-------+
                                          |             |
                             same data    |             |    same data
                                          v             v
                             +----------------+   +----------------+
                             |   ANALYST A    |   |   ANALYST B    |
                             | gemini-2.5-pro |   | claude-sonnet  |
                             |                |   |     -4-6       |
                             | FULL-SPECTRUM  |   | FULL-SPECTRUM  |
                             | (quant + qual) |   | (quant + qual) |
                             | IDENTICAL      |   | IDENTICAL      |
                             | prompt, NO     |   | prompt, NO     |
                             | tools          |   | tools          |
                             +-------+--------+   +--------+-------+
                                     |                     |
                                     +----------+----------+
                                                |  (judge waits for both)
                                                v
                                    +---------------------------+
                                    |         JUDGE             |
                                    |       (gpt-4.1)           |
                                    |   DISAGREEMENT-FINDER      |
                                    |                           |
                                    |  - third platform         |
                                    |  - persona set by         |
                                    |    thesis_bias            |
                                    |  - pinpoints where A & B   |
                                    |    disagree; tells them    |
                                    |    to reconsider           |
                                    |  - does NOT score          |
                                    |  - iterations += 1          |
                                    +------------+--------------+
                                                 |
                                          _should_loop(state)
                                        +--------+--------+
                                        |                 |
                            agreed=false &           agreed=true OR
                            iterations < 3           iterations >= 3
                                        |                 |
                                        |                 v
                                        |     +---------------------------+
                                        |     |       COMPILER            |
                                        |     |     (gemini-2.5-pro)      |
                                        |     |  max_tokens = 65536       |
                                        |     |                            |
                                        |     |  1. RECONCILE SCORES in    |
                                        |     |     code (extract from A/B) |
                                        |     |  2. weighted index, moat    |
                                        |     |     mean, expected return   |
                                        |     |  3. single-pass merge ->    |
                                        |     |     13-section report       |
                                        |     |  4. emit + validate         |
                                        |     |     market_map + ledger      |
                                        |     +------------+--------------+
                                        |                  |
                                        |                  v   (worker saves report to History store)
                                        |     +---------------------------+
                                        |     |           END             |
                                        |     +---------------------------+
                                        |
                                        |  loop back (max 3 rounds total);
                                        |  judge_critique (disagreement points)
                                        |  injected into both analysts' next message
                                        +-------> ANALYSTS_FANOUT
                                                  (ingest + researcher do NOT re-run)
```

## Two product modes

The `analysis_mode` control shapes the whole run:

- **VC** — the focal startup (if any) is **force-included and ranked within** the discovered competitive field.
- **FOUNDER** — the report is **centered on the focal startup** with an explicit build/keep-going vs pivot/pass verdict; the market is the backdrop. The report also gains **§0.5 Strategic Repositioning** (immediately after §0): 2–4 evidence-anchored moves to tweak the startup for better market fit + fundability, plus exactly one "What NOT to change". The spec (`FOUNDER_REPOSITIONING_SECTION` in `prompts.py`) is injected founder-only into both analysts' user message and the compiler note — never into the shared template, so VC mode can't emit it. The compiler's move anchors are **computed in code**: `_focal_weak_spots` extracts the focal's 2 weakest dimensions + 2 weakest moat sub-scores from the reconciled scorecard (fallback instruction when reconciliation fails). The judge's user message tells it mere §0.5 proposal divergence is compiler synthesis material, not a disagreement (it still flags §0.5 points when the analysts contradict on an underlying fact or score). Founder mode requires the startup name (`schemas.py` validator; the form gates Launch on it).

**Auto-scope (confirm-first):** when a focal startup is attached, the user can leave `market_prompt` blank; the market is derived from the startup (materials-first, else Tavily-grounded) via `POST /api/derive-scope`, shown for review, then submitted. If a request still arrives with no `market_prompt`, the `ingest_focal` node self-heals by deriving it.

## Data flow

```
User Query (market_prompt* + sector/stage/geography/thesis_bias/dimension_weights
            + analysis_mode + focal_startup + focal_upload_id)     (*optional when a focal startup is set)
    |
    v
+------------------+   +------------------+   +------------------+   +------------------+
| focal_materials  |-->|   research_data  |-->| agent_a_report   |-->|   final_report   |
| (parsed uploads) |   |  (shared facts)  |   | agent_b_report   |   |  (merged doc +   |
+------------------+   +------------------+   +------------------+   |  in-code scores) |
    ingest_focal            Researcher          Both analysts        +------------------+
    (parse + scope)         writes this         read the SAME              compile_report
                            (6 Tavily tools;    research_data, no          reconciles A+B scores
                            force-includes      tools, write              in code, computes the
                            the focal startup)  independent reports        weighted index, merges
```

`final_report` (assembled entirely by `compile_report`) carries:
`merged_report`, `research_data`, `analyst_a_report`, `analyst_b_report`,
`resolved_scores` (raw 0–100 per-dim, code-reconciled), `weighted_scores`, `ranking`, `applied_weights`, `weighting_unavailable`,
`incumbents`, `pre_pmf`, `moat_subscores`, `scenarios` (rows carry a `path` — who buys / what happens), `expected_return`,
`expected_return_low`/`_high` (honest EV range), `expected_return_net_low`/`_high` + `return_assumptions` (net of stage-banded
dilution-to-exit, `_stage_retention`), `return_dominance` (which scenario carries the EV), `recommended_pick`, `score_confidence`,
`market_map`, `financial_ledger`, `gradesheet` (per-startup letter grades, computed in code),
`acquisitions` (research-sourced exit-precedent deals, validated in code), `field_stats` (hero-card counts),
`fund_math` ("does this return my fund?" — turns-of-fund, required-exit, IRR; computed in code, None unless fund inputs given), `focal_rank`,
`methodology` (deterministic "Methodology & Scope" section, also appended to `merged_report`),
`research_manifest`, `data_freshness`,
`analysis_mode`, `focal_startup`, `focal_confidence`, `sector`, `scope_autoderived`,
`iterations_to_consensus`, `thesis_bias`, `status`. The frontend `ReportViewer` reads these keys directly.

## In-code invariants (the real IP)

Everything that is *arithmetic* or *bookkeeping* is computed in code in `compile_report` (not asserted by an LLM), so the report cannot contradict itself. `_extract_resolved_scores(analyst_a, analyst_b, settings, focal)` runs a focused JSON extraction over the analysts' §6–8/§12 and returns
`(resolved_scores, incumbents, scenarios, moat_subscores, pre_pmf, focal_confidence)`. Then:

- **R1 — incumbents excluded from the ranking.** Big-tech / EHR / platform players are dropped from `resolved_scores`/the map score; the **focal startup is force-kept** even if the model mislabels it.
- **R10 — Defensibility = mean of the four a16z moat sub-scores** (`_apply_moat_reconciliation`), so the §7 dimension can't disagree with the sub-scores.
- **R13 — pre-PMF / pre-launch startups excluded** from scoring (watchlist only); the focal startup is exempt.
- **R6 — probability-weighted expected return computed in code** (`_compute_expected_return` = Σ p·midpoint(multiple), renormalized) and fed to the compiler for §0/§12 verbatim — presented as an honest RANGE (`_expected_return_range`), with a **net-of-dilution** companion range (`_stage_retention`, stage-banded 60–85% retention-to-exit, default 70%) and an **EV-dominance** decomposition (`_scenario_dominance` → "N% of the EV sits in the <label> case").
- **R6-fund — fund-math engine** (`_compute_fund_math`, added 2026-07-07): when optional `FundEconomics` inputs are given, monetizes the SAME scenarios + retention into check→ownership→ownership-at-exit→proceeds→turns-of-fund, the required-exit-to-return-fund, `can_return_fund`/`is_fund_maker` booleans, and net IRR (`_net_irr`). Reconciles by construction with the net range (E[net_MoIC] = ρ·expected_return). Pure functions, expert-panel-verified against 8 worked vectors (`test_fund_math.py`); the compiler renders code-computed strings, asserts no fund numbers. `final_report.fund_math` (None unless fund_size given).
- **R3/R7 — financial ledger:** `implied_arr_multiple = valuation/ARR` computed in code; the ledger is reconciled against the canonical ranked set (missing startups backfilled), incumbents marked/sorted last.
- **Deterministic weighting:** `_compute_weighted_scores(resolved_scores, weights)` applies the (relative, normalized, renormalized-over-present-dims) slider weights in code → `weighted_scores` + `ranking`; the compiler is handed these verbatim. `weighting_unavailable=True` if no usable scores.
- **Structured artifacts:** `market_map` + `financial_ledger` are emitted as JSON by a dedicated extraction pass and **validated/coerced in code** (`_validate_market_map` / `_validate_financial_ledger`) so the UI always gets a render-safe shape or `null`.
- **Numeric hygiene:** `_as_score` / `_parse_money` reject non-finite (NaN/inf) values.

## ResearchState (`graph/state.py`)

`TypedDict(total=False)` — partial seeding is valid. Fields:

| Field | Written by | Reducer |
|-------|-----------|---------|
| `market_prompt`, `sector`, `stage`, `geography`, `thesis_bias`, `dimension_weights` | Celery task | last-write-wins |
| `analysis_mode`, `focal_startup`, `focal_upload_id`, `scope_autoderived` | Celery task | last-write-wins |
| `focal_materials`, `focal_confidence`, `sector`, `scope_autoderived`, `market_prompt` | ingest_focal (may write scope) | last-write-wins |
| `research_data` | researcher | last-write-wins |
| `agent_a_report` / `agent_b_report` | analyst_a / analyst_b | last-write-wins |
| `judge_critique`, `judge_agreed` | judge | last-write-wins |
| `iterations` | judge (`prior + 1`) | last-write-wins |
| `final_report` | compiler | last-write-wins |
| `agent_logs` | every node | **`add` (list concat)** |

Only `agent_logs` has a custom reducer, so the two analysts running in the same superstep concatenate logs instead of clobbering.

## Node responsibilities (`graph/nodes.py`)

- **`ingest_focal_materials`** — the new first node. `{}` pass-through when no focal startup. Otherwise: extracts text from the uploaded files (`services/ingest.extract_materials_cached`) into `focal_materials`, and if `market_prompt` is blank, derives `sector`+`market_prompt` via `services/scope.infer_scope` (self-heal). Best-effort — failures degrade to empty materials, never crash the run.
- **`researcher_node`** — `create_react_agent(_make_llm(researcher_model, max_tokens=65536), RESEARCH_TOOLS, prompt=RESEARCHER_SYSTEM)` via `_run_agent_with_retry` (which invokes with `recursion_limit=100` — the LangGraph default of 25 caps at ~12 sequential tool rounds, far below the ≥20-call protocol). RESEARCH_TOOLS = 6 Tavily tools + `search_google_live` (Gemini server-side Google grounding via a nested standalone call — never bound directly on the agent; sources redirect-resolved to real URLs). The *only* node with tools (6 Tavily tools; sources carry publication dates). Date-grounded via `_today_note`; ≥20 calls incl. a mandatory `search_latest_news` freshness pass per deep-dived startup (news topic, past 365 days); recency arbitration: newest source wins, no figures from model memory. Names 8–12 candidate startups first, deep-dives ≥6, and **force-includes the focal startup** (using `focal_materials` as primary source if stealth). Returns `research_data` + a log line.
- **`analysts_fanout`** — returns `{}`. Structural fan-out node; also the loop-back target.
- **`analyst_a_node` / `analyst_b_node`** — plain `llm.invoke([("system", ANALYST_*_SYSTEM), ("user", msg)])`, no tools, `max_tokens=16384`. `_build_analyst_user_message` injects `research_data`, the dimension weights, (in founder mode) the §0.5 block + spec with the focal R1/R13 waiver, and (on loop rounds) the `judge_critique`.
- **`judge_node`** — `gpt-4.1`, temp 0.1. **Disagreement-finder** (`get_judge_system_prompt(thesis_bias)`): pinpoints where A and B disagree and tells them to reconsider those points. `iteration = prior + 1`; force-consensus on the final round. Sets `judge_agreed` + `judge_critique` (formatted disagreement points) + `iterations`. **Does not score.**
- **`compile_report`** — `gemini-2.5-pro`, temp 0.15, `max_tokens=65536`, `COMPILE_SYSTEM_PROMPT`. (1) reconciles scores in code via `_extract_resolved_scores` → `_apply_moat_reconciliation` → `_compute_weighted_scores` → `_compute_expected_return`; (2) hands the compiler the authoritative numbers + mode-aware framing (VC vs Founder) + focal confidence; (3) merges both reports into the 13-section markdown; (4) emits + validates `market_map` + `financial_ledger` + `acquisitions` (`_extract_structured_artifacts` returns a 3-tuple); (5) appends the deterministic `_methodology_section` + `REPORT_DISCLAIMER` in code and computes `field_stats`. Returns a **new** `final_report` dict (`status:"completed"`), never mutating state in place.

### Helpers
- **`derive_scope(focal, context, settings)`** — one structured LLM call (`SCOPE_INFERENCE_SYSTEM`) → `{sector, market_prompt, rationale}` (string-guarded; `None` on failure).
- **`_extract_resolved_scores` / `_apply_moat_reconciliation` / `_compute_weighted_scores` / `_compute_expected_return`** — the in-code scoring pipeline (see *In-code invariants*).
- **`_focal_weak_spots(resolved_scores, moat_subscores, focal)`** — the focal startup's 2 weakest dimensions + 2 weakest moat sub-scores as a compiler-ready phrase (founder §0.5 anchors); name-matched via `_norm_name`, `""` when the focal has no usable scores.
- **`_today_note(role)`** — date-grounding line ("Today's date: …" + recency-arbitration rule) injected into the researcher/analyst/compiler/judge user messages, so the LLMs don't treat their training cutoff as "now".
- **`_research_manifest(messages)` / `_harvest_source_index(messages)`** — built from the researcher's ReAct transcript before it's discarded: a per-tool call audit (→ `final_report.research_manifest`, PROTOCOL SHORTFALL flag in the agent log) and an auto-generated Source Index of REAL transcript URLs appended to `research_data` (prevents fabricated Works Cited links). Duck-typed — no message-class imports.
- **`_compute_gradesheet(...)`** — per-startup letter gradesheet (A+…F / NR) — 6 cards matching a reference screenshot, honestly sourced (Market&Timing=market_urgency, Product&TechDepth=differentiated_technology, Regulatory&Compliance=regulatory_alignment, Financial Health&Cap-Eff=FH dim+`_capital_efficiency_score`, Traction&GTM=`_traction_score` stage-adjusted ledger rubric, Founder-Market Fit=founder_market_fit). All via `GRADE_BANDS`/`_grade_cell` (NR not F); Traction is the only absence→F card and only on affirmatively-disclosed zero/pre-revenue. Powers the UI Grades tab; no LLM grading.
- **`_data_freshness(md)`** — in-code evidence-recency audit of the compiled report (newest/oldest dated mention, count, months-lag vs today; bare years ignored) → `final_report.data_freshness`, rendered as the UI "Data as of" badge.
- **`_validate_market_map` / `_validate_financial_ledger` / `_validate_resolved_scores` / `_validate_moat_subscores` / `_validate_scenarios` / `_validate_acquisitions`** — coerce LLM JSON into render-safe shapes; drop malformed; incumbents/pre-PMF/focal handling; acquisitions must name target+acquirer (research-sourced only, ≤12 rows).
- **`_stage_retention(stage)` / `_scenario_dominance(scenarios)` / `_methodology_section(...)`** — the memo-adoption deterministic layer (2026-07-06): stage-banded dilution retention for the net return range, EV-dominance decomposition, and the code-built "## Methodology & Scope" section (search counts, source-tier distribution, freshness, debate telemetry, ARR-disclosure rate, an explicit NOT-diligenced list).
- **`_make_llm(model, temperature=0.2, max_tokens=8192)`** — provider factory keyed by model-ID prefix (`gemini`/`claude`/`gpt`|`o`/else→Groq).
- **`_normalize_content`** — coerces LLM `.content` (str or Anthropic-style block list) to a plain string.
- **`_last_balanced_json(text)`** — string-aware scanner returning the last top-level balanced `{...}` (via `json.JSONDecoder().raw_decode`), used to parse the judge/resolve/artifact JSON.
- **`_run_agent_with_retry` / `_invoke_llm_with_retry`** — up to 8 attempts on rate-limit/429/quota/`resource_exhausted` (agent variant also retries `tool_use_failed`); backoff from the provider hint, capped 900s.
- **`_parse_money` / `_norm_name`** — money/number parsing (finite-guarded) and normalized name matching across sections.

## Services layer (`backend/app/services/`)

- **`ingest.py`** — focal-startup document parsing. Hybrid: PyMuPDF text; sparse/image PDF pages and image files fall back to a **Gemini-vision** transcription; `.docx` via python-docx; `.txt`/`.md` direct. `extract_materials_cached` writes `_extracted.txt` so a deck is vision-parsed at most once (shared by the derive endpoint and the ingest node).
- **`scope.py`** — `infer_scope(focal, upload_id)`: materials-first (from the cache), else 1–2 Tavily searches on the name, then `nodes.derive_scope`. Returns `{market_prompt, sector, rationale, autoderived, source}`.
- **`store.py`** — durable file-based History store on the `reports` volume (`<id>.json` = meta + full report). `save_report` / `list_reports` (light meta, starred-first) / `get_report` / `update_meta` (label/star) / `delete_report`.

## HTTP API (`api/routes.py`)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/research` | enqueue a run; returns `task_id` |
| `GET /api/research/{task_id}` | poll status + final report |
| `GET /api/config` | deployment flags for the UI (auth_required, uploads_enabled) — unauthenticated |
| `POST /api/upload` | store focal-startup files on the `uploads` volume → `upload_id` (streamed caps; 403 in public-data mode) |
| `POST /api/derive-scope` | infer `{sector, market_prompt}` from a focal startup (confirm-first) |
| `GET /api/reports` | list saved analyses (History; light meta) |
| `GET /api/reports/{id}` | one saved analysis in full |
| `PATCH /api/reports/{id}` | rename (label) / star |
| `DELETE /api/reports/{id}` | delete |

`ResearchRequest.market_prompt` is optional when a focal startup is present (validated by a model validator).

**Auth:** with `API_KEYS` configured, every endpoint (except `GET /api/config`) requires `X-API-Key` (`services/auth.py`, constant-time compare); reports are owner-tagged and History list/get are per-owner filtered. Empty `API_KEYS` = auth disabled = pre-auth behavior. Stale Redis results expire via `result_expires` TTL (the wipe-all purge was removed).

## Model placement rationale

| Role | Model | Why |
|------|-------|-----|
| Researcher | `gemini-2.5-pro` | Reliable tool-calling, large context |
| Analyst A | `gemini-2.5-pro` | Strong general reasoning |
| Analyst B | `claude-sonnet-4-6` | **Different platform → genuinely independent opinion** |
| Judge / resolve | `gpt-4.1` | Neutral third platform, reliable JSON |
| Compiler / artifacts | `gemini-2.5-pro` | 65K output → single-pass merge |
| Vision (ingest) | `gemini-2.5-pro` | Multimodal transcription of deck pages |

## Debate loop semantics

1. Both analysts receive **identical** `research_data` and the **identical** system prompt; they diverge only because they run on different models.
2. The judge pinpoints contradictions/score mismatches and emits its verdict + disagreement points.
3. If `agreed=false` and `iterations < 3` → loop back to `analysts_fanout` (NOT ingest/researcher). Both analysts re-run with `judge_critique` injected.
4. Two independent stop conditions both reference `max_debate_iterations` (=3): the judge force-agrees on iteration 3, **and** `_should_loop` routes to the compiler when `iterations >= 3`. Hard-capped either way.
5. Final scoring is reconciled in code in `compile_report`, not by the judge.

## Execution & transport

The graph runs inside the Celery task `run_research_pipeline` (`worker/tasks.py`), streamed with `stream_mode="updates"`. Per update it skips `None` state, `.extend()`s logs, tracks `iterations`, captures `final_report`, and pushes `self.update_state("STARTED", meta={current_phase, iterations_completed, agent_logs[-20:]})`. **On completion it also persists the report to the History store** (`services/store.save_report`, best-effort). On `SUCCESS` it returns `{status, final_report, agent_logs, iterations_completed}`. Progress reaches the frontend by **polling** `GET /api/research/{task_id}` (no websocket/SSE). Celery limits: **soft 3000s / hard 3900s** (a full 3-round debate + 65K compile can run long).

## Infra

Docker Compose: redis, backend (FastAPI), celery-worker (`--concurrency=2`), frontend (Next.js). Two named volumes — **`uploads`** and **`reports`** — mounted into both backend and worker (`/data/uploads`, `/data/reports`; `UPLOADS_DIR`/`REPORTS_DIR`). Extra Python deps: `pymupdf`, `python-docx`, `python-multipart`. Images bake source (`COPY . .`) — **rebuild to pick up code changes**.
