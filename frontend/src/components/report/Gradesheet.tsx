"use client";

import { useState } from "react";
import type { Gradesheet as GradesheetData } from "@/lib/api";

interface Props {
  gradesheet: GradesheetData | null | undefined;
  analysisMode?: string;
}

/** Letter -> text color (semantic score band; magnitude is also legible from the
 * letter itself, so this is not color-only). NR is a quiet neutral, never a failure. */
const letterColor = (letter: string | null | undefined): string => {
  const c = (letter || "").trim().charAt(0).toUpperCase();
  switch (c) {
    case "A": return "text-emerald-400";
    case "B": return "text-lime-400";
    case "C": return "text-amber-400";
    case "D": return "text-orange-400";
    case "F": return "text-rose-400";
    default:  return "text-gray-500"; // NR / unknown — neutral
  }
};

/** Visual letter-grade tab. Every grade is computed IN CODE from the reconciled
 * scores (see final_report.gradesheet); this component only renders. */
export default function Gradesheet({ gradesheet, analysisMode }: Props) {
  const [showRubric, setShowRubric] = useState(false);
  const startups = gradesheet?.startups ?? [];
  const criteria = gradesheet?.criteria ?? [];

  if (startups.length === 0) {
    return <div className="empty-state">No gradesheet available for this run.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="panel-kicker">Grade sheet</div>
          <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
            Letter grades computed in code from the reconciled scorecard — never LLM-graded.{" "}
            <span className="text-gray-600">NR = not rated (metric undisclosed), a neutral — not a failure.</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowRubric((v) => !v)}
          className="shrink-0 rounded-md border border-gray-800 px-2.5 py-1 text-xs text-gray-400 hover:text-gray-200"
        >
          {showRubric ? "Hide" : "Show"} grading criteria
        </button>
      </div>

      {showRubric && (
        <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
          <div className="panel-kicker mb-2">Grading criteria — coded rubric</div>
          <div className="space-y-2">
            {criteria.map((c) => (
              <div key={c.key} className="text-[11px] leading-relaxed">
                <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-gray-300">{c.label}</span>
                <span className="text-gray-500"> — {c.calculation}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {startups.map((s) => {
        return (
          <section
            key={s.name}
            className={`rounded-lg border p-4 ${
              s.is_focal ? "border-brand-500/40 bg-brand-500/5" : "border-gray-800 bg-gray-900/40"
            }`}
          >
            {/* header: name + overall grade */}
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <h3 className="truncate text-[15px] font-semibold text-gray-100">{s.name}</h3>
                {s.is_focal && (
                  <span className="chip-accent shrink-0">
                    {analysisMode === "founder" ? "Your startup" : "Target"}
                  </span>
                )}
              </div>
              <div className="flex shrink-0 items-baseline gap-2.5">
                <span className="panel-kicker">Overall</span>
                <span
                  className={`text-2xl font-semibold leading-none ${letterColor(s.overall.letter)}`}
                  title={s.overall.note}
                >
                  {s.overall.letter}
                </span>
              </div>
            </div>

            {/* criterion cells — instrument grid with hairline seams */}
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60 sm:grid-cols-3">
              {criteria.map((c) => {
                const cell = s.cells[c.key];
                if (!cell) {
                  return <div key={c.key} className="bg-gray-900 px-4 py-3" />;
                }
                return (
                  <div key={c.key} className="bg-gray-900 px-4 py-3">
                    <div className="font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-gray-500">
                      {c.label}
                    </div>
                    <div className={`mt-1.5 text-xl font-semibold leading-7 ${letterColor(cell.letter)}`}>
                      {cell.letter}
                    </div>
                    <div className="mt-1 truncate font-mono text-[10px] text-gray-600" title={cell.note}>
                      {cell.note}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
