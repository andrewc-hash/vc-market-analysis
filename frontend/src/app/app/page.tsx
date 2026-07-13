"use client";

import { useCallback, useState } from "react";
import ResearchForm from "@/components/ResearchForm";
import ResearchStatus from "@/components/ResearchStatus";
import ReportViewer from "@/components/ReportViewer";
import HistoryDrawer from "@/components/HistoryDrawer";
import { Icon } from "@/components/icons";
import { Wordmark } from "@/components/Wordmark";
import {
  getReport,
  getStoredApiKey,
  setStoredApiKey,
  submitResearch,
  type ResearchRequest,
  type TaskStatusResponse,
} from "@/lib/api";

export default function AppConsole() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [completedResult, setCompletedResult] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);

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
    // A finished run is now saved to history — refresh the drawer next time it opens.
    if (result.status === "SUCCESS") setHistoryKey((k) => k + 1);
  }, []);

  // Open a past analysis from the History drawer into the report viewer.
  const openFromHistory = async (id: string) => {
    setDrawerOpen(false);
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

  const handleReset = () => {
    setTaskId(null);
    setIsLoading(false);
    setCompletedResult(null);
    setError(null);
  };

  const showForm = !taskId && !completedResult;

  return (
    <>
      {/* Top navigation */}
      <header className="no-print sticky top-0 z-30 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <Wordmark href="/" />
          <nav className="flex items-center gap-1 text-[13px]">
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100"
            >
              <Icon name="clock" className="h-3.5 w-3.5" />
              History
            </button>
            <a
              href="/demo"
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100"
            >
              Examples
              <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </a>
            <a
              href="/docs"
              className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100"
            >
              Docs
            </a>
            <button
              onClick={() => {
                const next = window.prompt(
                  "API key for this deployment (leave empty to clear):",
                  getStoredApiKey()
                );
                if (next !== null) setStoredApiKey(next.trim());
              }}
              title="Set the X-API-Key used for requests (required on secured deployments)"
              aria-label="Set API key"
              className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-200"
            >
              <Icon name="key" className="h-4 w-4" />
            </button>
          </nav>
        </div>
      </header>

      <HistoryDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSelect={openFromHistory}
        onRerun={(tid) => {
          // A re-run is a fresh pipeline task — reuse the normal polling flow.
          setDrawerOpen(false);
          setError(null);
          setCompletedResult(null);
          setIsLoading(true);
          setTaskId(tid);
        }}
        refreshKey={historyKey}
      />

      <main className="mx-auto max-w-6xl px-4 py-8">
        {/* Page title — only on the launch console (the report brings its own masthead) */}
        {showForm && (
          <div className="mb-8">
            <h1 className="text-2xl font-semibold tracking-tight text-gray-100">New analysis</h1>
            <p className="mt-1 text-sm text-gray-500">
              One prompt — or one startup — into an institutional, verdict-first market memo.
            </p>
          </div>
        )}

        <div className="space-y-6">
          {/* Config Form — only show when no task is active (renders its own 2×2 card grid) */}
          {showForm && <ResearchForm onSubmit={handleSubmit} isLoading={isLoading} />}

          {/* Error Banner (submit errors) */}
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

          {/* New Analysis Button — always visible when there's a result or stopped task */}
          {(completedResult || error) && (
            <div className="no-print text-center">
              <button onClick={handleReset} className="btn-primary">
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
    </>
  );
}
