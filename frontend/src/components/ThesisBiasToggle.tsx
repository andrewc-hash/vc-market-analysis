"use client";

interface Props {
  value: "Bear" | "Base" | "Bull";
  onChange: (v: "Bear" | "Base" | "Bull") => void;
}

// Semantic risk gradient (red -> amber -> green), refined to sit on the slate theme.
const options: { label: string; value: "Bear" | "Base" | "Bull"; color: string }[] = [
  { label: "Bear", value: "Bear", color: "bg-rose-500" },
  { label: "Base", value: "Base", color: "bg-amber-500" },
  { label: "Bull", value: "Bull", color: "bg-emerald-500" },
];

export default function ThesisBiasToggle({ value, onChange }: Props) {
  return (
    <div>
      <span className="label">Risk Appetite / Thesis Bias</span>
      <div className="flex rounded-lg border border-gray-700 overflow-hidden">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex-1 py-3 text-sm font-semibold transition-colors ${
              value === opt.value
                ? `${opt.color} text-white`
                : "bg-gray-800 text-gray-400 hover:bg-gray-750"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <p className="mt-1.5 text-xs text-gray-500">
        {value === "Bear" && "Hyper-skeptical Red-Team auditor — enforces strict scoring caps."}
        {value === "Base" && "Objective institutional partner — realistic mainstream evaluation."}
        {value === "Bull" && "High-conviction thesis investor — emphasizes explosive expansion."}
      </p>
    </div>
  );
}
