import type { FinalReport, TaskStatusResponse } from "@/lib/api";

// A realistic, self-consistent fixture for previewing the report UI with NO pipeline
// run and NO API calls. Company names are identical across merged_report (§8 profiles),
// market_map, financial_ledger, weighted_scores, resolved_scores and ranking so the
// click-to-profile and all graphics line up. Typed as FinalReport -> shape is checked.

const mergedReport = `## 1. Sector Narrative & Core Shift

The runtime/workload-security category is shifting from **perimeter and posture** tooling toward **inline, runtime enforcement** for autonomous AI agents. The technical bottleneck is that probabilistic LLM agents take real actions (code execution, API calls, data access) that static policy engines cannot reason about, so enforcement is moving down the stack toward the host and kernel.

Legacy CNAPP/posture vendors observe and alert; the new generation intercepts and blocks deterministically at the point of action.

## 2. Market Inflection & Bottoms-Up Sizing

**Why now:** enterprise agent deployments, breach-driven CISO demand, and EU AI Act timelines. Bottom-up SAM = Target Accounts (~8,000 large enterprises adopting agents) x Workload-Based ACV (~$180K) ≈ **$1.4B SAM**. Top-down anchor: the broader cloud-security market (~$25B) cross-checks this as an early, fast-growing slice. SOM at a 3% near-term penetration ≈ **$420M**.

There is a credible path to >$100M ARR for the category leader.

## 3. Competitive Landscape & Incumbent Encroachment

Incumbents (hyperscalers, posture managers, legacy SASE) won't easily absorb this as a feature: kernel-level enforcement requires deep systems engineering and a different trust boundary than their agent/proxy architectures. The structural gap is **deterministic enforcement at the host/kernel** vs. probabilistic detection at the app layer.

## 4. Investable White Space & Investment Thesis

> The defensible white space is **deterministic, kernel-level runtime enforcement** for AI agents — uncrowded and technically hard, versus the crowded probabilistic app-gateway quadrant.

## 5. Market Segmentation & Capability Map

Two axes fit this sector: **Y = Enforcement depth** (App/API gateway → Host/Kernel) and **X = Control philosophy** (Deterministic rules → Probabilistic ML). These are illustrative framing, not a rigorous taxonomy.

## 6. Financial Health & Valuation Stress-Test

Interpreted against each startup's stage. KernelGuard's 2.5x burn multiple is borderline for Series A; FortifyAI's metrics are strong but its moat is thin.

| Startup | Stage | Raised | Valuation | ARR | YoY | LTV/CAC | NRR | Burn | Rule of 40 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KernelGuard | Series A | $18M | $110M | $6M | 90% | 2.0 | 115% | 2.5 | 50 |
| RegShield | Seed | $9M | $55M | $10M | 70% | 2.5 | 108% | 2.0 | 40 |
| SandboxIO | Seed | $12M | $70M | $4M | 120% | Not Disclosed | 112% | 2.2 | 45 |
| MidMoat | Series A | $25M | $150M | $15M | 110% | 3.0 | 120% | 1.5 | 70 |
| AgentWall | Series A | $30M | $180M | $8M | 140% | Not Disclosed | 118% | 2.8 | 55 |
| FortifyAI | Series B | $85M | $600M | $40M | 180% | 5.0 | 140% | 0.8 | 95 |

## 7. Weighted Underwriting Index & Scorecard

Defensibility-weighted (30%). KernelGuard leads on a deep, deterministic moat despite mid financials; FortifyAI's elite financials can't offset a thin moat.

## 8. Detailed Startup Profiles

#### KernelGuard
eBPF kernel-level runtime enforcement with three granted patents. Founders ex-Unit 8200 and a former Linux kernel maintainer. **How it dies:** if probabilistic detection proves "good enough" for buyers, deep tech becomes over-engineering.

#### RegShield
Compliance automation mapped to EU AI Act / GDPR articles. Ex-regulator founder — elite founder-market fit for the regulatory dimension. **How it dies:** compliance commoditizes into a checkbox feature.

#### SandboxIO
Host-level sandboxing for agent tool-use. Strong technical approach, early ARR. **How it dies:** runs out of runway before the category matures.

#### MidMoat
Balanced CNAPP posture + light runtime. Solid but undifferentiated. **How it dies:** squeezed between hyperscalers and pure-plays.

#### AgentWall
Probabilistic agent guardrails at the API layer. Fast growth, shallow moat. **How it dies:** incumbents ship the same guardrails as a feature.

#### FortifyAI
Cloud API security gateway. Excellent financials, thin moat (replicable in ~12 months). **How it dies:** an incumbent absorbs it as a feature.

## 9. Team & Founder Assessment

KernelGuard and SandboxIO carry the strongest technical pedigrees; RegShield the strongest regulatory founder-market fit. Cap-table detail is largely Not Disclosed for private companies.

## 10. Regulatory Conformance & Compliance

EU AI Act high-risk obligations and enforcement deadlines favor deterministic, auditable enforcement. RegShield maps directly to binding articles.

## 11. Risk Factors, Mitigants & "What Would Make Us Wrong"

- **Probabilistic-good-enough risk** (market): buyers accept detection over enforcement. *Mitigant:* target regulated buyers needing auditable guarantees.
- **What would make us wrong:** if two of the top three deals close on probabilistic app-layer tools at premium multiples within 12 months, the deterministic-kernel thesis is invalidated.

## 12. Return Math & Exit Pathways

Strategic acquirers: hyperscalers and platform security vendors; recent comparable exits in cloud security at ~12–18x ARR. A KernelGuard entry at ~$110M with a credible path to a $1B+ outcome clears the fund-returner bar.

## 13. Visual Coordinate Market Map

    Host/Kernel ^
                |   KERNELGUARD*
                |   *SandboxIO
                |          *MidMoat
                +------------------------> Probabilistic
                |  *RegShield   *AgentWall   *FORTIFYAI
       App/API  |

*Axes are illustrative framing, not a rigorous classification.*

## Works Cited

1. Bessemer State of the Cloud — https://www.bvp.com/atlas/state-of-the-cloud-2024
2. ScaleVP SaaS benchmarks — https://www.scalevp.com/insights/benchmarking-saas-growth-and-burn/
3. EU AI Act, high-risk obligations — (regulatory source)
`;

const FINAL: FinalReport = {
  merged_report: mergedReport,
  synthesis: "KernelGuard is the top pick on a deep deterministic moat; FortifyAI's strong financials are offset by a thin, replicable moat.",
  research_data: "(raw research brief omitted in fixture)",
  thesis_bias: "Base",
  iterations_to_consensus: 2,
  weighting_unavailable: false,
  ranking: ["KernelGuard", "RegShield", "SandboxIO", "MidMoat", "AgentWall", "FortifyAI"],
  applied_weights: {
    financial_health: 0.2,
    defensibility: 0.3,
    market_urgency: 0.2,
    founder_market_fit: 0.15,
    regulatory_alignment: 0.15,
  },
  weighted_scores: {
    KernelGuard: { financial_health: 60, defensibility: 95, market_urgency: 88, founder_market_fit: 95, regulatory_alignment: 85, weighted_score: 84 },
    RegShield: { financial_health: 55, defensibility: 62, market_urgency: 85, founder_market_fit: 88, regulatory_alignment: 95, weighted_score: 72 },
    SandboxIO: { financial_health: 58, defensibility: 80, market_urgency: 72, founder_market_fit: 78, regulatory_alignment: 70, weighted_score: 68 },
    MidMoat: { financial_health: 72, defensibility: 62, market_urgency: 70, founder_market_fit: 66, regulatory_alignment: 60, weighted_score: 65 },
    AgentWall: { financial_health: 64, defensibility: 55, market_urgency: 75, founder_market_fit: 60, regulatory_alignment: 52, weighted_score: 58 },
    FortifyAI: { financial_health: 92, defensibility: 35, market_urgency: 60, founder_market_fit: 45, regulatory_alignment: 30, weighted_score: 49 },
  },
  resolved_scores: {
    KernelGuard: { financial_health: 60, defensibility: 95, market_urgency: 88, founder_market_fit: 95, regulatory_alignment: 85 },
    RegShield: { financial_health: 55, defensibility: 62, market_urgency: 85, founder_market_fit: 88, regulatory_alignment: 95 },
    SandboxIO: { financial_health: 58, defensibility: 80, market_urgency: 72, founder_market_fit: 78, regulatory_alignment: 70 },
    MidMoat: { financial_health: 72, defensibility: 62, market_urgency: 70, founder_market_fit: 66, regulatory_alignment: 60 },
    AgentWall: { financial_health: 64, defensibility: 55, market_urgency: 75, founder_market_fit: 60, regulatory_alignment: 52 },
    FortifyAI: { financial_health: 92, defensibility: 35, market_urgency: 60, founder_market_fit: 45, regulatory_alignment: 30 },
  },
  market_map: {
    axes: {
      x: { label: "Control philosophy", low: "Deterministic rules", high: "Probabilistic ML" },
      y: { label: "Enforcement depth", low: "App / API gateway", high: "Host / Kernel" },
    },
    quadrants: [
      { name: "Defensible white space", x: "low", y: "high" },
      { name: "Probabilistic kernel (hard)", x: "high", y: "high" },
      { name: "Compliance niche", x: "low", y: "low" },
      { name: "Crowded app layer", x: "high", y: "low" },
    ],
    white_space: { x: 25, y: 85, label: "Investable white space" },
    companies: [
      { name: "KernelGuard", x: 20, y: 90, segment: "Runtime enforcement", stage: "Series A", raised_usd_m: 18, weighted_score: 84, rationale: "eBPF kernel-level deterministic enforcement" },
      { name: "SandboxIO", x: 42, y: 78, segment: "Runtime enforcement", stage: "Seed", raised_usd_m: 12, weighted_score: 68, rationale: "host-level agent sandboxing" },
      { name: "MidMoat", x: 55, y: 52, segment: "CNAPP", stage: "Series A", raised_usd_m: 25, weighted_score: 65, rationale: "balanced posture + light runtime" },
      { name: "RegShield", x: 30, y: 35, segment: "Compliance automation", stage: "Seed", raised_usd_m: 9, weighted_score: 72, rationale: "deterministic compliance mapping" },
      { name: "AgentWall", x: 72, y: 45, segment: "Agent guardrails", stage: "Series A", raised_usd_m: 30, weighted_score: 58, rationale: "probabilistic API-layer guardrails" },
      { name: "FortifyAI", x: 82, y: 28, segment: "API security", stage: "Series B", raised_usd_m: 85, weighted_score: 49, rationale: "app/API gateway, thin moat" },
      { name: "CrowdStrike Falcon", x: 68, y: 72, segment: "Incumbent", stage: "Public", raised_usd_m: null, weighted_score: null, is_incumbent: true, rationale: "incumbent reference — probabilistic, host-level" },
    ],
  },
  financial_ledger: {
    columns: ["startup", "stage", "total_raised", "valuation", "arr", "implied_arr_multiple", "yoy_growth", "ltv_cac", "nrr", "burn_multiple", "rule_of_40"],
    stage_banded: true,
    rows: [
      { startup: "KernelGuard", stage: "Series A", total_raised: "$18M", valuation: "$110M", arr: "$6M", implied_arr_multiple: "18.3x", yoy_growth: "90%", ltv_cac: "2.0", nrr: "115%", burn_multiple: "2.5", rule_of_40: "50", flags: { burn_multiple: "warn" }, is_incumbent: false },
      { startup: "RegShield", stage: "Seed", total_raised: "$9M", valuation: "$55M", arr: "$10M", implied_arr_multiple: "5.5x", yoy_growth: "70%", ltv_cac: "2.5", nrr: "108%", burn_multiple: "2.0", rule_of_40: "40", flags: { rule_of_40: "bad" }, is_incumbent: false },
      { startup: "SandboxIO", stage: "Seed", total_raised: "$12M", valuation: "$70M", arr: "$4M", implied_arr_multiple: "17.5x", yoy_growth: "120%", ltv_cac: "Not Disclosed", nrr: "112%", burn_multiple: "2.2", rule_of_40: "45", flags: {}, is_incumbent: false },
      { startup: "MidMoat", stage: "Series A", total_raised: "$25M", valuation: "$150M", arr: "$15M", implied_arr_multiple: "10.0x", yoy_growth: "110%", ltv_cac: "3.0", nrr: "120%", burn_multiple: "1.5", rule_of_40: "70", flags: { rule_of_40: "ok", burn_multiple: "ok" }, is_incumbent: false },
      { startup: "AgentWall", stage: "Series A", total_raised: "$30M", valuation: "$180M", arr: "$8M", implied_arr_multiple: "22.5x", yoy_growth: "140%", ltv_cac: "Not Disclosed", nrr: "118%", burn_multiple: "2.8", rule_of_40: "55", flags: { burn_multiple: "warn" }, is_incumbent: false },
      { startup: "FortifyAI", stage: "Series B", total_raised: "$85M", valuation: "$600M", arr: "$40M", implied_arr_multiple: "15.0x", yoy_growth: "180%", ltv_cac: "5.0", nrr: "140%", burn_multiple: "0.8", rule_of_40: "95", flags: { rule_of_40: "ok", burn_multiple: "ok" }, is_incumbent: false },
      { startup: "CrowdStrike Falcon", stage: "Public", total_raised: "Not Disclosed", valuation: "Not Disclosed", arr: "Not Disclosed", implied_arr_multiple: "Not Disclosed", yoy_growth: "Not Disclosed", ltv_cac: "Not Disclosed", nrr: "Not Disclosed", burn_multiple: "Not Disclosed", rule_of_40: "Not Disclosed", flags: {}, is_incumbent: true },
    ],
  },
  incumbents: ["CrowdStrike Falcon"],
  pre_pmf: ["StealthRT (pre-launch)"],
  // sub-scores average to each startup's Defensibility above (R10): code enforces the mean.
  moat_subscores: {
    KernelGuard: { economies_of_scale: 90, differentiated_technology: 100, network_effects: 95, brand_power: 95 },
    RegShield: { economies_of_scale: 58, differentiated_technology: 64, network_effects: 60, brand_power: 66 },
    SandboxIO: { economies_of_scale: 78, differentiated_technology: 86, network_effects: 80, brand_power: 76 },
    MidMoat: { economies_of_scale: 64, differentiated_technology: 60, network_effects: 62, brand_power: 62 },
    AgentWall: { economies_of_scale: 56, differentiated_technology: 52, network_effects: 58, brand_power: 54 },
    FortifyAI: { economies_of_scale: 50, differentiated_technology: 20, network_effects: 30, brand_power: 40 },
  },
  expected_return: 6.04,
  scenarios: {
    startup: "RegShield",
    expected_return: 6.04,
    scenarios: [
      { label: "downside", probability: 0.25, multiple_low: 0.5, multiple_high: 1.0 },
      { label: "base", probability: 0.6, multiple_low: 5.0, multiple_high: 7.0 },
      { label: "outlier", probability: 0.15, multiple_low: 15.0, multiple_high: 15.0 },
    ],
  },
  status: "completed",
};

export const reportGolden: TaskStatusResponse = {
  task_id: "preview-fixture",
  status: "SUCCESS",
  current_phase: "compile_report",
  iterations_completed: 2,
  agent_logs: ["[Compiler] Merged report generated (4200 chars) · map=ok · ledger=ok"],
  final_report: FINAL as Record<string, unknown>,
  error: null,
};
