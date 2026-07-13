"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { FinalReport } from "@/lib/api";
import { pickLabel } from "@/lib/pickLabel";
import MarketMap from "./report/MarketMap";

// Hidden on screen (`.printable { display:none }`), shown only when printing (see globals.css
// @media print). Light memo layout with the real market-map SVG PLUS rendered appendices of
// every graphics tab (scorecard, moats, ledger, scenarios, exit precedents, fund fit, grades),
// so "Print → Save as PDF" yields a complete, VC-memo-grade PDF — not just the prose.

const musd = (v: number | null | undefined): string =>
  v == null ? "—" : v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`;

const LEDGER_HEADERS: Record<string, string> = {
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

const FLAG_SYM: Record<string, string> = { ok: " ✓", warn: " !", bad: " ✗" };

const FUND_FLAG_LABELS: Record<string, string> = {
  post_inferred: "entry post-money inferred from stage",
  ownership_infeasible: "check exceeds post-money — ownership clamped",
  retention_defaulted: "stage unknown — 0.70 retention assumed",
  ownership_mismatch: "stated ownership disagrees with check/post — check/post used",
  ownership_input_ignored: "target ownership out of range — ignored",
  unit_suspect: "a dollar input looks large — verify it is in $M",
  holding_too_short: "holding under a quarter — IRR suppressed",
  unusual_returner_bar: "return-the-fund bar set unusually low",
  check_exceeds_fund: "check is larger than the whole fund",
};

const DIMS: { key: "financial_health" | "defensibility" | "market_urgency" | "founder_market_fit" | "regulatory_alignment"; short: string }[] = [
  { key: "financial_health", short: "Financial" },
  { key: "defensibility", short: "Defens." },
  { key: "market_urgency", short: "Urgency" },
  { key: "founder_market_fit", short: "Founder" },
  { key: "regulatory_alignment", short: "Regul." },
];

const MOATS: { key: string; short: string }[] = [
  { key: "economies_of_scale", short: "Scale" },
  { key: "differentiated_technology", short: "Tech" },
  { key: "network_effects", short: "Network" },
  { key: "brand_power", short: "Brand" },
];

export default function PrintableReport({ report }: { report: FinalReport }) {
  const map = report.market_map ?? null;
  const ranking = report.ranking ?? [];
  const sector = (report.sector || "").trim();
  const mode = (report.analysis_mode || "vc").toUpperCase();

  const label = pickLabel(report);
  const pick = label.pick;
  const meta = [`Mode: ${mode}`];
  if (pick) meta.push(`${label.kicker}: ${pick}${label.rankSuffix}`);
  if (label.fieldLeader) meta.push(`Field leader: ${label.fieldLeader}`);
  // The probability-weighted return is the modelled pick's — in founder mode that's usually a
  // COMPETITOR (the field leader), so attribute it rather than let it read as the focal's.
  // Shown as the honest RANGE (gross multiple) when bounds differ.
  if (report.expected_return != null) {
    const who = report.scenarios?.startup;
    // Tolerant match, mirroring the backend's _norm_name containment ("NeuroScribe, Inc."
    // must not be attributed as a competitor of focal "NeuroScribe").
    const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "");
    const same =
      who && report.focal_startup
        ? (() => { const a = norm(who), b = norm(report.focal_startup); return a === b || a.includes(b) || b.includes(a); })()
        : false;
    const isCompetitor = mode === "FOUNDER" && !!who && !!report.focal_startup && !same;
    const lo = report.expected_return_low;
    const hi = report.expected_return_high;
    const val = lo != null && hi != null && lo !== hi ? `${lo}x–${hi}x (gross)` : `${report.expected_return}x (gross)`;
    meta.push(`Prob-weighted return${isCompetitor ? ` (${who})` : ""}: ${val}`);
    if (report.expected_return_net_low != null && report.expected_return_net_high != null) {
      meta.push(`Net of est. dilution: ≈${report.expected_return_net_low}x–${report.expected_return_net_high}x`);
    }
  }
  if (report.thesis_bias) meta.push(`Bias: ${report.thesis_bias}`);
  if (report.focal_startup) {
    meta.push(
      `${mode === "FOUNDER" ? "Subject" : "Focal"}: ${report.focal_startup}` +
        (report.focal_confidence ? ` (${report.focal_confidence} confidence)` : "")
    );
  }
  if (report.data_freshness?.report_date) meta.push(`Data as of ${report.data_freshness.report_date}`);

  // ---- appendix data (mirror the on-screen tabs; render only what exists) ----
  const weighted = report.weighted_scores ?? {};
  const rankedNames = ranking.filter((n) => weighted[n]);
  const conf = report.score_confidence ?? {};
  const fmtScore = (name: string, v: number | null | undefined) =>
    v == null ? "—" : conf[name] === "low" ? `≈${Math.round(v)}` : String(v);
  const moats = report.moat_subscores ?? {};
  const moatNames = rankedNames.filter((n) => moats[n]);
  const ledger = report.financial_ledger ?? null;
  const ledgerCols = ledger?.columns?.length ? ledger.columns : Object.keys(LEDGER_HEADERS);
  const scen = report.scenarios ?? null;
  const acq = report.acquisitions ?? null;
  const fm = report.fund_math ?? null;
  const gs = report.gradesheet ?? null;
  const cap = report.cap_table ?? null;
  const claims = report.call_claims_audit?.claims ?? [];
  const preds = report.prediction_audit ?? [];
  const rd = report.run_delta ?? null;

  return (
    <div className="printable">
      {/* Letterhead — branded header on the forwarded artifact */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "2px solid #2563eb", paddingBottom: 8, marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}>
            <rect width="24" height="24" rx="5" fill="#2563eb" />
            <path d="M12 4 L20 12 L12 20 L4 12 Z" fill="#ffffff" />
            <path d="M12 8.5 L15.5 12 L12 15.5 L8.5 12 Z" fill="#2563eb" />
          </svg>
          <span style={{ fontSize: "15pt", fontWeight: 700, color: "#0f1620", letterSpacing: "-0.01em" }}>Prospectus</span>
        </div>
        <div style={{ fontSize: "8.5pt", textTransform: "uppercase", letterSpacing: "0.08em", color: "#55637a" }}>
          {mode === "FOUNDER" ? "Founder Deal Screen" : "Investment Memo"}
        </div>
      </div>
      <h1>{sector || "Market Analysis"}</h1>
      <p className="print-meta">{meta.join("  ·  ")}</p>

      {map && (
        <div className="print-map">
          <MarketMap map={map} ranking={ranking} light />
        </div>
      )}

      <article className="print-prose">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.merged_report || ""}</ReactMarkdown>
      </article>

      {/* ---- Appendices: the graphics tabs, rendered for paper ---- */}

      {rankedNames.length > 0 && (
        <section className="print-prose page-break">
          <h2>Appendix A — Weighted Underwriting Index</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Startup</th>
                {DIMS.map((d) => <th key={d.key}>{d.short}</th>)}
                <th>Weighted</th>
              </tr>
            </thead>
            <tbody>
              {rankedNames.map((n, i) => (
                <tr key={n}>
                  <td>{i + 1}</td>
                  <td><b>{n}</b>{n === label.starName ? " ★" : ""}</td>
                  {DIMS.map((d) => <td key={d.key}>{fmtScore(n, weighted[n][d.key])}</td>)}
                  <td><b>{fmtScore(n, weighted[n].weighted_score)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          {report.applied_weights && (
            <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
              Applied weights: {DIMS.map((d) => `${d.short} ${Math.round((report.applied_weights?.[d.key] ?? 0) * 100)}%`).join(" · ")}.
              ≈ = disclosure-limited (approximate). Weighted index computed in code from the reconciled analyst scores.
            </p>
          )}

          {moatNames.length > 0 && (
            <>
              <h3>Defensibility moat sub-scores (a16z — Defensibility = their mean)</h3>
              <table>
                <thead>
                  <tr>
                    <th>Startup</th>
                    {MOATS.map((m) => <th key={m.key}>{m.short}</th>)}
                    <th>Mean</th>
                  </tr>
                </thead>
                <tbody>
                  {moatNames.map((n) => {
                    const subs = moats[n];
                    const present = MOATS.map((m) => subs[m.key]).filter((v) => typeof v === "number");
                    const mean = present.length ? Math.round((present.reduce((a, b) => a + b, 0) / present.length) * 10) / 10 : null;
                    return (
                      <tr key={n}>
                        <td>{n}</td>
                        {MOATS.map((m) => <td key={m.key}>{typeof subs[m.key] === "number" ? subs[m.key] : "—"}</td>)}
                        <td><b>{mean ?? "—"}</b></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
          {report.pre_pmf && report.pre_pmf.length > 0 && (
            <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
              Watchlist (pre-PMF, not scored): {report.pre_pmf.join(", ")}.
            </p>
          )}
        </section>
      )}

      {(ledger?.rows?.length || scen?.scenarios?.length || acq?.length || fm) && (
        <section className="print-prose page-break">
          <h2>Appendix B — Financial Ledger &amp; Return Math</h2>
          {ledger?.rows?.length ? (
            <table>
              <thead>
                <tr>{ledgerCols.map((c) => <th key={c}>{LEDGER_HEADERS[c] ?? c}</th>)}</tr>
              </thead>
              <tbody>
                {ledger.rows.map((row, i) => (
                  <tr key={i}>
                    {ledgerCols.map((c) => {
                      const val = String((row as unknown as Record<string, unknown>)[c] ?? "");
                      const flag = row.flags?.[c];
                      return (
                        <td key={c} style={val === "Not Disclosed" ? { color: "#8090a5", fontStyle: "italic" } : undefined}>
                          {c === "startup" ? (<b>{val}{row.is_incumbent ? " (ref)" : ""}</b>) : val}
                          {flag ? FLAG_SYM[flag] : ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {ledger?.rows?.length ? (
            <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
              Flags vs. stage band: ✓ meets · ! borderline · ✗ off-band. (ref) = incumbent, reference only. Val/ARR computed in code.
            </p>
          ) : null}

          {scen?.scenarios?.length ? (
            <>
              <h3>Probability-weighted return{scen.startup ? ` — ${scen.startup}` : ""}</h3>
              <table>
                <thead>
                  <tr>
                    <th>Scenario</th>
                    {scen.scenarios.some((s) => s.path) && <th>Path</th>}
                    <th>Probability</th>
                    <th>Multiple</th>
                  </tr>
                </thead>
                <tbody>
                  {scen.scenarios.map((s, i) => {
                    const lo = s.multiple_low, hi = s.multiple_high;
                    const mult = lo == null && hi == null ? "—" : lo === hi ? `${lo}x` : `${lo}x–${hi}x`;
                    return (
                      <tr key={i}>
                        <td style={{ textTransform: "capitalize" }}>{s.label}</td>
                        {scen.scenarios.some((x) => x.path) && <td>{s.path || "—"}</td>}
                        <td>{Math.round(s.probability * 100)}%</td>
                        <td>{mult}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
                Expected return = Σ probability × midpoint(multiple), computed in code
                {report.expected_return != null ? ` — ${report.expected_return}x gross midpoint` : ""}
                {report.expected_return_net_low != null && report.expected_return_net_high != null
                  ? `; ≈${report.expected_return_net_low}x–${report.expected_return_net_high}x net of estimated dilution`
                  : ""}
                {report.return_dominance ? `. ${report.return_dominance.share_pct}% of EV sits in the ${report.return_dominance.label} case` : ""}.
              </p>
            </>
          ) : null}

          {acq?.length ? (
            <>
              <h3>Exit precedents — sector acquisitions</h3>
              <table>
                <thead>
                  <tr>
                    <th>Target</th><th>Acquirer</th><th>Announced</th><th>Value</th><th>Target raised</th><th>× capital</th>
                  </tr>
                </thead>
                <tbody>
                  {acq.map((a, i) => (
                    <tr key={i}>
                      <td><b>{a.target}</b></td>
                      <td>{a.acquirer}</td>
                      <td>{a.announced}</td>
                      <td>{a.value}</td>
                      <td>{a.target_total_raised}</td>
                      <td>{a.multiple_on_capital != null ? `${a.multiple_on_capital}x` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
                Research-sourced deals only (validated in code). The weakest comparable anchors the downside scenario.
              </p>
            </>
          ) : null}

          {cap?.rounds?.length ? (
            <>
              <h3>Cap table — uploaded round history ({cap.source_file})</h3>
              <table>
                <thead>
                  <tr><th>Round</th><th>Date</th><th>Raised</th><th>Post-money</th><th>Investors</th></tr>
                </thead>
                <tbody>
                  {cap.rounds.map((r, i) => (
                    <tr key={i}>
                      <td><b>{r.round}</b></td>
                      <td>{r.date || "—"}</td>
                      <td>{musd(r.raised_musd)}</td>
                      <td>{musd(r.post_money_musd)}</td>
                      <td>{r.investors || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
                Parsed in code from the uploaded CSV — total raised {musd(cap.total_raised_musd)}
                {cap.latest_post_money_musd != null ? ` · latest post ${musd(cap.latest_post_money_musd)} (${cap.latest_round})` : ""}.
                Grounds the focal&rsquo;s ledger row and the fund-math entry price.
              </p>
            </>
          ) : null}

          {fm ? (
            <>
              <h3>Fund fit — does this return the fund?</h3>
              <p style={{ fontSize: "9pt" }}>
                For a {musd(fm.assumptions.fund_size_musd)} fund, a {musd(fm.assumptions.check_size_musd)} check
                {fm.assumptions.entry_post_money_musd != null ? ` at ${musd(fm.assumptions.entry_post_money_musd)} post` : ""}
                {fm.assumptions.entry_ownership_pct != null
                  ? ` = ${fm.assumptions.entry_ownership_pct}% entry → ${fm.assumptions.ownership_at_exit_pct}% at exit`
                  : ""}{" "}
                (after {Math.round((1 - fm.assumptions.retention) * 100)}% dilution to exit).
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Scenario</th><th>Prob</th><th>Net MoIC</th><th>Net proceeds</th><th>Turns of fund</th><th>Net IRR</th>
                  </tr>
                </thead>
                <tbody>
                  {fm.scenarios.map((s, i) => (
                    <tr key={i}>
                      <td style={{ textTransform: "capitalize" }}>{s.label}{s.returns_fund ? " ★" : ""}</td>
                      <td>{Math.round(s.probability * 100)}%</td>
                      <td>{s.net_MoIC}x</td>
                      <td>{musd(s.net_proceeds_musd)}</td>
                      <td>{s.net_turns}x</td>
                      <td>{s.net_irr_pct == null ? "—" : `${s.net_irr_pct > 0 ? "+" : ""}${s.net_irr_pct}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: "9pt" }}>
                <b>{fm.verdicts.can_return_fund ? "✓ Returns the fund" : "✗ Does not return the fund"}</b> in{" "}
                {fm.scenarios.filter((s) => s.returns_fund).length}/{fm.scenarios.length} modelled scenarios
                (best case {fm.verdicts.best_case_net_turns}x of the fund). Needs{" "}
                {fm.requirements.required_exit_value_musd != null ? `a ~${musd(fm.requirements.required_exit_value_musd)} exit ` : ""}
                ({fm.requirements.required_net_MoIC}x net
                {fm.requirements.required_gross_MoIC != null ? ` / ${fm.requirements.required_gross_MoIC}x gross` : ""} on the check)
                to return the fund. Fund-maker (≥{fm.requirements.target_fund_multiple}x the fund): {fm.verdicts.is_fund_maker ? "yes" : "no"}.
                {fm.expected != null
                  ? ` Expected: ${fm.expected.expected_net_MoIC}x net · ${fm.expected.expected_net_turns}x of fund${
                      fm.expected.expected_net_irr_pct != null ? ` · ${fm.expected.expected_net_irr_pct > 0 ? "+" : ""}${fm.expected.expected_net_irr_pct}% IRR` : ""
                    }.`
                  : ""}
              </p>
              {fm.flags.length > 0 && (
                <p style={{ fontSize: "8.5pt", color: "#8a6d1a" }}>
                  Assumption flags: {fm.flags.map((f) => FUND_FLAG_LABELS[f] || f).join(" · ")}.
                </p>
              )}
              <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
                Computed in code from the scenario table + fund inputs. Net = gross × stage dilution retention;
                turns and IRR are gross of fund fees/carry. Reserves/follow-on not modelled.
              </p>
            </>
          ) : null}
        </section>
      )}

      {gs?.startups?.length ? (
        <section className="print-prose page-break">
          <h2>Appendix C — Gradesheet</h2>
          <table>
            <thead>
              <tr>
                <th>Startup</th>
                <th>Overall</th>
                {gs.criteria.map((c) => <th key={c.key}>{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {gs.startups.map((s) => (
                <tr key={s.name}>
                  <td><b>{s.name}</b>{s.is_focal ? (mode === "FOUNDER" ? " (your startup)" : " (target)") : ""}</td>
                  <td><b>{s.overall.letter}</b></td>
                  {gs.criteria.map((c) => <td key={c.key}>{s.cells[c.key]?.letter ?? "—"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
            Letter grades computed in code from the reconciled scorecard (never LLM-graded). NR = not rated — metric undisclosed, never punished as F.
            {" "}Rubric: {gs.criteria.map((c) => `${c.label} — ${c.calculation}`).join("; ")}.
          </p>
        </section>
      ) : null}

      {claims.length > 0 && (
        <section className="print-prose page-break">
          <h2>Appendix D — Founder-Call Claim Audit</h2>
          <table>
            <thead>
              <tr><th>Claim (as spoken)</th><th>At</th><th>Verdict</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {claims.map((c, i) => (
                <tr key={i}>
                  <td>
                    <b>{c.claim}</b>
                    {c.quote ? <><br /><i>“{c.quote}”</i></> : null}
                  </td>
                  <td>{c.timestamp || "—"}</td>
                  <td style={{ textTransform: "uppercase", fontWeight: 700,
                               color: c.status === "contradicted" ? "#b91c1c" : c.status === "verified" ? "#15803d" : c.status === "vendor-only" ? "#b45309" : "#55637a" }}>
                    {c.status}
                  </td>
                  <td>
                    {c.evidence || "—"}
                    {c.deck_conflict ? <><br /><b style={{ color: "#b91c1c" }}>Deck conflict:</b> {c.deck_conflict}</> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
            Claims extracted from the uploaded call recording/transcript and cross-examined in the pipeline
            against the public record and the deck. “Verified” requires an independent source; the company&rsquo;s
            own materials count as vendor-only; absence of public evidence is “unsupported”, never “contradicted”.
          </p>
        </section>
      )}

      {(rd || preds.length > 0) && (
        <section className="print-prose page-break">
          <h2>Appendix E — Change vs Baseline Run{report.baseline_created_at ? ` (${report.baseline_created_at.slice(0, 10)})` : ""}</h2>
          {rd && (
            <ul>
              {rd.pick_changed && <li><b>Top pick changed:</b> {rd.prev_pick} → {rd.new_pick}</li>}
              {rd.entered.length > 0 && <li><b>Entered the field:</b> {rd.entered.join(", ")}</li>}
              {rd.exited.length > 0 && <li><b>Left the ranking:</b> {rd.exited.join(", ")}</li>}
              {rd.movers.slice(0, 5).map((m) => (
                <li key={m.startup}>
                  {m.startup}: #{m.prev_rank} → #{m.new_rank}
                  {m.score_delta != null ? ` (${m.score_delta > 0 ? "+" : ""}${m.score_delta} pts)` : ""}
                </li>
              ))}
              {rd.ledger_changes.slice(0, 6).map((c, i) => (
                <li key={`l${i}`}>
                  {c.startup} {c.field === "valuation" ? "valuation" : "raised"}: {musd(c.prev_musd)} → {musd(c.new_musd)}
                </li>
              ))}
              {rd.new_acquisitions.length > 0 && (
                <li><b>New exit precedents:</b> {rd.new_acquisitions.map((a) => `${a.target} ← ${a.acquirer}`).join("; ")}</li>
              )}
              {rd.prev_expected_return != null && rd.new_expected_return != null && (
                <li><b>Expected return (gross midpoint):</b> {rd.prev_expected_return}x → {rd.new_expected_return}x</li>
              )}
            </ul>
          )}
          {preds.length > 0 && (
            <>
              <h3>The baseline report&rsquo;s own dated predictions, graded today</h3>
              <table>
                <thead>
                  <tr><th>Prediction</th><th>Deadline</th><th>Status</th><th>Evidence</th></tr>
                </thead>
                <tbody>
                  {preds.map((p, i) => (
                    <tr key={i}>
                      <td>{p.prediction}</td>
                      <td>{p.deadline || "—"}</td>
                      <td style={{ textTransform: "uppercase", fontWeight: 700,
                                   color: p.status === "broken" ? "#b91c1c" : p.status === "validated" ? "#15803d" : p.status === "unresolved" ? "#b45309" : "#55637a" }}>
                        {p.status}
                      </td>
                      <td>{p.evidence || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: "8.5pt", color: "#55637a" }}>
                Diff computed in code from the two runs&rsquo; structured artifacts; predictions graded against the
                fresh research only. A future deadline is always “pending”; a passed deadline with no evidence
                either way is “unresolved”, never “broken”.
              </p>
            </>
          )}
        </section>
      )}

      {/* Static disclaimer: new reports carry one inside merged_report (code-appended),
          but pre-batch History runs and the demo fixtures do not — the printed PDF is
          the artifact most likely to be forwarded, so the boundary must always print. */}
      <p style={{ marginTop: "1.5rem", fontSize: "9px", color: "#555", borderTop: "1px solid #ccc", paddingTop: "0.5rem" }}>
        Decision-support only — not investment advice. AI-generated from public web sources;
        figures may be incomplete, stale, or wrong. Verify material figures against primary
        sources before acting. Return figures are scenario-derived multiples: gross unless
        explicitly labeled net (net reflects only a coarse stage-banded dilution assumption) —
        all before fees, taxes, and time-value.
      </p>
    </div>
  );
}
