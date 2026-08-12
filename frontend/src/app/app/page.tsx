"use client";

import { useCallback, useState, useEffect } from "react";
import ResearchForm, { type FormMode } from "@/components/ResearchForm";
import ResearchStatus from "@/components/ResearchStatus";
import ReportViewer from "@/components/ReportViewer";
import HistoryList from "@/components/HistoryList";
import TrackedList from "@/components/TrackedList";
import ViewHelp from "@/components/ViewHelp";
import ConsoleShell, { type ConsoleView } from "@/components/ConsoleShell";
import { ToastProvider } from "@/components/Toaster";
import ConfirmDialog from "@/components/ConfirmDialog";
import { Icon } from "@/components/icons";
import {
  clearFundProfile,
  isFundProfileSet,
  loadFundProfile,
  saveFundProfile,
  type FundProfile,
} from "@/lib/fundProfile";
import {
  getReport,
  listReports,
  submitResearch,
  type ReportSummary,
  type ResearchRequest,
  type TaskStatusResponse,
} from "@/lib/api";

// ── View copy — shared by the sidebar targets, Home's mode cards, and the mode headers ──

const MODE_META: Record<FormMode, { title: string; desc: string }> = {
  sector: { title: "Analyze a Market", desc: "Map and rank an entire sector — no specific startup required." },
  vc: { title: "Evaluate a Startup", desc: "A deal you're screening, ranked inside its real competitive field." },
  founder: { title: "Evaluate My Startup", desc: "A build / pass verdict on your own company." },
};

const MODE_ORDER: FormMode[] = ["vc", "founder", "sector"];

// ── Workspace header — operator greeting + local date ─────────────────────────

function greetingFor(d: Date): string {
  const h = d.getHours();
  if (h < 12) return "Good morning.";
  if (h < 18) return "Good afternoon.";
  return "Good evening.";
}

function WorkspaceHeader() {
  // Computed after mount — time-of-day is client-local and must not fight SSR markup.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <div className="kicker mb-2">Prospectus · Analysis console</div>
        <h1 className="font-serif text-3xl font-semibold tracking-tight text-gray-100">
          {now ? greetingFor(now) : " "}
        </h1>
        <p className="mt-1.5 text-sm text-gray-500">
          {now ? (
            <>
              {now.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
              <span className="mx-2 text-gray-700">·</span>
              One prompt — or one startup — into an institutional, verdict-first market memo.
            </>
          ) : (
            " "
          )}
        </p>
      </div>
      <ViewHelp view="home" />
    </div>
  );
}

// ── Stat strip — the computed-verdict layer over the History store ────────────

function relTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "—";
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "1d ago";
  if (days < 31) return `${days}d ago`;
  const months = Math.floor(days / 30.44);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

interface WorkspaceStats {
  total: number;
  sectors: number;
  targeted: number;
  starred: number;
  lastRun: string;
}

function computeStats(items: ReportSummary[]): WorkspaceStats {
  const sectors = new Set(
    items.map((r) => (r.sector || "").trim().toLowerCase()).filter(Boolean)
  ).size;
  const newest = items.reduce<string>(
    (acc, r) => (r.created_at > acc ? r.created_at : acc),
    ""
  );
  return {
    total: items.length,
    sectors,
    targeted: items.filter((r) => (r.focal_startup || "").trim()).length,
    starred: items.filter((r) => r.starred).length,
    lastRun: newest ? relTime(newest) : "—",
  };
}

function StatCell({ value, caption, loading = false }: { value: string; caption: string; loading?: boolean }) {
  return (
    <div className="bg-gray-900 px-5 py-3.5">
      {loading ? (
        // Shimmer matches the value line's box (leading-7) so the strip doesn't jump.
        <div className="flex h-7 items-center" aria-hidden>
          <div className="skeleton h-5 w-12" />
        </div>
      ) : (
        <div className="text-xl font-semibold tabular-nums leading-7 text-gray-100">{value}</div>
      )}
      <div className="mt-1 font-mono text-[9.5px] font-medium uppercase tracking-[0.16em] text-gray-500">
        {caption}
      </div>
    </div>
  );
}

function StatStrip({ refreshKey }: { refreshKey: number }) {
  // null = loading, "unavailable" = backend down (render dashes, never fake numbers)
  const [stats, setStats] = useState<WorkspaceStats | "unavailable" | null>(null);
  useEffect(() => {
    let alive = true;
    listReports()
      .then((items) => alive && setStats(computeStats(items)))
      .catch(() => alive && setStats("unavailable"));
    return () => {
      alive = false;
    };
  }, [refreshKey]);

  const s = stats && stats !== "unavailable" ? stats : null;
  const loading = stats === null; // shimmer only while loading — backend-down keeps the dashes
  const num = (v: number | undefined) => (s ? String(v) : "—");
  return (
    <div className="mb-8 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-gray-800 bg-gray-800/60 sm:grid-cols-3 lg:grid-cols-5">
      <StatCell value={num(s?.total)} caption="Analyses run" loading={loading} />
      <StatCell value={num(s?.sectors)} caption="Sectors covered" loading={loading} />
      <StatCell value={num(s?.targeted)} caption="Target-deal runs" loading={loading} />
      <StatCell value={num(s?.starred)} caption="Starred reports" loading={loading} />
      <StatCell value={s ? s.lastRun : "—"} caption="Most recent run" loading={loading} />
    </div>
  );
}

// ── Home: mode launcher cards ──────────────────────────────────────────────────

function ModeCards({ onPick }: { onPick: (m: FormMode) => void }) {
  return (
    <section className="mb-8">
      <div className="kicker mb-3">Start an analysis</div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {MODE_ORDER.map((m) => (
          <button
            key={m}
            onClick={() => onPick(m)}
            className="card group flex items-center justify-between gap-3 py-4 text-left transition-colors hover:border-gray-700 hover:bg-gray-900/80"
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-gray-100">{MODE_META[m].title}</div>
              <div className="mt-0.5 text-xs leading-relaxed text-gray-500">{MODE_META[m].desc}</div>
            </div>
            <Icon
              name="arrow-right"
              className="h-4 w-4 shrink-0 text-gray-600 transition-all group-hover:translate-x-0.5 group-hover:text-brand-300"
            />
          </button>
        ))}
      </div>
    </section>
  );
}

// ── Mode-view header (serif title + kicker, mirrors the workspace header) ──────

function ModeHeader({ mode }: { mode: FormMode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <div className="kicker mb-2">New analysis · {MODE_META[mode].title}</div>
        <h1 className="font-serif text-3xl font-semibold tracking-tight text-gray-100">
          {MODE_META[mode].title}
        </h1>
        <p className="mt-1.5 text-sm text-gray-500">{MODE_META[mode].desc}</p>
      </div>
      <ViewHelp view={mode} />
    </div>
  );
}

// ── Fund Profile view — workspace-level fund economics (set once, auto-applied) ──

const EMPTY_PROFILE: FundProfile = { fundSize: "", check: "", post: "", ownership: "", years: "" };

// Same labels/placeholders as the form's Fund Economics card — the profile IS that card,
// promoted to a workspace setting. Fund size is the gate for the profile to count as set.
const PROFILE_FIELDS = [
  ["fundSize", "Fund size ($M)", "50", true],
  ["check", "Check ($M)", "2", false],
  ["post", "Entry post-money ($M)", "20", false],
  ["ownership", "Target ownership (%)", "10", false],
  ["years", "Hold to exit (yrs)", "7", false],
] as const;

function FundProfileView() {
  const [draft, setDraft] = useState<FundProfile>(EMPTY_PROFILE);
  const [saved, setSaved] = useState(false); // a valid profile is currently persisted
  const [confirmation, setConfirmation] = useState<"saved" | "cleared" | null>(null);

  // localStorage is client-only — read after mount so SSR markup never mismatches.
  useEffect(() => {
    const p = loadFundProfile();
    if (p) {
      setDraft(p);
      setSaved(isFundProfileSet(p));
    }
  }, []);

  const draftValid = isFundProfileSet(draft);
  const edit = (key: keyof FundProfile, value: string) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setConfirmation(null);
  };

  const handleSave = () => {
    if (!draftValid) return;
    saveFundProfile(draft);
    setSaved(true);
    setConfirmation("saved");
  };

  const handleClear = () => {
    clearFundProfile();
    setDraft(EMPTY_PROFILE);
    setSaved(false);
    setConfirmation("cleared");
  };

  return (
    <div className="no-print">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="kicker mb-2">Investor · My Fund</div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-gray-100">
            My Fund
          </h1>
          <p className="mt-1.5 text-sm text-gray-500">
            Set once — every analysis computes whether the deal returns <em>your</em> fund.
          </p>
        </div>
        <ViewHelp view="fund" />
      </div>

      <div className="card max-w-3xl">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-gray-100">Fund economics</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Applied automatically to every new analysis. Amounts in $M · only fund size is
              required for the profile to count as set.
            </p>
          </div>
          {saved && (
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-900/60 bg-emerald-950/30 px-2.5 py-1 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-emerald-400">
              <Icon name="check" className="h-3 w-3" />
              Profile set
            </span>
          )}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {PROFILE_FIELDS.map(([key, label, ph, required]) => (
            <div key={key}>
              <label className="label">{label}{required ? " *" : ""}</label>
              <input
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                placeholder={ph}
                value={draft[key]}
                onChange={(e) => edit(key, e.target.value)}
                className="input-field"
              />
            </div>
          ))}
        </div>

        <p className="mt-3 text-[11px] text-gray-500">
          Fund math adds a Fund Fit panel and a §12 return-the-fund subsection to every report —
          turns of the fund, the required exit to return it, and net IRR, all computed in code.
        </p>

        <div className="mt-4 flex items-center gap-3 border-t border-gray-800/70 pt-4">
          <button type="button" onClick={handleSave} disabled={!draftValid} className="btn-primary px-6 disabled:cursor-not-allowed disabled:opacity-50">
            Save profile
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={!saved && Object.values(draft).every((v) => !v.trim())}
            className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
          >
            Clear
          </button>
          <span className="text-xs text-gray-500" aria-live="polite">
            {confirmation === "saved"
              ? "Saved — future analyses will apply this profile."
              : confirmation === "cleared"
                ? "Profile cleared — fund economics are back to per-run entry."
                : !draftValid
                  ? "Add the fund size ($M) to save."
                  : ""}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function AppConsole() {
  // Client-side view state machine: Home (greeting + stats + inline History) or one of
  // the three preconfigured launch views. Running/report states overlay whatever view
  // launched them; leaving a finished report always lands back on Home.
  const [view, setView] = useState<ConsoleView>("home");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [completedResult, setCompletedResult] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0); // bumped when a run completes
  const [statsKey, setStatsKey] = useState(0); // bumped when the list mutates (star/rename/delete)
  // Navigation attempted while a run is live — held until the themed dialog confirms.
  const [pendingNav, setPendingNav] = useState<ConsoleView | null>(null);

  const running = !!taskId && !completedResult;

  // Deep-linkable launch views (/app?view=sector|vc|founder|fund) — applied after mount
  // so SSR markup (Home) never mismatches hydration.
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v === "sector" || v === "vc" || v === "founder" || v === "fund" || v === "tracked") setView(v);
  }, []);

  const handleSubmit = async (request: ResearchRequest) => {
    setError(null);
    setCompletedResult(null);
    setIsLoading(true);
    try {
      const { task_id } = await submitResearch(request);
      setTaskId(task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit.");
      setIsLoading(false);
    }
  };

  const handleComplete = useCallback((result: TaskStatusResponse) => {
    setIsLoading(false);
    setCompletedResult(result);
    // A finished run is now saved to history — refresh Home's list + stats.
    if (result.status === "SUCCESS") setHistoryKey((k) => k + 1);
  }, []);

  // Sidebar / wordmark navigation. Navigating away also closes an open report; a run
  // in progress keeps executing server-side (and saves to History), but confirm first
  // via the themed dialog (replaces window.confirm).
  const doNavigate = (next: ConsoleView) => {
    setTaskId(null);
    setIsLoading(false);
    setCompletedResult(null);
    setError(null);
    setView(next);
    // URL-as-state: refresh and Back behave like a real console, and views stay shareable.
    window.history.replaceState(null, "", next === "home" ? "/app" : `/app?view=${next}`);
  };

  const navigate = (next: ConsoleView) => {
    if (running) {
      setPendingNav(next);
      return;
    }
    doNavigate(next);
  };

  // Open a past analysis from the inline History into the report viewer.
  const openFromHistory = async (id: string) => {
    setError(null);
    try {
      const rec = await getReport(id);
      setTaskId(null);
      setIsLoading(false);
      setCompletedResult({
        task_id: rec.id,
        status: "SUCCESS",
        current_phase: "compile_report",
        iterations_completed: rec.final_report?.iterations_to_consensus ?? 0,
        agent_logs: [],
        final_report: rec.final_report as unknown as Record<string, unknown>,
        error: null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open report.");
    }
  };

  // A re-run is a fresh pipeline task — reuse the normal polling flow.
  const startRerun = (tid: string) => {
    setError(null);
    setCompletedResult(null);
    setIsLoading(true);
    setTaskId(tid);
  };

  const showLaunch = !taskId && !completedResult;

  return (
    <ToastProvider>
    <ConsoleShell active={showLaunch ? view : null} onNavigate={navigate}>
      <main className="mx-auto max-w-6xl px-4 py-8 lg:px-6">
        {/* ── HOME: greeting + stat strip + mode launcher + inline History ── */}
        {showLaunch && view === "home" && (
          <div className="no-print stagger-children">
            <WorkspaceHeader />
            <StatStrip refreshKey={historyKey + statsKey} />
            <ModeCards onPick={(m) => setView(m)} />
            <HistoryList
              onSelect={openFromHistory}
              onRerun={startRerun}
              refreshKey={historyKey}
              onMutated={() => setStatsKey((k) => k + 1)}
            />
          </div>
        )}

        {/* ── FUND PROFILE: workspace settings view (no run state of its own) ── */}
        {showLaunch && view === "fund" && <FundProfileView />}

        {/* ── TRACKED: baseline→re-run chains, latest delta + graded predictions ── */}
        {showLaunch && view === "tracked" && (
          <div className="no-print">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <div className="kicker mb-2">Investor · Tracked Deals</div>
                <h1 className="font-serif text-3xl font-semibold tracking-tight text-gray-100">
                  Tracked Deals
                </h1>
                <p className="mt-1.5 text-sm text-gray-500">
                  Re-run any analysis and Prospectus diffs the field and grades its own past
                  predictions.
                </p>
              </div>
              <ViewHelp view="tracked" />
            </div>
            <TrackedList onSelect={openFromHistory} onRerun={startRerun} />
          </div>
        )}

        <div className="space-y-6">
          {/* ── MODE VIEWS: header + the preconfigured form (keyed so state resets) ── */}
          {showLaunch && view !== "home" && view !== "fund" && view !== "tracked" && (
            <div className="no-print">
              <ModeHeader mode={view} />
              <ResearchForm key={view} mode={view} onSubmit={handleSubmit} isLoading={isLoading} />
            </div>
          )}

          {/* Error Banner (submit / open errors) */}
          {error && (
            <div className="card no-print border-red-900/60 bg-red-950/20">
              <p className="text-sm font-semibold text-red-300">Submit error</p>
              <p className="mt-1 text-sm text-red-300/90">{error}</p>
            </div>
          )}

          {/* Live Status / Polling — stays visible even on failure */}
          {taskId && !completedResult && (
            <div className="no-print">
              <ResearchStatus taskId={taskId} onComplete={handleComplete} />
            </div>
          )}

          {/* Failed Result — show error details */}
          {completedResult && completedResult.status === "FAILURE" && (
            <div className="card no-print space-y-3 border-red-900/60">
              <h3 className="flex items-center gap-2 text-base font-semibold text-red-400">
                <Icon name="alert" className="h-4 w-4" />
                Pipeline failed
              </h3>
              {completedResult.error && (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-red-900 bg-red-950/30 p-4 font-mono text-xs text-red-300">
                  {completedResult.error}
                </pre>
              )}
              {completedResult.agent_logs.length > 0 && (
                <div>
                  <div className="mb-1 text-xs text-gray-500">Last agent activity before failure</div>
                  <div className="divide-y divide-gray-800/70 rounded-md border border-gray-800 bg-gray-900/60">
                    {completedResult.agent_logs.map((log, i) => (
                      <div key={i} className="px-3 py-1 text-[11px] leading-5 text-gray-500">
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Final Report */}
          {completedResult && completedResult.status === "SUCCESS" && (
            <ReportViewer result={completedResult} />
          )}

          {/* Back to Home — always visible when there's a result or stopped task */}
          {(completedResult || error) && (
            <div className="no-print text-center">
              <button onClick={() => navigate("home")} className="btn-primary">
                Start new analysis
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="mt-12 border-t border-gray-800 pt-5 text-center text-xs text-gray-500">
          Decision-support only — not investment advice.
          <span className="mx-2 text-gray-700">|</span>
          <a href="/terms" className="underline hover:text-gray-300">Terms of Use</a>
        </footer>
      </main>

      {/* Leave-while-running guard — themed replacement for window.confirm */}
      <ConfirmDialog
        open={pendingNav !== null}
        title="An analysis is running"
        body="Leave this view? The run keeps going in the background and saves to History when done."
        confirmLabel="Leave view"
        cancelLabel="Stay"
        onConfirm={() => {
          const next = pendingNav;
          setPendingNav(null);
          if (next) doNavigate(next);
        }}
        onClose={() => setPendingNav(null)}
      />
    </ConsoleShell>
    </ToastProvider>
  );
}
