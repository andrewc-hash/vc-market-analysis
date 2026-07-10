"use client";

import type { PredictionRow, RunDelta as RunDeltaData } from "@/lib/api";

interface Props {
  delta: RunDeltaData | null | undefined;
  predictions: PredictionRow[] | null | undefined;
  baselineDate?: string;
}

const PRED_STYLE: Record<string, { cls: string; label: string }> = {
  validated: { cls: "bg-emerald-950/40 text-emerald-300 border-emerald-900/60", label: "Validated" },
  broken: { cls: "bg-red-950/40 text-red-300 border-red-900/60", label: "Broken" },
  pending: { cls: "bg-gray-800/60 text-gray-400 border-gray-700", label: "Pending" },
  unresolved: { cls: "bg-amber-950/40 text-amber-300 border-amber-900/60", label: "Unresolved" },
};

const fmtDate = (iso?: string) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
};

/** "What changed since the baseline run" — the code-computed longitudinal diff plus
 * the baseline report's own dated predictions graded against today's evidence. */
export default function RunDelta({ delta, predictions, baselineDate }: Props) {
  if (!delta && !predictions?.length) return null;
  const d = delta;

  return (
    <div className="card space-y-3 border-brand-500/30">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-100">
          What changed since the baseline run{baselineDate ? ` (${fmtDate(baselineDate)})` : ""}
        </h3>
        <span className="text-[11px] text-gray-500">diff computed in code · predictions graded against fresh research</span>
      </div>

      {d && (
        <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
          {d.pick_changed && (
            <div className="rounded-md border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-amber-300 sm:col-span-2">
              Top pick changed: <b>{d.prev_pick}</b> → <b>{d.new_pick}</b>
            </div>
          )}
          {(d.entered.length > 0 || d.exited.length > 0) && (
            <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 text-gray-300">
              {d.entered.length > 0 && <div>Entered the field: <b>{d.entered.join(", ")}</b></div>}
              {d.exited.length > 0 && <div>Left the ranking: <b>{d.exited.join(", ")}</b></div>}
            </div>
          )}
          {d.movers.length > 0 && (
            <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 text-gray-300">
              {d.movers.slice(0, 4).map((m) => (
                <div key={m.startup} className="tabular-nums">
                  {m.startup}: #{m.prev_rank} → #{m.new_rank}
                  {m.score_delta != null ? ` (${m.score_delta > 0 ? "+" : ""}${m.score_delta} pts)` : ""}
                </div>
              ))}
            </div>
          )}
          {d.ledger_changes.length > 0 && (
            <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 text-gray-300">
              {d.ledger_changes.slice(0, 4).map((c, i) => (
                <div key={i} className="tabular-nums">
                  {c.startup} {c.field === "valuation" ? "valuation" : "raised"}: $
                  {c.prev_musd >= 1000 ? `${(c.prev_musd / 1000).toFixed(1)}B` : `${Math.round(c.prev_musd)}M`} → $
                  {c.new_musd >= 1000 ? `${(c.new_musd / 1000).toFixed(1)}B` : `${Math.round(c.new_musd)}M`}
                </div>
              ))}
            </div>
          )}
          {d.new_acquisitions.length > 0 && (
            <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 text-gray-300 sm:col-span-2">
              New exit precedents:{" "}
              {d.new_acquisitions.map((a) => `${a.target} ← ${a.acquirer}${a.value !== "Not Disclosed" ? ` (${a.value})` : ""}`).join(" · ")}
            </div>
          )}
          {d.prev_expected_return != null && d.new_expected_return != null && (
            <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 tabular-nums text-gray-300 sm:col-span-2">
              Expected return (gross midpoint): {d.prev_expected_return}x → {d.new_expected_return}x
            </div>
          )}
        </div>
      )}

      {predictions && predictions.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-medium text-gray-400">
            The baseline report&rsquo;s own dated predictions, graded today
          </div>
          <div className="space-y-1.5">
            {predictions.map((p, i) => {
              const st = PRED_STYLE[p.status] ?? PRED_STYLE.unresolved;
              return (
                <div key={i} className="flex items-start justify-between gap-2 rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2">
                  <div className="min-w-0 text-xs">
                    <span className="text-gray-200">{p.prediction}</span>
                    {p.deadline && <span className="ml-1 tabular-nums text-gray-500">(by {p.deadline})</span>}
                    {p.evidence && <div className="mt-0.5 text-gray-500">{p.evidence}</div>}
                  </div>
                  <span className={`shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${st.cls}`}>
                    {st.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
