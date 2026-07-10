"use client";

import { useState } from "react";
import type { AcquisitionRow, CapTable, FinancialLedgerData, FundMath, ReturnScenarios } from "@/lib/api";
import { FLAG_STYLE } from "@/lib/viz";

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
    return <p className="text-sm text-gray-500">No financial ledger available for this run.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500">
            {cols.map((c) => (
              <th
                key={c}
                onClick={() => toggle(c)}
                className="cursor-pointer whitespace-nowrap px-2 py-1.5 text-left font-medium hover:text-gray-300"
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
                const fs = flag ? FLAG_STYLE[flag] : null;
                const nd = val === "Not Disclosed";
                return (
                  <td key={c} className={`whitespace-nowrap px-2 py-1.5 ${nd ? "text-gray-600 italic" : "text-gray-300"}`}>
                    {c === "startup" ? (
                      <span className="font-medium text-gray-100">
                        {val}
                        {row.is_incumbent && <span className="ml-1 text-[10px] uppercase tracking-wide text-gray-500">ref</span>}
                      </span>
                    ) : val}
                    {fs && <span className={`ml-1 font-bold ${fs.cls}`} title={fs.label}>{fs.sym}</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-gray-600">
        Flags vs. stage band: <span className="text-green-300">✓ ok</span> · <span className="text-amber-300">! borderline</span> · <span className="text-red-300">✗ off-band</span>. <span className="text-gray-500">ref</span> = incumbent (not scored). Val/ARR computed in code. Click a header to sort.
      </p>

      {scenarios?.scenarios?.length ? (
        <div className="mt-4 rounded-md border border-gray-800 bg-gray-900/40 p-3">
          <div className="flex items-baseline justify-between">
            <h4 className="text-xs font-semibold text-gray-300">
              Probability-Weighted Return{scenarios.startup ? ` · ${scenarios.startup}` : ""}
            </h4>
            {expectedReturn != null && (
              <span
                className="text-sm font-bold text-brand-300"
                title="Gross multiple before dilution, ownership, fees, and time-value — computed in code from the scenario table"
              >
                {expectedReturnLow != null && expectedReturnHigh != null && expectedReturnLow !== expectedReturnHigh
                  ? `${expectedReturnLow}x–${expectedReturnHigh}x`
                  : `${expectedReturn}x`}{" "}
                <span className="text-[10px] font-normal text-gray-500">
                  expected (gross{expectedReturnLow != null && expectedReturnHigh != null && expectedReturnLow !== expectedReturnHigh ? `, mid ${expectedReturn}x` : ""})
                </span>
              </span>
            )}
          </div>
          {expectedReturnNetLow != null && expectedReturnNetHigh != null && (
            <p className="mt-0.5 text-right text-[10px] text-gray-500" title={returnAssumptions?.note || ""}>
              ≈{expectedReturnNetLow}x–{expectedReturnNetHigh}x net of estimated future dilution
              {returnAssumptions ? ` (${Math.round(returnAssumptions.retention * 100)}% stage-banded retention)` : ""} — computed in code
            </p>
          )}
          <table className="mt-2 w-full text-[11px]">
            <tbody>
              {scenarios.scenarios.map((s, i) => {
                const lo = s.multiple_low, hi = s.multiple_high;
                const mult = lo == null && hi == null ? "—" : lo === hi ? `${lo}x` : `${lo}x–${hi}x`;
                return (
                  <tr key={i} className="border-b border-gray-900 last:border-0">
                    <td className="py-1 capitalize text-gray-400">{s.label}</td>
                    {scenarios.scenarios.some((x) => x.path) && (
                      <td className="max-w-[220px] truncate py-1 pl-2 text-gray-500" title={s.path || ""}>{s.path || "—"}</td>
                    )}
                    <td className="py-1 text-right text-gray-400">{Math.round(s.probability * 100)}%</td>
                    <td className="py-1 text-right text-gray-300">{mult}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-gray-600">
            Expected return = Σ probability × midpoint(multiple), computed in code.
            {returnDominance ? ` ${returnDominance.share_pct}% of the expected value sits in the ${returnDominance.label} case.` : ""}
          </p>
        </div>
      ) : null}

      {acquisitions?.length ? (
        <div className="mt-4 rounded-md border border-gray-800 bg-gray-900/40 p-3">
          <h4 className="text-xs font-semibold text-gray-300">Exit Precedents — Sector Acquisitions</h4>
          <table className="mt-2 w-full text-[11px]">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500">
                <th className="py-1 text-left font-medium">Target</th>
                <th className="py-1 text-left font-medium">Acquirer</th>
                <th className="py-1 text-left font-medium">Announced</th>
                <th className="py-1 text-right font-medium">Value</th>
                <th className="py-1 text-right font-medium">Target Raised</th>
                <th className="py-1 text-right font-medium" title="Deal value ÷ target's total raised — computed in code">× capital</th>
              </tr>
            </thead>
            <tbody>
              {acquisitions.map((a, i) => (
                <tr key={i} className="border-b border-gray-900 last:border-0">
                  <td className="py-1 font-medium text-gray-200">{a.target}</td>
                  <td className="py-1 text-gray-400">{a.acquirer}</td>
                  <td className="py-1 text-gray-400">{a.announced}</td>
                  <td className={`py-1 text-right ${a.value === "Not Disclosed" ? "italic text-gray-600" : "text-gray-300"}`}>{a.value}</td>
                  <td className={`py-1 text-right ${a.target_total_raised === "Not Disclosed" ? "italic text-gray-600" : "text-gray-300"}`}>{a.target_total_raised}</td>
                  <td className="py-1 text-right text-gray-300">{a.multiple_on_capital != null ? `${a.multiple_on_capital}x` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-gray-600">
            Research-sourced deals only (validated in code, never invented). The weakest comparable anchors the downside scenario.
          </p>
        </div>
      ) : null}

      {capTable?.rounds?.length ? (
        <div className="mt-4 rounded-md border border-gray-800 bg-gray-900/40 p-3">
          <h4 className="text-xs font-semibold text-gray-300">
            Cap Table — uploaded round history <span className="font-normal text-gray-500">({capTable.source_file})</span>
          </h4>
          <table className="mt-2 w-full text-[11px]">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500">
                <th className="py-1 text-left font-medium">Round</th>
                <th className="py-1 text-left font-medium">Date</th>
                <th className="py-1 text-right font-medium">Raised</th>
                <th className="py-1 text-right font-medium">Post-money</th>
                <th className="py-1 text-left font-medium">Investors</th>
              </tr>
            </thead>
            <tbody>
              {capTable.rounds.map((r, i) => (
                <tr key={i} className="border-b border-gray-900 last:border-0">
                  <td className="py-1 font-medium text-gray-200">{r.round}</td>
                  <td className="py-1 tabular-nums text-gray-400">{r.date || "—"}</td>
                  <td className="py-1 text-right tabular-nums text-gray-300">{musd(r.raised_musd)}</td>
                  <td className="py-1 text-right tabular-nums text-gray-300">{musd(r.post_money_musd)}</td>
                  <td className="max-w-[140px] truncate py-1 pl-2 text-gray-500" title={r.investors}>{r.investors || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-gray-600">
            Parsed in code from the uploaded CSV — total raised {musd(capTable.total_raised_musd)}
            {capTable.latest_post_money_musd != null ? <> · latest post {musd(capTable.latest_post_money_musd)} ({capTable.latest_round})</> : null}.
            Grounds the focal&rsquo;s ledger row and the fund-math entry price.
          </p>
        </div>
      ) : null}

      {fundMath ? (() => {
        const a = fundMath.assumptions, v = fundMath.verdicts, req = fundMath.requirements, e = fundMath.expected;
        const nRet = fundMath.scenarios.filter((s) => s.returns_fund).length;
        return (
          <div className="mt-4 rounded-md border border-brand-500/30 bg-brand-600/5 p-3">
            <h4 className="text-xs font-semibold text-brand-200">Fund Fit — does this return the fund?</h4>
            <p className="mt-1 text-[11px] text-gray-400">
              For a {musd(a.fund_size_musd)} fund, a {musd(a.check_size_musd)} check
              {a.entry_post_money_musd != null ? ` at ${musd(a.entry_post_money_musd)} post` : ""}
              {a.entry_ownership_pct != null
                ? ` = ${a.entry_ownership_pct}% entry → ${a.ownership_at_exit_pct}% at exit`
                : ""}{" "}
              (after {Math.round((1 - a.retention) * 100)}% dilution to exit).
            </p>
            <table className="mt-2 w-full text-[11px]">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="py-1 text-left font-medium">Scenario</th>
                  <th className="py-1 text-right font-medium">Prob</th>
                  <th className="py-1 text-right font-medium">Net MoIC</th>
                  <th className="py-1 text-right font-medium">Net proceeds</th>
                  <th className="py-1 text-right font-medium">Turns of fund</th>
                  <th className="py-1 text-right font-medium">Net IRR</th>
                </tr>
              </thead>
              <tbody>
                {fundMath.scenarios.map((s, i) => (
                  <tr key={i} className={`border-b border-gray-900 last:border-0 ${s.returns_fund ? "text-brand-200" : "text-gray-300"}`}>
                    <td className="py-1 capitalize">{s.label}{s.returns_fund ? " ★" : ""}</td>
                    <td className="py-1 text-right text-gray-400">{Math.round(s.probability * 100)}%</td>
                    <td className="py-1 text-right">{s.net_MoIC}x</td>
                    <td className="py-1 text-right">{musd(s.net_proceeds_musd)}</td>
                    <td className="py-1 text-right">{s.net_turns}x</td>
                    <td className="py-1 text-right">{s.net_irr_pct == null ? "—" : `${s.net_irr_pct > 0 ? "+" : ""}${s.net_irr_pct}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-2 space-y-0.5 text-[11px]">
              <p className={v.can_return_fund ? "text-green-300" : "text-amber-300"}>
                {v.can_return_fund ? "✓" : "✗"} Returns the fund in {nRet}/{fundMath.scenarios.length} modelled scenarios
                {" "}(best case {v.best_case_net_turns}x of the fund).
              </p>
              <p className="text-gray-400">
                Needs {req.required_exit_value_musd != null ? `a ~${musd(req.required_exit_value_musd)} exit ` : ""}
                ({req.required_net_MoIC}x net{req.required_gross_MoIC != null ? ` / ${req.required_gross_MoIC}x gross` : ""} on the check) to return the fund.
              </p>
              <p className="text-gray-400">
                Fund-maker (≥{req.target_fund_multiple}x the fund): <span className={v.is_fund_maker ? "text-green-300" : "text-gray-300"}>{v.is_fund_maker ? "Yes" : "No"}</span>.
                {e != null && (
                  <> Expected: {e.expected_net_MoIC}x net · {e.expected_net_turns}x of fund
                  {e.expected_net_irr_pct != null ? ` · ${e.expected_net_irr_pct > 0 ? "+" : ""}${e.expected_net_irr_pct}% IRR` : ""}.</>
                )}
              </p>
            </div>
            {fundMath.flags.length > 0 && (
              <p className="mt-1 text-[10px] text-amber-400/80">
                {fundMath.flags.map((f) => FUND_FLAG_LABELS[f] || f).join(" · ")}
              </p>
            )}
            <p className="mt-1 text-[10px] text-gray-600">
              Computed in code from the scenario table + your fund inputs. Net = gross × stage dilution retention;
              turns and IRR are gross of fund fees/carry. Reserves/follow-on not modelled.
            </p>
          </div>
        );
      })() : null}
    </div>
  );
}
