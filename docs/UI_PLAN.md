# UI Plan — Report + Market Map + Graphics

> **Status:** design/plan only — **no code has been changed for this.** Goal: replace the current "one big markdown page" with a navigable full report beside a panel of graphics (market map, leaderboard, financials). Grounded in (a) what the pipeline actually outputs today and (b) deep research on market-map / data-viz best practice (sources at the bottom). Where guidance is opinion vs. established practice, it's marked **[opinion]** / **[established]**.

---

## 1. The problem (today)

The pipeline's headline output is a single `merged_report` markdown string (the whole 13-section report). `frontend/src/components/ReportViewer.tsx` renders it as **one `<ReactMarkdown>` blob** in the "Final Report" tab. The financial ledger (§6), scorecard (§7), and market map (§13 ASCII) are all **embedded as text inside that one string**, so the UI has no structure to turn into graphics. That's the root cause of "hard to read."

---

## 2. Target layout (sketch)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  AI Agent Security & Runtime Governance            Bias: Base · Consensus in 2 rounds  │
│  Generated 2026-06-27 · 6 startups · sources: Tavily        [Export ▾] [Re-run]        │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  ▸ EXEC SUMMARY (one-pager): 3-sentence thesis · top pick · TAM/SAM/SOM · key risk      │
│  ▸ KEY-METRICS STRIP:  TAM $14B │ SOM $480M │ Top: KernelGuard 84 │ AI mult 24x │ ⚠3 risks│
├────────────────────────────────────────────┬─────────────────────────────────────────┤
│  LEFT — FULL REPORT (scrolls)              │  RIGHT — GRAPHICS PANEL (sticky)         │
│ ┌── section nav (sticky) ──┐               │  ┌ Map ┊ Scores ┊ Financials ┊ Sources ┐│
│ │ 1  Narrative             │  ## 1 ...      │  ┌───────────────────────────────────┐ │
│ │ 2  Sizing                │  prose…        │  │   SCORED 2×2 POSITIONING MATRIX   │ │
│ │ …                        │                │  │  Host/Kernel ▲   ◇ white space    │ │
│ │ 7  Scorecard  ◀ active   │  ## 6 | table  │  │      ●KernelGuard                  │ │
│ │ 8  Profiles              │  ## 7 ...       │  │   ●RegShield   ·MidMoat           │ │
│ │ …                        │  (click a dot  │  │  App/API └──────────●FortifyAI──▶ │ │
│ │ 13 Market map            │   → scroll to  │  │     Deterministic       Probab.   │ │
│ └──────────────────────────┘   that §8)     │  └───────────────────────────────────┘ │
│                                            │  ● size = capital raised · hue = segment │
│                                            │  ◇ = investable white space (thesis)     │
│                                            │  ├─────────────────────────────────────┤ │
│                                            │  │ LEADERBOARD (weighted index)      │ │
│                                            │  │ 1 KernelGuard ███████████ 84      │ │
│                                            │  │ 2 RegShield   ████████ 72         │ │
│                                            │  └───────────────────────────────────┘ │
└────────────────────────────────────────────┴─────────────────────────────────────────┘
   (mobile: graphics panel collapses to a top carousel; report stacks below)
```

The side-by-side layout itself is **[opinion]** (research did not surface evidence for left-report/right-graphics specifically), but the *components* and *encodings* below are evidence-backed.

---

## 3. Map design rules (research-backed)

### 3a. Archetype — use a SCORED 2×2 positioning matrix as the primary graphic
Your §5 axes + §13 coordinate map already map to a 2×2. The research validates making it a **scored** matrix:
- Gartner Magic Quadrant and Forrester Wave place vendors by **scoring them against explicit criteria, not by eyeballing** — *"placement is not arbitrary but is scored against criteria"* **[established]**. You already produce `weighted_scores` / `resolved_scores`, so your placement can be genuinely scored (a real edge over logo-soup maps).
- Use **four named quadrants** (the matrix "is divided into four named quadrants") **[established]** — e.g. "Defensible white space", "Crowded app layer", etc.
- **Single placement per company, scored — not spanning.** The belief that landscape maps let a company appear in multiple segments was **refuted** in research (the FirstMark MAD "span" claim failed 1-2). For a scored matrix, place each company once. *(Your current §5/§13 prompt says "companies may occupy multiple cells" — reconsider that for the scored view; spanning belongs only to a separate logo-grid landscape, if you add one.)*
- A **logo-grid / value-chain "landscape"** (FirstMark MAD style, organized **left-to-right as a functional/value-chain flow** **[established]**) is a good *secondary* view for showing the whole sector, but the scored 2×2 is the primary because you have scores.

### 3b. Visual encoding — match channel to data type, by perceptual accuracy
Munzner / Cleveland-McGill (verified):
- **Encodings have a perceptual-accuracy hierarchy: position > length > angle > area > color/hue** **[established]**. So:
  - **Position (X/Y)** → the two axis variables (your most important signal). Most accurately read.
  - **Size (bubble area)** → capital raised or ARR (a magnitude; area is lower-accuracy, fine for "roughly bigger"). *"Companies allocated visual space proportional to"* prominence is established practice in MAD.
  - **Color hue** → **segment** (categorical/identity), NOT a quantity — *"hue is the most challenging encoding for detailed [magnitude] reading"* and *"channels should be matched to data type"* **[established]**.
- **Default to grey; add color only to highlight** **[established]** — grey out the field, color only the thesis pick / white-space companies.
- Marks + channels are the building blocks (Munzner) **[established]** — keep it to a few channels; don't over-encode.

### 3c. Color & accessibility
- Use **ColorBrewer** palettes — it has **3 scheme types** (qualitative for segments, sequential for ordered, diverging for +/-) and **explicit colorblind-safe filters** **[established]**. Stage/segment = qualitative, colorblind-safe.

### 3d. Density / clutter
- **Cap the number of dots.** The **2025 MAD landscape deliberately CUT its logo count** to stay legible **[established]**; "logo soup" is a top market-map failure (CB Insights' "7 worst things about making market maps"). You profile 6–8 startups, so you're already in a safe range — keep the scored map at **≤ ~15–20** companies. Exact cap is **[opinion]** (research left "density cap" open).

### 3e. Pairing with the narrative (interactivity)
- **Cross-reference map ⟷ prose** — click a dot → scroll the left report to that startup's §8 profile; hover → tooltip with the placement rationale + key metrics **[opinion, but standard]** (interactive-viz best practices: filter, hover, drill-down, click-through).
- Show a small **methodology/freshness note** on the map (axes definition + "scores from N analysts, bias=X, generated <date>") — *deliverables should disclose data-freshness and methodology* **[established]**.

### 3f. Anti-patterns to avoid (verified failure modes)
Logo soup (too many logos), **false precision** (don't imply exact coordinates you didn't measure — the placement is judgment scored 0–100, label it as such), cherry-picked axes, no methodology, stale data. Roger Martin's "market maps make me nervous" is the caution that 2×2 axes can be chosen to flatter a thesis — so **state the axes' definitions and why they matter** for the sector.

---

## 4. Graphics inventory → data plumbing (grounded in the pipeline)

| Graphic | Data source | Status |
|---------|-------------|--------|
| Ranked **leaderboard** bars | `ranking` + `weighted_scores[*].weighted_score` | ✅ **exists today** |
| Per-startup **radar** / **heatmap** | `resolved_scores` | ✅ exists |
| **Weights donut** | `applied_weights` | ✅ exists |
| Header / key-metric **badges** | `thesis_bias`, `iterations_to_consensus`, `weighting_unavailable` | ✅ exists |
| **Navigable full report** | split `merged_report` on `## N.` headings (frontend only) | ✅ exists (no pipeline change) |
| **Market map** (dots) | `market_map` (new) | ⚙️ **new field** — today only ASCII in prose |
| **Financial ledger** table | `financial_ledger` (new) | ⚙️ **new field** — today markdown table in prose |
| **Exec summary** / one-pager | `executive_summary` (new) or derive from `synthesis` | ⚙️ new field (or derive) |

**So the only real pipeline work** to unlock the full graphics panel is emitting **two structured companion fields** (`market_map`, `financial_ledger`) — the scorecard graphics already work from data you have. Recommend the **compiler emits these as JSON** the same way `judge_node` emits `resolved_scores` (a dedicated structured output, validated/coerced in code like `_compute_weighted_scores` — don't parse them out of prose).

### Proposed `market_map` shape
```json
{
  "axes": {
    "x": { "label": "Control philosophy", "low": "Deterministic rules", "high": "Probabilistic ML" },
    "y": { "label": "Enforcement depth", "low": "App / API gateway", "high": "Host / Kernel" }
  },
  "quadrants": [ { "name": "Defensible white space", "x": "low", "y": "high" }, "…(4 named)" ],
  "white_space": { "x": 35, "y": 85, "label": "Investable white space (thesis)" },
  "companies": [
    {
      "name": "KernelGuard",
      "x": 35, "y": 90,            // 0-100 scored position on each axis
      "segment": "Runtime enforcement",
      "stage": "Series A",
      "raised_usd_m": 18,           // -> bubble size (area)
      "weighted_score": 84,         // -> highlight ranking, ties to leaderboard
      "rationale": "kernel-level eBPF, deterministic policy"  // -> hover tooltip
    }
  ]
}
```

### Proposed `financial_ledger` shape
```json
{
  "rows": [
    {
      "startup": "KernelGuard", "stage": "Series A",
      "total_raised": "$18M", "valuation": "$110M", "arr": "$6M",
      "yoy_growth": "90%", "ltv_cac": "2.0", "nrr": "115%",
      "burn_multiple": "2.5", "rule_of_40": "50",
      "flags": { "burn_multiple": "warn", "rule_of_40": "ok" }  // stage-band color cue: ok|warn|bad
    }
  ],
  "stage_banded": true
}
```
Use `"Not Disclosed"` for missing values (consistent with the researcher playbook); `flags` drive the green/amber/red cell coloring against the stage bands already in `STAGE_BENCHMARKS`.

---

## 5. What else to put in "the return" (beyond narrative + map)

Verified components of a complete market-intelligence deliverable (most map to data you already produce):

| Component | Backed by | Feed |
|-----------|-----------|------|
| **Executive summary / one-pager** | standard top section **[established]** | `synthesis` → or new `executive_summary` |
| **Scored leaderboard** | Dealroom uses an explicit, transparent ranking methodology **[established]** | `ranking` + `weighted_scores` ✅ |
| **Comparison / feature matrix** | competitive-landscape section is core **[established]** | `financial_ledger` + `resolved_scores` |
| **Watchlist / "deal radar"** | common in CB Insights / CI reports **[opinion/common]** | top-N of `ranking` |
| **Key-metrics dashboard** | — **[opinion/common]** | TAM/SAM/SOM + top score + AI multiple |
| **Methodology + Works Cited + freshness** | deliverables disclose freshness & methodology **[established]** | `research_data` URLs + run metadata |
| **"What changed since last run" delta** | data-freshness is a tracked concern **[established]**; the delta itself is **[opinion]** | requires storing prior runs |

Note: the **six-layer MI-report structure** was **refuted** — don't adopt it as a template; your 13-section framework + these panels is the better fit.

---

## 6. Testing the new UI

Principle: **deterministic-first, capture one golden fixture.** Run the pipeline once, save `final_report` as `frontend/tests/fixtures/report.golden.json`, and test the whole UI against it (no token cost). Layers:

1. **Data contract** (pytest, 0 tokens) — validate/coerce `market_map` + `financial_ledger`: axes present, every company x/y in 0–100, segment/stage/raised present; malformed LLM output coerced not crashed. Extends `backend/tests/test_filters_sliders.py`.
2. **Component tests** (Vitest + React Testing Library, 0 tokens) — report splits on `## N.`; map draws N dots at right coords; leaderboard order = `ranking`; radar/heatmap; ledger sort; **empty / `weighting_unavailable` states**.
3. **Visual regression** (Playwright screenshots / Storybook+Chromatic) — the *map*: overlap, edge clipping, density, long labels.
4. **E2E with mocked backend** (Playwright) — two-column layout, tab switching, **click-dot → scroll to §8**, export, mobile carousel.
5. **Accessibility** (jest-axe / axe-playwright) — contrast, **colorblind safety** (color = segment), keyboard nav, dots have SR labels.
6. **Manual/visual** — `/run` + `/verify` skills to launch the real app and screenshot.
7. **LLM-behavioral (opt-in, tokens)** — a few real runs to confirm the model emits *sensible* placements, not just valid JSON.

**Map-specific cases:** density (4 vs 8), overlapping dots, edge dots (x=0/100), missing coords, long names, colorblind, click accuracy.

Frontend has **no test infra today** → step zero is adding Vitest + RTL + Playwright (+ axe). Backend already has the `backend/tests/` pattern.

---

## 7. Sources (deep research, 23/25 claims verified 3-0)

Primary: FirstMark MAD Landscape (mad.firstmark.com) + 2025 "bubble build" writeup; CB Insights "Book of Market Maps" + "7 worst things about making market maps"; Gartner Magic Quadrant methodology; Forrester Wave methodology (2024 update); Munzner *Visualization Analysis & Design* (marks/channels, accuracy hierarchy); ColorBrewer (colorblind-safe palettes); Dealroom VC investor ranking; UC Davis DataLab visual-perception principles. Caution: Roger Martin, "Market Maps Make Me Nervous" (axis-choice bias).

**Caveats:** the side-by-side *layout* and the exact *density cap* are not directly evidenced (opinion); "how top VCs pick the two axes" stayed an open question — treat axis selection as analyst judgment per sector (the framework already proposes sector-fit axes).

---

## 8. Next steps
1. ✅ **DONE (2026-06-27):** `compile_report` emits `market_map` + `financial_ledger` as structured JSON via a dedicated extraction call, **validated/coerced in code** (`_validate_market_map` / `_validate_financial_ledger`; tests in `backend/tests/test_structured_artifacts.py`). Either is `null` on failure → UI degrades to prose. *(Backend only — no frontend yet.)*
2. ✅ **DONE (2026-06-27):** Frontend two-column UI built — `ReportViewer.tsx` composes a navigable report (left, `report/ReportSections.tsx`) + a sticky graphics panel (right): `report/MarketMap.tsx` (hand-rolled SVG scored 2×2), `report/Leaderboard.tsx`, `report/Scorecard.tsx` (heatmap + weights), `report/FinancialLedger.tsx`. Helpers in `lib/viz.ts`; types in `lib/api.ts`. No new deps (SVG hand-rolled). Adversarially reviewed (TS/React/null-safety + data-shape integration), pass-with-nits, all fixed. Click a map dot / leaderboard row → scrolls the report to that startup's profile. Graceful "unavailable" fallbacks when a structured field is null.
3. 🟡 **Golden fixture + preview DONE (2026-06-27):** `frontend/src/fixtures/reportGolden.ts` (typed `FinalReport`, self-consistent 6-startup runtime-security report) + a `/preview` route (`src/app/preview/page.tsx`) render the full UI with **no pipeline / no API calls** — run `cd frontend && npm install && npm run dev` then open `http://localhost:3000/preview`. This doubles as the frontend **build check** (catches TS errors) and a **visual check** of the SVG map before any token-spending run. *Automated* test layers (Vitest/RTL/Playwright/axe, §6 layers 1–5) are still pending.
