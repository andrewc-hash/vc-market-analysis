# VC Market Analysis Engine

> Name a market — or a single startup — and get the document an associate would take a week to draft: a 13-section, verdict-first IC memo with a scored market map, stage-benchmarked financials, worked return math, and a recommendation at a price. In about 20 minutes.

**Live demo (no keys, no backend):** https://vc-market-analysis.vercel.app — three real, unedited pipeline outputs.
**How it works, in plain language:** https://vc-market-analysis.vercel.app/docs

---

## What it produces

- **A 13-section memo that leads with the verdict** — top pick and INVEST / WATCH / PASS *at a stated valuation*, the one non-consensus insight, the single variable the bet turns on, and a dated, falsifiable prediction. Then bottoms-up market sizing (accounts × ACV, not a Gartner quote), incumbent threat with a window clock, startup profiles, team assessment, severity-tagged risks with kill criteria, and probability-weighted return scenarios anchored to real acquisition precedents.
- **The instrument panel beside it:** a 2×2 market map with the white space marked · a weighted scorecard (your slider weights, applied exactly) with the a16z moat breakdown · per-startup letter grades · a financial ledger with every metric flagged against its stage benchmark · exit precedents · a fund-fit panel.
- **Exports built to be forwarded:** full PDF with every visual, a one-page tear sheet, Markdown, raw JSON. Every run is saved to History and can be re-run later — the engine diffs the market and grades its own past predictions.

**Two modes, opposite questions.** *VC mode:* "Should I write a check into this company — at what price?" (the target is force-ranked inside its real competitive field). *Founder mode:* "Should I keep building — and will it raise?" (BUILD / PIVOT / STOP verdict, a repositioning plan aimed at your weakest computed scores, and your own raise math). Attach a pitch deck (image-only PDFs are vision-parsed), a founder-call recording (claims are extracted with timestamps and cross-examined against the public record), a cap-table CSV, and your fund's size and check.

## How the answer gets made

```
START
  ├─ INGEST        parse deck/docs/audio/cap-table · extract founder claims ·
  │                auto-derive the market scope if the prompt is blank
  ├─ RESEARCHER    Gemini 2.5 Pro + 7 live-search tools (Tavily + Google-grounded) ·
  │                35–45 dated searches · fresh-news pass per startup · facts only
  ├─ ANALYST A ∥ ANALYST B   Gemini 2.5 Pro ∥ Claude Sonnet 4.6 — the identical brief,
  │                independently · raw 0–100 scores · bear case argued first
  ├─ JUDGE         GPT-4.1 · finds their genuine disagreements · loops the debate
  │                back to both analysts (max 3 rounds) until they converge
  └─ COMPILER + CODE   one memo — every figure computed in code from the analysts'
                   raw inputs, then rendered (never asserted) by the LLM
```

Three design decisions carry the system:

1. **Cross-provider consensus as error detection.** Two full-spectrum analysts on *different AI vendors* write competing analyses from the same research; a third-provider referee forces every disagreement to resolution. Where one model hallucinates, the other contests it — the error-detection step a single chatbot doesn't have.
2. **Software does the math, not the AI.** Rankings, weighted indices, return ranges (gross *and* net of stage-banded dilution), valuation multiples, moat means, letter grades, and fund math ("does this deal return *my* fund?" — ownership at exit, turns-of-fund, required exit, net IRR) are computed deterministically in code from the analysts' raw scores. The scorecard can't contradict the map; the headline return always equals its own scenario table; the weight sliders have an exact, reproducible effect.
3. **Researched live, dated, and honest about gaps.** Every agent is date-grounded; sources carry publication dates; citations are harvested from the actual search transcripts so fabricated links can't survive; a "Data as of" badge flags staleness. Undisclosed metrics say **Not Disclosed** — never a guess; thin-data companies get approximate (≈) scores; every memo ends with a code-generated methodology section stating what was and wasn't checked.

## Engineering notes

- **LangGraph `StateGraph`** with a fan-out/fan-in debate loop (researcher runs once; only the analysts re-argue, with the judge's critique injected). FastAPI + Celery/Redis backend, Next.js 14 frontend, Docker Compose.
- **576 token-free tests** (`backend/tests/`, no API keys — LLM deps are stubbed) pin the deterministic layer: score reconciliation, weighting, fund-math vectors (8 hand-cross-checked worked examples), claim-audit joins, freshness audits, arithmetic linting.
- **An adversarial eval loop**: output is graded against a 24-point rubric distilled from published top-fund memos (`docs/QUALITY_RUBRIC.md`), and recurring failure classes get moved from prompt-space into code-enforced invariants (the "R-series" in `docs/KNOWN_ISSUES.md` — incumbents can never be ranked, Defensibility always equals the mean of its moat sub-scores, the §12 table always reconciles to its headline, and so on).
- **Deep reference:** [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`CLAUDE.md`](CLAUDE.md) (session guide) · [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) (the honest bug-and-fix trail).

## Run it locally

```bash
cp backend/.env.example backend/.env   # fill in the 5 API keys
docker compose up --build              # redis · backend :8000 · worker · frontend :3000
open http://localhost:3000
```

Models are config-driven (`backend/app/config.py`): Gemini 2.5 Pro (researcher / analyst A / compiler / vision), Claude Sonnet 4.6 (analyst B), GPT-4.1 (judge), Whisper (call transcription). A full run takes ~15–25 minutes and a few dollars of API cost.

```bash
# token-free test suite (no keys needed) — run from the repo root
for f in backend/tests/test_*.py; do python3 "$f"; done
```

## What this is not

Decision-support, not investment advice — a first-pass screen, not diligence. Figures come from public sources and can be wrong; verify anything material before acting. Returns are scenario multiples (gross unless labeled net). References, legal, and private financials are not checked. Every memo states this about itself.
