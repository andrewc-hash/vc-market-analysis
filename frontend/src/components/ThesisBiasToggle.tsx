"use client";

interface Props {
  value: "Bear" | "Base" | "Bull";
  onChange: (v: "Bear" | "Base" | "Bull") => void;
}

// Semantic risk gradient (rose -> amber -> emerald) as a quiet tint + dot,
// not a filled block — the saturated fill fought the azure console theme.
const options: { label: "Bear" | "Base" | "Bull"; dot: string; selected: string }[] = [
  { label: "Bear", dot: "bg-rose-400", selected: "bg-rose-500/10 text-rose-300 ring-1 ring-inset ring-rose-500/40" },
  { label: "Base", dot: "bg-amber-400", selected: "bg-amber-500/10 text-amber-300 ring-1 ring-inset ring-amber-500/40" },
  { label: "Bull", dot: "bg-emerald-400", selected: "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/40" },
];

export default function ThesisBiasToggle({ value, onChange }: Props) {
  return (
    <div>
      <span className="label">Risk Appetite / Thesis Bias</span>
      <div className="mt-1 flex gap-1 rounded-lg border border-gray-700 bg-gray-900/60 p-1">
        {options.map((opt) => (
          <button
            key={opt.label}
            type="button"
            onClick={() => onChange(opt.label)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md py-2 text-sm font-medium transition-colors ${
              value === opt.label ? opt.selected : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${opt.dot} ${value === opt.label ? "" : "opacity-40"}`} />
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
