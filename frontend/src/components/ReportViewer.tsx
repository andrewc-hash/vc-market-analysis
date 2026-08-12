"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { FinalReport, TaskStatusResponse, TourStep } from "@/lib/api";
import { toMarkdown, downloadFile, reportSlug } from "@/lib/exportReport";
import { buildFallbackTour } from "@/lib/tour";
import { pickLabel } from "@/lib/pickLabel";
import ReportSections from "./report/ReportSections";
import MarketMap from "./report/MarketMap";
import Leaderboard from "./report/Leaderboard";
import Scorecard from "./report/Scorecard";
import Gradesheet from "./report/Gradesheet";
import FinancialLedger from "./report/FinancialLedger";
import ClaimsAudit from "./report/ClaimsAudit";
import AuditTrail from "./report/AuditTrail";
import PresentMode from "./report/PresentMode";
import HelpGuide from "./HelpGuide";
import RunDeltaPanel from "./report/RunDelta";
import PrintableReport from "./PrintableReport";
import TearSheet from "./TearSheet";
import { Icon } from "./icons";
import { useToast } from "./Toaster";

interface Props {
  result: TaskStatusResponse;
}

type Tab = "memo" | "map" | "scores" | "grades" | "financials" | "claims" | "audit" | "raw";

// Shared dashed placeholder (.empty-state in globals.css — report/* tabs use the same).
const Empty = ({ children }: { children: ReactNode }) => (
  <div className="empty-state">{children}</div>
);

// Masthead meta chips — shared .chip/.chip-accent/.chip-warn classes in globals.css.
const chip = "chip";
const chipAccent = "chip-accent";
const chipWarn = "chip-warn";

export default function ReportViewer({ result }: Props) {
  const report = result.final_report as FinalReport | null;
  const [tab, setTab] = useState<Tab>("memo");
  const bodyRef = useRef<HTMLDivElement>(null);
  // Hooks must run unconditionally — declare ALL of them before the null guard.
  const [dlOpen, setDlOpen] = useState(false);
  // Which artifact the browser print dialog renders: the full memo or the one-page tear sheet.
  const [printMode, setPrintMode] = useState<"full" | "tearsheet">("full");
  const [presentOpen, setPresentOpen] = useState(false);
  // No-op outside a <ToastProvider> (/demo, /preview) — the actions still work silently.
  const toast = useToast();
  // Backend-emitted tour when present; otherwise built client-side from merged_report
  // so Present works on /demo fixtures and pre-tour History runs.
  const tourSteps = useMemo<TourStep[]>(
    () => (report ? (report.tour?.steps?.length ? report.tour.steps : buildFallbackTour(report)) : []),
    [report]
  );
  // ?tab= deep link (post-mount — tab is client state): handy in demos, required for
  // headless screenshot verification of non-default tabs.
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t && ["memo", "map", "scores", "grades", "financials", "claims", "audit", "raw"].includes(t)) {
      setTab(t as Tab);
    }
  }, []);

  if (!report) return null;

  const markdown = report.merged_report || report.synthesis || "No report available.";
  const ranking = report.ranking ?? [];
  const weighted = report.weighted_scores ?? {};
  const map = report.market_map ?? null;
  const ledger = report.financial_ledger ?? null;
  const mode = report.analysis_mode === "founder" ? "founder" : "vc";
  const sector = (report.sector || "").trim();
  // R11 header consistency (VC+focal → "Target evaluated", never "Top pick") is centralized
  // in pickLabel() so the masthead, tear sheet, PDF, and Markdown export never diverge.
  const { pick, kicker: pickKicker, rankSuffix: pickSuffix, fieldLeader, focalIsPick } = pickLabel(report);

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
  const dlMarkdown = () => { downloadFile(`${slug}.md`, toMarkdown(report), "text/markdown"); setDlOpen(false); toast("Markdown downloaded", "success"); };
  const dlJson = () => { downloadFile(`${slug}.json`, JSON.stringify(report, null, 2), "application/json"); setDlOpen(false); toast("JSON downloaded", "success"); };
  // The two print-based exports open the browser dialog — no toast (nothing has saved yet).
  const dlPdf = () => { setDlOpen(false); setPrintMode("full"); setTimeout(() => window.print(), 80); };
  const dlTearSheet = () => { setDlOpen(false); setPrintMode("tearsheet"); setTimeout(() => window.print(), 80); };

  // "Copy verdict" — a plain-text masthead summary for pasting into notes/Slack.
  // Uses pickLabel's kicker verbatim so the R11 semantics survive the copy (a VC+focal
  // run reads "Target evaluated:", never "Top pick:").
  const copyVerdict = () => {
    const lines: string[] = [];
    if (sector) lines.push(sector);
    if (pick) lines.push(`${pickKicker}: ${pick}${pickSuffix}`);
    if (fieldLeader) lines.push(`Field leader: ${fieldLeader}`);
    if (retRange) {
      const nLo = report.expected_return_net_low;
      const nHi = report.expected_return_net_high;
      const net = nLo != null && nHi != null ? ` · ${nLo === nHi ? `${nLo}x` : `${nLo}x–${nHi}x`} net` : "";
      lines.push(`Expected return: ${retRange} gross${net}`);
    }
    if (report.data_freshness?.report_date) lines.push(`Data as of ${report.data_freshness.report_date}`);
    lines.push("Decision-support only — not investment advice. Generated by Prospectus.");
    if (!navigator.clipboard?.writeText) {
      toast("Clipboard unavailable in this browser", "error");
      return;
    }
    navigator.clipboard.writeText(lines.join("\n")).then(
      () => toast("Verdict copied", "success"),
      () => toast("Clipboard access denied by the browser", "error")
    );
  };

  const segments: Record<string, string | null> = {};
  map?.companies.forEach((c) => {
    segments[c.name] = c.segment;
  });

  // Click a company (map dot or leaderboard row) -> open the memo and scroll to its profile.
  // Prefer h3/h4 (the §8 per-company profiles): the numbered h2 section headers now carry
  // verdict clauses that can name the pick, so an h2 match would hijack the scroll to §0-§13.
  const selectCompany = (name: string) => {
    setTab("memo");
    setTimeout(() => {
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
    }, 120);
  };

  // Present-mode "Open full section →": close the overlay, open the memo tab, and
  // scroll to the step's section header (§N is only visible on the Memo tab now).
  const jumpToStep = (step: TourStep) => {
    setPresentOpen(false);
    setTab("memo");
    setTimeout(() => {
      const container = bodyRef.current;
      if (!container) return;
      container
        .querySelector(`section[data-secnum="${String(step.section)}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  };

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "memo", label: "Memo", show: true },
    { key: "map", label: "Market Map", show: true },
    { key: "scores", label: "Scores", show: true },
    { key: "grades", label: "Grades", show: !!report.gradesheet?.startups?.length },
    { key: "financials", label: "Financials", show: true },
    { key: "claims", label: "Claims", show: !!report.call_claims_audit?.claims?.length },
    { key: "audit", label: "Audit", show: true },
    { key: "raw", label: "Raw JSON", show: true },
  ];

  return (
    <>
    <div className="space-y-4 no-print stagger-children">
      {/* Masthead — a terminal header block: title row / verdict row / meta row */}
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="kicker">
              {mode === "founder" ? "Founder deal screen" : "Sector analysis"} · {report.thesis_bias ?? "Base"} bias
            </div>
            <h2 className="mt-1.5 font-serif text-[26px] font-semibold leading-tight tracking-tight text-gray-100">
              {sector || "Market Analysis Report"}
            </h2>
          </div>

          {/* Present + Copy verdict + Download menu */}
          <div className="no-print flex shrink-0 items-start gap-2">
            <button
              onClick={copyVerdict}
              className="btn-secondary"
              title="Copy a plain-text verdict summary to the clipboard"
            >
              <Icon name="copy" className="h-3.5 w-3.5" />
              Copy verdict
            </button>
            {tourSteps.length > 0 && (
              <button onClick={() => setPresentOpen(true)} className="btn-secondary" title="A step-through presentation of the report's key findings">
                <Icon name="play" className="h-3.5 w-3.5" />
                Quick Overview
              </button>
            )}
            <div className="relative">
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
        </div>

        {/* verdict row — primary = the pick; secondaries hairline-separated, one shared baseline */}
        {(pick || fieldLeader || retRange) && (
          <div className="mt-4 flex flex-wrap gap-x-8 gap-y-3 border-t border-gray-800/80 pt-4">
            {pick && (
              <div
                title={
                  focalIsPick
                    ? "This report evaluates your target — see §0/§12 for its INVEST/WATCH/PASS verdict. This is NOT a buy recommendation."
                    : report.recommended_pick && ranking[0] && report.recommended_pick !== ranking[0]
                      ? `The report's §0/§12 recommendation. #1 by quality index: ${ranking[0]} — see the "quality rank vs price" bridge in §12.`
                      : "The report's recommendation"
                }
              >
                <div className="kicker">{pickKicker}</div>
                <div className="mt-1 text-lg font-semibold leading-6 text-brand-300">
                  {pick}
                  <span className="ml-1 font-mono text-[11px] font-normal tabular-nums text-gray-500">{pickSuffix}</span>
                </div>
              </div>
            )}
            {fieldLeader && (
              <div
                className="sm:border-l sm:border-gray-800 sm:pl-8"
                title="The highest-scoring startup in the field by the weighted quality index — not necessarily the recommended investment."
              >
                <div className="kicker">Field leader</div>
                <div className="mt-1 text-lg font-medium leading-6 text-gray-200">{fieldLeader}</div>
              </div>
            )}
            {retRange && (
              <div className="sm:border-l sm:border-gray-800 sm:pl-8">
                <div className="kicker">Expected return{report.scenarios?.startup && report.scenarios.startup !== pick ? ` · ${report.scenarios.startup}` : ""}</div>
                <div className="mt-1 text-lg font-medium tabular-nums leading-6 text-gray-200">
                  {retRange} <span className="font-mono text-[11px] font-normal text-gray-500">gross</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* run meta chips — one tidy mono row */}
        <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-gray-800/80 pt-3.5">
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

      {/* hero stats — ledger-derived field facts, computed in code (StatStrip instrument cells) */}
      {report.field_stats && (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60 sm:grid-cols-4">
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
            <div key={s.label} className="stat-cell">
              <div className="stat-value">{s.value}</div>
              <div className="stat-caption">{s.label}</div>
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

      {/* single full-width panel: Memo | graphics instruments, one tab at a time */}
      <div className="card">
        {/* tab bar — full-card-width hairline (-mx-5 bleeds through the card padding);
            Raw JSON stays but is pushed right + dimmed (utility, not a headline view). */}
        <div className="-mx-5 mb-5 flex items-end gap-6 overflow-x-auto border-b border-gray-800 px-5">
          {tabs.filter((t) => t.show).map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`-mb-px whitespace-nowrap border-b-2 pb-2.5 text-[13px] font-medium transition-colors ${
                t.key === "raw" ? "ml-auto" : ""
              } ${
                tab === t.key
                  ? "border-brand-500 text-gray-100"
                  : t.key === "raw"
                    ? "border-transparent text-gray-600 hover:text-gray-400"
                    : "border-transparent text-gray-500 hover:text-gray-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Memo stays mounted (hidden) so company/section jumps can scroll it after a tab switch. */}
        <div className={tab === "memo" ? "block" : "hidden"}>
          <div className="max-h-[82vh] overflow-y-auto rounded-lg bg-white p-6 shadow-sheet ring-1 ring-black/40 sm:px-12 sm:py-10">
            <div className="mx-auto max-w-[1010px]">
              <ReportSections ref={bodyRef} markdown={markdown} />
            </div>
          </div>
        </div>

        {tab !== "memo" && (
          <div className="mx-auto max-h-[82vh] w-full max-w-5xl overflow-y-auto">
              {tab === "map" &&
                (map ? (
                  <MarketMap map={map} ranking={ranking} onSelect={selectCompany} side />
                ) : (
                  <Empty>No market map was produced for this run (the model didn’t return usable coordinates). The full report is in the Memo tab.</Empty>
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

              {tab === "grades" && <Gradesheet gradesheet={report.gradesheet} analysisMode={report.analysis_mode} />}

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

              {tab === "audit" && <AuditTrail report={report} />}

              {tab === "raw" && (
                <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-gray-400">
                  {JSON.stringify(report, null, 2)}
                </pre>
              )}
          </div>
        )}
      </div>
    </div>
    {presentOpen && tourSteps.length > 0 && (
      <PresentMode report={report} steps={tourSteps} onClose={() => setPresentOpen(false)} onJump={jumpToStep} />
    )}
    <HelpGuide />
    {printMode === "tearsheet" ? <TearSheet report={report} /> : <PrintableReport report={report} />}
    </>
  );
}
