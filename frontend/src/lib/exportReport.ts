import type { FinalReport } from "./api";
import { pickLabel } from "./pickLabel";

const DIMS: [string, string][] = [
  ["financial_health", "Financial"],
  ["defensibility", "Defensibility"],
  ["market_urgency", "Mkt Urgency"],
  ["founder_market_fit", "Founder Fit"],
  ["regulatory_alignment", "Regulatory"],
];
const LEDGER: [string, string][] = [
  ["startup", "Startup"], ["stage", "Stage"], ["total_raised", "Raised"], ["valuation", "Valuation"],
  ["arr", "ARR"], ["implied_arr_multiple", "Val/ARR"], ["yoy_growth", "YoY"], ["ltv_cac", "LTV/CAC"],
  ["nrr", "NRR"], ["burn_multiple", "Burn"], ["rule_of_40", "Rule of 40"],
];

function table(headers: string[], rows: (string | number)[][]): string {
  const h = `| ${headers.join(" | ")} |`;
  const sep = `| ${headers.map(() => "---").join(" | ")} |`;
  return [h, sep, ...rows.map((r) => `| ${r.join(" | ")} |`)].join("\n");
}

/** A clean, self-contained Markdown export: metadata header → narrative → appendix tables. */
export function toMarkdown(r: FinalReport): string {
  const L: string[] = [];
  const sector = (r.sector || "").trim();
  const ranking = r.ranking ?? [];
  const ws = (r.weighted_scores ?? {}) as unknown as Record<string, Record<string, unknown>>;
  const mode = (r.analysis_mode || "vc").toUpperCase();

  L.push("# VC Market Analysis" + (sector ? ` — ${sector}` : ""));
  const meta = [`**Mode:** ${mode}`];
  const pl = pickLabel(r);
  const pick = pl.pick;
  if (pick) meta.push(`**${pl.kicker}:** ${pick}${pl.rankSuffix}`);
  if (pl.fieldLeader) meta.push(`**Field leader:** ${pl.fieldLeader}`);
  if (r.expected_return != null) {
    const lo = r.expected_return_low, hi = r.expected_return_high;
    const val = lo != null && hi != null && lo !== hi
      ? `${lo}x–${hi}x (gross, mid ${r.expected_return}x)`
      : `${r.expected_return}x (gross)`;
    meta.push(`**Prob-weighted return:** ${val}`);
    if (r.expected_return_net_low != null && r.expected_return_net_high != null) {
      const ret = r.return_assumptions ? ` @ ${Math.round(r.return_assumptions.retention * 100)}% retention` : "";
      meta.push(`**Net of est. dilution:** ≈${r.expected_return_net_low}x–${r.expected_return_net_high}x${ret}`);
    }
  }
  if (r.thesis_bias) meta.push(`**Thesis bias:** ${r.thesis_bias}`);
  if (r.iterations_to_consensus != null) meta.push(`**Consensus in:** ${r.iterations_to_consensus} round(s)`);
  L.push(meta.join(" · "));
  if (r.focal_startup) {
    const label = mode === "FOUNDER" ? "Subject" : "Focal";
    L.push(`\n> **${label} startup:** ${r.focal_startup}${r.focal_confidence ? ` — _${r.focal_confidence} data confidence_` : ""}`);
  }
  L.push("\n---\n");
  L.push(r.merged_report || "_(no narrative report)_");

  const names = ranking.filter((n) => ws[n]);
  if (names.length) {
    L.push("\n\n---\n\n## Appendix A — Weighted Underwriting Scorecard\n");
    const rows = names.map((n) => [
      n,
      ...DIMS.map(([k]) => String(ws[n][k] ?? "—")),
      `**${ws[n]["weighted_score"] ?? "—"}**`,
    ]);
    L.push(table(["Startup", ...DIMS.map(([, l]) => l), "Weighted"], rows));
  }

  const led = r.financial_ledger;
  if (led?.rows?.length) {
    L.push("\n\n## Appendix B — Financial Ledger\n");
    const rows = led.rows.map((rw) => {
      const row = rw as unknown as Record<string, unknown>;
      const name = row["is_incumbent"] ? `${row["startup"]} (ref)` : String(row["startup"]);
      return [name, ...LEDGER.slice(1).map(([k]) => String(row[k] ?? "—"))];
    });
    L.push(table(LEDGER.map(([, l]) => l), rows));
  }

  const sc = r.scenarios;
  if (sc?.scenarios?.length) {
    L.push("\n\n## Appendix C — Probability-Weighted Return\n");
    const clo = sc.expected_return_low, chi = sc.expected_return_high;
    const cval = clo != null && chi != null && clo !== chi
      ? `${clo}x–${chi}x (gross, mid ${sc.expected_return}x)`
      : `${sc.expected_return}x (gross)`;
    L.push(`_For **${sc.startup || ranking[0] || "top pick"}**. Expected return (code-computed, before dilution/ownership/fees/time-value): **${cval}**._\n`);
    const hasPath = sc.scenarios.some((s) => s.path);
    const rows = sc.scenarios.map((s) => {
      const lo = s.multiple_low, hi = s.multiple_high;
      const mult = lo == null && hi == null ? "—" : lo === hi ? `${lo}x` : `${lo}x–${hi}x`;
      const label = (s.label || "").replace(/^\w/, (c) => c.toUpperCase());
      return hasPath
        ? [label, s.path || "—", `${Math.round((s.probability || 0) * 100)}%`, mult]
        : [label, `${Math.round((s.probability || 0) * 100)}%`, mult];
    });
    L.push(table(hasPath ? ["Scenario", "Path", "Probability", "Return"] : ["Scenario", "Probability", "Return"], rows));
    if (r.return_dominance) {
      L.push(`\n_${r.return_dominance.share_pct}% of the expected value sits in the **${r.return_dominance.label}** case._`);
    }
  }

  if (r.acquisitions?.length) {
    L.push("\n\n## Appendix D — Exit Precedents (Sector Acquisitions)\n");
    const rows = r.acquisitions.map((a) => [a.target, a.acquirer, a.announced, a.value, a.target_total_raised]);
    L.push(table(["Target", "Acquirer", "Announced", "Value", "Target Raised"], rows));
    L.push("\n_Research-sourced deals only (validated in code). The weakest comparable anchors the downside scenario._");
  }

  return L.join("\n") + "\n";
}

/** kebab filename from the sector/focal for the download. */
export function reportSlug(r: FinalReport): string {
  const base = (r.focal_startup || r.sector || "vc-analysis").toLowerCase();
  return base.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "vc-analysis";
}

/** Trigger a client-side file download from a string (no backend needed). */
export function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
