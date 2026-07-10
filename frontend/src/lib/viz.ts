// Visualization helpers — colorblind-safe palette + scales for the report graphics.

// Okabe-Ito qualitative palette (colorblind-safe) for categorical segments.
export const CB_PALETTE = [
  "#56B4E9", // sky blue
  "#E69F00", // orange
  "#009E73", // bluish green
  "#CC79A7", // reddish purple
  "#0072B2", // blue
  "#D55E00", // vermillion
  "#F0E442", // yellow
  "#BBBBBB", // grey
];

/** Map distinct segments to stable colors (null/empty -> "Other"). */
export function segmentColors(segments: (string | null | undefined)[]): Record<string, string> {
  const map: Record<string, string> = {};
  let i = 0;
  for (const s of segments) {
    const key = s && s.trim() ? s : "Other";
    if (!(key in map)) {
      map[key] = CB_PALETTE[i % CB_PALETTE.length];
      i += 1;
    }
  }
  return map;
}

/**
 * Sequential single-hue scale for a 0-100 score (colorblind-safe: magnitude is
 * encoded by lightness, not by red/green). Higher score -> darker/more saturated.
 */
export function scoreColor(score: number | null | undefined): { bg: string; fg: string } {
  // Coerce defensively: a judge can emit a quoted number ("85") despite the type.
  const n = typeof score === "number" ? score : Number(score);
  if (score == null || Number.isNaN(n)) {
    return { bg: "#111827", fg: "#6b7280" }; // gray-900 / gray-500 for "no data"
  }
  const s = Math.max(0, Math.min(100, n));
  const lightness = 90 - (s / 100) * 55; // 90% (low) -> 35% (high)
  return { bg: `hsl(212 70% ${lightness}%)`, fg: lightness < 58 ? "#ffffff" : "#0b1220" };
}

/** Letter grade -> color, keyed by the letter's first char (A green → F red; NR gray).
 * Magnitude is also legible from the letter itself, so this is not color-only. */
export function gradeColor(letter: string | null | undefined): { bg: string; fg: string } {
  const c = (letter || "").trim().charAt(0).toUpperCase();
  switch (c) {
    case "A": return { bg: "#15803d", fg: "#ffffff" }; // green-700
    case "B": return { bg: "#4d7c0f", fg: "#ffffff" }; // lime-700
    case "C": return { bg: "#b45309", fg: "#ffffff" }; // amber-700
    case "D": return { bg: "#c2410c", fg: "#ffffff" }; // orange-700
    case "F": return { bg: "#b91c1c", fg: "#ffffff" }; // red-700
    default:  return { bg: "#1f2937", fg: "#9ca3af" }; // gray — NR / unknown
  }
}

// Ledger flags — color + symbol (symbol so it's not color-only / colorblind-safe).
export const FLAG_STYLE: Record<string, { cls: string; sym: string; label: string }> = {
  ok: { cls: "text-green-300", sym: "✓", label: "meets stage band" },
  warn: { cls: "text-amber-300", sym: "!", label: "borderline" },
  bad: { cls: "text-red-300", sym: "✗", label: "off stage band" },
};

/** Bubble radius from capital raised ($M), area-proportional (sqrt), with a floor. */
export function radiusFor(raised: number | null | undefined, maxRaised: number): number {
  if (raised == null || raised <= 0 || maxRaised <= 0) return 7;
  return 7 + 13 * Math.sqrt(raised / maxRaised);
}

export const DIMENSION_LABELS: { key: keyof import("./api").DimensionScores; short: string }[] = [
  { key: "financial_health", short: "Financial" },
  { key: "defensibility", short: "Defensibility" },
  { key: "market_urgency", short: "Mkt Urgency" },
  { key: "founder_market_fit", short: "Founder Fit" },
  { key: "regulatory_alignment", short: "Regulatory" },
];
