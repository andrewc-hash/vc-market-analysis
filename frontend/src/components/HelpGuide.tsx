"use client";

import { useEffect, useState } from "react";

// Floating "How to use this page" helper — a persistent ? button (bottom-right)
// that opens a plain-language guide to every control and tab in the report view.

const Row = ({ term, children }: { term: string; children: React.ReactNode }) => (
  <div className="flex gap-3">
    <div className="w-40 shrink-0 text-[13px] font-semibold text-gray-100">{term}</div>
    <div className="text-[13px] leading-relaxed text-gray-400">{children}</div>
  </div>
);

const SectionTitle = ({ children }: { children: React.ReactNode }) => (
  <div className="kicker mt-5 first:mt-0">{children}</div>
);

export default function HelpGuide() {
  const [open, setOpen] = useState(false);

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
        className="no-print fixed bottom-4 right-4 z-40 flex h-9 items-center gap-2 rounded-full border border-gray-700 bg-gray-900 px-3.5 text-[13px] font-medium text-gray-400 shadow-pop transition-colors hover:border-gray-600 hover:text-gray-100"
        aria-label="How to use this page"
      >
        <span className="flex h-4.5 w-4.5 items-center justify-center text-brand-300">?</span>
        How to use this page
      </button>

      {open && (
        <div
          className="no-print fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-pop"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="kicker">Guide</div>
                <h3 className="mt-0.5 font-serif text-xl font-semibold text-gray-100">How to use this page</h3>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-800 hover:text-gray-200"
              >
                Close ✕
              </button>
            </div>

            <div className="mt-4 space-y-2.5">
              <SectionTitle>The buttons</SectionTitle>
              <Row term="Quick Overview">
                A step-through presentation of the report&rsquo;s key beats — verdict, timing, the field, scores, money, risks, return math. Arrow keys to navigate, Esc to exit, or jump into any full section from a step.
              </Row>
              <Row term="Download">
                Export the report: a one-page tear sheet, the full memo as PDF with all visuals, Markdown, or the raw JSON data.
              </Row>
              <Row term="History (☰)">
                Every past run is saved — reopen, star, rename, or re-run any report. A re-run diffs what changed in the field and grades the original report&rsquo;s predictions.
              </Row>

              <SectionTitle>The tabs</SectionTitle>
              <Row term="Report">
                The full 13-section memo, verdict first. Every material figure carries a source; Works Cited is at the bottom.
              </Row>
              <Row term="Market Map">
                The field on a 2×2 — the axes come from the memo&rsquo;s segmentation analysis, bubble size tracks capital raised, and incumbents appear as reference points (they aren&rsquo;t scored).
              </Row>
              <Row term="Scores">
                The weighted underwriting index. Two independent AI analysts score each startup 0–100 per dimension; the weighting and ranking are then computed in code from your slider weights — so weights have an exact, reproducible effect. Defensibility shows its four moat sub-scores.
              </Row>
              <Row term="Grades">
                Per-startup letter grades computed in code from the reconciled scores and financials. NR means a metric wasn&rsquo;t disclosed — absence is never punished as an F.
              </Row>
              <Row term="Financials">
                The financial ledger benchmarked against each company&rsquo;s stage, the return scenarios, exit precedents, and — when you provide a fund profile — Fund Fit: the exit size required to return your fund.
              </Row>
              <Row term="Claims">
                Appears when a founder call recording or transcript was uploaded: each claim from the call, cross-examined against the independent research.
              </Row>
              <Row term="Audit">
                The glass box: the analysts&rsquo; recorded disagreements round by round, every search the researcher ran, and the worked arithmetic behind each score — so any number can be traced.
              </Row>
              <Row term="Raw JSON">The complete underlying data for the run.</Row>

              <SectionTitle>The header</SectionTitle>
              <Row term="Recommendation">
                The report&rsquo;s own pick and INVEST / WATCH / PASS call from §0/§12. Decision-support, not investment advice.
              </Row>
              <Row term="Field leader">
                The highest-scoring startup on the weighted quality index — not always the recommended investment (quality and price differ; §12 explains when they split).
              </Row>
              <Row term="Expected return">
                The probability-weighted return range across the modelled exit scenarios, gross of dilution and fees.
              </Row>
              <Row term="&ldquo;Data as of&rdquo; chip">
                The date of the newest evidence found during research. Amber means the freshest source is over six months old.
              </Row>

              <SectionTitle>Reading the numbers</SectionTitle>
              <Row term="&ldquo;Not Disclosed&rdquo;">
                Honest absence — the figure isn&rsquo;t public. The system never fabricates a number to fill a cell.
              </Row>
              <Row term="≈ approximate">
                A company with thin public disclosure gets approximate scores on purpose — precision never exceeds the underlying evidence.
              </Row>
              <Row term="Tooltips">
                Most chips, headers, and figures explain themselves on hover.
              </Row>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
