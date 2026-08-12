"use client";

// Tracked — the longitudinal watchlist ("the watchlist that re-underwrites itself").
// Builds re-run CHAINS from the light history list: a baseline report + every re-run
// that points at it via baseline_report_id (re-runs of re-runs fold into the root
// chain). For each chain the LATEST re-run's full report is fetched once to render a
// compact code-computed delta summary: pick change, expected-return move, field
// churn, and how the baseline's own dated predictions graded.

import { useEffect, useState } from "react";
import {
  getReport,
  listReports,
  rerunReport,
  type FinalReport,
  type PredictionRow,
  type ReportSummary,
} from "@/lib/api";
import { Icon } from "./icons";
import { useToast } from "./Toaster";

interface Props {
  onSelect: (id: string) => void; // open a report in the viewer (same flow as Home)
  onRerun?: (taskId: string) => void; // parent starts polling the new task
}

interface Chain {
  rootId: string;
  baseline: ReportSummary | null; // null = baseline record was deleted
  reruns: ReportSummary[]; // oldest → newest
}

/** Group the flat history list into baseline→re-runs chains. A re-run's
 * baseline_report_id is walked up to the ROOT baseline so re-running a re-run
 * extends the original chain instead of forking a new one. */
function buildChains(items: ReportSummary[]): Chain[] {
  const byId = new Map(items.map((r) => [r.id, r]));
  const rootOf = (r: ReportSummary): string => {
    let cur = r;
    const seen = new Set<string>([cur.id]);
    while (cur.baseline_report_id) {
      const parent = byId.get(cur.baseline_report_id);
      if (!parent || seen.has(parent.id)) return cur.baseline_report_id;
      seen.add(parent.id);
      cur = parent;
    }
    return cur.id;
  };
  const chains = new Map<string, Chain>();
  for (const r of items) {
    if (!r.baseline_report_id) continue;
    const rootId = rootOf(r);
    if (rootId === r.id) continue; // degenerate self-reference
    let c = chains.get(rootId);
    if (!c) {
      c = { rootId, baseline: byId.get(rootId) ?? null, reruns: [] };
      chains.set(rootId, c);
    }
    c.reruns.push(r);
  }
  const out = Array.from(chains.values());
  for (const c of out) c.reruns.sort((a, b) => a.created_at.localeCompare(b.created_at));
  // Most recently re-underwritten chain first.
  out.sort((a, b) =>
    (b.reruns[b.reruns.length - 1]?.created_at ?? "").localeCompare(
      a.reruns[a.reruns.length - 1]?.created_at ?? ""
    )
  );
  return out;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}

function fmtX(v: number | null | undefined): string {
  return v == null ? "—" : `${v}x`;
}

/** "5 predictions: 4 pending · 1 unresolved" — tallied from the graded audit rows. */
function predictionTally(preds: PredictionRow[]): string {
  const counts = new Map<string, number>();
  for (const p of preds) counts.set(p.status, (counts.get(p.status) ?? 0) + 1);
  const order: PredictionRow["status"][] = ["validated", "broken", "pending", "unresolved"];
  const parts = order.filter((s) => counts.has(s)).map((s) => `${counts.get(s)} ${s}`);
  return `${preds.length} prediction${preds.length === 1 ? "" : "s"}: ${parts.join(" · ")}`;
}

function DeltaCell({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2">
      <div className="font-mono text-[9px] font-medium uppercase tracking-[0.16em] text-gray-600">{label}</div>
      <div className={`mt-0.5 text-xs font-medium tabular-nums ${accent ? "text-amber-300" : "text-gray-200"}`}>
        {value}
      </div>
    </div>
  );
}

function ChainCard({
  chain,
  onSelect,
  onRerunChain,
  rerunning,
}: {
  chain: Chain;
  onSelect: (id: string) => void;
  onRerunChain: (id: string) => void;
  rerunning: boolean;
}) {
  const latest = chain.reruns[chain.reruns.length - 1];
  // Full report for the LATEST re-run only — the light list never carries the delta.
  const [fr, setFr] = useState<FinalReport | "error" | null>(null);
  useEffect(() => {
    let alive = true;
    getReport(latest.id)
      .then((rec) => alive && setFr(rec.final_report ?? "error"))
      .catch(() => alive && setFr("error"));
    return () => {
      alive = false;
    };
  }, [latest.id]);

  const meta = chain.baseline ?? latest;
  const title = meta.label || meta.sector || "Untitled analysis";
  const d = fr && fr !== "error" ? fr.run_delta : null;
  const preds = fr && fr !== "error" ? (fr.prediction_audit ?? []) : [];

  return (
    <div className="card space-y-3">
      {/* Header: chain identity + actions */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-gray-100">{title}</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
            <span
              className={`rounded-sm px-1 font-mono text-[9px] font-medium uppercase tracking-[0.12em] ${
                meta.analysis_mode === "founder"
                  ? "bg-brand-500/15 text-brand-300"
                  : "border border-gray-700 text-gray-400"
              }`}
            >
              {meta.analysis_mode === "founder" ? "Founder" : "VC"}
            </span>
            {meta.focal_startup && (
              <span className="inline-flex max-w-[11rem] items-center gap-1 truncate">
                <Icon name="target" className="h-3 w-3 shrink-0 text-gray-600" />
                {meta.focal_startup}
              </span>
            )}
            {meta.sector && meta.label && <span className="max-w-[16rem] truncate">· {meta.sector}</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => onRerunChain(chain.rootId)}
            disabled={rerunning || !chain.baseline}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-700 px-2.5 py-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-gray-400 transition-colors hover:border-gray-600 hover:text-brand-300 disabled:cursor-not-allowed disabled:opacity-40"
            title={
              chain.baseline
                ? "Re-run on the baseline's original inputs — extends this chain and re-grades its predictions"
                : "Baseline record was deleted — re-run unavailable"
            }
          >
            <Icon name="refresh" className={`h-3 w-3 ${rerunning ? "animate-spin" : ""}`} />
            Re-run
          </button>
          <button
            onClick={() => onSelect(latest.id)}
            className="inline-flex items-center gap-1.5 rounded-md bg-brand-600/15 px-2.5 py-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-brand-300 transition-colors hover:bg-brand-600/25"
            title="Open the latest re-run in the report viewer"
          >
            Open latest
            <Icon name="arrow-right" className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* Run timeline: baseline → each re-run */}
      <div className="flex flex-wrap items-center gap-1.5 border-t border-gray-800/70 pt-3 font-mono text-[10px] tabular-nums">
        {chain.baseline ? (
          <button
            onClick={() => onSelect(chain.rootId)}
            className="rounded-md border border-gray-700 px-2 py-1 text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
            title="Open the baseline report"
          >
            Baseline · {fmtDate(chain.baseline.created_at)}
          </button>
        ) : (
          <span className="rounded-md border border-dashed border-gray-800 px-2 py-1 text-gray-600" title="Baseline record was deleted">
            Baseline · deleted
          </span>
        )}
        {chain.reruns.map((r, i) => (
          <span key={r.id} className="inline-flex items-center gap-1.5">
            <Icon name="arrow-right" className="h-3 w-3 text-gray-700" />
            <button
              onClick={() => onSelect(r.id)}
              className={`rounded-md border px-2 py-1 transition-colors ${
                i === chain.reruns.length - 1
                  ? "border-brand-500/40 bg-brand-600/10 text-brand-300 hover:bg-brand-600/20"
                  : "border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-200"
              }`}
              title={`Open re-run of ${fmtDate(r.created_at)}`}
            >
              Re-run · {fmtDate(r.created_at)}
            </button>
          </span>
        ))}
      </div>

      {/* Latest-delta summary — everything below is computed in code by the worker */}
      {fr === null && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2">
              <div className="skeleton h-2.5 w-16" />
              <div className="skeleton mt-1.5 h-3.5 w-20" />
            </div>
          ))}
        </div>
      )}
      {fr === "error" && <p className="text-xs text-gray-600">Couldn&rsquo;t load the latest re-run&rsquo;s delta.</p>}
      {fr !== null && fr !== "error" && !d && (
        <p className="text-xs text-gray-600">No baseline diff on the latest re-run.</p>
      )}
      {d && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <DeltaCell
            label="Top pick"
            value={d.pick_changed ? `${d.prev_pick || "—"} → ${d.new_pick || "—"}` : `Pick held — ${d.new_pick || d.prev_pick || "—"}`}
            accent={d.pick_changed}
          />
          <DeltaCell
            label="Expected return"
            value={
              d.prev_expected_return == null && d.new_expected_return == null
                ? "—"
                : `${fmtX(d.prev_expected_return)} → ${fmtX(d.new_expected_return)}`
            }
          />
          <DeltaCell
            label="Field churn"
            value={`+${d.entered.length} entered · −${d.exited.length} exited`}
          />
          <DeltaCell label="Rank movers" value={`${d.movers.length} mover${d.movers.length === 1 ? "" : "s"}`} />
        </div>
      )}
      {preds.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Icon name="check" className="h-3.5 w-3.5 shrink-0 text-gray-600" />
          <span className="tabular-nums">{predictionTally(preds)}</span>
          <span className="text-gray-600">— the baseline&rsquo;s own dated calls, graded against fresh evidence</span>
        </div>
      )}
    </div>
  );
}

export default function TrackedList({ onSelect, onRerun }: Props) {
  const [items, setItems] = useState<ReportSummary[] | null>(null); // null = loading
  const [rerunning, setRerunning] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    let alive = true;
    listReports()
      .then((r) => alive && setItems(r))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, []);

  // Re-run the chain's BASELINE (not the latest re-run) so the new run keeps grading
  // the ORIGINAL report's predictions and joins the same chain. Mirrors HistoryList's
  // rerun flow — kept as a small local copy since the two rows differ in shape.
  const rerunChain = async (baselineId: string) => {
    if (rerunning) return;
    setRerunning(baselineId);
    try {
      const { task_id } = await rerunReport(baselineId);
      toast("Re-run started — the chain extends when it finishes", "success");
      onRerun?.(task_id);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Re-run failed", "error");
    } finally {
      setRerunning(null);
    }
  };

  const chains = items ? buildChains(items) : [];

  return (
    <section className="space-y-3">
      {/* First load — a shape-matched shimmer chain card (header / timeline / delta cells) */}
      {items === null && (
        <div className="card space-y-3" aria-hidden>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="skeleton h-4 w-52" />
              <div className="skeleton mt-2 h-3 w-32" />
            </div>
            <div className="flex shrink-0 gap-2">
              <div className="skeleton h-7 w-20 rounded-md" />
              <div className="skeleton h-7 w-24 rounded-md" />
            </div>
          </div>
          <div className="flex items-center gap-1.5 border-t border-gray-800/70 pt-3">
            <div className="skeleton h-6 w-28 rounded-md" />
            <div className="skeleton h-6 w-28 rounded-md" />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2">
                <div className="skeleton h-2.5 w-16" />
                <div className="skeleton mt-1.5 h-3.5 w-20" />
              </div>
            ))}
          </div>
        </div>
      )}

      {items !== null && chains.length === 0 && (
        <div className="card max-w-3xl">
          <div className="flex items-start gap-3">
            <Icon name="history" className="mt-0.5 h-5 w-5 shrink-0 text-gray-600" />
            <div>
              <h2 className="text-sm font-semibold text-gray-100">Nothing tracked yet</h2>
              <p className="mt-1.5 text-xs leading-relaxed text-gray-500">
                Tracked is the watchlist that re-underwrites itself. Re-run any saved analysis and
                Prospectus re-executes it on the original inputs, diffs the field in code — who
                entered, who left, rank and valuation moves, pick and expected-return changes —
                and grades the original report&rsquo;s own dated predictions against fresh evidence.
              </p>
              <p className="mt-2 text-xs text-gray-400">
                Re-run any analysis from Home (↻) to start tracking it.
              </p>
            </div>
          </div>
        </div>
      )}

      {chains.map((c) => (
        <ChainCard
          key={c.rootId}
          chain={c}
          onSelect={onSelect}
          onRerunChain={rerunChain}
          rerunning={rerunning === c.rootId}
        />
      ))}
    </section>
  );
}
