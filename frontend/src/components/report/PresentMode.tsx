"use client";

import { useEffect, useState } from "react";
import type { FinalReport, TourStep } from "@/lib/api";
import MarketMap from "./MarketMap";
import Leaderboard from "./Leaderboard";
import Scorecard from "./Scorecard";
import Gradesheet from "./Gradesheet";
import FinancialLedger from "./FinancialLedger";
import { Icon } from "../icons";

interface Props {
  report: FinalReport;
  steps: TourStep[];
  onClose: () => void;
  onJump: (step: TourStep) => void;
}

/** Full-screen guided walkthrough of a finished report — a slide deck derived
 * from report.tour (or the client-side fallback in lib/tour.ts). */
export default function PresentMode({ report, steps, onClose, onJump }: Props) {
  const [idx, setIdx] = useState(0);
  const step = steps[idx];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        setIdx((i) => Math.min(i + 1, steps.length - 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps.length, onClose]);

  if (!step) return null;

  const ranking = report.ranking ?? [];
  const weighted = report.weighted_scores ?? {};
  const map = report.market_map ?? null;
  const ledger = report.financial_ledger ?? null;
  const segments: Record<string, string | null> = {};
  map?.companies.forEach((c) => {
    segments[c.name] = c.segment;
  });

  const visual = (() => {
    switch (step.visual) {
      case "map":
        return map ? <MarketMap map={map} ranking={ranking} /> : null;
      case "scorecard":
        return Object.keys(weighted).length ? (
          <div className="space-y-5">
            <Leaderboard ranking={ranking} weightedScores={weighted} segments={segments} scoreConfidence={report.score_confidence} />
            <Scorecard
              ranking={ranking}
              weightedScores={weighted}
              appliedWeights={report.applied_weights}
              moatSubscores={report.moat_subscores}
              prePmf={report.pre_pmf}
              scoreConfidence={report.score_confidence}
            />
          </div>
        ) : null;
      case "grades":
        return report.gradesheet?.startups?.length ? (
          <Gradesheet gradesheet={report.gradesheet} analysisMode={report.analysis_mode} />
        ) : null;
      case "ledger":
      case "fundfit":
        // Fund Fit renders inside FinancialLedger (fundMath prop); when fund_math
        // is absent this degrades to the scenarios/ledger view, and with no ledger
        // at all we show no visual.
        return ledger ? (
          <FinancialLedger
            ledger={ledger}
            scenarios={report.scenarios ?? null}
            expectedReturn={report.expected_return ?? null}
            expectedReturnLow={report.expected_return_low ?? null}
            expectedReturnHigh={report.expected_return_high ?? null}
            expectedReturnNetLow={report.expected_return_net_low ?? null}
            expectedReturnNetHigh={report.expected_return_net_high ?? null}
            returnAssumptions={report.return_assumptions ?? null}
            returnDominance={report.return_dominance ?? null}
            acquisitions={report.acquisitions ?? null}
            fundMath={report.fund_math ?? null}
            capTable={report.cap_table ?? null}
          />
        ) : null;
      default:
        return null;
    }
  })();

  return (
    <div className="no-print fixed inset-0 z-50 flex flex-col bg-gray-950">
      {/* top bar */}
      <div className="flex shrink-0 items-center justify-between border-b border-gray-800 px-6 py-3">
        <div className="kicker">
          Present · {(report.sector || "Market analysis").trim() || "Market analysis"}
        </div>
        <button
          onClick={onClose}
          aria-label="Close presentation"
          className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-200"
        >
          <Icon name="x" className="h-4 w-4" />
        </button>
      </div>

      {/* slide */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col justify-center px-6 py-10">
          <div className="kicker">
            Step {idx + 1} of {steps.length} · §{step.section}
          </div>
          <h2 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-gray-100 sm:text-4xl">
            {step.title}
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-relaxed text-gray-400">{step.summary}</p>
          <button
            onClick={() => onJump(step)}
            className="mt-4 inline-flex w-fit items-center gap-1.5 text-sm text-brand-300 transition-colors hover:text-brand-200"
          >
            Open full section
            <Icon name="arrow-right" className="h-3.5 w-3.5" />
          </button>
          {visual && (
            <div className="mt-8 rounded-lg border border-gray-800 bg-gray-900 p-4">{visual}</div>
          )}
        </div>
      </div>

      {/* nav */}
      <div className="flex shrink-0 items-center justify-between border-t border-gray-800 px-6 py-3">
        <button
          onClick={() => setIdx((i) => Math.max(i - 1, 0))}
          disabled={idx === 0}
          className="btn-secondary disabled:cursor-default disabled:opacity-40"
        >
          ← Prev
        </button>
        <div className="flex items-center gap-1.5">
          {steps.map((s, i) => (
            <button
              key={s.id + i}
              onClick={() => setIdx(i)}
              aria-label={`Go to step ${i + 1}: ${s.title}`}
              className={`h-1.5 rounded-full transition-all ${
                i === idx ? "w-5 bg-brand-400" : "w-1.5 bg-gray-700 hover:bg-gray-500"
              }`}
            />
          ))}
        </div>
        <button
          onClick={() => setIdx((i) => Math.min(i + 1, steps.length - 1))}
          disabled={idx === steps.length - 1}
          className="btn-secondary disabled:cursor-default disabled:opacity-40"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
