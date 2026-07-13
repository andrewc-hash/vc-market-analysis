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

export interface PickLabel {
  pick: string; // the name to display (recommended_pick, or ranking[0] fallback)
  kicker: string; // "Top pick" | "Subject" | "Target evaluated"
  rankSuffix: string; // " · ranked #N of M" when the focal is the evaluated pick, else ""
  fieldLeader: string | null; // the quality #1 to surface separately when it isn't the pick
  focalIsPick: boolean; // VC mode AND the pick resolves to the focal (the R11 case)
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
  const kicker = isFounder ? "Subject" : focalIsPick ? "Target evaluated" : "Top pick";
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
    // Star the field leader, never a PASS'd focal that happens to be `pick`.
    starName: focalIsPick ? leader : pick,
  };
}
