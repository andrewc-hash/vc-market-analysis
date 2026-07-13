"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { FinalReport } from "@/lib/api";
import { pickLabel } from "@/lib/pickLabel";

// A ONE-PAGE IC tear sheet — the artifact forwarded to / read at a partner meeting.
// Hidden on screen (`.printable`), shown only when printing (see globals.css @media print),
// rendered instead of the full PrintableReport when the user picks "One-page tear sheet".
// Deliberately dense and computed-data-first: every number here is code-computed upstream.

const musd = (v: number | null | undefined): string =>
  v == null ? "—" : v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`;
const pct = (v: number | null | undefined): string =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`;

/** Slice "## N. …" up to the next "## " heading. */
function sectionText(md: string, n: number): string {
  const re = new RegExp(`(?:^|\\n)##\\s+${n}\\.[^\\n]*\\n([\\s\\S]*?)(?=\\n##\\s|$)`);
  const m = md.match(re);
  return m ? m[1].trim() : "";
}

export default function TearSheet({ report }: { report: FinalReport }) {
  const md = report.merged_report || "";
  const mode = (report.analysis_mode || "vc").toUpperCase();
  const label = pickLabel(report);
  const pick = label.pick || "—";
  const conf = report.score_confidence ?? {};
  const fmtScore = (n: string): string | number => {
    const v = ws[n]?.weighted_score;
    return v == null ? "—" : conf[n] === "low" ? `≈${Math.round(v)}` : v;
  };
  const sector = (report.sector || "").trim();
  const asOf = report.data_freshness?.report_date || "";
  const ranking = report.ranking ?? [];
  const ws = report.weighted_scores ?? {};
  const fs = report.field_stats;
  const fm = report.fund_math;

  // §0 (BLUF) is the tear sheet's verdict spine; trim to keep it one page.
  const bluf = sectionText(md, 0).replace(/\*Research data as of[\s\S]*$/, "").trim().slice(0, 1100);

  const retRange =
    report.expected_return_low != null && report.expected_return_high != null &&
    report.expected_return_low !== report.expected_return_high
      ? `${report.expected_return_low}x–${report.expected_return_high}x`
      : report.expected_return != null
        ? `${report.expected_return}x`
        : null;
  const netRange =
    report.expected_return_net_low != null && report.expected_return_net_high != null
      ? `${report.expected_return_net_low}x–${report.expected_return_net_high}x`
      : null;

  const topRanked = ranking.slice(0, 6);

  return (
    <div className="printable tearsheet" style={{ fontVariantNumeric: "tabular-nums" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", borderBottom: "3px solid #2563eb", paddingBottom: 6, marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: "9pt", letterSpacing: "0.08em", textTransform: "uppercase", color: "#55637a" }}>
            {mode === "FOUNDER" ? "Founder Deal Screen" : "Investment Tear Sheet"}
          </div>
          <div style={{ fontSize: "18pt", fontWeight: 700, color: "#0f1620", lineHeight: 1.1 }}>{sector || "Market Analysis"}</div>
        </div>
        <div style={{ textAlign: "right", fontSize: "9pt", color: "#55637a" }}>
          <div><b style={{ color: "#0f1620" }}>{label.kicker}:</b> {pick}{label.rankSuffix}</div>
          {label.fieldLeader && <div>Field leader: {label.fieldLeader}</div>}
          <div>Bias: {report.thesis_bias || "Base"}{asOf ? ` · as of ${asOf}` : ""}</div>
        </div>
      </div>

      {/* Two columns: verdict prose | the numbers */}
      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 18 }}>
        {/* LEFT — BLUF verdict */}
        <div>
          <div style={{ fontSize: "10.5pt", fontWeight: 700, color: "#2563eb", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Investment Take
          </div>
          <div className="ts-prose" style={{ fontSize: "9.5pt", color: "#22304a", lineHeight: 1.5 }}>
            {bluf ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{bluf}</ReactMarkdown> : <p>See full memo.</p>}
          </div>
        </div>

        {/* RIGHT — computed facts */}
        <div style={{ fontSize: "9pt" }}>
          {/* Field stats strip */}
          {fs && (
            <div style={{ display: "flex", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
              {[
                [String(fs.startups), "startups"],
                [String(fs.incumbents), "incumbents"],
                [fs.total_raised_musd != null ? musd(fs.total_raised_musd) : "—", "raised"],
                [`${fs.arr_disclosed}/${fs.startups}`, "ARR disc."],
              ].map(([v, l]) => (
                <div key={l}>
                  <div style={{ fontSize: "13pt", fontWeight: 700, color: "#0f1620" }}>{v}</div>
                  <div style={{ fontSize: "7.5pt", textTransform: "uppercase", color: "#8090a5" }}>{l}</div>
                </div>
              ))}
            </div>
          )}

          {/* Scorecard */}
          {topRanked.length > 0 && (
            <>
              <div style={{ fontSize: "8.5pt", fontWeight: 700, color: "#2563eb", marginBottom: 3, textTransform: "uppercase" }}>Weighted Index</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "8.5pt", marginBottom: 10 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #cdd8e6" }}>
                    <th style={{ padding: "2px 0", width: 16 }} />
                    <th style={{ padding: "2px 0", textAlign: "left", fontSize: "7.5pt", textTransform: "uppercase", letterSpacing: "0.04em", color: "#8090a5", fontWeight: 600 }}>Startup</th>
                    <th style={{ padding: "2px 0", textAlign: "right", fontSize: "7.5pt", textTransform: "uppercase", letterSpacing: "0.04em", color: "#8090a5", fontWeight: 600 }}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {topRanked.map((n, i) => (
                    <tr key={n} style={{ borderBottom: "1px solid #e4eaf2" }}>
                      <td style={{ padding: "2.5px 0", color: "#8090a5" }}>{i + 1}</td>
                      <td style={{ padding: "2.5px 0", color: "#0f1620", fontWeight: n === label.starName ? 700 : 400 }}>{n}{n === label.starName ? " ★" : ""}</td>
                      <td style={{ padding: "2.5px 0", textAlign: "right", color: "#22304a", fontWeight: 600 }}>
                        {fmtScore(n)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {/* Return math */}
          {retRange && (
            <div style={{ background: "#f2f6fd", border: "1px solid #d3e0f5", borderRadius: 6, padding: "7px 9px", marginBottom: 8 }}>
              <div style={{ fontSize: "8.5pt", fontWeight: 700, color: "#2563eb", textTransform: "uppercase", marginBottom: 2 }}>Return Math{report.scenarios?.startup ? ` · ${report.scenarios.startup}` : ""}</div>
              <div style={{ color: "#0f1620" }}>
                <b>{retRange}</b> gross{netRange ? <> · <b>≈{netRange}</b> net of dilution</> : null}
              </div>
              {report.return_dominance && (
                <div style={{ fontSize: "8pt", color: "#55637a", marginTop: 2 }}>
                  {report.return_dominance.share_pct}% of EV in the {report.return_dominance.label} case.
                </div>
              )}
            </div>
          )}

          {/* Fund fit — the partner-meeting money line */}
          {fm && (
            <div style={{ background: fm.verdicts.can_return_fund ? "#eef8f0" : "#fdf3ec", border: "1px solid #d7e6da", borderRadius: 6, padding: "7px 9px" }}>
              <div style={{ fontSize: "8.5pt", fontWeight: 700, color: "#2563eb", textTransform: "uppercase", marginBottom: 2 }}>Fund Fit</div>
              <div style={{ color: "#0f1620" }}>
                {musd(fm.assumptions.check_size_musd)} into {musd(fm.assumptions.fund_size_musd)} fund:{" "}
                <b>{fm.verdicts.can_return_fund ? "can return the fund" : "does not return the fund"}</b>
                {" "}(best {fm.verdicts.best_case_net_turns}x of fund).
              </div>
              <div style={{ fontSize: "8pt", color: "#55637a", marginTop: 2 }}>
                Needs {fm.requirements.required_exit_value_musd != null ? `~${musd(fm.requirements.required_exit_value_musd)} exit` : `${fm.requirements.required_net_MoIC}x net`} to return it
                {fm.expected ? ` · exp. ${fm.expected.expected_net_MoIC}x net${fm.expected.expected_net_irr_pct != null ? ` / ${pct(fm.expected.expected_net_irr_pct)} IRR` : ""}` : ""}.
                {" "}Fund-maker: {fm.verdicts.is_fund_maker ? "yes" : "no"}.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid #d5dde8", marginTop: 12, paddingTop: 6, fontSize: "7.5pt", color: "#8090a5" }}>
        Decision-support only — not investment advice. AI-generated from public web sources; scores, rankings,
        and returns are computed heuristics (returns gross unless labeled net; net reflects a coarse stage-banded
        dilution assumption). Verify material figures against primary sources. Full memo available on request.
      </div>
    </div>
  );
}
