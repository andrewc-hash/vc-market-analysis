import type { FinalReport } from "./api";

// Single source of truth for how the "pick" is labeled across EVERY surface
// (masthead, tear sheet, printed PDF, Markdown export). Prevents the R11 header
// trap: in VC + focal mode `recommended_pick` is the evaluated TARGET, which §0/§12
// may verdict WATCH/PASS — so it must never be headlined as a buy ("Top pick").
// Founder mode already reads "Subject". Keep all export paths using THIS.

export const norm = (s: string) => (s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Tolerant name match (equality or containment), mirroring backend `_norm_name`. */
export const nameMatch = (a: string, b: string): boolean =>
  !!a && !!b && (a === b || a.includes(b) || b.includes(a));

export type Verdict = "INVEST" | "WATCH" | "PASS" | null;

/**
 * Extract the §0 verdict (INVEST/WATCH/PASS) from the first ~2500 chars of
 * merged_report. The report template requires §0 to state the verdict explicitly
 * as a standalone word, so a simple keyword scan over the opening section is
 * reliable enough for display purposes (never used for routing logic).
 */
export function extractVerdict(report: FinalReport): Verdict {
  const text = (report.merged_report || "").slice(0, 2500).toUpperCase();
  // Look for the verdict keyword near §0/§12 signal words first, then anywhere.
  const signalZone = text.slice(0, 800);
  if (/\bINVEST\b/.test(signalZone)) return "INVEST";
  if (/\bWATCH\b/.test(signalZone)) return "WATCH";
  if (/\bPASS\b/.test(signalZone)) return "PASS";
  // Broader scan of the full opening block.
  if (/\bINVEST\b/.test(text)) return "INVEST";
  if (/\bWATCH\b/.test(text)) return "WATCH";
  if (/\bPASS\b/.test(text)) return "PASS";
  return null;
}

export interface PickLabel {
  pick: string;        // the name to display (recommended_pick, or ranking[0] fallback)
  kicker: string;      // "Top pick" | "Subject" | "Investment verdict" | "Prospectus take"
  rankSuffix: string;  // " · ranked #N of M" when the focal is the evaluated pick, else ""
  fieldLeader: string | null; // the quality #1 to surface separately when it isn't the pick
  focalIsPick: boolean;       // VC mode AND the pick resolves to the focal (the R11 case)
  verdict: Verdict;           // INVEST/WATCH/PASS extracted from §0, null if unresolved
  /** The name that should carry the ★ "field leader" star in ranked tables. */
  starName: string;
}

export function pickLabel(report: FinalReport): PickLabel {
  const ranking = report.ranking ?? [];
  const isFounder = (report.analysis_mode || "vc").toLowerCase() === "founder";
  const pick = report.recommended_pick || ranking[0] || "";
  const focalNorm = report.focal_startup ? norm(report.focal_startup) : "";
  const focalIsPick = !isFounder && !!focalNorm && !!pick && nameMatch(norm(pick), focalNorm);
  const leader = ranking[0] || "";
  const showLeader = focalIsPick && !!leader && !nameMatch(norm(leader), focalNorm);
  const verdict = (focalIsPick || isFounder) ? extractVerdict(report) : null;
  const kicker = isFounder
    ? "Subject"
    : focalIsPick
      ? verdict
        ? "Prospectus recommendation"
        : "Investment verdict"
      : "Top pick";
  const rankSuffix =
    focalIsPick && report.focal_rank && ranking.length
      ? ` · ranked #${report.focal_rank} of ${ranking.length}`
      : "";
  return {
    pick,
    kicker,
    rankSuffix,
    fieldLeader: showLeader ? leader : null,
    focalIsPick,
    verdict,
    starName: focalIsPick ? leader : pick,
  };
}
