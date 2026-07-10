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
    return <p className="text-sm text-gray-500">No weighted ranking available for this run.</p>;
  }
  const colors = segmentColors(ranked.map((n) => segments[n] ?? null));
  const max = Math.max(...ranked.map((n) => weightedScores[n].weighted_score as number), 1);

  return (
    <div className="space-y-2">
      {ranked.map((name, i) => {
        const score = weightedScores[name].weighted_score as number;
        const pct = Math.max(2, (score / max) * 100);
        return (
          <button
            key={name}
            onClick={() => onSelect?.(name)}
            className="block w-full text-left group"
          >
            <div className="flex items-center gap-2 text-sm">
              <span className="w-5 shrink-0 text-right font-mono text-gray-500">{i + 1}</span>
              <span className="w-32 shrink-0 truncate text-gray-200 group-hover:text-white">{name}</span>
              <div className="relative h-4 flex-1 rounded bg-gray-800">
                <div
                  className="h-4 rounded"
                  style={{ width: `${pct}%`, background: colors[segments[name] || "Other"] }}
                />
              </div>
              <span className="w-11 shrink-0 text-right font-mono text-gray-300" title={scoreConfidence?.[name] === "low" ? "Disclosure-limited — approximate" : undefined}>
                {scoreConfidence?.[name] === "low" ? `≈${Math.round(score)}` : score}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
