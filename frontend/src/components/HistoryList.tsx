"use client";

// The workspace History, rendered INLINE (Home's "Recent analyses" table).
// This replaces the old HistoryDrawer as the single browse surface for past runs —
// same store, same mutations (star / rename / re-run / delete), but actions are
// always visible (not hover-only) and rows read like an operator console table.

import { useEffect, useState } from "react";
import { listReports, updateReport, deleteReport, rerunReport, type ReportSummary } from "@/lib/api";
import { norm, nameMatch } from "@/lib/pickLabel";
import { Icon } from "./icons";
import { useToast } from "./Toaster";
import ConfirmDialog from "./ConfirmDialog";

// ── Filter pills — live counts over the UNFILTERED list, AND-combined with search ──

type Filter = "all" | "vc" | "founder" | "rerun" | "starred";

const FILTERS: { key: Filter; label: string; match: (r: ReportSummary) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  // "VC" mirrors the row badge: anything not explicitly founder-mode reads as VC.
  { key: "vc", label: "VC", match: (r) => r.analysis_mode !== "founder" },
  { key: "founder", label: "Founder", match: (r) => r.analysis_mode === "founder" },
  { key: "rerun", label: "Re-runs", match: (r) => !!r.baseline_report_id },
  { key: "starred", label: "★", match: (r) => r.starred },
];

interface Props {
  onSelect: (id: string) => void;
  // Re-run a past analysis on its original inputs; parent starts polling the new task.
  onRerun?: (taskId: string) => void;
  refreshKey?: number; // bump to force a reload (e.g., a run just completed)
  onMutated?: () => void; // star/rename/delete changed the store — parent can refresh stats
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function HistoryList({ onSelect, onRerun, refreshKey, onMutated }: Props) {
  const [items, setItems] = useState<ReportSummary[] | null>(null); // null = first load pending
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [rerunning, setRerunning] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ReportSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const toast = useToast();

  const load = async () => {
    try {
      setItems(await listReports());
    } catch {
      setItems([]); // backend down → calm empty state, not a spinner forever
    }
  };

  useEffect(() => {
    let alive = true;
    listReports()
      .then((r) => alive && setItems(r))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, [refreshKey]);

  const rerun = async (r: ReportSummary) => {
    if (rerunning) return;
    setRerunning(r.id);
    try {
      const { task_id } = await rerunReport(r.id);
      toast("Re-run started — it will diff against this report when done", "success");
      onRerun?.(task_id);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Re-run failed", "error");
    } finally {
      setRerunning(null);
    }
  };

  // Mutations no longer swallow failures — every path surfaces a toast.
  const toggleStar = async (r: ReportSummary) => {
    try {
      await updateReport(r.id, { starred: !r.starred });
      toast(r.starred ? "Star removed" : "Starred", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn't update the star", "error");
    }
    await load();
    onMutated?.();
  };
  const saveLabel = async (r: ReportSummary) => {
    try {
      await updateReport(r.id, { label: editVal });
      toast("Renamed", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Rename failed", "error");
    }
    setEditing(null);
    await load();
    onMutated?.();
  };
  const remove = async (r: ReportSummary) => {
    setDeleting(true);
    try {
      await deleteReport(r.id);
      toast("Report deleted", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
    setDeleting(false);
    setConfirmDelete(null);
    await load();
    onMutated?.();
  };

  const all = items ?? [];
  const activeFilter = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
  const filtered = all.filter((r) => {
    if (!activeFilter.match(r)) return false;
    if (!q.trim()) return true;
    const hay = `${r.label} ${r.sector} ${r.focal_startup} ${r.top_pick} ${r.analysis_mode}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  return (
    <section>
      {/* Heading + search */}
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="kicker">Workspace · History</div>
          <h2 className="mt-0.5 text-base font-semibold text-gray-100">
            Recent analyses
            {all.length > 0 && (
              <span className="ml-2 text-xs font-normal tabular-nums text-gray-500">{all.length}</span>
            )}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Filter pills — counts always tally the UNFILTERED list; AND with search. */}
          <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Filter analyses">
            {FILTERS.map((f) => {
              const count = all.filter(f.match).length;
              return (
                <button
                  key={f.key}
                  onClick={() => setFilter(f.key)}
                  className={`${filter === f.key ? "chip-accent" : "chip hover:border-gray-700 hover:text-gray-200"} transition-colors`}
                  aria-pressed={filter === f.key}
                  title={f.key === "starred" ? "Starred reports" : undefined}
                >
                  {f.label}
                  <span className={`tabular-nums ${filter === f.key ? "text-brand-300/70" : "text-gray-600"}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search analyses…"
            className="input-field h-9 w-full text-sm sm:w-56"
            aria-label="Search analyses"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-800 bg-gray-900/40">
        {/* Column header (md+) */}
        <div className="hidden items-center gap-3 border-b border-gray-800 bg-gray-900/80 px-4 py-2 font-mono text-[9px] font-medium uppercase tracking-[0.18em] text-gray-600 md:flex">
          <span className="w-4 shrink-0" aria-hidden />
          <span className="flex-1">Analysis</span>
          <span className="w-40 shrink-0">Top pick</span>
          <span className="w-14 shrink-0 text-right">Date</span>
          <span className="w-[5.25rem] shrink-0 text-right">Actions</span>
        </div>

        {/* First load — shape-matched shimmer rows (star / title+meta / pick / date / actions) */}
        {items === null && (
          <div className="divide-y divide-gray-800/70" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                <div className="skeleton h-3.5 w-3.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="skeleton h-3.5" style={{ width: `${52 - i * 7}%` }} />
                  <div className="skeleton mt-1.5 h-3 w-32" />
                </div>
                <div className="hidden w-40 shrink-0 md:block">
                  <div className="skeleton h-3 w-24" />
                </div>
                <div className="hidden w-14 shrink-0 md:flex md:justify-end">
                  <div className="skeleton h-3 w-10" />
                </div>
                <div className="flex w-[5.25rem] shrink-0 justify-end">
                  <div className="skeleton h-3.5 w-16" />
                </div>
              </div>
            ))}
          </div>
        )}

        {items !== null && filtered.length === 0 && (
          <div className="px-4 py-8 text-center text-xs text-gray-500">
            {all.length === 0 ? (
              <>
                <p className="text-[13px] font-medium text-gray-400">No analyses yet</p>
                <p className="mt-1">Start one above — finished runs are saved here automatically.</p>
                <a href="/demo" className="mt-3 inline-block text-brand-300 hover:text-brand-200">
                  Browse example reports →
                </a>
              </>
            ) : (
              `No matches${filter !== "all" ? " in this filter" : ""}.`
            )}
          </div>
        )}

        <div className="divide-y divide-gray-800/70">
          {filtered.map((r) => {
            // Suppress the pick when it just repeats the focal (VC+focal mode stores the
            // evaluated target as top_pick) — showing it as "Top pick" wrongly implies a
            // recommendation (R11).
            const pick =
              r.top_pick && !(r.focal_startup && nameMatch(norm(r.top_pick), norm(r.focal_startup)))
                ? r.top_pick
                : "";
            return (
              <div key={r.id} className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-gray-900/70">
                <button
                  onClick={() => toggleStar(r)}
                  className={`w-4 shrink-0 ${r.starred ? "text-amber-400" : "text-gray-600 hover:text-gray-400"}`}
                  title={r.starred ? "Unstar" : "Star"}
                  aria-label={r.starred ? "Unstar" : "Star"}
                >
                  <Icon name="star" className="h-3.5 w-3.5" filled={r.starred} />
                </button>

                <button onClick={() => onSelect(r.id)} className="min-w-0 flex-1 text-left">
                  {editing === r.id ? (
                    <input
                      autoFocus
                      value={editVal}
                      onChange={(e) => setEditVal(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveLabel(r);
                        if (e.key === "Escape") setEditing(null);
                      }}
                      onBlur={() => saveLabel(r)}
                      className="w-full rounded bg-gray-800 px-1 py-0.5 text-sm text-gray-100 outline-none ring-1 ring-brand-500/50"
                    />
                  ) : (
                    <div className="truncate text-[13px] font-medium text-gray-200">
                      {r.label || r.sector || "Untitled analysis"}
                    </div>
                  )}
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
                    <span
                      className={`rounded-sm px-1 font-mono text-[9px] font-medium uppercase tracking-[0.12em] ${
                        r.analysis_mode === "founder"
                          ? "bg-brand-500/15 text-brand-300"
                          : "border border-gray-700 text-gray-400"
                      }`}
                    >
                      {r.analysis_mode === "founder" ? "Founder" : "VC"}
                    </span>
                    {/* Longitudinal marker — this record is a re-run of a baseline (see Tracked) */}
                    {r.baseline_report_id && (
                      <span className="rounded-sm border border-gray-700 px-1 font-mono text-[9px] font-medium uppercase tracking-[0.12em] text-gray-400">
                        Rerun
                      </span>
                    )}
                    {r.focal_startup && (
                      <span className="inline-flex max-w-[9rem] items-center gap-1 truncate">
                        <Icon name="target" className="h-3 w-3 shrink-0 text-gray-600" />
                        {r.focal_startup}
                      </span>
                    )}
                    {/* On <md the pick + date collapse into the meta line */}
                    {pick && <span className="max-w-[8rem] truncate md:hidden">· {pick}</span>}
                    <span className="tabular-nums md:hidden">· {fmtDate(r.created_at)}</span>
                  </div>
                </button>

                <div className="hidden w-40 shrink-0 md:block">
                  {pick ? (
                    <span className="block truncate text-[12px] text-gray-300">{pick}</span>
                  ) : (
                    <span className="text-[12px] text-gray-700">—</span>
                  )}
                </div>
                <div className="hidden w-14 shrink-0 text-right text-[11px] tabular-nums text-gray-500 md:block">
                  {fmtDate(r.created_at)}
                </div>

                {/* Row actions — deliberately always visible (hover-only was a real complaint) */}
                <div className="flex w-[5.25rem] shrink-0 items-center justify-end gap-1 text-gray-500">
                  {onRerun && (
                    <button
                      onClick={() => rerun(r)}
                      disabled={!!rerunning}
                      className="rounded p-1 hover:bg-gray-800 hover:text-brand-300 disabled:opacity-40"
                      title="Re-run on the same inputs — diffs against this report and grades its predictions"
                    >
                      <Icon name="refresh" className={`h-3.5 w-3.5 ${rerunning === r.id ? "animate-spin" : ""}`} />
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setEditing(r.id);
                      setEditVal(r.label || r.sector || "");
                    }}
                    className="rounded p-1 hover:bg-gray-800 hover:text-gray-300"
                    title="Rename"
                  >
                    <Icon name="pencil" className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setConfirmDelete(r)}
                    className="rounded p-1 hover:bg-gray-800 hover:text-rose-400"
                    title="Delete"
                  >
                    <Icon name="trash" className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Themed replacement for the old window.confirm() delete guard */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete this analysis?"
        body={
          <>
            <span className="font-medium text-gray-300">
              {confirmDelete ? confirmDelete.label || confirmDelete.sector || "Untitled analysis" : ""}
            </span>{" "}
            will be removed from History. This can&rsquo;t be undone.
          </>
        }
        confirmLabel="Delete"
        destructive
        busy={deleting}
        onConfirm={() => confirmDelete && remove(confirmDelete)}
        onClose={() => setConfirmDelete(null)}
      />
    </section>
  );
}
