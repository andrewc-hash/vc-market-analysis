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
    return <p className="text-sm text-gray-500">No scorecard available for this run.</p>;
  }

  return (
    <div className="space-y-4">
      {/* applied weights */}
      {appliedWeights && Object.keys(appliedWeights).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium text-gray-400">Applied weights</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-400">
            {DIMENSION_LABELS.map(({ key, short }) => (
              <span key={key} className="font-mono">
                {short} <span className="text-gray-200">{Math.round((appliedWeights[key] ?? 0) * 100)}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* heatmap: startups x dimensions (color = score magnitude, colorblind-safe) */}
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-xs">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left font-medium">Startup</th>
              {DIMENSION_LABELS.map(({ key, short }) => (
                <th key={key} className="px-1 text-center font-medium">{short}</th>
              ))}
              <th className="px-1 text-center font-medium text-gray-300">Weighted</th>
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
                  <td className="max-w-[8rem] truncate pr-2 text-gray-200" title={lowConf ? "Disclosure-limited: most ledger metrics are Not Disclosed — scores are approximate" : undefined}>
                    {name}
                    {lowConf && <span className="ml-1 rounded bg-gray-800 px-1 text-[9px] uppercase tracking-wide text-gray-500">low data</span>}
                  </td>
                  {DIMENSION_LABELS.map(({ key }) => {
                    const v = row[key];
                    const c = scoreColor(v);
                    return (
                      <td key={key} className="rounded px-1.5 py-1 text-center font-mono" style={{ background: c.bg, color: c.fg }}>
                        {fmt(v)}
                      </td>
                    );
                  })}
                  <td className="rounded px-1.5 py-1 text-center font-mono font-semibold" style={(() => { const c = scoreColor(row.weighted_score); return { background: c.bg, color: c.fg }; })()}>
                    {fmt(row.weighted_score)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-gray-600">Darker = higher score (0–100). Weighted column is system-computed from the applied weights.</p>

      {/* R10: Defensibility moat breakdown — the Defensibility column above = mean of these 4 */}
      {moatSubscores && Object.keys(moatSubscores).length > 0 && (
        <div className="overflow-x-auto">
          <div className="mb-1 text-xs font-medium text-gray-400">Defensibility moat sub-scores <span className="font-normal text-gray-600">(a16z — Defensibility = their mean)</span></div>
          <table className="w-full border-separate border-spacing-1 text-xs">
            <thead>
              <tr className="text-gray-500">
                <th className="text-left font-medium">Startup</th>
                {MOAT_LABELS.map(({ key, short }) => (
                  <th key={key} className="px-1 text-center font-medium">{short}</th>
                ))}
                <th className="px-1 text-center font-medium text-gray-300">Mean</th>
              </tr>
            </thead>
            <tbody>
              {names.filter((n) => moatSubscores[n]).map((name) => {
                const subs = moatSubscores[name];
                const present = MOAT_LABELS.map((m) => subs[m.key]).filter((v) => typeof v === "number");
                const mean = present.length ? Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 10) / 10 : null;
                return (
                  <tr key={name}>
                    <td className="max-w-[8rem] truncate pr-2 text-gray-300">{name}</td>
                    {MOAT_LABELS.map(({ key }) => {
                      const v = subs[key];
                      const c = scoreColor(typeof v === "number" ? v : null);
                      return (
                        <td key={key} className="rounded px-1.5 py-1 text-center font-mono" style={{ background: c.bg, color: c.fg }}>
                          {typeof v === "number" ? v : "—"}
                        </td>
                      );
                    })}
                    <td className="rounded px-1.5 py-1 text-center font-mono font-semibold" style={(() => { const c = scoreColor(mean); return { background: c.bg, color: c.fg }; })()}>
                      {mean ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {prePmf && prePmf.length > 0 && (
        <p className="text-[11px] text-gray-500">
          <span className="font-medium text-gray-400">Watchlist (pre-PMF, not scored):</span> {prePmf.join(", ")}
        </p>
      )}
    </div>
  );
}
