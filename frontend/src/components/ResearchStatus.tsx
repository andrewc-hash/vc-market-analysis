"use client";

import { useEffect, useRef, useState } from "react";
import { pollResearchStatus, type TaskStatusResponse } from "@/lib/api";
import { Icon } from "./icons";

interface Props {
  taskId: string;
  onComplete: (result: TaskStatusResponse) => void;
}

export default function ResearchStatus({ taskId, onComplete }: Props) {
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [pollCount, setPollCount] = useState(0);
  const [pollErrors, setPollErrors] = useState<string[]>([]);
  const [elapsedSec, setElapsedSec] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Elapsed time counter
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setElapsedSec((s) => s + 1);
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    const poll = async () => {
      setPollCount((c) => c + 1);
      try {
        const data = await pollResearchStatus(taskId);
        setStatus(data);

        if (data.status === "SUCCESS" || data.status === "FAILURE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (timerRef.current) clearInterval(timerRef.current);
          onComplete(data);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setPollErrors((prev) => [...prev.slice(-4), `[${new Date().toLocaleTimeString()}] ${msg}`]);
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, onComplete]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [status?.agent_logs]);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const phaseLabel: Record<string, string> = {
    initializing: "Initializing pipeline…",
    researcher: "Researcher gathering live market data…",
    analysts_fanout: "Dispatching analysts…",
    analyst_a: "Analyst A drafting independent analysis…",
    analyst_b: "Analyst B drafting independent analysis…",
    judge: "Judge locating analyst disagreements…",
    compile_report: "Compiling the final report…",
  };

  const phaseStep: Record<string, number> = {
    initializing: 1,
    researcher: 2,
    analysts_fanout: 3,
    analyst_a: 3,
    analyst_b: 4,
    judge: 5,
    compile_report: 6,
  };

  // Model attributions surface the multi-provider pipeline in the UI itself.
  // Keep in sync with backend/app/config.py model defaults (CLAUDE.md §9).
  const STEPS: { label: string; model: string; key: string }[] = [
    { label: "Initialize", model: "pipeline setup", key: "initializing" },
    { label: "Research", model: "Gemini 2.5 Pro · live web", key: "researcher" },
    { label: "Analyst A", model: "Gemini 2.5 Pro", key: "analyst_a" },
    { label: "Analyst B", model: "Claude Sonnet 4.6", key: "analyst_b" },
    { label: "Judge", model: "GPT-4.1 · disagreement finder", key: "judge" },
    { label: "Compile", model: "Gemini 2.5 Pro", key: "compile_report" },
  ];

  const currentPhase = status?.current_phase || "";
  const step = phaseStep[currentPhase] || 0;

  return (
    <div className="card space-y-4">
      {/* Status Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {(!status || status.status === "STARTED" || status.status === "PENDING") && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-500 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-brand-600" />
            </span>
          )}
          <div>
            <h3 className="text-base font-semibold text-gray-100">
              {!status && "Connecting…"}
              {status?.status === "STARTED" && "Running analysis"}
              {status?.status === "SUCCESS" && "Analysis complete"}
              {status?.status === "FAILURE" && "Analysis failed"}
              {status?.status === "PENDING" && "Queued — waiting for worker…"}
            </h3>
            {status?.status === "STARTED" && (
              <p className="mt-0.5 text-xs text-gray-500">{phaseLabel[currentPhase] || "Processing…"}</p>
            )}
          </div>
        </div>
        <div
          className="text-right text-sm tabular-nums text-gray-500"
          title={`${pollCount} status checks · 3s interval`}
        >
          Elapsed {formatTime(elapsedSec)}
        </div>
      </div>

      {/* Pipeline stepper — vertical, with model attribution */}
      <ol className="space-y-0">
        {STEPS.map((s, i) => {
          const state = step > i + 1 ? "done" : step === i + 1 ? "active" : "todo";
          return (
            <li key={s.key} className="relative flex gap-3 pb-3.5 last:pb-0">
              {i < STEPS.length - 1 && (
                <span className="absolute left-[11px] top-6 h-full w-px bg-gray-800" aria-hidden />
              )}
              <span
                className={`z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                  state === "done"
                    ? "bg-brand-600 text-white"
                    : state === "active"
                      ? "animate-pulse bg-gray-900 text-brand-300 ring-2 ring-brand-500"
                      : "bg-gray-800 text-gray-500"
                }`}
              >
                {state === "done" ? <Icon name="check" className="h-3 w-3" /> : i + 1}
              </span>
              <div className="min-w-0">
                <div
                  className={`text-sm ${
                    state === "active"
                      ? "font-semibold text-gray-100"
                      : state === "done"
                        ? "text-gray-300"
                        : "text-gray-500"
                  }`}
                >
                  {s.label}
                </div>
                <div className="text-[11px] text-gray-500">{s.model}</div>
              </div>
            </li>
          );
        })}
      </ol>

      {/* Round Info */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="rounded-md border border-gray-800 bg-gray-800/60 px-2 py-0.5 tabular-nums text-gray-400">
          Debate round {status?.iterations_completed || 0} / 3
        </span>
        <span className="font-mono text-[11px]">Run {taskId.slice(0, 8)}</span>
      </div>

      {/* Agent activity feed */}
      {status && status.agent_logs.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-gray-500">Pipeline activity</div>
          <div className="max-h-48 divide-y divide-gray-800/70 overflow-y-auto rounded-md border border-gray-800 bg-gray-900/60">
            {status.agent_logs.map((log, i) => (
              <div key={i} className="px-3 py-1 text-[11px] leading-5 text-gray-500">
                {log}
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}

      {/* Poll Errors (so you can see what's going wrong) */}
      {pollErrors.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-red-500">Poll errors</div>
          <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-red-900 bg-red-950/30 p-3 font-mono text-xs text-red-400">
            {pollErrors.map((err, i) => (
              <div key={i}>{err}</div>
            ))}
          </div>
        </div>
      )}

      {/* Task Error */}
      {status?.error && (
        <div className="rounded-md border border-red-900 bg-red-950/30 p-4 text-sm text-red-300">
          <div className="mb-1 font-semibold">Pipeline error</div>
          <pre className="whitespace-pre-wrap text-xs">{status.error}</pre>
        </div>
      )}

      {/* Rate limit note */}
      {status?.status === "STARTED" && elapsedSec > 30 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-300/90">
          <Icon name="alert" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Pipeline is running with rate-limit retries. This is normal — a full run takes several minutes.
        </div>
      )}
    </div>
  );
}
