# Known Issues & Tech Debt

> Running tracker for the VC Market Analysis Engine. When you fix something, move it to **§ Fixed** and update `CLAUDE.md` §9/§10 if it's referenced there.
>
> Latest batches: **2026-07-02** research freshness layer (stale-competitor fix) and **2026-07-01** founder-mode §0.5 Strategic Repositioning — both in **§ Added**, neither validated live yet. The 2026-07-01 feature batch (focal/founder mode, auto-scope, history, download, theme/layout) is in **§ Fixed**. What remains open is below.

---

## A. Output-quality (still open)

> **Status (2026-07-01):** the coherence-bug layer (R1, R3, R4/R5, R6/R7/R8, R10, R13) is **all fixed in code and validated live** (sim4/sim5/sim6 + the Fidea founder run) — see § Fixed. Codex graded runs **16–18/24 ("competent, not top-fund")**. What's left below is the *analytical-depth* gap and a few *prose-level* coherence contradictions — the harder, judgment-shaped work that separates "competent" from "top-fund."

### A-depth. Underwriting depth — the biggest remaining gap to top-fund *(rubric dims 2/3)*
- **R6′ — probability-weighted return is a false-precise point estimate.** *(Substantially CLOSED 2026-07-07 by the fund-math engine* — see "Added — 2026-07-07". The return is a RANGE + net-of-dilution range + per-scenario PATHS + EV-dominance + price-conditional verdict + CONDITIONS PRECEDENT, AND — when fund inputs are given — check → entry ownership → ownership-at-exit → proceeds → **turns-of-fund**, required-exit-to-return-fund, fund-returner/maker booleans, and net **IRR**; `_compute_fund_math`, 8 verified vectors.) **Residual (v2):** gross of fund fees/carry (no net-to-LP bridge), no reserves/follow-on modelling, a single stage-defaulted holding horizon for all scenarios, and `_STAGE_POST` (typical post by stage, used only to infer a missing entry post) is calibration-pending. The retention haircut remains a stated heuristic, not a per-round cap-table model.
- Sources are still mostly secondary landing pages, not primary/diligence-grade. Content depth, not a coherence bug.

### A-prose. Prose-level coherence contradictions (prompt-hardening candidates)
- **R9 — §4 thesis vs §12 exit value can disagree.** e.g. §4 says ~$50M ARR → offer >$1.5B while §12 base case has the same ~$50M ARR → only $500M–$1B exit.
- **R11 — recommended pick ≠ top-ranked, with no bridge.** When the INVEST pick isn't `ranking[0]` (e.g. Freed recommended over #1 Abridge), the report needs an explicit **valuation-adjusted framework** explaining why the lower-quality-scored company is the better *investment* (quality score vs price-adjusted return). The weighted index ranks on quality; price isn't in it.
- **R12 — map placement vs §8 profile can disagree.** e.g. a company described as "Full Workflow Automation" in §8 but plotted near the "Pure Scribing" end in §13.
- **R14 (minor) — map size-legend text vs render.** Legend says a company is BOLD CAPS but it renders normally.

### A3. Analyst debate tension doesn't surface in the final report
- **Symptom:** the compiled report reads as a single consensus voice; the genuine A-vs-B disagreement is invisible.
- **Root cause:** only `judge_critique` is passed back into the loop; the merged report has no structured channel carrying analyst-vs-analyst disagreement or `disputed_facts`. (The judge is now a disagreement-finder, so the raw material exists — it just isn't threaded into `final_report`.)
- **Fix idea:** thread a `disagreement_summary` into `final_report` and add a "Points of Contention" subsection to `COMPILE_SYSTEM_PROMPT`.
- **Files:** `backend/app/graph/prompts.py` (`COMPILE_SYSTEM_PROMPT`), `backend/app/graph/nodes.py` (`judge_node`, `compile_report`).

### A4. Works Cited missing source URLs  *(prompt-hardened — re-verify)*
- **Symptom:** the Works Cited section can lack the URLs the researcher actually found.
- **Status:** researcher/analyst/compile prompts carry source URLs into a numbered Works Cited (a strong "=== SOURCING (NON-NEGOTIABLE) ===" block exists), but it's prose-propagated, not structurally guaranteed. Recent live runs DO include URLs; if a run drops them, thread URLs as a structured field.
- **Files:** `backend/app/graph/prompts.py`.

---

## B. Feature fast-follows (nice-to-have, scoped)

### B-mapfile. Draw the market-map SVG into the STANDALONE file exports
- Today the **in-app Print → PDF** (Download menu) includes the market map (renders `PrintableReport` with the real SVG). But the **CLI/file exporters** (`scripts/format_report.py` → `scripts/report_to_html.py`) are **text + tables only** — a shared `.md`/`.pdf` produced from the CLI has no map.
- **Fix idea:** port the 2×2 scatter to an inline SVG in `report_to_html.py` (positions from 0–100 coords, dots sized by funding, colored by score, axis + quadrant labels). ~1–2 hrs; self-contained. Also cheap: scorecard heatmap + leaderboard bars as light tables.

### B-deploy. Ship it as a portfolio piece
- The app is a **portfolio piece** (not being raised for). Highest-leverage remaining work is **packaging**, not features:
  - **Deploy `/demo` publicly** (Vercel frontend — the demo mode is backend-free, so it works standalone). Decide the root `/` behavior (needs the live backend to actually run an analysis).
  - **Case-study README** — problem → architecture diagram → the 3–4 hardest decisions (multi-model consensus, determinism-in-code, the adversarial eval loop, self-healing scope) → the eval methodology (Codex rubric grading) → results/screenshots.

---

## C. Infra & robustness (still open)

### C2. ~~`_purge_stale_results` wipes ALL Redis task results on every submit~~ ✅ FIXED 2026-07-06
- Purge removed; `result_expires=259200` TTL in `celery_app.py` + explicit ack/prefetch settings. Concurrent in-flight runs no longer clobber each other.

### C3. Unpinned LLM dependencies *(backend ✅ FIXED 2026-07-06 — langchain/langgraph family pinned to the known-good image versions)*
- Remaining: the frontend `Dockerfile` still `npm install`s without a lockfile (commit a package-lock.json to finish this).

### C4. No Redis persistence
- `docker-compose.yml` defines no volume for redis, so a restart wipes in-flight task state and stored results. (Completed reports survive — they're on the `reports` volume — but a run *in progress* during a restart is lost.)
- **File:** `docker-compose.yml`.

### C5. Dev-mode deployment only
- `uvicorn --reload` and `npm run dev`; no `next build`/`start`, no gunicorn/worker tuning, no resource limits, no `service_healthy` gate, no auth on any endpoint. (Relevant to B-deploy.)
- **Files:** `docker-compose.yml`, both `Dockerfile`s.

### C10. Auto-scope can misidentify a stealth startup with an ambiguous name
- **Observed live (2026-07-02):** a founder-mode API run for "Fidea" (stealth agent-auth startup, no uploaded materials, blank prompt) self-healed its scope to "Digital Asset Wealth Management & Crypto Custody" — the name-only Tavily grounding found a different Fidea. The **confirm-first UI flow catches this** (the derived scope is shown for review before launch); the risk is the `ingest_focal` self-heal path (direct API calls / blank prompt), which proceeds unreviewed.
- **Mitigations:** attach materials (materials-first inference is accurate), or pass an explicit `market_prompt`. **Fix idea:** when scope inference is search-grounded (not materials-grounded) AND the startup has thin public presence, have `infer_scope` flag low confidence and either fail the run with a clear message or force the derive-scope confirmation.
- **Files:** `backend/app/services/scope.py`, `backend/app/graph/nodes.py` (`ingest_focal_materials`).

### C7. Live progress shows only the last 20 logs
- While `STARTED`, `agent_logs` is truncated to `[-20:]`; the full set only appears on `SUCCESS`.
- **File:** `backend/app/worker/tasks.py`.

---

## Added — 2026-07-09 (differentiation batch — call-claim audit · cap-table fund math · longitudinal re-run)

Three features chosen explicitly because a chat AI structurally cannot replicate them (proprietary
inputs, deterministic math, state over time). All backend logic follows the R-series philosophy —
LLMs supply judgment, code does arithmetic/joins/deadline logic. Token-free coverage grew 491 → **576**
(new: `test_captable.py` 30, `test_call_claims.py` 26, `test_delta.py` 29); all 13 suites green;
tsc clean; rebuilt + smoke-checked. **Not yet validated on a live run** — the first founder-mode run
with a call recording + cap-table CSV, and the first re-run of a saved report, should be watched.

- **Founder-call claim audit (flagship).** Upload a meeting recording (`.mp3/.m4a/.wav/.webm` ≤25MB —
  transcribed via OpenAI `whisper-1` with [mm:ss] segment stamps) or a `.vtt/.srt`/name-hinted
  transcript. Ingest tags chunks `[CALL TRANSCRIPT]`; `_extract_call_claims` pulls ≤12 falsifiable
  claims (validated in code); the researcher's Phase-0 audit gains a per-claim verification pass
  (choreography updated); `_audit_call_claims` then cross-examines every claim against the research
  brief AND the deck — statuses verified / contradicted / vendor-only / unsupported plus
  `deck_conflict` (call-vs-deck inconsistency, deliberately hunted). Verdicts join back onto the
  REAL claims in code (`_validate_claim_audit` — order-fallback join, hallucinated rows dropped,
  counts computed in code) → `final_report.call_claims_audit`, a **Claims** tab, PDF Appendix D,
  and a compiler note that weaves CONTRADICTED/DECK-CONFLICT findings into §9/§11 verbatim.
- **Cap-table CSV → grounded fund math.** `services/captable.py` parses a round-history CSV
  (flexible headers; $5M / 5,000,000 / 1.2B / 750K all normalize to $M in code; missing post
  derived as pre + raised). Entry-post precedence is now user input > cap table (gated on the
  scenarios describing the focal, flag `post_from_cap_table`) > resolve-emitted > stage-inferred —
  so "does this return MY fund?" runs on real terms, not `_STAGE_POST` guesses. The focal's ledger
  row backfills missing raised/valuation from it (fills only, never overwrites); a cap-table block
  renders in Financials + the PDF; the compiler grounds §6/§12 on it tagged "(per cap table)".
- **Longitudinal re-run + prediction self-grading.** History records now persist `request_params`;
  `POST /api/reports/{id}/rerun` re-executes a saved run on identical inputs with
  `baseline_report_id`. After compile, the worker computes `run_delta` PURE-CODE
  (`services/delta.py`: entered/exited, rank+score movers, ledger money deltas >2%, new
  acquisitions, pick/EV change; containment name-matching ≥4 chars) and grades the baseline's own
  dated predictions (§0 binary variable, §4 dated prediction, §11 kill criteria, §12 conditions)
  against the fresh evidence — one judge-model call, then `validate_prediction_audit` enforces the
  calendar IN CODE (future deadline ≠ broken/unresolved → pending; passed 'pending' → unresolved;
  silence on a passed deadline = unresolved, never broken). → `final_report.run_delta` /
  `prediction_audit` / `baseline_id`, a "What changed since the baseline" panel, a ↻ re-run button
  per History row, PDF Appendix E. Legacy records without stored params 400 with a clear message.
- **Known v1 limits:** whisper caps audio at ~25MB (≈50 min of m4a) and diarization is not modelled
  (claims are attributed to "the founder"); cap-table parsing is round-history-level (no per-class
  share math — future dilution stays the stage-banded retention heuristic); prediction extraction
  quality depends on the baseline actually containing dated commitments (older reports may yield
  few rows); re-run compares only against the SINGLE chosen baseline, not the whole chain.

## Added — 2026-07-07 (Fable-benchmark consensus batch — pipeline vs frontier-soloist gap closure)

A Fable-authored solo memo on the same deal (deck + live web) was compared head-to-head against the pipeline's report by a 4-judge panel (judgment / decision-usefulness / technical depth / craft), every proposed change adversarially validated against the already-shipped fix stack (26/28 confirmed net-new). Verdict: the gap traces to two root causes — research-supply (the researcher never queried incumbent roadmaps/protocol standards/deck claims) and calibration rules (no base-rate anchor, one-way M&A tape reading). All 8 consensus prompt changes + 3 of 4 architecture changes implemented (#4, compiler-edits-stronger-memo, parked pending an A/B harness):

- **Research supply (choreography):** per-incumbent PRODUCT-ROADMAP sweeps (quoted ship-date language; absence citable) + PROTOCOL/STANDARDS sweeps (MCP/OAuth-extension class) feeding the starved WINDOW CLOCK; conditional Phase 0 deck-claim audit (verified-independent / vendor-origin / unverifiable per claim); mandatory per-startup architecture follow-up when differentiation is capability-based; per-acquisition date + target-total-raised fetch. Coverage checklist + call budget (~36-48) updated.
- **Calibration (template/prompts):** BASE-RATE ANCHOR (probabilities cite a named stage cohort rate — new OUTCOME BASE RATES table in STAGE_BENCHMARKS — and outliers >30x justify against the tape's ceiling); two-sided M&A tape rule (absorption vs coronation, buyer depletion net of build-not-buy incumbents); binary-variable LOAD-BEARING test; founder-mode variant-view-must-diverge-from-deck; WHAT WE MUST BELIEVE tagged ledger + NEXT DILIGENCE STEPS closers; capability-verified map placement ("(claimed, per deck — unshipped)" focal carve-out); founder MECHANISM RED-TEAM (per-mechanism attack surface, deck-internal contradictions, second-meeting objections + pre-emptive artifacts) + IP-PROVENANCE flag + ONE-TELLING dedup rule; resolve example weights annotated format-only; _dom_note defends tail dominance against the cited base rate.
- **Architecture (code):** exit-dollar-derived scenario multiples (`_validate_scenarios`: exit ÷ entry computed in code, fills missing multiples, OVERRIDES stated ones off by >25%, tagged multiple_source); pre-compile `exit_tape` (resolve now emits it — post-compile acquisitions arrive too late to inform §12) with `_acq_multiple_on_capital` computed in code and cited verbatim; entry-post precedence (user fund_economics wins, resolve-emitted post fills gaps); deterministic ARITHMETIC LINT (`_lint_arithmetic`, "A × B = C" product claims, %-aware, range-safe) + one-round section-scoped REPAIR pass with invariant guards (re-lint, citation count, header, 0.5-2.0x length) — the _sanitize_citations pattern applied to the SAM-10x error class. `_extract_resolved_scores` widened to a 7-tuple (all stubs updated); resolve max_tokens 4096→6144; §3 added to the resolve slice.
- **Verification:** suites grew to **491 checks** (structured_artifacts 82→103 incl. lint/repair/tape/exit-derived; trust 72→76), all green; tsc clean; rebuilt + in-container smoke (lint + tape math live). Artifacts: reports/fable_fidea_memo_2026-07-07.md (the benchmark memo), consensus in the session workflow logs.
- **Accepted capability limits (not chased):** single-author throughline, unprompted security-insight density, reliable deck-internal contradiction detection — instructions shipped, partial returns expected.

## Added — 2026-07-07 (editorial rigor pass — elite-VC-editor critique → prompt hardening)

An expert-agent panel of IC-veteran editors red-lined the latest live report against a TOP-FUND bar (5 lenses: what's missing / what to cut / decision-usefulness / section-by-section / craft & voice; each finding double-validated as *real* AND *elite-bar-worthy* — 27 of 35 confirmed). Honest verdict: the draft lands ~16-18/24 ("smart associate, not IC-ready partner") and the dominant lever is **adding rigor, not trimming**. The generalizable, net-new rules were folded into `prompts.py` + `nodes.py` (findings the earlier batches already fixed — binary-variable contradiction, §0/§0.5 decimal precision, amount-raised≠valuation — were skipped to avoid duplication; that report predated them). All prompt-level so they lift EVERY future report:

- **ADD rigor:** §2 founder-mode bottoms-up model (pricing unit + land/expand ACV + a logos×ACV bridge that must arithmetically equal the §12 ARR milestone); §12 runway-to-milestone check (raise ÷ implied burn vs months-to-milestone, computed in prose); §3 THREAT COMPLETENESS (any named falsifier/threat, and in founder mode the ecosystem incumbent, MUST appear in the §3 matrix AND the §12 acquirer list — the "Salesforce named as the only falsifier but absent from the matrix and exits" miss); §4 OCCUPANCY TEST (can't call a §5 quadrant "white space" if a ranked leader/>$500M-exit already sits there); §8 ARCHITECTURE LIABILITY (a thesis resting on an architectural choice must state that choice's own costs — latency/SPOF/blast-radius for in-path — and why competitors chose otherwise); §11 mandatory TEAM/EXECUTION risk line for ≤3-person / pre-Series-A teams (key-person / bus-factor).
- **DEEPEN:** §12 leads with the BASE case + labels the blend "tail-dominated" when a non-base scenario carries >50% of EV (computed in code from `_scenario_dominance`, injected via `_dom_note`); §0 VOICE ban ("never open with 'This report assesses…'"; deck-only claims voiced as unproven bets, not asserted facts); §7 EARN-THE-MOAT-SCORE (a deck-only company can't out-score a shipping peer on Differentiated Technology without a §8 head-to-head, else the sub-score is capped); §8 interrogate capital-efficiency/build-speed claims for the moat they may contradict; §9 comparative (rank founder-market-fit, don't re-list §8 bios).
- **CUT bloat:** HONEST CAVEATS changed from per-section mandatory to a report-level cap (≤3, paste-test-guarded — no swap-the-name filler, no restating a §3/§11 risk); §6 dead-column collapse (drop any ledger column that's "Not Disclosed" for every startup); §5 restatement cut (define axes + name only non-obvious placement disputes).
- **Verification:** `test_trust.py` +2 (tail-dominated headline logic), `test_repositioning.py` +1 (runway line); full suite **465** green; rebuilt + live. Net length ≈ flat — denser and more decision-bearing, not longer.

## Added — 2026-07-07 (deterministic fund-math engine — "does THIS deal return MY fund?")

The single highest-leverage item from the VC-platform deep research (S-tier), and the answer to R6′'s core gap: the same startup is a pass for a $500M fund and a fund-maker for a $50M fund, and the tool couldn't tell them apart. **Designed and adversarially verified by an expert-agent panel before a line of code** (3 independent VC-financial-math designs → synthesis → 4 verifiers each recomputing a shared worked example from scratch → final spec with hand-cross-checked test vectors; verdicts sound/fixable/sound/fixable, no "broken").

- **What it computes (all in code, `_compute_fund_math` + helpers in nodes.py):** entry ownership = check/post; ownership-at-exit = ownership × `_stage_retention`; per-scenario gross/net proceeds ($M); turns-of-fund; **required exit value to return the fund** = fraction × fund / ownership-at-exit; `required_net_MoIC` / `required_gross_MoIC`; `can_return_fund` / `expected_returns_fund` / `is_fund_maker` booleans; net IRR (primary = IRR of the expected multiple, secondary = prob-weighted mean, both disclosed).
- **Reconciliation is structural, not asserted:** retention ρ is constant across scenarios, so `E[net_MoIC] = ρ × E[gross_MoIC] = ρ × expected_return` — exactly the already-shipped `expected_return_net_*` midpoint. The engine is the SAME dilution haircut monetized through ownership and dollars; it is impossible for it to contradict the shipped net range (a test asserts the identity).
- **Inputs:** optional `FundEconomics` submodel on `ResearchRequest` (fund_size / check / entry_post_money / target_ownership_pct / holding_years, all $M; + optional returner-fraction & fund-multiple bars), threaded through `ResearchState.fund_economics` and the Celery task. **Master gate:** absent fund_size → `final_report.fund_math` is None and the existing gross/net ranges render unchanged. Optional-degrades everywhere (missing post inferred from stage via `_STAGE_POST`; missing hold stage-defaulted via `_STAGE_HOLD`).
- **Robustness (verifier-driven):** the ownership>100% clamp is DISPLAY-only (internal math uses the true unclamped ratio so the reconciliation identity holds); the total-loss floor (−100% IRR) is applied BEFORE the power op (no complex numbers); sub-quarter horizons suppress IRR; every degenerate input coerces to None (JSON-safe); nine in-code flags surface assumptions (post_inferred, ownership_infeasible, retention_defaulted, unit_suspect, holding_too_short, …).
- **Anti-double-count guard (residual risk #1):** the analyst/compiler §12 prompt now DEFINES the scenario multiple as the GROSS, pre-dilution MoIC (= exit value ÷ entry post-money), so the code's retention haircut isn't applied on top of an already-diluted figure.
- **UI:** `FundEconomics` types + an optional "Fund Economics" card on the form (`ResearchForm`); a "Fund Fit — does this return the fund?" panel in the Financials tab (`FinancialLedger`) rendering the code-computed scenario table, verdict one-liners, and flag footnotes; a §12 "Fund Fit" subsection (compiler renders the code-computed strings verbatim).
- **Verification:** `test_fund_math.py` — 8 hand-verified worked vectors (shared example + tiny-fund-flips-returner + master-gate + ownership-infeasible + partial-degrade + total-loss + short-horizon + prob-renormalization) + the reconciliation identity = 53 checks. Full suite 463 green; tsc clean; live-smoked in-container with the real pydantic model.
- **Deferred to v2 (named in-code, not silently omitted):** net-to-LP bridge (fund fees/carry), reserves/follow-on modelling, per-scenario holding horizons, `_STAGE_POST` calibration vs 2025/26 benchmarks.

## Added — 2026-07-06 (memo-grade underwriting layer — FideaAnalysis.pdf adoption batch)

All 12 ranked adoption items from the side-by-side against an institutional IC memo (`~/Documents/FideaAnalysis.pdf`), implemented as judgment rules in `prompts.py` + a deterministic layer in `nodes.py` (per the R-series philosophy: every number the LLM shouldn't own is computed in code). Token-free coverage: `test_trust.py` grew 44→60 and `test_structured_artifacts.py` 73→76; all 9 suites green (**377 checks**); tsc clean on live source. A 24-agent adversarial review (4 dimensions × per-finding refutation) confirmed 9 findings, all fixed: the REPORT_DISCLAIMER/terms/print texts no longer claim all returns are gross (net figures exist now); the GRADE BRIDGE pick-lookup uses tolerant _norm_name matching (founder-mode name variants); `"path": null` no longer renders a literal "None"; the net note words degenerate (point-only) EVs as a single figure, not an "X–X range"; STRUCTURED_ARTIFACTS_SYSTEM says THREE artifacts; `_parse_money` scales by the unit ATTACHED to the number (K→/1000, so a $750K row can't inflate the disclosed-capital hero card 1000×); ReportViewer's click-to-profile prefers h3/h4 so verdict-bearing h2 headers can't hijack the scroll; two doc claims corrected (retention band 60–85%, test counts).

- **Verdict quality (§0/§12):** PRICE-CONDITIONAL VERDICT (invest **at/below a stated valuation**; "(assumed; no formal ask)" when none is public); 3–5 measurable + dated **CONDITIONS PRECEDENT** (gated on low confidence / EXISTENTIAL risks); **WHY NOT PASS — AND WHY NOT MORE** dialectic (each objection tagged priced / conditioned / cuts-both-ways); §0 capped at three sentences and must **NAME THE BINARY VARIABLE** the whole bet turns on.
- **Return math (code):** `_stage_retention` (stage-banded dilution-to-exit retention, default 0.70) → `expected_return_net_low/high` + `return_assumptions` (presented as "net of estimated future dilution", never replacing the gross range); `_scenario_dominance` → `return_dominance` (e.g. "60% of EV sits in the base case") + a compiler belief-requirement sentence; per-scenario **`path`** ("who buys / what happens") carried through `_validate_scenarios`.
- **Evidence devices:** `acquisitions` structured artifact (`_validate_acquisitions`, research-sourced only, never invented) → Exit-Precedents table (UI + exports) + the **exit-precedent floor** rule (DOWNSIDE must cite the weakest named comparable deal); severity-tagged risks (EXISTENTIAL/HIGH/MEDIUM) with **RESIDUAL** lines (§11); THE CATALYST + bimodal-sizing honesty (§2); THE WINDOW CLOCK (§3); verdict-bearing section headers (canonical `## N. Name` prefix preserved for the section parser).
- **Deterministic transparency:** `_methodology_section` — a code-built "## Methodology & Scope" (search counts by tool, source-tier distribution, freshness, debate rounds/models, focal-materials presence, ARR-disclosure rate, an explicit **NOT diligenced** list) appended before the disclaimer, so scope honesty never depends on the LLM; `field_stats` (startups / incumbents / disclosed capital / ARR-disclosure) → hero-stat cards in the ReportViewer; **GRADE BRIDGE** — when the pick has failing (<35) dimensions the compiler must classify each as buyable-with-the-round vs structural.
- **Files:** `graph/prompts.py`, `graph/nodes.py` (`_extract_structured_artifacts` now returns a 3-tuple — test stubs updated), `lib/api.ts`, `report/FinancialLedger.tsx` (paths/net/dominance/acquisitions), `ReportViewer.tsx` (hero cards), `lib/exportReport.ts` (+Appendix D), `PrintableReport.tsx`.
- **Not adopted (deliberate):** IRR/fund-returner math (needs check-size input — see R6′ remainder), memo-style "we spoke to N customers" claims (no primary diligence channel exists; the methodology section says so instead of faking it).

## Added — 2026-07-06 (VC-readiness trust + security layer)

The full pre-pitch checklist from the VC-readiness review, implemented in one batch and then hardened by a 3-lens adversarial review (token-free coverage: `test_trust.py` 44/44; all 9 suites = ~358 checks green; tsc clean; live-smoked with auth on AND off). Review fixes that rode along: prod compose `ports: !override []` (plain `ports: []` does NOT unpublish — merged config verified to expose ONLY caddy 80/443); owner-scoped task polling (a leaked task_id no longer exposes another tenant's report for the result-TTL window); legacy (pre-auth) reports are READ-ONLY for authed users (mutation requires exact owner); non-ASCII API keys 401 instead of 500 (bytes compare_digest); Content-Length 413 gate in main.py + Caddy request_body cap (Starlette spools bodies before deps run); upload cleanup on ANY failure (BaseException) + index-prefixed stored names (no `_`-prefix ingest skips, no collisions); `recommended_pick` canonicalized against the ranked universe (variant/incumbent names can't become the badge) and = the SUBJECT in founder mode; `_ledger_confidence` no longer counts the code-derived Val/ARR column and re-keys to canonical names; hostname-based source tiering (?ref=sec.gov can't launder a mill link); the .md/CLI exports + printed PDF now carry the pick/range/disclaimer too; Leaderboard shows ≈ for low-disclosure names; ReportViewer hooks order fixed.

- **Trust/accuracy:** `REPORT_DISCLAIMER` appended to every report IN CODE (both compile paths) + UI banner + `/terms` page; `expected_return_low/high` — the return is now presented as an honest RANGE with stated assumptions (gross, pre-dilution), never a lone point estimate (kills the "6.05x on a Not-Disclosed entry" failure); `recommended_pick` threads the report's own §0/§12 pick to the UI/History "Top pick" badge (R11 header-vs-§0 contradiction is now structurally impossible) + compiler rules for the quality-vs-price bridge and §4↔§12 reconciliation; `_source_tier` labels every Source Index URL (official/wire > press > unverified > report-mill) with weak-source discipline; `_ledger_confidence` bands score precision by ledger disclosure (≈approximate scores + "low data" chips for low-disclosure startups; low-confidence focal rows presented as "disclosure-limited").
- **Security/data:** pilot API-key auth (`services/auth.py`, `API_KEYS` env, X-API-Key header, constant-time compare; **empty = disabled = pre-auth behavior**) with per-owner report tagging + filtered History (legacy ownerless records visible to all authed users); `UPLOADS_ENABLED=false` = public-data mode (403 + hidden dropzone via new `GET /api/config`); uploads now streamed with per-file AND per-request aggregate caps, full cleanup on rejection, self-contained `_safe_filename`.
- **Reliability/ops:** `_purge_stale_results` REMOVED → `result_expires` TTL (fixes **C2**: concurrent in-flight runs no longer clobber each other) + explicit ack semantics (`task_acks_late=False`, `worker_prefetch_multiplier=1`, `visibility_timeout=4500` — the ghost-task redelivery class); langchain/langgraph family PINNED to the known-good image versions (fixes **C3** backend half); `docker-compose.prod.yml` + `deploy/Caddyfile` (fixes **C5**: prod uvicorn ×2 workers, `next build && next start`, TLS via Caddy, healthchecks, restart policies, redis AOF persistence volume — addresses **C4**); History store hardened (atomic tmp+rename writes, None-safe meta — one bad record can't 500 the list).
- **Not in scope (still roadmap, gated for confidential data):** DPAs/zero-retention provider terms, SOC 2, tenant encryption, audit logging, SSO — required before any confidential-deck tier; public-data mode is the honest pilot posture until then.

## Added — 2026-07-05 (visual Gradesheet tab — per-startup letter grades, computed in code)

New **Grades** tab in the ReportViewer: a per-startup A+…F letter gradesheet, **computed 100% in code** from the already-reconciled scores (no LLM grading, so it can never disagree with the scorecard). `GRADE_BANDS` in `nodes.py` IS the coded rubric; `_compute_gradesheet` builds `final_report.gradesheet`. **Six cards matching a reference screenshot the user liked, honestly sourced** — a design panel (VC / impl / honesty-skeptic lenses) resolved that 3 of the 6 were repo-derived (Product depth, Security posture, Engineering quality) and can't be honestly proxied without git: Market & Timing (`market_urgency`), Product & Tech Depth (`differentiated_technology` moat sub — renamed, NOT a package audit), Regulatory & Compliance (`regulatory_alignment` — renamed off 'Security posture', all pen-test/findings language dropped), Financial Health & Capital Efficiency (mean of FH dim + coded R40/burn — REPLACES the repo-only 'Engineering quality', disclosed swap), Traction & GTM (`_traction_score` stage-adjusted ledger rubric — the ONLY absence→F card, and only on affirmatively-disclosed zero/pre-revenue), Founder-Market Fit (`founder_market_fit` — continuity/key-person out of scope). **NR** never F for undisclosed. Verified on the live Fidea field (Oasis B+; Fidea: Founder-Market-Fit B+, Financial Health F, Traction NR since no deck disclosed zero). `test_gradesheet.py` 45/45; all suites green (~314 checks). Files: `graph/nodes.py`, `lib/api.ts`, `lib/viz.ts` (`gradeColor`), `components/report/Gradesheet.tsx`, `components/ReportViewer.tsx`.
- Deliberately NOT git/repo-derived (the "engineering evidence" cards from the design discussion were dropped) — grades come only from the pipeline's existing reconciled data.

## Added — 2026-07-02 (Google-grounded precision search — search_google_live)

Motivated by a Gemini-app critique of the Fidea rerun: the same gemini-2.5-pro model produced fresher facts in Google's harness because of **retrieval, not weights** (Google Search grounding + full-page depth vs ~25 Tavily snippet searches). New 7th researcher tool `search_google_live` = Gemini's server-side **Grounding with Google Search**, wrapped as a **nested standalone LLM call** (the API doesn't reliably mix the built-in google_search tool with client-side function declarations in one request, so it is never bound on the ReAct agent directly). Verified live in-container before building: grounded answers return with real source chunks. All suites green.

**✅ VALIDATED LIVE (2026-07-03, third Fidea agent-IAM run — A/B vs the 07-02 run):** manifest shows full protocol compliance (41 searches: 6 financial+raw-content, 6 latest-news, **10 grounded** incl. per-incumbent sweeps, 0 failed). Every stale item the Gemini critique flagged got fixed: Oasis ledger now **~$700M** valuation (was ">$1B"; matches the critique's post-money figure), the **consolidation wave is fully covered** (Astrix→Cisco, Entro→SailPoint, Veza→ServiceNow named as acquired players and excluded from the ranked field; Palo Alto's ~$25B CyberArk acquisition reflected — CyberArk reclassified under PANW as an incumbent), and exit math anchors to real strategic multiples from those deals. Works Cited: **0 of 15 URLs untraceable** (was 7 of 7 fabricated). Debate converged (17→7, forced round 3) instead of exploding.

- **Choreography:** per-startup PRECISION CHECK (exact latest round / post-money valuation / M&A status — grounded answer is the authority) + a Phase-4 CONSOLIDATION SWEEP ("which <sector> startups were acquired, by whom, at what price") + one PER-INCUMBENT acquisition sweep ("<incumbent> acquisitions <sector> <years>") — targets the two live-run misses: valuation precision ($700M post vs ">$1B") and the platform-consolidation blind spot. Phases now sum ~33-42 calls (floor stays ≥20; recursion_limit=100 has headroom).
- **Deeper Tavily reads (same batch):** `search_startup_financials` now requests `include_raw_content` and injects a capped 2.5K-char page-body excerpt per source (paragraph-level financials never survive into snippets); `search_latest_news` query gained acquisition/acquired/merger terms.
- **Observability + freshness audit (same batch):** `_research_manifest` (tool-call counts from the ReAct transcript → `final_report.research_manifest`, PROTOCOL SHORTFALL agent-log flag), `_harvest_source_index` (real transcript URLs → "Source Index" appended to `research_data` — closes the **fabricated Works Cited** finding from the 2026-07-02 E2E analysis: the compiler had invented 7 URLs from memory because the real ones were discarded with the transcript), `_data_freshness` (newest/oldest dated mention + months-lag → `final_report.data_freshness` + a "Data as of" ReportViewer badge, amber when newest evidence >6mo old), per-call Tavily/grounded logging, and a compiler data-as-of stamp in §0. `test_freshness.py` 65/65.
- **✅ VALIDATED LIVE (2026-07-03 run):** manifest emitted and matched the independently-logged call stream (41=41); brief carried 82 URLs in prose + a 100-URL Source Index (was 0 URLs); Works Cited fully traceable (0 fabricated); data-as-of stamp rendered. One audit flaw found+fixed live: future-dated predictions ("by October 2027") counted as newest evidence — `_data_freshness` now bounds mentions to the current month.
- **Plumbing:** `_grounded_search`/`_make_grounded_llm`/`_resolve_redirect` in `tools.py`; grounding sources arrive as Google redirect URLs → resolved via HEAD (3s timeout, redirect fallback) so Works Cited carries real links. Gated by `GROUNDED_SEARCH` (config, default true) + Gemini-researcher prefix check; degrades to a note on any failure. Costs Gemini grounding quota (free daily tier ≈ 1,500), zero Tavily credits.

## Added — 2026-07-02 (research freshness layer — stale-competitor fix)

Root cause of stale competitor data in live runs (seen in the Fidea founder run): **no agent knew the current date** (LLMs default to their training-cutoff sense of "now" and backfill from memory), **publication dates were discarded** by `_tavily_search`, and **nothing requested recency** from Tavily. Fixed at the researcher/tools layer so the whole pipeline inherits it (analysts have no tools). Token-free coverage: `test_freshness.py` 32/32; all prior suites green.

**✅ VALIDATED LIVE (2026-07-02, Fidea agent-IAM founder rerun, 25 min end-to-end, researcher ~4 min):** the brief carried dated rounds inline ("Oasis $120M (Mar 2026)", "Token Security $20M (Jan 2025)"), used the "date not stated" fallback, honestly aged old data ("Teleport $1.1B as of Apr 2022"), and surfaced same-week M&A intel (Cisco reportedly in talks to acquire Astrix — the previous run's #2). The ranked field refreshed materially vs the 07-01 run (Zenity, Token Security, Clutch Security in; Astrix out on the acquisition news). §6 ledger cells stayed bare point estimates (dates in prose only). *Observations:* the literal "(published:)" tags don't survive verbatim into the brief — the researcher rewrites them as inline dates (fine; the dates are the point); the judge found 6 disagreements in round 1 but 35 in round 2 (convergence explosion — invisible without A3's structured disagreement channel; worth watching). An adversarial 3-lens review then caught + fixed: a **blocker** (the ≥20-call mandate exceeded LangGraph's default `recursion_limit=25` ≈ 12 sequential tool rounds — `_run_agent_with_retry` now invokes with `recursion_limit=100`), date-fabrication pressure (as-of dates are now conditional: "(date not stated)" fallback, never invented — general-topic Tavily results are often undated), ledger-cell pollution (as-of dates scoped to prose, never table cells), **judge date grounding** (the one agent that could re-inject stale figures via debate arbitration — now dated + told never to arbitrate from memory), compiler `_today_note` referencing research data it never receives (own branch now), researcher output 32768→65536 (bigger briefs; truncation was a prior failure), `search_latest_news` at basic depth (1 credit vs 2), and a distinctive quota-exhausted marker (stop-retrying signal instead of 20 silent failures).

- **Date grounding:** `_today_note(role)` (`nodes.py`) injects "Today's date: …" + a recency-arbitration rule into the researcher, analyst, and compiler user messages; researcher/analyst/compiler prompts ban time-sensitive figures from model memory.
- **Publication dates:** `_tavily_search` now emits "(published: <date>)" per source when Tavily returns one (always for news topic); `services/scope.py` inherits it for free.
- **Freshness pass:** new 6th tool `search_latest_news(startup)` — news topic, past 365 days — mandatory once per deep-dived startup (Phase 2 of the choreography); protocol minimum raised ≥14 → **≥20 calls** (~25-30 Tavily calls/run, still fine on the 1,000/mo free tier).
- **Recency arbitration:** RECENCY DISCIPLINE block (researcher) + RECENCY sourcing rule (shared template → analysts + compiler): newest source wins, older figure noted with its date, never averaged.
- Files: `graph/tools.py`, `graph/nodes.py` (`_today_note`, 3 message builders), `graph/prompts.py` (choreography, researcher rules, sourcing block), `backend/tests/test_freshness.py`.
- **Escalation if still insufficient after a live run:** a dedicated freshness-verifier node after the researcher that re-checks the brief's key figures per startup (deliberately NOT built yet — prompt+plumbing fix first).

## Added — 2026-07-01 (founder-mode §0.5 Strategic Repositioning)

New founder-mode-only report section: `## 0.5 Strategic Repositioning — What to Change, What to Keep`, rendered immediately after §0 — how the founder's startup should be TWEAKED to fit the market better and maximize fundability. `test_repositioning.py` 41/41, all prior suites green; adversarially reviewed by a 3-lens multi-agent pass, all findings fixed.

**✅ VALIDATED LIVE (2026-07-02, Fidea agent-IAM founder rerun):** §0.5 rendered exactly after §0 with the pinned heading; moves follow the full 4-element anatomy (named weak-dimension targets citing the system scores VERBATIM — 17.0/16.8 matched `resolved_scores` to the decimal; named competitor evidence; dated falsifiers; cost statements), exactly one "What NOT to change", and the low-confidence "(assumed)" tag in use. *Observation (anchor softness):* the compiler skipped Financial Health (15.0, the listed weakest dim — meaningless for a stealth pre-seed with no financials) in favor of a well-evidenced Founder-Market Fit move (17.0, 3rd-weakest) — evidence won over the anchor, consistent with the "do not fabricate" instruction; acceptable, but tighten the anchor language if strict compliance is wanted.

- **Shape:** 2–4 repositioning moves max, each ONE dense paragraph with four elements — TARGET (a named weakest dimension/moat sub-score), EVIDENCE (named competitor gap / benchmark band / regulatory item / §4 white space), FUNDABILITY EFFECT (directional only + the partner objection it removes + a research-sourced comparable), COST & FALSIFIER — plus exactly ONE "What NOT to change". Anti-slop: the PASTE TEST + a banned-phrase list; low-confidence focal claims must be tagged "(per founder materials)"/"(assumed)".
- **Plumbing:** spec = `FOUNDER_REPOSITIONING_SECTION` (`prompts.py`), injected founder-only into (a) both analysts' user message (with the explicit R1/R13 waiver so an early-stage focal can't be watchlisted out of its own §0.5 anchor; analysts draft §0.5 LAST so their scorecard exists first — placement after §0 is the compiler's job) and (b) the compiler's founder `focal_note` — never into the shared template (zero VC-mode leak surface). Compiler anchors are **computed in code**: `_focal_weak_spots` (2 weakest dims + 2 weakest moat sub-scores, rendered VERBATIM at stored 1-decimal precision; three-way fallback: anchored / focal-missing-from-good-scorecard / nothing-reconciled). Judge user message: mere §0.5 divergence is synthesis material, not a disagreement (fact/score contradictions still count). Files: `graph/prompts.py`, `graph/nodes.py` (`_focal_weak_spots`, `_build_analyst_user_message`, `judge_node`, `compile_report`), `backend/tests/test_repositioning.py`.
- **Hardening that rode along:** the R1/R13 focal exception now also filters the emitted `incumbents`/`pre_pmf` NAME lists (an LLM slip could previously tag the focal both scored and excluded in the same compiler message); `_report_sections` no longer keys `## 0.5` as section 0 (`(?!\d)`); **founder mode now REQUIRES the startup name** (`schemas.py` validator — every founder surface gates on the name, so an unnamed founder run silently degraded to a plain sector report; the form disables Launch + hints, and no longer sends a stale `analysis_mode=founder` when the Target-Startup panel is OFF).
- **Touches A3:** the compiler must now keep the better-evidenced move where analysts conflict "AND SAY WHY" — prompt-level surfacing of debate tension only (no structured field; A3's `disagreement_summary` threading stays fully open).
- **Fast-follow:** the baked `/demo` founder fixture (Fidea/NeuroScribe) predates §0.5 — re-run + re-bake the founder scenario to showcase the section; validate live with a real founder run and grade against the rubric (note: the rubric needs a §0.5 criterion first — see the addendum in `QUALITY_RUBRIC.md`). The schemas validator needs real pydantic, so it's exercised in the Docker image, not the token-free suite.

## Fixed — 2026-07-01 (focal startup / founder mode / auto-scope / history / download / UI)

Large feature session. All backend token-free suites green: `test_focal.py` 22/22, `test_ingest.py` 8/8, `test_scope.py` 16/16, `test_structured_artifacts.py` 73/73, `test_filters_sliders.py` 27/27. Frontend `tsc --noEmit` clean; deployed image == source.

**R10 + R13 — the last two coherence bugs, closed in code and validated live (sim6):**
- **R10 — Defensibility now = mean of its 4 a16z moat sub-scores, in code.** The reconciler emits `moat_subscores` (Economies of Scale / Differentiated Tech / Network Effects / Brand Power) per startup; `_apply_moat_reconciliation` overwrites the Defensibility dimension with their mean (name-matched) in `compile_report`, so §7 can't disagree with the sub-scores shown beside it. Surfaced in the Scorecard UI. *(sim6: every ranked startup's Defensibility == mean, verified.)*
- **R13 — pre-PMF companies excluded from scoring.** Reconciler emits a `pre_pmf` watchlist; `_validate_resolved_scores` drops those names (same guard as incumbents); analyst/§7/compiler prompts mark pre-PMF/pre-launch as WATCHLIST-only (profiled in §8, not scored). **EXCEPTION:** a user's focal startup is force-kept even if early-stage (see focal feature).

**Focal Startup + Founder mode** (`analysis_mode` = `vc` | `founder`):
- Upload deck/financials/idea docs → `POST /api/upload` (shared `uploads` volume) → new `ingest_focal` graph node parses them (`services/ingest.py`: PyMuPDF text with a **vision fallback** for image-only PDF pages, docx, images) into `focal_materials`, cached to `_extracted.txt` so a deck is vision-parsed at most once.
- Researcher force-includes the focal startup (materials = primary source if stealth); **R13 exemption** keeps it scored even pre-PMF; the reconciler tags a **data-confidence** (low/med/high).
- **VC mode** ranks it in the field; **Founder mode** centers the report on it with a build/pass verdict.
- Validated live: the **Fidea founder run** (AI Agent IAM sector) — Fidea profiled + scored at *low confidence*, ranked among funded incumbents, WATCH verdict, deck specifics (founders, Pear VC, ICU/enforcement wedge) flowed into the analysis.
- Files: `graph/nodes.py` (`ingest_focal_materials`, `_focal_research_block`, `_extract_resolved_scores` focal-aware, `compile_report` mode framing), `services/ingest.py`, `graph/prompts.py`, `graph/state.py`, `models/schemas.py` (`AnalysisMode`), `api/routes.py`, `worker/tasks.py`, frontend `FocalStartupPanel.tsx`.

**Auto-scope** (derive the sector + market prompt from the focal startup so the user needn't type it):
- **Confirm-first UX:** if a focal startup is set and the prompt is blank, "Identify market" → `POST /api/derive-scope` (`services/scope.py` + `derive_scope` in nodes) infers `{sector, market_prompt, rationale}` — **from uploaded materials if present, else grounded by 1–2 Tavily searches** on the name — then prefills the editable fields for review before launch. `market_prompt` is now optional when a focal startup is attached (model validator). Pipeline self-heals if a request arrives with no prompt.
- **SCOPE-1 guard:** `derive_scope` rejects a non-string LLM `market_prompt` (a JSON `null` would `str()`-coerce to the literal `"None"` and bypass the 10-char floor). Validated live (materials + search paths).

**History** (durable, browsable past analyses):
- `services/store.py` — file-based store (`<id>.json` = meta + full report) on a new `reports` Docker volume (mounted in backend + worker). Survives restarts **and** the Redis purge. Worker **saves on completion**.
- `GET /api/reports` (light list), `GET /api/reports/{id}` (full), `PATCH` (rename/star), `DELETE`.
- **Left drawer** (`HistoryDrawer.tsx`): search · star favorites · rename/label · delete · click-to-reopen in the ReportViewer (reopened runs render all visuals → Print→PDF gives a PDF with the map).

**Download + tabs:**
- Download menu on every report: **PDF (with visuals)** via browser Print → Save as PDF (renders `PrintableReport` — a light memo layout incl. the real market-map SVG; `@media print` in globals.css hides app chrome via `.no-print`/`header`/`footer`), **Markdown** (`lib/exportReport.ts` `toMarkdown` — header → narrative → appendix tables), **Raw JSON**. All client-side (no backend).
- **Sources tab REMOVED** from the ReportViewer graphics panel (sources already live at the bottom of the written report). Tabs now: Market Map · Scores · Financials · Raw JSON.

**UI polish + demo:**
- **Azure + Slate theme** — `brand` retargeted to azure (`#3B82F6`), `gray` overridden to a cool-slate ramp, card elevation + a faint header glow, gradient title. One accent for chrome; scores/thesis toggle stay semantic. (`tailwind.config.ts`, `globals.css`.)
- **2×2 dashboard layout** for the form (Market Analysis Prompt · Target Startup Details [with on/off switch] · Metadata Controls · Evaluation Dimension Weights) + footer.
- **Public `/demo`** — three baked, backend-free scenarios (VC sector · VC + target startup · Founder test), rendering real pipeline outputs. Linked from the header.

**Infra / hygiene:**
- **Celery time limits raised to soft 3000s / hard 3900s** (was 1800/2400) — fixes a `TimeLimitExceeded(2400)` that SIGKILLed a max-debate (3-round) run mid-compile. (`worker/celery_app.py`.)
- **Non-finite guards** — `_as_score`/`_parse_money`/`_compute_expected_return` reject NaN/inf (defense-in-depth; Pydantic already coerces to null on the poll endpoint).
- **3 TS build-hygiene fixes** (`FinancialLedger.tsx` casts through `unknown`) so `tsc`/production build is clean.
- Two adversarial multi-agent readiness audits (UI-safety + scope-feature review) — verdict **ready**, zero confirmed UI-breaking issues.

---

## Fixed — 2026-06-28 (sim3 regressions → code-enforced coherence)

Driven by the sim3 live run (Codex 18/24). Philosophy: anything the LLM *asserts* that is really *arithmetic* or *bookkeeping* moves INTO code, so sections can't disagree. **All validated live on sim4/sim5/sim6.**

- **R1 — incumbents leaked into the investable ranking.** Prompts say "score ONLY pure-play startups"; the reconciler emits an `incumbents` list and `_validate_resolved_scores` DROPS matches; map/ledger force `is_incumbent` (no investable weighted score; incumbent ledger rows sort last).
- **R2 — coverage variance (3–4 startups).** Researcher Phase 1c forces breadth-before-depth: named list of 8–12 candidates first, then deep-dive ≥6. *(sim5: 7 startups; sim6: 6 — resolved.)*
- **R3 — company universe inconsistent across sections.** `compile_report` threads the canonical ranked set into both artifact validators; the ledger backfills a "Not Disclosed" row for any dropped ranked startup; compiler told §6/§7/§8/§13 share one universe.
- **R4/R5 — ASCII map contradicted §5 / violated its size legend.** Compiler prompt: §13 map MUST use the EXACT §5 axis labels + a MECHANICAL funding-based size encoding, no omissions.
- **R6 — probability-weighted return asserted, not computed.** Reconciler extracts the recommended startup's `scenarios`; `_compute_expected_return` does `Σ p × midpoint(multiple)` in code; compiler handed the EXACT figure for §0/§12.
- **R7 — valuation multiple disagreed across sections (24x vs 28x).** `_validate_financial_ledger` derives `implied_arr_multiple = valuation / ARR` in code (new ledger column); compiler uses it verbatim everywhere.
- **R8 (residual of R6) — the §12 scenario *table* didn't reconcile to the headline (5.4x vs table-implied 4.5x).** `compile_report` now hands the compiler the EXACT scenario rows with "render verbatim; the headline must equal this table's average." *(sim5: §0 & §12 both 8.95x, table averages to exactly 8.95x.)*

Tests at the time: `test_structured_artifacts.py` 60/60, `test_filters_sliders.py` 27/27. (Now 73/73 after R10/R13 + non-finite guards.)

## Fixed — 2026-06-27 (template overhaul + filter wiring)

Driven by an empirical filter-efficacy battery + deep research on top-tier VC frameworks.

- **Sliders had no real effect / weight-bleed / LLM arithmetic errors.** Weighting moved OUT of the LLM into code: `nodes._compute_weighted_scores` applies the (normalized, relative) dimension weights to the reconciled per-dimension scores to produce the authoritative `weighted_scores` + `ranking`. Proven by a unit test (financial-heavy → FortifyAI #1; defensibility-heavy → KernelGuard #1). Handles partial scorecards, numeric strings, and missing-score consensus (`weighting_unavailable` flag).
- **Stage / geography were dead controls.** Researcher scopes its Tavily queries by stage + geography; framework is stage-banded (`STAGE_BENCHMARKS`).
- **Template overhaul (research-informed):** expanded TAM/SAM/SOM sizing; Defensibility decomposed into a16z's 4 moat sub-types; reweighted defaults (20/30/20/15/15); generalized §5 axes to be sector-adaptive; added Team & Founder, Risk + Mitigants + "what would make us wrong", Return Math.
- **C9 — hard-coded query years** now use `datetime.now().year`.
- **Structured UI artifacts** — `compile_report` emits `market_map` + `financial_ledger` as JSON, validated/coerced in code (`_validate_market_map`/`_validate_financial_ledger`).
- **Latent JSON-extractor bug fixed** — `_last_balanced_json` returned the *innermost* object for nested JSON; now scans depth-0 spans and returns the whole top-level object.

## Fixed — 2026-06-26

- **A1 — Financial `$` rendered as broken LaTeX.** Removed the math pipeline (`remark-math` + `rehype-katex`); `$` renders literally. Prompts forbid LaTeX. *(superseded B5)*
- **B1** — `nodes.py` "Quantitative Challenger / Qualitative Auditor" comments → "full-spectrum analyst."
- **B2** — `tools.py` docstring corrected to researcher-only tools.
- **B3** — Frontend hard-coded "Gemini Flash" → real models (Gemini 2.5 Pro / Claude Sonnet 4.6 / GPT-4.1).
- **B4** — Frontend stepper now includes the researcher (6-column: Init · Research · Analyst A · Analyst B · Judge · Compile).
- **C1** — Malformed judge reply no longer silently fakes consensus; debate loops instead.
- **C6** — `.env.example` gained per-role model overrides; fixed the misleading search-key comment.
- **C8** — All 5 Tavily tools on a shared `_tavily_search` helper with try/except degradation.
- **A2** — researcher truncation mitigated (token budget 8192 → 32768).

## Fixed — earlier sessions

- `state_update is None` crash in the stream loop — guarded.
- Logs replaced instead of accumulated — now `.extend()`.
- Claude `.content` returned a list — `_normalize_content()` applied to all 5 LLM outputs.
- Greedy JSON regex in verdict extraction — replaced with reverse-scan brace matching.
- `compile_report` mutated state in place — now returns a new dict.
- `.env` relative-path failure in Docker — now absolute via `Path(__file__)`.
- Custom `update_state("FAILURE", meta=…)` corrupted Redis — removed; Celery sets FAILURE natively.
- Stale-result purge targets only `celery-task-meta-*` (not full `flushdb`).
- Invalid model ID `claude-sonnet-4-20250514` → `claude-sonnet-4-6`.
