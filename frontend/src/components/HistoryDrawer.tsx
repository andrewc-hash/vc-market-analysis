"use client";

import { useEffect, useState } from "react";
import { listReports, updateReport, deleteReport, rerunReport, type ReportSummary } from "@/lib/api";
import { norm, nameMatch } from "@/lib/pickLabel";
import { Icon } from "./icons";

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  // Re-run a past analysis on its original inputs; parent starts polling the new task.
  onRerun?: (taskId: string) => void;
  refreshKey?: number; // bump to force a reload
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function HistoryDrawer({ open, onClose, onSelect, onRerun, refreshKey }: Props) {
  const [items, setItems] = useState<ReportSummary[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [rerunning, setRerunning] = useState<string | null>(null);
  const [rerunErr, setRerunErr] = useState("");

  const rerun = async (r: ReportSummary) => {
    if (rerunning) return;
    setRerunErr("");
    setRerunning(r.id);
    try {
      const { task_id } = await rerunReport(r.id);
      onRerun?.(task_id);
    } catch (e) {
      setRerunErr(e instanceof Error ? e.message : "Re-run failed");
    } finally {
      setRerunning(null);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      setItems(await listReports());
    } catch {
      /* ignore — empty list */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open, refreshKey]);

  const filtered = items.filter((r) => {
    if (!q.trim()) return true;
    const hay = `${r.label} ${r.sector} ${r.focal_startup} ${r.top_pick} ${r.analysis_mode}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  const toggleStar = async (r: ReportSummary) => {
    await updateReport(r.id, { starred: !r.starred }).catch(() => {});
    load();
  };
  const saveLabel = async (r: ReportSummary) => {
    await updateReport(r.id, { label: editVal }).catch(() => {});
    setEditing(null);
    load();
  };
  const remove = async (r: ReportSummary) => {
    if (!confirm("Delete this analysis? This can't be undone.")) return;
    await deleteReport(r.id).catch(() => {});
    load();
  };

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-black/60" onClick={onClose} aria-hidden />}
      <aside
        className={`fixed left-0 top-0 z-50 flex h-full w-80 max-w-[85vw] flex-col border-r border-gray-800 bg-gray-900 shadow-pop transition-transform duration-200 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-gray-800 px-4">
          <h2 className="text-sm font-semibold text-gray-100">
            History
            {items.length > 0 && (
              <span className="ml-2 text-xs font-normal tabular-nums text-gray-500">{items.length}</span>
            )}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300"
            aria-label="Close history"
          >
            <Icon name="x" className="h-4 w-4" />
          </button>
        </div>

        <div className="p-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search analyses…"
            className="input-field text-sm"
          />
          {rerunErr && <p className="mt-1.5 text-xs text-red-400">{rerunErr}</p>}
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {loading && <p className="px-2 py-4 text-xs text-gray-500">Loading…</p>}
          {!loading && filtered.length === 0 && (
            <div className="px-2 py-6 text-center text-xs text-gray-500">
              {items.length === 0 ? (
                <>
                  <p className="font-medium text-gray-400">No analyses yet</p>
                  <p className="mt-1">Finished runs are saved here automatically.</p>
                  <a href="/demo" className="mt-3 inline-block text-brand-300 hover:text-brand-200">
                    Browse example reports →
                  </a>
                </>
              ) : (
                "No matches."
              )}
            </div>
          )}
          {filtered.map((r) => (
            <div
              key={r.id}
              className="group mb-1 rounded-md border border-transparent px-2 py-2 hover:border-gray-800 hover:bg-gray-800/60"
            >
              <div className="flex items-start gap-2">
                <button
                  onClick={() => toggleStar(r)}
                  className={r.starred ? "text-amber-400" : "text-gray-600 hover:text-gray-400"}
                  title={r.starred ? "Unstar" : "Star"}
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
                      className={`rounded-sm px-1 text-[10px] ${
                        r.analysis_mode === "founder"
                          ? "bg-brand-500/15 text-brand-300"
                          : "border border-gray-700 text-gray-400"
                      }`}
                    >
                      {r.analysis_mode === "founder" ? "Founder" : "VC"}
                    </span>
                    {r.focal_startup && <span className="max-w-[7rem] truncate">{r.focal_startup}</span>}
                    {/* Suppress the pick chip when it just repeats the focal (VC+focal mode
                        stores the evaluated target as top_pick) — showing "· KBO" next to the
                        focal "KBO" wrongly implies KBO is the recommendation (R11). */}
                    {r.top_pick && !(r.focal_startup && nameMatch(norm(r.top_pick), norm(r.focal_startup))) && (
                      <span className="max-w-[8rem] truncate">· {r.top_pick}</span>
                    )}
                    <span className="tabular-nums">· {fmtDate(r.created_at)}</span>
                  </div>
                </button>

                <div className="flex shrink-0 gap-1 text-gray-600 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
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
                    onClick={() => remove(r)}
                    className="rounded p-1 hover:bg-gray-800 hover:text-rose-400"
                    title="Delete"
                  >
                    <Icon name="trash" className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
