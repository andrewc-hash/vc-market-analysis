"use client";

import { useState, type ReactNode } from "react";
import type { DebateRound, FinalReport } from "@/lib/api";
import { DIMENSION_LABELS } from "@/lib/viz";

// The glass-box audit trail: the analysts' recorded debate, the researcher's
// tool-call receipts, and the deterministic computation paths behind every number.
// All arithmetic shown here is recomputed client-side FROM the report's own data
// and displayed next to the report's stored value so the reader can verify they match.

interface Props {
  report: FinalReport;
}

const Section = ({ kicker, title, children }: { kicker: string; title: string; children: ReactNode }) => (
  <section>
    <div className="kicker">{kicker}</div>
    <h3 className="mt-0.5 font-serif text-lg font-semibold text-gray-100">{title}</h3>
    <div className="mt-3 space-y-3">{children}</div>
  </section>
);

// Shared quiet placeholder — the .empty-state dashed treatment, tightened for in-section use.
const Quiet = ({ children }: { children: ReactNode }) => (
  <div className="empty-state min-h-[88px] py-5">{children}</div>
);

const box = "rounded-md border border-gray-800 bg-gray-900/40 p-3";

const round1 = (v: number) => Math.round(v * 10) / 10;
const round2 = (v: number) => Math.round(v * 100) / 100;
const musd = (v: number | null | undefined): string =>
  v == null ? "—" : v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`;

// ✓ when the client-side recomputation lands on the report's stored value —
// rendered as an evidence badge (emerald chip on match, amber chip on drift).
const Check = ({ ok }: { ok: boolean }) =>
  ok ? (
    <span
      className="inline-flex items-center gap-1 rounded border border-emerald-900/60 bg-emerald-950/40 px-1.5 py-px align-[1px] font-mono text-[10px] font-medium text-emerald-300"
      title="Recomputed here from the report's own inputs — matches the stored value"
    >
      ✓ MATCHES
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1 rounded border border-amber-900/50 bg-amber-950/30 px-1.5 py-px align-[1px] font-mono text-[10px] font-medium text-amber-300"
      title="Recomputed value differs from the stored one — inputs may have been reconciled further in the pipeline"
    >
      ≠ STORED VALUE
    </span>
  );

// ---- 01 · The debate ----------------------------------------------------------

function DebateRoundCard({ r }: { r: DebateRound }) {
  const n = r.disagreements?.length ?? 0;
  return (
    <li className="relative pl-8">
      {/* timeline marker */}
      <span className="absolute left-0 top-0 flex h-5 w-5 items-center justify-center rounded-full border border-gray-700 bg-gray-900 font-mono text-[10px] font-medium tabular-nums text-gray-300">
        {r.round}
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="panel-kicker">Round {r.round}</span>
        <span className="chip">
          {n} disagreement{n === 1 ? "" : "s"}
        </span>
        {r.forced ? (
          <span className="chip-warn">round cap reached — compiled with open disagreements</span>
        ) : r.converged ? (
          <span className="chip text-emerald-300">converged</span>
        ) : (
          <span className="chip">re-argued next round</span>
        )}
      </div>
      {n === 0 && r.converged && (
        <p className="mt-2 text-xs text-gray-500">
          The judge found no material disagreements this round — both analysts read the research the same way.
        </p>
      )}
      {r.disagreements?.map((d, i) => (
        <div key={i} className="mt-3 overflow-hidden rounded-md border border-gray-800">
          <div className="border-b border-gray-800 bg-gray-900/60 px-3 py-2 text-xs font-semibold text-gray-200">
            {d.point}
          </div>
          {/* the A/B confrontation — two columns split by a hairline */}
          <div className="grid divide-y divide-gray-800 sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            <div className="bg-gray-950/60 p-3">
              <div className="panel-kicker">Analyst A</div>
              <p className="mt-1.5 text-xs leading-relaxed text-gray-300">{d.analyst_a}</p>
            </div>
            <div className="bg-gray-950/60 p-3">
              <div className="panel-kicker">Analyst B</div>
              <p className="mt-1.5 text-xs leading-relaxed text-gray-300">{d.analyst_b}</p>
            </div>
          </div>
          {d.reconsider && (
            <div className="border-t border-gray-800 bg-gray-900/40 px-3 py-2 text-[11px] leading-relaxed text-gray-500">
              <span className="mr-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-gray-600">
                Judge → both analysts
              </span>
              <span className="italic">{d.reconsider}</span>
            </div>
          )}
        </div>
      ))}
    </li>
  );
}

function DebateSection({ report }: Props) {
  const log = report.debate_log ?? [];
  if (!log.length) {
    return (
      <Quiet>
        Debate log available on runs after 2026-07-23 — re-run this report to capture it.
        {report.iterations_to_consensus != null && (
          <> This run reached consensus in {report.iterations_to_consensus} round(s); the per-round transcript wasn&rsquo;t recorded.</>
        )}
      </Quiet>
    );
  }
  const immediate = log.length === 1 && log[0].converged && !(log[0].disagreements?.length);
  return (
    <>
      <p className="text-xs text-gray-500">
        Two independent analysts on different model platforms scored the same research; a third-platform judge
        recorded every material disagreement each round. This is that record, verbatim.
      </p>
      {immediate ? (
        <div className={box}>
          <p className="text-xs text-gray-300">
            <span className="mr-1.5 inline-flex align-[1px]"><span className="chip text-emerald-300">Round 1 · converged</span></span>
            <span className="font-semibold">Consensus, zero disagreements.</span>{" "}
            <span className="text-gray-500">
              Both analysts independently reached the same read of the research on the first pass. That is a
              signal of an unambiguous evidence base, not a missing log.
            </span>
          </p>
        </div>
      ) : (
        /* vertical timeline — one node per debate round */
        <ol className="relative ml-2.5 space-y-6 before:absolute before:bottom-1 before:left-[9px] before:top-1 before:w-px before:bg-gray-800">
          {log.map((r) => (
            <DebateRoundCard key={r.round} r={r} />
          ))}
        </ol>
      )}
    </>
  );
}

// ---- 02 · Research receipts ---------------------------------------------------

function ReceiptsSection({ report }: Props) {
  const [showCalls, setShowCalls] = useState(false);
  const m = report.research_manifest;
  const fresh = report.data_freshness;
  if (!m && !fresh) return <Quiet>No research manifest was recorded for this run.</Quiet>;

  const byTool = Object.entries(m?.by_tool ?? {}).sort((a, b) => b[1] - a[1]);
  const calls = m?.calls ?? [];

  // Instrument cells: the headline counters, then one cell per tool. Padded with
  // blank cells so the hairline-seam grid's last row stays filled (visual only).
  const cells: { value: string; caption: string; tone?: string }[] = m
    ? [
        { value: String(m.total), caption: "Tool calls" },
        { value: String(m.failed), caption: "Failed", tone: m.failed ? "text-amber-300" : undefined },
        ...(m.urls_in_brief != null && m.urls_in_brief > 0
          ? [{ value: String(m.urls_in_brief), caption: "Source URLs harvested" }]
          : []),
        ...byTool.map(([tool, count]) => ({ value: String(count), caption: tool })),
      ]
    : [];
  const pad = cells.length % 4 === 0 ? 0 : 4 - (cells.length % 4);

  return (
    <>
      {m && (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60 sm:grid-cols-4">
            {cells.map((c) => (
              <div key={c.caption} className="stat-cell">
                <div className={`stat-value ${c.tone ?? ""}`}>{c.value}</div>
                <div className="stat-caption break-words tracking-[0.08em]">{c.caption}</div>
              </div>
            ))}
            {Array.from({ length: pad }).map((_, i) => (
              <div
                key={`pad-${i}`}
                className={`stat-cell sm:block ${i === 0 && cells.length % 2 === 1 ? "" : "hidden"}`}
                aria-hidden
              />
            ))}
          </div>
          {calls.length > 0 && (
            <div className={box}>
              <button
                onClick={() => setShowCalls((s) => !s)}
                className="font-mono text-[11px] text-brand-300 hover:text-brand-200"
              >
                {showCalls ? "Hide" : "Show"} all {calls.length} recorded queries
              </button>
              {showCalls && (
                <ol className="mt-2 max-h-72 space-y-1 overflow-y-auto border-t border-gray-800/70 pt-2">
                  {calls.map((c, i) => (
                    <li key={i} className="flex gap-2 font-mono text-[11px]">
                      <span className="shrink-0 text-gray-600">{c.tool}</span>
                      <span className="text-gray-400">{Object.values(c.args ?? {}).join(" · ")}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </>
      )}
      {fresh && (
        <div className={box}>
          <div className="panel-kicker">Evidence freshness (audited in code)</div>
          <div className="mt-1.5 flex flex-wrap gap-x-6 gap-y-1 text-xs tabular-nums text-gray-300">
            {fresh.report_date && <span>Report date <span className="text-gray-100">{fresh.report_date}</span></span>}
            {fresh.newest_dated_mention && <span>Newest dated mention <span className="text-gray-100">{fresh.newest_dated_mention}</span></span>}
            {fresh.oldest_dated_mention && <span>Oldest <span className="text-gray-100">{fresh.oldest_dated_mention}</span></span>}
            {fresh.dated_mentions != null && <span className="text-gray-500">{fresh.dated_mentions} dated mentions in the memo</span>}
          </div>
        </div>
      )}
    </>
  );
}

// ---- 03 · How the numbers are computed ---------------------------------------

function WeightingWorkedExample({ report }: Props) {
  const weights = report.applied_weights;
  const weighted = report.weighted_scores ?? {};
  const name = (report.ranking ?? []).find((n) => weighted[n]);
  if (!weights || !name) {
    return <Quiet>No weighted scorecard was computed for this run{report.weighting_unavailable ? " (the analysts' scores could not be reconciled)" : ""}.</Quiet>;
  }
  const row = weighted[name];
  // Mirror the backend exactly: Σ weight×score over the scored dimensions,
  // renormalized over the weights of the dimensions actually present.
  let wsum = 0;
  let present = 0;
  const terms = DIMENSION_LABELS.map(({ key, short }) => {
    const v = row[key];
    const w = weights[key] ?? 0;
    if (typeof v === "number") {
      wsum += w * v;
      present += w;
    }
    return { key, short, v: typeof v === "number" ? v : null, w };
  });
  const computed = present > 0 ? round1(wsum / present) : null;
  const partial = present > 0 && Math.abs(present - 1) > 0.001;

  return (
    <div className={box}>
      <div className="panel-kicker">
        Weighted index — worked example · {name} (ranked #1)
      </div>
      <table className="mt-2 w-full max-w-md text-[11px] tabular-nums">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="th-label py-1 text-left">Dimension</th>
            <th className="th-label py-1 text-right">Score</th>
            <th className="th-label py-1 text-right">× Weight</th>
            <th className="th-label py-1 text-right">= Contribution</th>
          </tr>
        </thead>
        <tbody>
          {terms.map((t) => (
            <tr key={t.key} className="border-b border-gray-900 last:border-0">
              <td className="py-1 text-gray-400">{t.short}</td>
              <td className="py-1 text-right text-gray-300">{t.v ?? "—"}</td>
              <td className="py-1 text-right text-gray-400">{Math.round(t.w * 100)}%</td>
              <td className="py-1 text-right text-gray-300">{t.v != null ? (t.w * t.v).toFixed(1) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {computed != null && (
        <p className="mt-2 text-[11px] tabular-nums text-gray-400">
          Σ contributions {round2(wsum)}
          {partial ? ` ÷ ${round2(present)} (weights of the scored dimensions — unscored ones are renormalized away)` : ""} ={" "}
          <span className="font-semibold text-gray-100">{computed}</span>{" "}
          <Check ok={row.weighted_score != null && Math.abs(computed - row.weighted_score) < 0.06} />
          <span className="text-gray-600"> — the Scores tab shows {row.weighted_score ?? "—"}.</span>
        </p>
      )}
      <p className="mt-1 text-[11px] text-gray-600">
        The analysts emit raw 0–100 scores per dimension; your slider weights are normalized and applied in code —
        the ranking is this arithmetic, nothing else.
      </p>
    </div>
  );
}

function ExpectedReturnWorkedExample({ report }: Props) {
  const sc = report.scenarios;
  const rows = sc?.scenarios?.filter((s) => s.multiple_low != null || s.multiple_high != null) ?? [];
  if (!rows.length) return <Quiet>No return scenarios were modelled for this run.</Quiet>;

  const psum = rows.reduce((a, s) => a + (s.probability || 0), 0);
  if (psum <= 0) return <Quiet>No return scenarios were modelled for this run.</Quiet>;
  const terms = rows.map((s) => {
    const mids = [s.multiple_low, s.multiple_high].filter((m): m is number => typeof m === "number");
    const mid = mids.reduce((a, b) => a + b, 0) / mids.length;
    return { s, mid, term: ((s.probability || 0) / psum) * mid };
  });
  const ev = round2(terms.reduce((a, t) => a + t.term, 0));
  const stored = report.expected_return ?? sc?.expected_return ?? null;
  const retention = report.return_assumptions?.retention;

  return (
    <div className={box}>
      <div className="panel-kicker">
        Expected return — worked arithmetic{sc?.startup ? ` · ${sc.startup}` : ""}
      </div>
      <table className="mt-2 w-full text-[11px] tabular-nums">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="th-label py-1 text-left">Scenario</th>
            {rows.some((s) => s.path) && <th className="th-label py-1 text-left">Path</th>}
            <th className="th-label py-1 text-right">Probability</th>
            <th className="th-label py-1 text-right">Multiple</th>
            <th className="th-label py-1 text-right">Midpoint</th>
          </tr>
        </thead>
        <tbody>
          {terms.map(({ s, mid }, i) => (
            <tr key={i} className="border-b border-gray-900 last:border-0">
              <td className="py-1 capitalize text-gray-400">{s.label}</td>
              {rows.some((x) => x.path) && (
                <td className="max-w-[220px] truncate py-1 pr-2 text-gray-500" title={s.path || ""}>{s.path || "—"}</td>
              )}
              <td className="py-1 text-right text-gray-300">{Math.round((s.probability || 0) * 100)}%</td>
              <td className="py-1 text-right text-gray-300">
                {s.multiple_low === s.multiple_high ? `${s.multiple_low}x` : `${s.multiple_low ?? "?"}x–${s.multiple_high ?? "?"}x`}
              </td>
              <td className="py-1 text-right text-gray-300">{round2(mid)}x</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] tabular-nums text-gray-400">
        {terms.map((t, i) => (
          <span key={i}>
            {i > 0 && " + "}
            {round2((t.s.probability || 0) / psum)}×{round2(t.mid)}
          </span>
        ))}{" "}
        = <span className="font-semibold text-gray-100">{ev}x</span> gross{" "}
        {stored != null && <Check ok={Math.abs(ev - stored) < 0.006} />}
        {stored != null && <span className="text-gray-600"> — the report states {stored}x.</span>}
      </p>
      {Math.abs(psum - 1) > 0.001 && (
        <p className="mt-1 text-[11px] text-gray-600">
          Stated probabilities sum to {Math.round(psum * 100)}% — renormalized in code before weighting.
        </p>
      )}
      {report.expected_return_low != null && report.expected_return_high != null && (
        <p className="mt-1 text-[11px] tabular-nums text-gray-500">
          Same arithmetic over the low / high multiple bounds gives the honest range:{" "}
          <span className="text-gray-300">{report.expected_return_low}x–{report.expected_return_high}x</span> gross.
        </p>
      )}
      {report.expected_return_net_low != null && report.expected_return_net_high != null && retention != null && (
        <p className="mt-1 text-[11px] tabular-nums text-gray-500">
          × {Math.round(retention * 100)}% stage-banded ownership retention to exit →{" "}
          <span className="text-gray-300">{report.expected_return_net_low}x–{report.expected_return_net_high}x</span> net of estimated
          future dilution{report.return_assumptions?.note ? ` (${report.return_assumptions.note})` : ""}.
        </p>
      )}
    </div>
  );
}

function FundMathSummary({ report }: Props) {
  const fm = report.fund_math;
  if (!fm) return null;
  const a = fm.assumptions;
  const ownershipLine =
    a.check_size_musd != null && a.entry_post_money_musd != null && a.entry_ownership_pct != null;
  return (
    <div className={box}>
      <div className="panel-kicker">Fund math — the deterministic chain</div>
      <div className="mt-2 space-y-1 text-[11px] tabular-nums text-gray-400">
        {ownershipLine && (
          <p>
            Check {musd(a.check_size_musd)} ÷ entry post-money {musd(a.entry_post_money_musd)} ={" "}
            <span className="text-gray-200">{a.entry_ownership_pct}%</span> entry ownership
            {a.ownership_at_exit_pct != null && (
              <> · × {a.retention} retention → <span className="text-gray-200">{a.ownership_at_exit_pct}%</span> at exit</>
            )}
          </p>
        )}
        {fm.requirements.required_exit_value_musd != null && a.ownership_at_exit_pct != null && (
          <p>
            To return the {musd(a.fund_size_musd)} fund at {a.ownership_at_exit_pct}% exit ownership, the company must
            exit at <span className="text-gray-200">{musd(fm.requirements.required_exit_value_musd)}</span>
            {" "}(fund ÷ ownership-at-exit, computed in code).
          </p>
        )}
        {fm.expected && (
          <p>
            Probability-weighted across the scenarios: expected net{" "}
            <span className="text-gray-200">{fm.expected.expected_net_MoIC}x</span> MoIC ·{" "}
            <span className="text-gray-200">{fm.expected.expected_net_turns}</span> turns of the fund
            {fm.expected.expected_net_irr_pct != null && <> · ≈{fm.expected.expected_net_irr_pct}% net IRR</>}
          </p>
        )}
        <p>
          Verdicts:{" "}
          <span className={fm.verdicts.can_return_fund ? "text-green-300" : "text-gray-300"}>
            {fm.verdicts.can_return_fund ? "can return the fund in the best case" : "cannot return the fund even in the best case"}
          </span>
          {" · "}
          <span className={fm.verdicts.is_fund_maker ? "text-green-300" : "text-gray-300"}>
            {fm.verdicts.is_fund_maker ? "fund-maker on expected value" : "not a fund-maker on expected value"}
          </span>
        </p>
      </div>
      <p className="mt-2 text-[11px] text-gray-600">
        Pure functions over your fund profile — every figure above is check → ownership → dilution → proceeds
        arithmetic; the model never asserts a fund number. Full detail in the Financials tab.
      </p>
    </div>
  );
}

// ---- 04 · Standing guarantees -------------------------------------------------

const GUARANTEES: { rule: string; detail: string }[] = [
  { rule: "Incumbents are never scored or ranked", detail: "code drops any incumbent from the scorecard and ranking; they render as reference points only." },
  { rule: "Defensibility = the mean of the four a16z moat sub-scores", detail: "so the headline Defensibility score can never disagree with the sub-scores shown next to it." },
  { rule: "Pre-PMF startups are excluded from the ranking", detail: "watchlist-only, never underwritten; a focal startup you attach is exempt." },
  { rule: "Expected return is computed in code from the scenario table", detail: "Σ probability × midpoint — the exact figure is fed to the writer, never asserted by it." },
  { rule: "Val/ARR multiples are derived, not asserted", detail: "valuation ÷ ARR computed in code for every ledger row." },
  { rule: "NaN and infinite values are rejected", detail: "finite guards on every parsed number; missing data renders as Not Disclosed, never a fabricated figure." },
];

// ---- assembled tab ------------------------------------------------------------

export default function AuditTrail({ report }: Props) {
  return (
    <div className="space-y-8">
      <Section kicker="01 · The debate" title="What the analysts fought about">
        <DebateSection report={report} />
      </Section>

      <Section kicker="02 · Research receipts" title="Every search the researcher ran">
        <ReceiptsSection report={report} />
      </Section>

      <Section kicker="03 · Computation paths" title="How the numbers are computed">
        <p className="text-xs text-gray-500">
          Anything arithmetic is done in code, not by a model. The worked examples below are recomputed in your
          browser from the report&rsquo;s own inputs, next to the stored result — so you can check the math yourself.
        </p>
        <WeightingWorkedExample report={report} />
        <ExpectedReturnWorkedExample report={report} />
        <FundMathSummary report={report} />
      </Section>

      <Section kicker="04 · Standing guarantees" title="Enforced in code on every run">
        <ul className="grid gap-x-8 gap-y-2.5 sm:grid-cols-2">
          {GUARANTEES.map((g) => (
            <li key={g.rule} className="flex gap-2 text-xs text-gray-400">
              <span className="mt-px shrink-0 font-mono text-emerald-400" aria-hidden>✓</span>
              <span>
                <span className="font-semibold text-gray-200">{g.rule}</span>
                <span className="text-gray-500"> — {g.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
