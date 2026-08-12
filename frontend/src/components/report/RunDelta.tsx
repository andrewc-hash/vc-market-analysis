"use client";

import type { PredictionRow, RunDelta as RunDeltaData } from "@/lib/api";

interface Props {
  delta: RunDeltaData | null | undefined;
  predictions: PredictionRow[] | null | undefined;
  baselineDate?: string;
}

// Same chip anatomy as the Claims tab so prediction verdicts read as one language.
const chipBase =
  "inline-flex shrink-0 items-center gap-1 rounded border px-2 py-[3px] font-mono text-[10px] font-medium uppercase tracking-[0.08em]";
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

const fmtMusd = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`);

// Signed movement — emerald/rose ONLY where direction is meaningful (rank up/down,
// money up/down); neutral facts stay gray.
const Dir = ({ up, children }: { up: boolean; children: React.ReactNode }) => (
  <span className={`font-mono text-[10.5px] tabular-nums ${up ? "text-emerald-300" : "text-rose-300"}`}>{children}</span>
);

const deltaBox = "rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2";

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
        <span className="panel-kicker normal-case tracking-[0.08em]">
          diff computed in code · predictions graded against fresh research
        </span>
      </div>

      {d && (
        <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
          {d.pick_changed && (
            <div className="rounded-md border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-amber-300 sm:col-span-2">
              <span className="mr-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-amber-400">Top pick changed</span>
              <b>{d.prev_pick}</b> → <b>{d.new_pick}</b>
            </div>
          )}
          {(d.entered.length > 0 || d.exited.length > 0) && (
            <div className={`${deltaBox} text-gray-300`}>
              <div className="panel-kicker mb-1">Field</div>
              {d.entered.length > 0 && (
                <div>
                  <span className="mr-1 font-mono text-emerald-300">+</span>
                  Entered the field: <b>{d.entered.join(", ")}</b>
                </div>
              )}
              {d.exited.length > 0 && (
                <div>
                  <span className="mr-1 font-mono text-rose-300">−</span>
                  Left the ranking: <b>{d.exited.join(", ")}</b>
                </div>
              )}
            </div>
          )}
          {d.movers.length > 0 && (
            <div className={`${deltaBox} text-gray-300`}>
              <div className="panel-kicker mb-1">Rank movers</div>
              {d.movers.slice(0, 4).map((m) => (
                <div key={m.startup} className="tabular-nums">
                  <Dir up={m.new_rank < m.prev_rank}>{m.new_rank < m.prev_rank ? "▲" : "▼"}</Dir>{" "}
                  {m.startup}: #{m.prev_rank} → #{m.new_rank}
                  {m.score_delta != null ? (
                    <>
                      {" "}
                      <Dir up={m.score_delta > 0}>
                        ({m.score_delta > 0 ? "+" : ""}
                        {m.score_delta} pts)
                      </Dir>
                    </>
                  ) : null}
                </div>
              ))}
            </div>
          )}
          {d.ledger_changes.length > 0 && (
            <div className={`${deltaBox} text-gray-300`}>
              <div className="panel-kicker mb-1">Ledger</div>
              {d.ledger_changes.slice(0, 4).map((c, i) => (
                <div key={i} className="tabular-nums">
                  {c.startup} {c.field === "valuation" ? "valuation" : "raised"}: {fmtMusd(c.prev_musd)} →{" "}
                  <Dir up={c.new_musd >= c.prev_musd}>{fmtMusd(c.new_musd)}</Dir>
                </div>
              ))}
            </div>
          )}
          {d.new_acquisitions.length > 0 && (
            <div className={`${deltaBox} text-gray-300 sm:col-span-2`}>
              <div className="panel-kicker mb-1">New exit precedents</div>
              {d.new_acquisitions.map((a) => `${a.target} ← ${a.acquirer}${a.value !== "Not Disclosed" ? ` (${a.value})` : ""}`).join(" · ")}
            </div>
          )}
          {d.prev_expected_return != null && d.new_expected_return != null && (
            <div className={`${deltaBox} tabular-nums text-gray-300 sm:col-span-2`}>
              <div className="panel-kicker mb-1">Expected return (gross midpoint)</div>
              {d.prev_expected_return}x →{" "}
              {d.new_expected_return === d.prev_expected_return ? (
                <span>{d.new_expected_return}x</span>
              ) : (
                <Dir up={d.new_expected_return > d.prev_expected_return}>{d.new_expected_return}x</Dir>
              )}
            </div>
          )}
        </div>
      )}

      {predictions && predictions.length > 0 && (
        <div>
          <div className="panel-kicker mb-1.5">
            The baseline report&rsquo;s own dated predictions, graded today
          </div>
          <div className="space-y-1.5">
            {predictions.map((p, i) => {
              const st = PRED_STYLE[p.status] ?? PRED_STYLE.unresolved;
              return (
                <div key={i} className="flex items-start justify-between gap-3 rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2">
                  <div className="min-w-0 text-xs">
                    <span className="text-gray-200">{p.prediction}</span>
                    {p.deadline && <span className="ml-1 font-mono text-[10.5px] tabular-nums text-gray-500">(by {p.deadline})</span>}
                    {p.evidence && <div className="mt-0.5 leading-relaxed text-gray-500">{p.evidence}</div>}
                  </div>
                  <span className={`${chipBase} ${st.cls}`}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
