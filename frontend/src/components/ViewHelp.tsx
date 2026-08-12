"use client";

import { useEffect, useState } from "react";

// Per-view "How to use" affordance — a small pill in each console view's header
// corner opening a contextual guide (the report view has its own HelpGuide).

type HelpRow = { term: string; body: string };

const CONTENT = {
  home: {
    title: "Home",
    intro: "Your workspace: everything you've run, and the doors to run more.",
    rows: [
      { term: "The stat strip", body: "Live counts from your report history — analyses run, sectors covered, target-deal runs, starred reports, and how recent the last run is." },
      { term: "Start an analysis", body: "Three doors: Evaluate a Startup screens one deal inside its competitive field; Evaluate My Startup gives founders a build / pass verdict; Analyze a Market maps a whole sector." },
      { term: "Recent analyses", body: "Click any row to reopen its full report. Star pins favorites to the top; the pencil renames; the trash deletes." },
      { term: "Re-run (↻)", body: "Runs the same analysis again on fresh research. The new report diffs what changed in the field and grades the original's predictions — chains appear under Tracked." },
      { term: "Search", body: "Filters the list by label, sector, or startup name." },
    ],
  },
  sector: {
    title: "Analyze a Market",
    intro: "Map and rank an entire market — no specific startup required.",
    rows: [
      { term: "Scope", body: "Describe the sector with focus — the sub-space, the kind of startups, what matters to you. Specific prompts produce sharper fields." },
      { term: "Parameters", body: "Optional framing: a sector label for the masthead, stage and geography focus, and the thesis bias — Bear is a red-team skeptic, Base a neutral partner, Bull a high-conviction optimist." },
      { term: "Weights", body: "How the scorecard weighs its five dimensions. They're relative (needn't sum to 100) and applied in code, so they have an exact, reproducible effect on the ranking." },
      { term: "Fund economics", body: "With a Fund Profile saved it applies automatically, and the report gains the Fund Fit panel — including the exit size required to return your fund." },
      { term: "What you get", body: "In under an hour: a 13-section verdict-first memo, a 2×2 market map, weighted scorecard, letter grades, a stage-benchmarked financial ledger, and a full audit trail." },
    ],
  },
  vc: {
    title: "Evaluate a Startup",
    intro: "Evaluate one startup inside its real competitive field.",
    rows: [
      { term: "Startup + files", body: "Name the target and optionally upload its pitch deck, documents, a founder-call recording or transcript, or a cap-table CSV. Uploads ground the analysis — essential for stealth companies." },
      { term: "Call recordings", body: "Upload a founder call and every factual claim from it is cross-examined against independent research — the report gains a Claims tab." },
      { term: "Market prompt", body: "Optional. Leave it blank and “Identify market” derives the market from the startup — you review and edit it before launching." },
      { term: "The verdict", body: "The target is force-included and ranked against its field; the memo closes with INVEST / WATCH / PASS at a stated price." },
    ],
  },
  founder: {
    title: "Evaluate My Startup",
    intro: "Center the entire analysis on one company — yours.",
    rows: [
      { term: "Your startup", body: "Name required. Upload your deck — founder mode feeds it to the analysts directly, so stealth companies aren't treated as unknowns." },
      { term: "The verdict", body: "The memo opens with an investor check (would they invest today?) and a founder call: BUILD / KEEP GOING / PIVOT / STOP." },
      { term: "Repositioning", body: "Section 0.5 gives 2–4 concrete moves targeting your weakest scored dimensions, one “what NOT to change,” a sequenced 90-day plan, and a fastest-signal-to-quit gate." },
      { term: "Honesty note", body: "Low scores pre-revenue are stage-normal, and the report says so itself. It grades evidence, not potential — that's what makes the good news believable." },
    ],
  },
  fund: {
    title: "My Fund",
    intro: "Fund economics as a workspace setting — set once, applied to every run.",
    rows: [
      { term: "What it unlocks", body: "Reports gain the Fund Fit panel: entry ownership, dilution to exit, per-scenario proceeds, turns of the fund, the exit required to return it, and net IRR — all computed in code." },
      { term: "Only fund size is required", body: "Missing fields are inferred from stage benchmarks, and every inference is disclosed as an assumption in the report." },
      { term: "Per-run control", body: "Every analysis form shows the applied profile with options to adjust for that run only, or to run without fund math. Nothing a form does writes back here." },
      { term: "Stored locally", body: "Saved in this browser only — it never leaves your machine." },
    ],
  },
  tracked: {
    title: "Tracked Deals",
    intro: "The watchlist that re-underwrites itself.",
    rows: [
      { term: "Chains", body: "A baseline report plus every re-run of it. Re-run from here — or with ↻ on Home — and the new run joins the chain." },
      { term: "What changed", body: "The latest re-run's delta, computed in code: pick held or changed, expected-return movement, rank movers, entrants and exits, new acquisitions." },
      { term: "Predictions, graded", body: "Every report makes dated, falsifiable predictions. Re-runs grade the baseline's own calls against fresh evidence: validated, broken, pending, or unresolved." },
      { term: "Reading it", body: "Click a run pill to open that report. A delta is only as good as the fresh run's research — the Audit tab's receipts tell you whether to trust it." },
    ],
  },
} as const;

export type HelpView = keyof typeof CONTENT;

export default function ViewHelp({ view }: { view: HelpView }) {
  const [open, setOpen] = useState(false);
  const c = CONTENT[view];

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="no-print inline-flex shrink-0 items-center gap-1.5 rounded-full border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-100"
        aria-label={`How to use ${c.title}`}
      >
        <span className="text-brand-300">?</span>
        How to use
      </button>

      {open && (
        <div
          className="no-print fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[80vh] w-full max-w-xl overflow-y-auto rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-pop"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="kicker">How to use</div>
                <h3 className="mt-0.5 font-serif text-xl font-semibold text-gray-100">{c.title}</h3>
                <p className="mt-1 text-[13px] text-gray-500">{c.intro}</p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-800 hover:text-gray-200"
              >
                Close ✕
              </button>
            </div>
            <div className="mt-4 space-y-2.5">
              {c.rows.map((r) => (
                <div key={r.term} className="flex gap-3">
                  <div className="w-40 shrink-0 text-[13px] font-semibold text-gray-100">{r.term}</div>
                  <div className="text-[13px] leading-relaxed text-gray-400">{r.body}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
