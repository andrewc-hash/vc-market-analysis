// Workspace fund profile — fund economics as a set-once setting, not a per-run input.
// Persisted in localStorage; ResearchForm reads it at mount and auto-applies it to the
// Fund Economics card, and the /app "Fund Profile" view edits it. Values are kept as
// STRINGS matching the form's state shape (the form owns numeric coercion at submit).

export interface FundProfile {
  fundSize: string;
  check: string;
  post: string;
  ownership: string;
  years: string;
}

const STORAGE_KEY = "prospectus-fund-profile";

const FIELDS: (keyof FundProfile)[] = ["fundSize", "check", "post", "ownership", "years"];

/** A profile only "counts" (gets auto-applied) when it has a valid fund size —
 *  the same master gate the backend fund-math engine uses. */
export function isFundProfileSet(p: FundProfile | null): p is FundProfile {
  return !!p && Number.isFinite(parseFloat(p.fundSize)) && parseFloat(p.fundSize) > 0;
}

/** SSR-safe load. Returns null when absent, corrupt, or not in a browser. */
export function loadFundProfile(): FundProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
    const rec = parsed as Record<string, unknown>;
    const profile = {} as FundProfile;
    for (const f of FIELDS) {
      const v = rec[f];
      // Tolerate legacy/foreign shapes: strings pass through, finite numbers stringify,
      // anything else becomes empty (never crash the form over a corrupt profile).
      profile[f] =
        typeof v === "string" ? v : typeof v === "number" && Number.isFinite(v) ? String(v) : "";
    }
    return profile;
  } catch {
    return null;
  }
}

export function saveFundProfile(p: FundProfile): void {
  if (typeof window === "undefined") return;
  try {
    const clean = {} as FundProfile;
    for (const f of FIELDS) clean[f] = (p[f] ?? "").trim();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
  } catch {
    // Storage full / blocked (private mode) — the profile simply doesn't persist.
  }
}

export function clearFundProfile(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

/** One-line human summary of the set fields, e.g.
 *  "$50M fund · $2M check · 10% target ownership". */
export function summarizeFundProfile(p: FundProfile): string {
  const parts: string[] = [];
  const has = (s: string) => Number.isFinite(parseFloat(s)) && parseFloat(s) > 0;
  if (has(p.fundSize)) parts.push(`$${p.fundSize.trim()}M fund`);
  if (has(p.check)) parts.push(`$${p.check.trim()}M check`);
  if (has(p.post)) parts.push(`$${p.post.trim()}M entry post`);
  if (has(p.ownership)) parts.push(`${p.ownership.trim()}% target ownership`);
  if (has(p.years)) parts.push(`${p.years.trim()}-yr hold`);
  return parts.join(" · ");
}
