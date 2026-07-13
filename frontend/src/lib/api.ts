// Empty string = same-origin relative /api (the prod TLS proxy); unset = local dev default.
const API_URL =
  process.env.NEXT_PUBLIC_API_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_URL
    : "http://localhost:8000";

// ---- Pilot auth (X-API-Key) ----
// The key is user-supplied (stored locally, never bundled); when the deployment has
// API_KEYS configured, every request must carry it.

const API_KEY_STORAGE = "vcma_api_key";

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(API_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

export function setStoredApiKey(key: string): void {
  if (typeof window === "undefined") return;
  try {
    if (key) window.localStorage.setItem(API_KEY_STORAGE, key);
    else window.localStorage.removeItem(API_KEY_STORAGE);
  } catch {
    /* storage unavailable (private mode) — requests just go keyless */
  }
}

function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const key = getStoredApiKey();
  if (key) headers.set("X-API-Key", key);
  return fetch(`${API_URL}${path}`, { ...init, headers });
}

export interface AppConfig {
  auth_required: boolean;
  uploads_enabled: boolean;
}

/** Deployment flags (auth/uploads). Fails open to permissive defaults so the UI still
 * renders if the backend is briefly unreachable. */
export async function fetchConfig(): Promise<AppConfig> {
  try {
    const res = await apiFetch("/api/config");
    if (!res.ok) throw new Error(String(res.status));
    return await res.json();
  } catch {
    return { auth_required: false, uploads_enabled: true };
  }
}

export interface DimensionWeights {
  financial_health: number;
  defensibility: number;
  market_urgency: number;
  founder_market_fit: number;
  regulatory_alignment: number;
}

export type AnalysisMode = "vc" | "founder";

export interface FundEconomics {
  fund_size_musd?: number | null; // master gate — omit to skip fund-math
  check_size_musd?: number | null;
  entry_post_money_musd?: number | null;
  target_ownership_pct?: number | null;
  holding_years?: number | null;
  fund_returner_fraction?: number | null;
  target_fund_multiple?: number | null;
}

export interface ResearchRequest {
  market_prompt: string;
  sector: string;
  stage: string;
  geography: string;
  thesis_bias: "Bear" | "Base" | "Bull";
  dimension_weights: DimensionWeights;
  analysis_mode?: AnalysisMode;
  focal_startup?: string;
  focal_upload_id?: string;
  scope_autoderived?: boolean;
  fund_economics?: FundEconomics | null;
}

export interface TaskCreatedResponse {
  task_id: string;
  message: string;
}

export interface ScopeResponse {
  market_prompt: string;
  sector: string;
  rationale: string;
  autoderived: boolean;
  source: "materials" | "materials+search" | "search" | "none";
}

export interface UploadResponse {
  upload_id: string;
  files: string[];
  message: string;
}

// ---- Structured report artifacts (emitted + validated in code by the pipeline) ----

export interface DimensionScores {
  // Sourced from the judge's raw resolved_scores, which may omit a dimension
  // (null) — so these are nullable to match what the pipeline can actually emit.
  financial_health: number | null;
  defensibility: number | null;
  market_urgency: number | null;
  founder_market_fit: number | null;
  regulatory_alignment: number | null;
}

export interface WeightedScore extends DimensionScores {
  weighted_score: number | null;
}

export interface MarketMapAxis {
  label: string;
  low: string;
  high: string;
}

export interface MarketMapCompany {
  name: string;
  x: number; // 0-100 scored position on the x-axis
  y: number; // 0-100 scored position on the y-axis
  segment: string | null;
  stage: string | null;
  raised_usd_m: number | null;
  weighted_score: number | null;
  is_incumbent?: boolean; // greyed reference point (not scored)
  rationale: string | null;
}

export interface MarketMap {
  axes: { x: MarketMapAxis; y: MarketMapAxis };
  quadrants: { name: string; x: string; y: string }[];
  white_space: { x: number; y: number; label: string } | null;
  companies: MarketMapCompany[];
}

export type LedgerFlag = "ok" | "warn" | "bad";

export interface LedgerRow {
  startup: string;
  stage: string;
  total_raised: string;
  valuation: string;
  arr: string;
  implied_arr_multiple: string; // computed in code: valuation / ARR (R7)
  yoy_growth: string;
  ltv_cac: string;
  nrr: string;
  burn_multiple: string;
  rule_of_40: string;
  flags: Record<string, LedgerFlag>;
  is_incumbent?: boolean; // reference row, sorted last (R1/R3)
}

export interface FinancialLedgerData {
  columns: string[];
  rows: LedgerRow[];
  stage_banded: boolean;
}

export interface ReturnScenario {
  label: string;
  probability: number; // 0-1
  multiple_low: number | null;
  multiple_high: number | null;
  multiple_source?: "stated" | "exit-derived"; // exit-derived = computed in code as exit ÷ entry
  exit_value_low_musd?: number | null;
  exit_value_high_musd?: number | null;
  path?: string; // one-phrase outcome path (who buys / what happens)
}

export interface ReturnScenarios {
  startup: string | null;
  entry_post_money_musd?: number | null; // the modelled entry post (resolve-emitted)
  scenarios: ReturnScenario[];
  expected_return: number | null; // Σ probability × midpoint(multiple), computed in code
  expected_return_low?: number | null; // EV over the low multiples (honest lower bound)
  expected_return_high?: number | null; // EV over the high multiples (honest upper bound)
}

export interface ResearchManifest {
  total: number;
  by_tool: Record<string, number>;
  failed: number;
  urls_in_brief?: number;
  calls?: { tool: string; args: Record<string, string> }[];
}

export interface DataFreshness {
  report_date: string; // run date (YYYY-MM-DD)
  newest_dated_mention: string; // YYYY-MM
  oldest_dated_mention: string; // YYYY-MM
  dated_mentions: number;
  months_since_newest: number;
}

export interface GradeCell {
  letter: string; // A+ … F, or "NR" (not rated — undisclosed, never punished as F)
  score: number | null; // the 0-100 value behind the letter
  note: string;
}

export interface GradesheetCriterion {
  key: string;
  label: string;
  calculation: string; // the coded rubric behind the grade (shown to the user)
}

export interface GradesheetStartup {
  name: string;
  is_focal: boolean;
  overall: GradeCell;
  cells: Record<string, GradeCell>;
}

export interface Gradesheet {
  criteria: GradesheetCriterion[];
  startups: GradesheetStartup[];
}

export interface AcquisitionRow {
  target: string;
  acquirer: string;
  announced: string;
  value: string;
  target_total_raised: string;
  multiple_on_capital?: number | null; // deal value ÷ target's total raised, computed in code
}

export interface FieldStats {
  startups: number;
  incumbents: number;
  total_raised_musd: number | null;
  arr_disclosed: number;
}

// Fund-math engine output ("does THIS deal return MY fund?") — computed in code.
export interface FundMathScenario {
  label: string;
  probability: number;
  gross_MoIC: number;
  net_MoIC: number;
  implied_exit_value_musd: number | null;
  gross_proceeds_musd: number;
  net_proceeds_musd: number;
  gross_turns: number;
  net_turns: number;
  net_irr_pct: number | null;
  returns_fund: boolean;
  is_fund_maker: boolean;
}

export interface FundMath {
  scenarios: FundMathScenario[];
  expected: {
    expected_gross_MoIC: number;
    expected_net_MoIC: number;
    expected_gross_proceeds_musd: number;
    expected_net_proceeds_musd: number;
    expected_net_turns: number;
    expected_net_irr_pct: number | null;
    expected_net_irr_pw_pct: number | null;
  } | null;
  requirements: {
    required_exit_value_musd: number | null;
    required_net_MoIC: number;
    required_gross_MoIC: number | null;
    preserved_ownership_ref_musd: number | null;
    fund_returner_fraction: number;
    target_fund_multiple: number;
  };
  verdicts: {
    can_return_fund: boolean;
    best_case_net_turns: number;
    expected_returns_fund: boolean;
    is_fund_maker: boolean;
  };
  assumptions: {
    fund_size_musd: number;
    check_size_musd: number;
    entry_post_money_musd: number | null;
    entry_ownership_pct: number | null;
    ownership_at_exit_pct: number | null;
    retention: number;
    holding_years: number | null;
    stage: string;
  };
  flags: string[];
}

// Founder-call claim audit — claims extracted from an uploaded call recording/
// transcript, cross-examined against the public record + the deck (validated in code).
export interface CallClaim {
  claim: string;
  quote: string;
  timestamp: string; // [mm:ss] or ""
  category: "financial" | "traction" | "team" | "product" | "market" | "other";
  status: "verified" | "contradicted" | "unsupported" | "vendor-only";
  evidence: string;
  deck_conflict: string; // non-empty = the call contradicts the uploaded materials
}

export interface CallClaimsAudit {
  claims: CallClaim[];
  counts: Record<string, number>; // per-status + deck_conflicts, computed in code
}

// Uploaded round-history CSV, parsed in code (grounds fund-math entry post + ledger).
export interface CapTableRound {
  round: string;
  date: string;
  raised_musd: number | null;
  pre_money_musd: number | null;
  post_money_musd: number | null;
  investors: string;
}

export interface CapTable {
  rounds: CapTableRound[];
  total_raised_musd: number | null;
  latest_post_money_musd: number | null;
  latest_round: string;
  source_file: string;
}

// Longitudinal re-run: code-computed diff vs the baseline report.
export interface RunDeltaMover {
  startup: string;
  prev_rank: number;
  new_rank: number;
  score_delta?: number;
}

export interface RunDelta {
  entered: string[];
  exited: string[];
  movers: RunDeltaMover[];
  ledger_changes: { startup: string; field: string; prev_musd: number; new_musd: number }[];
  new_acquisitions: AcquisitionRow[];
  pick_changed: boolean;
  prev_pick: string;
  new_pick: string;
  prev_expected_return: number | null;
  new_expected_return: number | null;
}

// The baseline report's own dated predictions, graded against the new evidence.
export interface PredictionRow {
  prediction: string;
  metric: string;
  deadline: string; // YYYY-MM or ""
  status: "validated" | "broken" | "pending" | "unresolved";
  evidence: string;
}

export interface FinalReport {
  merged_report?: string;
  synthesis?: string;
  research_data?: string;
  research_manifest?: ResearchManifest | null; // tool-call audit (protocol compliance), computed in code
  data_freshness?: DataFreshness | null; // report evidence-recency audit, computed in code
  gradesheet?: Gradesheet | null; // per-startup letter grades, computed in code (Grades tab)
  analyst_a_report?: string;
  analyst_b_report?: string;
  resolved_scores?: Record<string, DimensionScores>;
  weighted_scores?: Record<string, WeightedScore>;
  ranking?: string[];
  applied_weights?: Record<string, number>;
  weighting_unavailable?: boolean;
  incumbents?: string[];
  pre_pmf?: string[]; // watchlist — profiled but not scored (R13)
  moat_subscores?: Record<string, Record<string, number>>; // 4 a16z sub-scores; Defensibility = their mean (R10)
  scenarios?: ReturnScenarios | null;
  expected_return?: number | null; // probability-weighted return midpoint, computed in code (R6)
  expected_return_low?: number | null; // range bounds — presented instead of a lone point estimate
  expected_return_high?: number | null;
  expected_return_net_low?: number | null; // net of stage-banded dilution-to-exit, computed in code
  expected_return_net_high?: number | null;
  return_assumptions?: { retention: number; note: string } | null;
  return_dominance?: { label: string; share_pct: number } | null; // which scenario dominates the EV
  methodology?: string; // deterministic "What we diligenced" section (also appended to merged_report)
  acquisitions?: AcquisitionRow[] | null; // exit-precedent table, validated in code
  field_stats?: FieldStats | null; // ledger-derived hero-card stats, computed in code
  fund_math?: FundMath | null; // "does this return my fund?" — computed in code (null unless fund_size given)
  cap_table?: CapTable | null; // uploaded round-history CSV, parsed in code
  call_claims_audit?: CallClaimsAudit | null; // founder-call claims cross-examined (Claims tab)
  run_delta?: RunDelta | null; // re-run only: code-computed diff vs the baseline
  prediction_audit?: PredictionRow[] | null; // re-run only: baseline predictions graded
  baseline_id?: string; // re-run only: the baseline History record
  baseline_created_at?: string;
  recommended_pick?: string; // the report's own §0/§12 pick — badges use THIS, never just ranking[0] (R11)
  focal_rank?: number | null; // VC-focal: the focal deal's rank in the field (computed in code), never the field-pick badge
  score_confidence?: Record<string, "low" | "medium" | "high">; // ledger-disclosure-based, computed in code
  market_map?: MarketMap | null;
  financial_ledger?: FinancialLedgerData | null;
  iterations_to_consensus?: number;
  thesis_bias?: string;
  analysis_mode?: AnalysisMode;
  focal_startup?: string;
  focal_confidence?: "low" | "medium" | "high" | "";
  sector?: string;
  scope_autoderived?: boolean;
  status?: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  current_phase: string | null;
  iterations_completed: number;
  agent_logs: string[];
  final_report: Record<string, unknown> | null;
  error: string | null;
}

export async function submitResearch(
  request: ResearchRequest
): Promise<TaskCreatedResponse> {
  const res = await apiFetch(`/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to submit research: ${detail}`);
  }
  return res.json();
}

export async function deriveScope(focalStartup: string, focalUploadId: string): Promise<ScopeResponse> {
  const res = await apiFetch(`/api/derive-scope`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ focal_startup: focalStartup, focal_upload_id: focalUploadId }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Scope derivation failed: ${detail}`);
  }
  return res.json();
}

export async function uploadFocalFiles(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await apiFetch(`/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload failed: ${detail}`);
  }
  return res.json();
}

export async function pollResearchStatus(
  taskId: string
): Promise<TaskStatusResponse> {
  const res = await apiFetch(`/api/research/${taskId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch status for task ${taskId}`);
  }
  return res.json();
}

// ---- Analysis history ----

export interface ReportSummary {
  id: string;
  created_at: string;
  sector: string;
  analysis_mode: AnalysisMode;
  focal_startup: string;
  top_pick: string;
  thesis_bias: string;
  label: string;
  starred: boolean;
}

export async function listReports(): Promise<ReportSummary[]> {
  const res = await apiFetch(`/api/reports`);
  if (!res.ok) throw new Error("Failed to load history");
  return res.json();
}

export async function getReport(
  id: string
): Promise<ReportSummary & { final_report: FinalReport }> {
  const res = await apiFetch(`/api/reports/${id}`);
  if (!res.ok) throw new Error("Failed to load report");
  return res.json();
}

export async function updateReport(
  id: string,
  patch: { label?: string; starred?: boolean }
): Promise<ReportSummary> {
  const res = await apiFetch(`/api/reports/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error("Failed to update report");
  return res.json();
}

export async function deleteReport(id: string): Promise<void> {
  const res = await apiFetch(`/api/reports/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete report");
}

/** Re-run a saved analysis on its original parameters; the new run diffs itself
 * against the baseline and grades the baseline's own dated predictions. */
export async function rerunReport(id: string): Promise<TaskCreatedResponse> {
  const res = await apiFetch(`/api/reports/${id}/rerun`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Re-run failed: ${detail}`);
  }
  return res.json();
}
