"use client";

import { useState } from "react";
import type { AcquisitionRow, CapTable, FinancialLedgerData, FundMath, ReturnScenarios } from "@/lib/api";

interface Props {
  ledger: FinancialLedgerData;
  scenarios?: ReturnScenarios | null;
  expectedReturn?: number | null;
  expectedReturnLow?: number | null;
  expectedReturnHigh?: number | null;
  expectedReturnNetLow?: number | null;
  expectedReturnNetHigh?: number | null;
  returnAssumptions?: { retention: number; note: string } | null;
  returnDominance?: { label: string; share_pct: number } | null;
  acquisitions?: AcquisitionRow[] | null;
  fundMath?: FundMath | null;
  capTable?: CapTable | null;
}

const musd = (v: number | null | undefined): string =>
  v == null ? "—" : v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`;

const FUND_FLAG_LABELS: Record<string, string> = {
  post_inferred: "entry post-money inferred from stage (calibration-pending)",
  ownership_infeasible: "check exceeds post-money — entry ownership clamped to 100%",
  retention_defaulted: "stage unknown — 0.70 dilution retention assumed",
  ownership_mismatch: "stated ownership disagrees with check/post — check/post used",
  ownership_input_ignored: "target ownership out of range — ignored",
  unit_suspect: "a dollar input looks large — verify it is in $M, not raw dollars",
  holding_too_short: "holding under a quarter — IRR suppressed",
  unusual_returner_bar: "return-the-fund bar set unusually low",
  check_exceeds_fund: "check is larger than the whole fund",
  post_from_cap_table: "entry post-money taken from the uploaded cap table",
};

const HEADERS: Record<string, string> = {
  startup: "Startup",
  stage: "Stage",
  total_raised: "Raised",
  valuation: "Valuation",
  arr: "ARR",
  implied_arr_multiple: "Val/ARR",
  yoy_growth: "YoY",
  ltv_cac: "LTV/CAC",
  nrr: "NRR",
  burn_multiple: "Burn",
  rule_of_40: "Rule of 40",
};

// Semantic band chips (symbol included so it's never color-only / colorblind-safe).
const FLAG_CHIP: Record<string, { cls: string; sym: string; label: string }> = {
  ok: { cls: "border-emerald-900/50 bg-emerald-950/30 text-emerald-300", sym: "✓", label: "meets stage band" },
  warn: { cls: "border-amber-900/50 bg-amber-950/30 text-amber-300", sym: "!", label: "borderline" },
  bad: { cls: "border-rose-900/50 bg-rose-950/30 text-rose-300", sym: "✗", label: "off stage band" },
};

// Left-aligned text columns; everything else is a right-aligned numeric.
const TEXT_COLS = new Set(["startup", "stage"]);

const panel = "rounded-lg border border-gray-800 bg-gray-900/40 p-4";

export default function FinancialLedger({
  ledger, scenarios, expectedReturn, expectedReturnLow, expectedReturnHigh,
  expectedReturnNetLow, expectedReturnNetHigh, returnAssumptions, returnDominance, acquisitions,
  fundMath, capTable,
}: Props) {
  const cols = ledger.columns?.length ? ledger.columns : Object.keys(HEADERS);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [asc, setAsc] = useState(true);

  const rows = ledger.rows ? [...ledger.rows] : [];
  if (sortCol) {
    rows.sort((a, b) => {
      const av = String((a as unknown as Record<string, unknown>)[sortCol] ?? "");
      const bv = String((b as unknown as Record<string, unknown>)[sortCol] ?? "");
      const an = parseFloat(av.replace(/[^0-9.\-]/g, ""));
      const bn = parseFloat(bv.replace(/[^0-9.\-]/g, ""));
      const cmp = !Number.isNaN(an) && !Number.isNaN(bn) ? an - bn : av.localeCompare(bv);
      return asc ? cmp : -cmp;
    });
  }

  const toggle = (c: string) => {
    if (sortCol === c) setAsc(!asc);
    else {
      setSortCol(c);
      setAsc(true);
    }
  };

  if (!rows.length) {
    return <div className="empty-state">No financial ledger available for this run.</div>;
  }

  const grossIsRange =
    expectedReturnLow != null && expectedReturnHigh != null && expectedReturnLow !== expectedReturnHigh;

  return (
    <div className="space-y-4">
      {/* ── Ledger ─────────────────────────────────────────────────── */}
      <section className={panel}>
        <div className="panel-kicker">Ledger — disclosed financials</div>
        <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
          Stage-banded metrics from research; Val/ARR computed in code. Click a column head to sort.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800">
                {cols.map((c) => (
                  <th
                    key={c}
                    onClick={() => toggle(c)}
                    className={`th-label cursor-pointer whitespace-nowrap px-2 py-1.5 hover:text-gray-300 ${
                      TEXT_COLS.has(c) ? "text-left" : "text-right"
                    }`}
                  >
                    {HEADERS[c] ?? c}
                    {sortCol === c ? (asc ? " ▲" : " ▼") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={`border-b border-gray-900 ${row.is_incumbent ? "opacity-50" : ""}`}>
                  {cols.map((c) => {
                    const val = String((row as unknown as Record<string, unknown>)[c] ?? "");
                    const flag = row.flags?.[c];
                    const fs = flag ? FLAG_CHIP[flag] : null;
                    const nd = val === "Not Disclosed";
                    return (
                      <td
                        key={c}
                        className={`whitespace-nowrap px-2 py-1.5 tabular-nums ${
                          TEXT_COLS.has(c) ? "text-left" : "text-right"
                        } ${nd ? "italic text-gray-600" : "text-gray-300"}`}
                      >
                        {c === "startup" ? (
                          <span className="font-medium text-gray-100">
                            {val}
                            {row.is_incumbent && (
                              <span className="ml-1.5 rounded border border-gray-800 bg-gray-900 px-1 font-mono text-[9px] uppercase tracking-wide text-gray-500">
                                ref
                              </span>
                            )}
                          </span>
                        ) : val}
                        {fs && (
                          <span
                            className={`ml-1.5 inline-flex items-center justify-center rounded border px-1 font-mono text-[9px] leading-[14px] ${fs.cls}`}
                            title={fs.label}
                          >
                            {fs.sym}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="panel-kicker mr-1">Flags vs stage band</span>
          {(["ok", "warn", "bad"] as const).map((k) => (
            <span
              key={k}
              className={`inline-flex items-center gap-1 rounded border px-2 py-[3px] font-mono text-[10.5px] leading-4 ${FLAG_CHIP[k].cls}`}
            >
              {FLAG_CHIP[k].sym} {FLAG_CHIP[k].label}
            </span>
          ))}
          <span className="chip">ref = incumbent · reference only, not scored</span>
        </div>
      </section>

      {/* ── Return scenarios ───────────────────────────────────────── */}
      {scenarios?.scenarios?.length ? (
        <section className={panel}>
          <div className="panel-kicker">
            Return scenarios — probability-weighted{scenarios.startup ? ` · ${scenarios.startup}` : ""}
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
            Expected return = Σ probability × midpoint(multiple) — computed in code, never asserted by the model.
          </p>

          {(expectedReturn != null ||
            (expectedReturnNetLow != null && expectedReturnNetHigh != null) ||
            returnDominance != null) && (
            <div className="mt-3 grid auto-cols-fr grid-flow-col gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60">
              {expectedReturn != null && (
                <div
                  className="stat-cell"
                  title="Gross multiple before dilution, ownership, fees, and time-value — computed in code from the scenario table"
                >
                  <div className="stat-value">
                    {grossIsRange ? `${expectedReturnLow}x–${expectedReturnHigh}x` : `${expectedReturn}x`}
                  </div>
                  <div className="stat-caption">
                    Expected gross{grossIsRange ? ` · mid ${expectedReturn}x` : ""}
                  </div>
                </div>
              )}
              {expectedReturnNetLow != null && expectedReturnNetHigh != null && (
                <div className="stat-cell" title={returnAssumptions?.note || ""}>
                  <div className="stat-value">≈{expectedReturnNetLow}x–{expectedReturnNetHigh}x</div>
                  <div className="stat-caption">
                    Net of dilution{returnAssumptions ? ` · ${Math.round(returnAssumptions.retention * 100)}% retention` : ""}
                  </div>
                </div>
              )}
              {returnDominance != null && (
                <div className="stat-cell" title="Share of the expected value carried by a single scenario">
                  <div className="stat-value">{returnDominance.share_pct}%</div>
                  <div className="stat-caption">EV in {returnDominance.label} case</div>
                </div>
              )}
            </div>
          )}

          <table className="mt-3 w-full text-[11px]">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th-label py-1 text-left">Scenario</th>
                {scenarios.scenarios.some((x) => x.path) && (
                  <th className="th-label py-1 pl-2 text-left">Path</th>
                )}
                <th className="th-label py-1 text-right">Prob</th>
                <th className="th-label py-1 text-right">Multiple</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.scenarios.map((s, i) => {
                const lo = s.multiple_low, hi = s.multiple_high;
                const mult = lo == null && hi == null ? "—" : lo === hi ? `${lo}x` : `${lo}x–${hi}x`;
                return (
                  <tr key={i} className="border-b border-gray-900 last:border-0">
                    <td className="py-1.5 capitalize text-gray-300">{s.label}</td>
                    {scenarios.scenarios.some((x) => x.path) && (
                      <td className="max-w-[220px] truncate py-1.5 pl-2 text-gray-500" title={s.path || ""}>{s.path || "—"}</td>
                    )}
                    <td className="py-1.5 text-right tabular-nums text-gray-400">{Math.round(s.probability * 100)}%</td>
                    <td className="py-1.5 text-right tabular-nums text-gray-200">{mult}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-[10.5px] text-gray-600">
            Gross of fund fees, ownership, and time-value.
            {returnDominance ? ` ${returnDominance.share_pct}% of the expected value sits in the ${returnDominance.label} case.` : ""}
          </p>
        </section>
      ) : null}

      {/* ── Exit precedents ────────────────────────────────────────── */}
      {acquisitions?.length ? (
        <section className={panel}>
          <div className="panel-kicker">Exit precedents — sector acquisitions</div>
          <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
            Research-sourced deals only, validated in code — never invented. The weakest comparable anchors the downside scenario.
          </p>
          <table className="mt-3 w-full text-[11px]">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th-label py-1 text-left">Target</th>
                <th className="th-label py-1 text-left">Acquirer</th>
                <th className="th-label py-1 text-left">Announced</th>
                <th className="th-label py-1 text-right">Value</th>
                <th className="th-label py-1 text-right">Target Raised</th>
                <th className="th-label py-1 text-right" title="Deal value ÷ target's total raised — computed in code">× capital</th>
              </tr>
            </thead>
            <tbody>
              {acquisitions.map((a, i) => (
                <tr key={i} className="border-b border-gray-900 last:border-0">
                  <td className="py-1.5 font-medium text-gray-200">{a.target}</td>
                  <td className="py-1.5 text-gray-400">{a.acquirer}</td>
                  <td className="py-1.5 tabular-nums text-gray-400">{a.announced}</td>
                  <td className={`py-1.5 text-right tabular-nums ${a.value === "Not Disclosed" ? "italic text-gray-600" : "text-gray-300"}`}>{a.value}</td>
                  <td className={`py-1.5 text-right tabular-nums ${a.target_total_raised === "Not Disclosed" ? "italic text-gray-600" : "text-gray-300"}`}>{a.target_total_raised}</td>
                  <td className="py-1.5 text-right tabular-nums text-gray-300">{a.multiple_on_capital != null ? `${a.multiple_on_capital}x` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {/* ── Cap table (when uploaded) ──────────────────────────────── */}
      {capTable?.rounds?.length ? (
        <section className={panel}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="panel-kicker">Cap table — uploaded round history</div>
            <span className="chip">{capTable.source_file}</span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
            Parsed in code from the uploaded CSV. Grounds the focal&rsquo;s ledger row and the fund-math entry price.
          </p>
          <table className="mt-3 w-full text-[11px]">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="th-label py-1 text-left">Round</th>
                <th className="th-label py-1 text-left">Date</th>
                <th className="th-label py-1 text-right">Raised</th>
                <th className="th-label py-1 text-right">Post-money</th>
                <th className="th-label py-1 pl-2 text-left">Investors</th>
              </tr>
            </thead>
            <tbody>
              {capTable.rounds.map((r, i) => (
                <tr key={i} className="border-b border-gray-900 last:border-0">
                  <td className="py-1.5 font-medium text-gray-200">{r.round}</td>
                  <td className="py-1.5 tabular-nums text-gray-400">{r.date || "—"}</td>
                  <td className="py-1.5 text-right tabular-nums text-gray-300">{musd(r.raised_musd)}</td>
                  <td className="py-1.5 text-right tabular-nums text-gray-300">{musd(r.post_money_musd)}</td>
                  <td className="max-w-[140px] truncate py-1.5 pl-2 text-gray-500" title={r.investors}>{r.investors || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[10.5px] tabular-nums text-gray-600">
            Total raised {musd(capTable.total_raised_musd)}
            {capTable.latest_post_money_musd != null ? <> · latest post {musd(capTable.latest_post_money_musd)} ({capTable.latest_round})</> : null}.
          </p>
        </section>
      ) : null}

      {/* ── Fund Fit (when fund economics were provided) ───────────── */}
      {fundMath ? (() => {
        const a = fundMath.assumptions, v = fundMath.verdicts, req = fundMath.requirements, e = fundMath.expected;
        const nRet = fundMath.scenarios.filter((s) => s.returns_fund).length;
        return (
          <section className="rounded-lg border border-brand-500/30 bg-gray-900/40 p-4">
            <div className="panel-kicker text-brand-300">Fund fit — does this return the fund?</div>
            <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
              For a {musd(a.fund_size_musd)} fund, a {musd(a.check_size_musd)} check
              {a.entry_post_money_musd != null ? ` at ${musd(a.entry_post_money_musd)} post` : ""}
              {a.entry_ownership_pct != null
                ? ` = ${a.entry_ownership_pct}% entry → ${a.ownership_at_exit_pct}% at exit`
                : ""}{" "}
              (after {Math.round((1 - a.retention) * 100)}% dilution to exit).
            </p>

            {/* verdict readout — instrument cells */}
            <div className="mt-3 grid auto-cols-fr grid-flow-col gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60">
              <div className="stat-cell" title={`Best case ${v.best_case_net_turns}x of the fund`}>
                <div className={`stat-value ${v.can_return_fund ? "text-emerald-300" : "text-amber-300"}`}>
                  {nRet}/{fundMath.scenarios.length}
                </div>
                <div className="stat-caption">Scenarios return the fund</div>
              </div>
              <div
                className="stat-cell"
                title={`${req.required_net_MoIC}x net${req.required_gross_MoIC != null ? ` / ${req.required_gross_MoIC}x gross` : ""} on the check`}
              >
                <div className="stat-value">
                  {req.required_exit_value_musd != null ? `~${musd(req.required_exit_value_musd)}` : `${req.required_net_MoIC}x net`}
                </div>
                <div className="stat-caption">Exit to return the fund</div>
              </div>
              <div className="stat-cell">
                <div className={`stat-value ${v.is_fund_maker ? "text-emerald-300" : "text-gray-300"}`}>
                  {v.is_fund_maker ? "Yes" : "No"}
                </div>
                <div className="stat-caption">Fund-maker · ≥{req.target_fund_multiple}x fund</div>
              </div>
              {e != null && (
                <div className="stat-cell">
                  <div className="stat-value">{e.expected_net_MoIC}x</div>
                  <div className="stat-caption">Expected net MoIC</div>
                </div>
              )}
            </div>

            <table className="mt-3 w-full text-[11px]">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="th-label py-1 text-left">Scenario</th>
                  <th className="th-label py-1 text-right">Prob</th>
                  <th className="th-label py-1 text-right">Net MoIC</th>
                  <th className="th-label py-1 text-right">Net proceeds</th>
                  <th className="th-label py-1 text-right">Turns of fund</th>
                  <th className="th-label py-1 text-right">Net IRR</th>
                </tr>
              </thead>
              <tbody>
                {fundMath.scenarios.map((s, i) => (
                  <tr key={i} className={`border-b border-gray-900 last:border-0 ${s.returns_fund ? "text-brand-200" : "text-gray-300"}`}>
                    <td className="py-1.5 capitalize">{s.label}{s.returns_fund ? " ★" : ""}</td>
                    <td className="py-1.5 text-right tabular-nums text-gray-400">{Math.round(s.probability * 100)}%</td>
                    <td className="py-1.5 text-right tabular-nums">{s.net_MoIC}x</td>
                    <td className="py-1.5 text-right tabular-nums">{musd(s.net_proceeds_musd)}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.net_turns}x</td>
                    <td className="py-1.5 text-right tabular-nums">{s.net_irr_pct == null ? "—" : `${s.net_irr_pct > 0 ? "+" : ""}${s.net_irr_pct}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[10.5px] tabular-nums text-gray-500">
              Best case {v.best_case_net_turns}x of the fund
              {e != null ? (
                <>
                  {" "}· expected {e.expected_net_turns}x of fund
                  {e.expected_net_irr_pct != null ? ` · ${e.expected_net_irr_pct > 0 ? "+" : ""}${e.expected_net_irr_pct}% expected net IRR` : ""}
                </>
              ) : null}
              . ★ = returns the fund.
            </p>
            {fundMath.flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {fundMath.flags.map((f) => (
                  <span key={f} className="chip-warn">{FUND_FLAG_LABELS[f] || f}</span>
                ))}
              </div>
            )}
            <p className="mt-2 text-[10.5px] text-gray-600">
              Computed in code from the scenario table + your fund inputs. Net = gross × stage dilution retention;
              turns and IRR are gross of fund fees/carry. Reserves/follow-on not modelled.
            </p>
          </section>
        );
      })() : null}
    </div>
  );
}
