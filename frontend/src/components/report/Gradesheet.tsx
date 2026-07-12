"use client";

import { useState } from "react";
import type { Gradesheet as GradesheetData } from "@/lib/api";
import { gradeColor } from "@/lib/viz";

interface Props {
  gradesheet: GradesheetData | null | undefined;
  analysisMode?: string;
}

/** Visual letter-grade tab. Every grade is computed IN CODE from the reconciled
 * scores (see final_report.gradesheet); this component only renders. */
export default function Gradesheet({ gradesheet, analysisMode }: Props) {
  const [showRubric, setShowRubric] = useState(false);
  const startups = gradesheet?.startups ?? [];
  const criteria = gradesheet?.criteria ?? [];

  if (startups.length === 0) {
    return <p className="text-sm text-gray-500">No gradesheet available for this run.</p>;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">
          Letter grades computed in code from the reconciled scorecard — never LLM-graded.
          <span className="text-gray-600"> NR = not rated (metric undisclosed).</span>
        </p>
        <button
          type="button"
          onClick={() => setShowRubric((v) => !v)}
          className="shrink-0 rounded-md border border-gray-800 px-2.5 py-1 text-xs text-gray-400 hover:text-gray-200"
        >
          {showRubric ? "Hide" : "Show"} grading criteria
        </button>
      </div>

      {showRubric && (
        <div className="space-y-2 rounded-lg border border-gray-800 bg-gray-900/40 p-3">
          {criteria.map((c) => (
            <div key={c.key} className="text-xs">
              <span className="font-semibold text-gray-200">{c.label}</span>
              <span className="text-gray-500"> — {c.calculation}</span>
            </div>
          ))}
        </div>
      )}

      {startups.map((s) => {
        const oc = gradeColor(s.overall.letter);
        return (
          <div
            key={s.name}
            className={`rounded-xl border p-4 ${
              s.is_focal ? "border-brand-500/40 bg-brand-500/5" : "border-gray-800 bg-gray-900/30"
            }`}
          >
            {/* header: name + overall grade */}
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-gray-100">{s.name}</h3>
                {s.is_focal && (
                  <span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-brand-300 ring-1 ring-brand-500/20">
                    {analysisMode === "founder" ? "Your startup" : "Target"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wide text-gray-500">Overall</span>
                <span
                  className="rounded-md px-2.5 py-1 text-lg font-black leading-none"
                  style={{ backgroundColor: oc.bg, color: oc.fg }}
                  title={s.overall.note}
                >
                  {s.overall.letter}
                </span>
              </div>
            </div>

            {/* criterion cards */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {criteria.map((c) => {
                const cell = s.cells[c.key];
                if (!cell) return null;
                const col = gradeColor(cell.letter);
                return (
                  <div
                    key={c.key}
                    className="flex items-start justify-between gap-2 rounded-lg border border-gray-800 bg-gray-950/40 p-2.5"
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-gray-200">{c.label}</div>
                      <div className="mt-0.5 truncate text-[11px] text-gray-500" title={cell.note}>
                        {cell.note}
                      </div>
                    </div>
                    <span
                      className="shrink-0 rounded-md px-2 py-0.5 text-sm font-black leading-tight"
                      style={{ backgroundColor: col.bg, color: col.fg }}
                    >
                      {cell.letter}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
