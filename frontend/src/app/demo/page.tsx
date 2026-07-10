"use client";

import { useState } from "react";
import ReportViewer from "@/components/ReportViewer";
import { Icon } from "@/components/icons";
import { demoScenarios } from "@/fixtures/demoScenarios";

// Public, backend-free showcase: three real multi-agent reports the visitor can explore
// instantly. This is the page to put on a resume / portfolio.
export default function DemoPage() {
  const [idx, setIdx] = useState(0);
  const s = demoScenarios[idx];

  return (
    <>
      {/* Top navigation (backend-free: links only) */}
      <header className="no-print sticky top-0 z-30 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <a href="/" className="flex items-center gap-2.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-brand-600 text-[11px] font-bold leading-none text-white">
              V
            </span>
            <span className="text-sm font-semibold text-gray-100">VC Market Analysis</span>
            <span className="hidden text-[10px] font-medium uppercase tracking-[0.2em] text-gray-500 sm:inline">
              Engine
            </span>
          </a>
          <nav className="flex items-center gap-1 text-[13px]">
            <a
              href="/"
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100"
            >
              New analysis
              <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </a>
            <a
              href="/docs"
              className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100"
            >
              Docs
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="no-print mb-6">
          <div className="kicker">Live examples</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-gray-100">See it in action</h1>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Three real multi-agent reports — pick a scenario below. No sign-up, no waiting, no API keys.
            Each was produced by the pipeline (researcher → two debating analysts → judge → compiler).
          </p>
        </div>

        {/* Scenario picker */}
        <div className="no-print grid gap-4 sm:grid-cols-3">
          {demoScenarios.map((sc, i) => {
            const active = i === idx;
            return (
              <button
                key={sc.id}
                type="button"
                onClick={() => setIdx(i)}
                className={`card text-left transition ${
                  active ? "border-brand-500/60 ring-2 ring-brand-500/40" : "hover:border-gray-700"
                }`}
              >
                <div className="kicker text-brand-300">{sc.tag}</div>
                <div className="mt-1 text-base font-semibold text-gray-100">{sc.title}</div>
                <div className="mt-1 text-xs leading-relaxed text-gray-500">{sc.subtitle}</div>
              </button>
            );
          })}
        </div>

        {/* Config summary — shows what was fed in to produce this report */}
        <div className="no-print mt-6 flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg border border-gray-800 bg-gray-900/60 px-4 py-3 text-xs text-gray-400">
          <span className="font-semibold text-gray-300">Inputs</span>
          <span>Sector: <span className="text-gray-200">{s.config.sector}</span></span>
          <span>Stage: <span className="text-gray-200">{s.config.stage}</span></span>
          <span>Mode: <span className="text-gray-200">{s.config.mode}</span></span>
          {s.config.target && (
            <span>Target startup: <span className="text-gray-200">{s.config.target}</span></span>
          )}
        </div>

        {/* The report */}
        <div className="mt-6">
          <ReportViewer result={s.result} />
        </div>

        <div className="no-print mt-10 text-center text-sm">
          <a href="/" className="text-brand-300 hover:text-brand-200">← Build your own analysis</a>
        </div>
      </main>
    </>
  );
}
