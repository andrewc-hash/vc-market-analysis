# Top-Fund Quality Rubric — grading a VC sector analysis

> A calibrated rubric for judging whether the platform's 13-section sector analysis + scored market map matches the quality bar of what a **top fund** actually produces (not just "is it complete"). Built from a deep-research pass anchored in **primary sources**: Bessemer's publicly published recommendation memos (Shopify, Twilio, Toast, ServiceTitan…) and State-of-the-Cloud benchmarks, **Sequoia's** own writing-the-memo guidance, an **arXiv AI-slop taxonomy** (2509.19163), corroborated by HBS "Catching Outliers," Popper, and IC-process write-ups. Sources at the bottom; confidence flagged per dimension.

## How to score
Each dimension: **Top-fund = 3 · Competent = 2 · Weak/AI-slop = 1**. Total out of **24** (8 dims). Suggested bands: **≥21 top-fund · 16–20 competent · ≤15 weak**. (Weights are a judgment call — dims 1, 3, 4, 7 are the highest-signal differentiators; see "5 tells.")

| # | Dimension | Top-fund (3) | Competent (2) | Weak (1) | Where to look (§) | Conf. |
|---|-----------|-------------|---------------|----------|-------------------|-------|
| 1 | **Falsifiable, time-bound thesis** | Sharp dated/observable predictions + pre-committed "what would make us wrong" tripwires | Directional view, no tripwires | Hedged take consistent with any outcome | §4 thesis, §11 kill-criteria | High |
| 2 | **Evidence density / quantification** | Calibrated numeric tiers + **bottoms-up** TAM w/ citations + named-customer/primary data | Some cited 3rd-party benchmarks | Top-down TAM, hand-wavy adjectives, no primary data | §2, §6, §7 | High |
| 3 | **Argument → a real DECISION** | Clear pick + return math with **probability-weighted scenarios incl. an outlier "just goes nuts" case** + fund-returner logic | A recommendation but thin return logic | Describes/lists without deciding | §7 ranking, §12 return math | High |
| 4 | **Intellectual honesty / pre-mortem** | Bear case **steelmanned before** the bull thesis + genuine "risks we'd lose sleep over" | Risks listed after the bull case | Boilerplate/token risks | §11, §8 "how it dies" | High |
| 5 | **"Why Now" + team depth** | Specific tech/behavioral/regulatory inflection ("why hasn't this been built before?") + concrete founder pedigree | Generic tailwinds | No timing argument / interchangeable team boilerplate | §2 why-now, §9 team | High |
| 6 | **Competition = a plan to win** | Direct+indirect competitors **and a defensible wedge** vs. incumbents | Competitor map, no win path | Feature-comparison list, no judgment | §3, §4 | High |
| 7 | **Variant perception** | Pre-consensus, non-obvious angle held with conviction | Sound but consensus take | Generic consensus narrative | §1, §4 | Med* |
| 8 | **Signal-to-noise (anti-slop)** | High density (substance-per-length), on-topic, no padding/fake precision/templatedness | Some filler | Padding, repetition, fake precision, inflated formality | Whole report | Med* |

\*Dims 7–8 rest on corroborated blogs + one recent arXiv paper (vs. firm-primary for 1–6) — gradeable, slightly lower confidence.

## The 5 highest-signal "tells" — what top-fund analysis has that AI almost always lacks
1. A **falsifiable, time-bound thesis with explicit kill-criteria** (AI hedges).
2. A **clear decision *at a price*, with an outlier return scenario** (AI describes; won't commit).
3. **Pre-consensus / variant insight** (AI defaults to consensus).
4. **Bear-case-first honesty** — disconfirming evidence *before* the bull case (AI lists token risks after).
5. **Proprietary/bottoms-up evidence + calibrated numeric bands** (AI reaches for top-down TAM + adjectives).

## Calibration notes
- **Penalize fence-sitting.** Some ICs literally *ban 5–6 scores* (1–10 scale) to force a position. If the scorecard clusters everything at 50–70, that is a **weakness**, not neutrality — the analysis should take sharp positions.
- **Do NOT over-weight these (research *refuted* them as hard rules):** a dated expiration trigger on the thesis; "why now" as the single most-important element; a fixed mandatory section list; risks-section as the sole decision determinant. Treat as nice-to-haves.

## Founder-mode addendum (§0.5 Strategic Repositioning)
When grading a FOUNDER-mode run, also grade the §0.5 section (same 3/2/1 scale, reported separately — not part of the /24): **Top** = every move names one of the system-computed weakest dimensions/moat sub-scores, cites named research evidence (survives the paste test: swap the focal for a competitor and the move stops making sense), states cost + falsifier, and there is exactly ONE "What NOT to change"; **Competent** = moves are anchored but evidence is thin or a falsifier/cost is missing; **Weak** = generic startup advice, unanchored targets, hedged non-moves, or new/recomputed numbers (a scoring-contract violation is an automatic 1).

## Applying it
Grade each dimension 1–3 with a one-line justification citing the actual report text, sum to /24, and list the specific gaps. Optional future automation: wire this as an LLM-judge grading step (a `grade_report` node or a `/grade` tool) that scores `final_report.merged_report` + the structured fields and returns `{dimension: score, evidence}` — deterministic prompt, validated in code like the other extraction steps.

## Sources
Primary: **Bessemer** `bvp.com/memos` (published recommendation memos) + `bvp.com/atlas/state-of-the-cloud` (Good/Better/Best benchmark bands); **Sequoia** `sequoiacap.com/article/writing-a-business-plan` (10-element structure, "why now", "plan to win"); **arXiv 2509.19163** (AI-slop taxonomy: Density, Relevance, Tone as strongest low-quality predictors). Corroborating: HBS "Catching Outliers" (champion-rule beats unanimity), Popper (falsifiability), pre-mortem/debiasing literature, IC-process write-ups (score-voting bans on 5–6). 20/25 claims verified 3-0; 5 refuted (see "Calibration notes").
