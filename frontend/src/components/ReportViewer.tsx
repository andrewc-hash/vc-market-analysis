"use client";

import { useRef, useState, type ReactNode } from "react";
import type { FinalReport, TaskStatusResponse } from "@/lib/api";
import { toMarkdown, downloadFile, reportSlug } from "@/lib/exportReport";
import ReportSections from "./report/ReportSections";
import MarketMap from "./report/MarketMap";
import Leaderboard from "./report/Leaderboard";
import Scorecard from "./report/Scorecard";
import Gradesheet from "./report/Gradesheet";
import FinancialLedger from "./report/FinancialLedger";
import ClaimsAudit from "./report/ClaimsAudit";
import RunDeltaPanel from "./report/RunDelta";
import PrintableReport from "./PrintableReport";
import TearSheet from "./TearSheet";
import { Icon } from "./icons";

interface Props {
  result: TaskStatusResponse;
}

type Tab = "map" | "scores" | "grades" | "financials" | "claims" | "raw";

const Empty = ({ children }: { children: ReactNode }) => (
  <div className="rounded-md border border-dashed border-gray-800 bg-gray-900/40 p-4 text-sm text-gray-500">{children}</div>
);

// Neutral / accent / warning chips for the masthead meta row.
const chip = "inline-flex items-center gap-1 rounded-md border border-gray-800 bg-gray-800/60 px-2 py-0.5 text-[11px] tabular-nums text-gray-400";
const chipAccent = "inline-flex items-center gap-1 rounded-md border border-brand-500/30 bg-brand-500/10 px-2 py-0.5 text-[11px] text-brand-300";
const chipWarn = "inline-flex items-center gap-1 rounded-md border border-amber-900/50 bg-amber-950/30 px-2 py-0.5 text-[11px] text-amber-300";

export default function ReportViewer({ result }: Props) {
  const report = result.final_report as FinalReport | null;
  const [tab, setTab] = useState<Tab>("map");
  const bodyRef = useRef<HTMLDivElement>(null);
  // Hooks must run unconditionally — declare ALL of them before the null guard.
  const [dlOpen, setDlOpen] = useState(false);
  // Which artifact the browser print dialog renders: the full memo or the one-page tear sheet.
  const [printMode, setPrintMode] = useState<"full" | "tearsheet">("full");

  if (!report) return null;

  const markdown = report.merged_report || report.synthesis || "No report available.";
  const ranking = report.ranking ?? [];
  const weighted = report.weighted_scores ?? {};
  const map = report.market_map ?? null;
  const ledger = report.financial_ledger ?? null;
  const mode = report.analysis_mode === "founder" ? "founder" : "vc";
  const sector = (report.sector || "").trim();
  const pick = report.recommended_pick || ranking[0];

  // Honest return range (gross), matching PrintableReport's null guards.
  const retLo = report.expected_return_low;
  const retHi = report.expected_return_high;
  const retRange =
    retLo != null && retHi != null && retLo !== retHi
      ? `${retLo}x–${retHi}x`
      : report.expected_return != null
        ? `${report.expected_return}x`
        : null;

  // Client-side downloads (no backend). PDF uses the browser's print → "Save as PDF",
  // which renders the print-only <PrintableReport> (light memo layout incl. the map).
  const slug = reportSlug(report);
  const dlMarkdown = () => { downloadFile(`${slug}.md`, toMarkdown(report), "text/markdown"); setDlOpen(false); };
  const dlJson = () => { downloadFile(`${slug}.json`, JSON.stringify(report, null, 2), "application/json"); setDlOpen(false); };
  const dlPdf = () => { setDlOpen(false); setPrintMode("full"); setTimeout(() => window.print(), 80); };
  const dlTearSheet = () => { setDlOpen(false); setPrintMode("tearsheet"); setTimeout(() => window.print(), 80); };

  const segments: Record<string, string | null> = {};
  map?.companies.forEach((c) => {
    segments[c.name] = c.segment;
  });

  // Click a company (map dot or leaderboard row) -> scroll the report to its profile.
  // Prefer h3/h4 (the §8 per-company profiles): the numbered h2 section headers now carry
  // verdict clauses that can name the pick, so an h2 match would hijack the scroll to §0-§13.
  const selectCompany = (name: string) => {
    const container = bodyRef.current;
    if (!container) return;
    const matches = (sel: string) =>
      Array.from(container.querySelectorAll(sel)).find((h) =>
        (h.textContent || "").toLowerCase().includes(name.toLowerCase())
      );
    const profiles = Array.from(container.querySelectorAll("h2,h3,h4")).find((h) =>
      /profile/i.test(h.textContent || "")
    );
    (matches("h3,h4") ?? matches("h2") ?? profiles)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "map", label: "Market Map", show: true },
    { key: "scores", label: "Scores", show: true },
    { key: "grades", label: "Grades", show: !!report.gradesheet?.startups?.length },
    { key: "financials", label: "Financials", show: true },
    { key: "claims", label: "Claims", show: !!report.call_claims_audit?.claims?.length },
    { key: "raw", label: "Raw JSON", show: true },
  ];

  return (
    <>
    <div className="space-y-4 no-print">
      {/* Masthead — verdict first */}
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="kicker">
              {mode === "founder" ? "Founder deal screen" : "Sector analysis"} · {report.thesis_bias ?? "Base"} bias
            </div>
            <h2 className="mt-1 font-serif text-2xl font-semibold tracking-tight text-gray-100">
              {sector || "Market Analysis Report"}
            </h2>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-8 gap-y-1.5">
              {pick && (
                <div
                  title={
                    report.recommended_pick && ranking[0] && report.recommended_pick !== ranking[0]
                      ? `The report's §0/§12 recommendation. #1 by quality index: ${ranking[0]} — see the "quality rank vs price" bridge in §12.`
                      : "The report's recommendation"
                  }
                >
                  <div className="kicker">{mode === "founder" ? "Subject" : "Top pick"}</div>
                  <div className="text-lg font-semibold text-brand-300">{pick}</div>
                </div>
              )}
              {retRange && (
                <div>
                  <div className="kicker">Expected return{report.scenarios?.startup && report.scenarios.startup !== pick ? ` · ${report.scenarios.startup}` : ""}</div>
                  <div className="text-lg font-semibold tabular-nums text-gray-100">
                    {retRange} <span className="text-xs font-normal text-gray-500">gross</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Download menu */}
          <div className="relative no-print shrink-0">
            <button
              onClick={() => setDlOpen((o) => !o)}
              onBlur={() => setTimeout(() => setDlOpen(false), 150)}
              className="btn-secondary"
            >
              <Icon name="download" className="h-3.5 w-3.5" />
              Download
              <Icon name="chevron" className="h-3 w-3" />
            </button>
            {dlOpen && (
              <div className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-md border border-gray-700 bg-gray-900 shadow-pop">
                <button onClick={dlTearSheet} className="block w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800">One-page tear sheet (PDF)</button>
                <button onClick={dlPdf} className="block w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800">Full memo PDF (with visuals)</button>
                <button onClick={dlMarkdown} className="block w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800">Markdown (.md)</button>
                <button onClick={dlJson} className="block w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800">Raw data (.json)</button>
              </div>
            )}
          </div>
        </div>

        {/* run meta chips */}
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          {report.focal_startup && (
            <span className={chipAccent}>
              {mode === "founder" ? "Subject" : "Focal"}: {report.focal_startup}
              {report.focal_confidence ? ` · ${report.focal_confidence} confidence` : ""}
            </span>
          )}
          {report.scope_autoderived && sector && (
            <span className={chipAccent}>Sector auto-identified</span>
          )}
          <span className={chip}>Consensus in {report.iterations_to_consensus ?? "?"} round(s)</span>
          {map && <span className={chip}>{map.companies.length} startups</span>}
          {report.weighting_unavailable && (
            <span className={chipWarn}>
              <Icon name="alert" className="h-3 w-3" />
              weighted index unavailable
            </span>
          )}
          {report.data_freshness && (
            <span
              className={(report.data_freshness.months_since_newest ?? 99) <= 6 ? chip : chipWarn}
              title={`Newest dated evidence: ${report.data_freshness.newest_dated_mention} · oldest: ${report.data_freshness.oldest_dated_mention} · ${report.data_freshness.dated_mentions} dated mentions`}
            >
              {(report.data_freshness.months_since_newest ?? 99) > 6 && <Icon name="alert" className="h-3 w-3" />}
              Data as of {report.data_freshness.report_date}
              {(report.data_freshness.months_since_newest ?? 99) > 6 ? " · stale evidence" : ""}
            </span>
          )}
        </div>
      </div>

      {/* hero stats — ledger-derived field facts, computed in code */}
      {report.field_stats && (
        <div className="grid grid-cols-2 divide-y divide-gray-800 rounded-lg border border-gray-800 bg-gray-900 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
          {[
            { label: "Startups underwritten", value: String(report.field_stats.startups) },
            { label: "Incumbents (reference)", value: String(report.field_stats.incumbents) },
            {
              label: "Disclosed capital in field",
              value: report.field_stats.total_raised_musd != null
                ? report.field_stats.total_raised_musd >= 1000
                  ? `$${(report.field_stats.total_raised_musd / 1000).toFixed(1)}B`
                  : `$${Math.round(report.field_stats.total_raised_musd)}M`
                : "—",
            },
            { label: "ARR disclosed", value: `${report.field_stats.arr_disclosed}/${report.field_stats.startups}` },
          ].map((s) => (
            <div key={s.label} className="px-4 py-3">
              <div className="text-xl font-semibold tabular-nums text-gray-100">{s.value}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wider text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* longitudinal re-run: what changed vs the baseline + prediction self-grading */}
      {(report.run_delta || report.prediction_audit?.length) ? (
        <RunDeltaPanel
          delta={report.run_delta}
          predictions={report.prediction_audit}
          baselineDate={report.baseline_created_at}
        />
      ) : null}

      {/* liability boundary — always visible on investment-adjacent output */}
      <p className="px-1 text-[11px] text-gray-500">
        Decision-support only — not investment advice. AI-generated from public web sources;
        verify material figures against primary sources before acting.{" "}
        <a href="/terms" className="underline hover:text-gray-300">Terms</a>
      </p>

      {/* two columns: paper memo | graphics instruments */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_460px]">
        {/* LEFT — the memo, rendered as a white paper sheet */}
        <div className="order-2 max-h-[80vh] overflow-y-auto rounded-lg bg-white p-6 shadow-sheet ring-1 ring-black/40 sm:p-8 lg:order-1">
          <ReportSections ref={bodyRef} markdown={markdown} />
        </div>

        {/* RIGHT — graphics panel (sticky on desktop) */}
        <div className="order-1 lg:order-2">
          <div className="card lg:sticky lg:top-[4.5rem]">
            <div className="mb-3 flex gap-4 overflow-x-auto border-b border-gray-800">
              {tabs.filter((t) => t.show).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`-mb-px whitespace-nowrap border-b-2 pb-2 text-xs font-medium transition-colors ${
                    tab === t.key
                      ? "border-brand-500 text-gray-100"
                      : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="max-h-[78vh] overflow-y-auto">
              {tab === "map" &&
                (map ? (
                  <MarketMap map={map} ranking={ranking} onSelect={selectCompany} />
                ) : (
                  <Empty>No market map was produced for this run (the model didn’t return usable coordinates). The full report is on the left.</Empty>
                ))}

              {tab === "scores" &&
                (Object.keys(weighted).length ? (
                  <div className="space-y-5">
                    <Leaderboard ranking={ranking} weightedScores={weighted} segments={segments} onSelect={selectCompany} scoreConfidence={report.score_confidence} />
                    <Scorecard ranking={ranking} weightedScores={weighted} appliedWeights={report.applied_weights} moatSubscores={report.moat_subscores} prePmf={report.pre_pmf} scoreConfidence={report.score_confidence} />
                  </div>
                ) : (
                  <Empty>No scores were computed for this run.</Empty>
                ))}

              {tab === "grades" && <Gradesheet gradesheet={report.gradesheet} />}

              {tab === "financials" &&
                (ledger ? (
                  <FinancialLedger
                    ledger={ledger}
                    scenarios={report.scenarios ?? null}
                    expectedReturn={report.expected_return ?? null}
                    expectedReturnLow={report.expected_return_low ?? null}
                    expectedReturnHigh={report.expected_return_high ?? null}
                    expectedReturnNetLow={report.expected_return_net_low ?? null}
                    expectedReturnNetHigh={report.expected_return_net_high ?? null}
                    returnAssumptions={report.return_assumptions ?? null}
                    returnDominance={report.return_dominance ?? null}
                    acquisitions={report.acquisitions ?? null}
                    fundMath={report.fund_math ?? null}
                    capTable={report.cap_table ?? null}
                  />
                ) : (
                  <Empty>No financial ledger was produced for this run.</Empty>
                ))}

              {tab === "claims" && <ClaimsAudit audit={report.call_claims_audit} />}

              {tab === "raw" && (
                <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-gray-400">
                  {JSON.stringify(report, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
    {printMode === "tearsheet" ? <TearSheet report={report} /> : <PrintableReport report={report} />}
    </>
  );
}
