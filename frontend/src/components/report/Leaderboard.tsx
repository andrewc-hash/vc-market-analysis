"use client";

import type { WeightedScore } from "@/lib/api";
import { segmentColors } from "@/lib/viz";

interface Props {
  ranking: string[];
  weightedScores: Record<string, WeightedScore>;
  segments?: Record<string, string | null>; // startup -> segment (for bar color)
  onSelect?: (name: string) => void;
  scoreConfidence?: Record<string, "low" | "medium" | "high">;
}

export default function Leaderboard({ ranking, weightedScores, segments = {}, onSelect, scoreConfidence }: Props) {
  const ranked = ranking.filter((n) => weightedScores[n]?.weighted_score != null);
  if (ranked.length === 0) {
    return <div className="empty-state">No weighted ranking available for this run.</div>;
  }
  const colors = segmentColors(ranked.map((n) => segments[n] ?? null));
  const max = Math.max(...ranked.map((n) => weightedScores[n].weighted_score as number), 1);

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/40 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="panel-kicker">Weighted underwriting index</div>
        <span className="font-mono text-[10px] tabular-nums text-gray-600">0–100 · higher is better</span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
        Field ranking by the slider-weighted quality index — reconciled from both analysts and computed in code.
        Bar color = market segment. ≈ marks disclosure-limited approximate scores.
      </p>
      <div className="mt-3.5 space-y-1.5">
        {ranked.map((name, i) => {
          const score = weightedScores[name].weighted_score as number;
          const pct = Math.max(2, (score / max) * 100);
          const approx = scoreConfidence?.[name] === "low";
          return (
            <button
              key={name}
              onClick={() => onSelect?.(name)}
              className="group block w-full text-left"
            >
              <div className="flex items-center gap-3 text-[13px]">
                <span className="w-6 shrink-0 text-right font-mono text-[11px] tabular-nums text-gray-600">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="w-36 shrink-0 truncate text-gray-200 group-hover:text-white">{name}</span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-gray-800/70">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, background: colors[segments[name] || "Other"] }}
                  />
                </div>
                <span
                  className="w-12 shrink-0 text-right font-mono text-[12px] tabular-nums text-gray-200"
                  title={approx ? "Disclosure-limited — approximate" : undefined}
                >
                  {approx ? `≈${Math.round(score)}` : score}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
