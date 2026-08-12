"use client";

import type { WeightedScore } from "@/lib/api";
import { DIMENSION_LABELS, scoreColor } from "@/lib/viz";

interface Props {
  ranking: string[];
  weightedScores: Record<string, WeightedScore>;
  appliedWeights?: Record<string, number>;
  moatSubscores?: Record<string, Record<string, number>>;
  prePmf?: string[];
  // Ledger-disclosure-based confidence, computed in code: low-disclosure startups get
  // "≈" (approximate) scores so precision never exceeds the underlying data.
  scoreConfidence?: Record<string, "low" | "medium" | "high">;
}

const MOAT_LABELS: { key: string; short: string }[] = [
  { key: "economies_of_scale", short: "Scale" },
  { key: "differentiated_technology", short: "Tech" },
  { key: "network_effects", short: "Network" },
  { key: "brand_power", short: "Brand" },
];

export default function Scorecard({ ranking, weightedScores, appliedWeights, moatSubscores, prePmf, scoreConfidence }: Props) {
  const names = (ranking.length ? ranking : Object.keys(weightedScores)).filter((n) => weightedScores[n]);
  if (names.length === 0) {
    return <div className="empty-state">No scorecard available for this run.</div>;
  }

  return (
    <div className="space-y-4">
      {/* heatmap panel: startups x dimensions (cell shade = score magnitude, colorblind-safe) */}
      <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
        <div className="panel-kicker">Dimension scorecard</div>
        <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
          Per-dimension 0–100 scores reconciled from both analysts; the Weighted column applies your slider weights in code.
        </p>

        {/* applied weights */}
        {appliedWeights && Object.keys(appliedWeights).length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="panel-kicker mr-1">Applied weights</span>
            {DIMENSION_LABELS.map(({ key, short }) => (
              <span key={key} className="chip">
                {short} <span className="text-gray-200">{Math.round((appliedWeights[key] ?? 0) * 100)}%</span>
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-separate border-spacing-1 text-xs">
            <thead>
              <tr>
                <th className="th-label pb-1 text-left">Startup</th>
                {DIMENSION_LABELS.map(({ key, short }) => (
                  <th key={key} className="th-label px-1 pb-1 text-center">{short}</th>
                ))}
                <th className="th-label px-1 pb-1 text-center text-gray-300">Weighted</th>
              </tr>
            </thead>
            <tbody>
              {names.map((name) => {
                const row = weightedScores[name];
                // Low-disclosure startups: approximate integers, never decimal precision.
                const lowConf = scoreConfidence?.[name] === "low";
                const fmt = (v: number | null | undefined) =>
                  v == null ? "—" : lowConf ? `≈${Math.round(v)}` : v;
                return (
                  <tr key={name}>
                    <td className="max-w-[9rem] whitespace-nowrap pr-2 text-gray-200" title={lowConf ? "Disclosure-limited: most ledger metrics are Not Disclosed — scores are approximate" : undefined}>
                      <span className="truncate align-middle">{name}</span>
                      {lowConf && <span className="chip ml-1.5 align-middle">low data</span>}
                    </td>
                    {DIMENSION_LABELS.map(({ key }) => {
                      const v = row[key];
                      const c = scoreColor(v);
                      return (
                        <td key={key} className="rounded px-1.5 py-1 text-center font-mono tabular-nums" style={{ background: c.bg, color: c.fg }}>
                          {fmt(v)}
                        </td>
                      );
                    })}
                    <td className="rounded px-1.5 py-1 text-center font-mono font-semibold tabular-nums" style={(() => { const c = scoreColor(row.weighted_score); return { background: c.bg, color: c.fg }; })()}>
                      {fmt(row.weighted_score)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[10.5px] text-gray-600">
          Cell shade encodes the 0–100 score (darker = higher). Weighted column is system-computed from the applied weights.
        </p>
      </section>

      {/* R10: Defensibility moat breakdown — the Defensibility column above = mean of these 4 */}
      {moatSubscores && Object.keys(moatSubscores).length > 0 && (
        <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
          <div className="panel-kicker">Defensibility moat sub-scores</div>
          <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
            The four a16z moat components — the Defensibility dimension above = their mean, enforced in code (R10).
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-separate border-spacing-1 text-xs">
              <thead>
                <tr>
                  <th className="th-label pb-1 text-left">Startup</th>
                  {MOAT_LABELS.map(({ key, short }) => (
                    <th key={key} className="th-label px-1 pb-1 text-center">{short}</th>
                  ))}
                  <th className="th-label px-1 pb-1 text-center text-gray-300">Mean</th>
                </tr>
              </thead>
              <tbody>
                {names.filter((n) => moatSubscores[n]).map((name) => {
                  const subs = moatSubscores[name];
                  const present = MOAT_LABELS.map((m) => subs[m.key]).filter((v) => typeof v === "number");
                  const mean = present.length ? Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 10) / 10 : null;
                  return (
                    <tr key={name}>
                      <td className="max-w-[9rem] truncate pr-2 text-gray-300">{name}</td>
                      {MOAT_LABELS.map(({ key }) => {
                        const v = subs[key];
                        const c = scoreColor(typeof v === "number" ? v : null);
                        return (
                          <td key={key} className="rounded px-1.5 py-1 text-center font-mono tabular-nums" style={{ background: c.bg, color: c.fg }}>
                            {typeof v === "number" ? v : "—"}
                          </td>
                        );
                      })}
                      <td className="rounded px-1.5 py-1 text-center font-mono font-semibold tabular-nums" style={(() => { const c = scoreColor(mean); return { background: c.bg, color: c.fg }; })()}>
                        {mean ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {prePmf && prePmf.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-1">
          <span className="panel-kicker mr-1">Watchlist · pre-PMF, not scored</span>
          {prePmf.map((n) => (
            <span key={n} className="chip">{n}</span>
          ))}
        </div>
      )}
    </div>
  );
}
