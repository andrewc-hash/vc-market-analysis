"use client";

import type { DimensionWeights as DW } from "@/lib/api";

interface Props {
  weights: DW;
  onChange: (w: DW) => void;
}

const dimensions: { key: keyof DW; label: string }[] = [
  { key: "financial_health", label: "Financial Health & Capital Efficiency" },
  { key: "defensibility", label: "Defensibility & IP Moat" },
  { key: "market_urgency", label: "Market Urgency & TRL" },
  { key: "founder_market_fit", label: "Founder-Market Fit" },
  { key: "regulatory_alignment", label: "Regulatory Alignment" },
];

export default function DimensionWeightsPanel({ weights, onChange }: Props) {
  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-100">Evaluation Dimension Weights</h2>
        <span className="text-xs tabular-nums text-gray-400">Total: {total}%</span>
      </div>
      <p className="mb-4 text-xs text-gray-500">
        Weights are <span className="text-gray-400">relative</span> — normalized automatically, so they need not sum to 100.
      </p>
      <div className="space-y-4">
        {dimensions.map(({ key, label }) => (
          <div key={key}>
            <label className="mb-1.5 block text-sm text-gray-300">{label}</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={100}
                value={weights[key]}
                onChange={(e) => onChange({ ...weights, [key]: Number(e.target.value) })}
                className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-700 accent-brand-500"
              />
              <span className="w-14 shrink-0 rounded-md border border-gray-700 bg-gray-800 py-1 text-center text-xs tabular-nums text-gray-200">
                {weights[key]}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
