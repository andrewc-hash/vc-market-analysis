"use client";

import { useRef, useState } from "react";
import type { AnalysisMode } from "@/lib/api";
import { uploadFocalFiles } from "@/lib/api";

export interface FocalState {
  enabled: boolean;
  analysisMode: AnalysisMode;
  focalStartup: string;
  uploadId: string;
}

interface Props {
  value: FocalState;
  onChange: (v: FocalState) => void;
  disabled?: boolean;
  // Public-data deployments disable uploads (confidential material must not reach
  // third-party LLM APIs without data-handling agreements). null = config pending.
  uploadsEnabled?: boolean | null;
}

const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.gif,.csv,.vtt,.srt,.mp3,.m4a,.wav,.webm";

const MODES: { key: AnalysisMode; title: string; blurb: string }[] = [
  {
    key: "vc",
    title: "VC · Evaluate a target",
    blurb: "You're the investor. Verdict: INVEST / WATCH / PASS at a price, the deal ranked against its real field, its own return scenarios — and a deal path on WATCH or PASS.",
  },
  {
    key: "founder",
    title: "Founder · Test my startup",
    blurb: "You're the founder. Verdict: fundable today? + BUILD / KEEP GOING / PIVOT / STOP, a repositioning plan aimed at your weakest scores, and YOUR raise modelled (size, post-money, dilution, conditions to close).",
  },
];

function Switch({ on, onToggle, disabled }: { on: boolean; onToggle: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Enable target startup"
      disabled={disabled}
      onClick={onToggle}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
        on ? "bg-brand-500" : "bg-gray-700"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          on ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

export default function FocalStartupPanel({ value, onChange, disabled, uploadsEnabled = true }: Props) {
  const uploadsPending = uploadsEnabled === null;
  const [files, setFiles] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const set = (patch: Partial<FocalState>) => onChange({ ...value, ...patch });
  const on = value.enabled;

  const handleFiles = async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    setError("");
    setUploading(true);
    try {
      const res = await uploadFocalFiles(Array.from(list));
      set({ uploadId: res.upload_id });
      setFiles(res.files);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const clearUpload = () => {
    setFiles([]);
    set({ uploadId: "" });
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div>
      {/* Header + on/off */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Target Startup Details</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            Analyze a specific company — a target you&rsquo;re evaluating, or your own startup.
          </p>
        </div>
        <Switch on={on} onToggle={() => set({ enabled: !on })} disabled={disabled} />
      </div>

      {!on ? (
        <p className="mt-5 rounded-lg border border-dashed border-gray-800 px-4 py-6 text-center text-sm text-gray-600">
          Turn on to focus the analysis on a specific startup.
        </p>
      ) : (
        <div className="mt-5 space-y-4">
          {/* Mode toggle */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {MODES.map((m) => {
              const active = value.analysisMode === m.key;
              return (
                <button
                  key={m.key}
                  type="button"
                  disabled={disabled}
                  onClick={() => set({ analysisMode: m.key })}
                  className={`rounded-md border p-3 text-left transition ${
                    active ? "border-brand-400 bg-brand-500/10" : "border-gray-800 hover:border-gray-700"
                  }`}
                >
                  <div className={`text-sm font-medium ${active ? "text-brand-200" : "text-gray-200"}`}>{m.title}</div>
                  <div className="mt-0.5 text-xs text-gray-500">{m.blurb}</div>
                </button>
              );
            })}
          </div>

          {/* Startup name */}
          <div>
            <label className="label">Startup name</label>
            <input
              type="text"
              value={value.focalStartup}
              onChange={(e) => set({ focalStartup: e.target.value })}
              placeholder="e.g., Abridge — or your own startup's name"
              className="input-field"
              maxLength={200}
              disabled={disabled}
            />
          </div>

          {/* Upload dropzone (gated off on public-data deployments; hidden while config pends) */}
          {uploadsPending ? null : !uploadsEnabled ? (
            <p className="rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2 text-xs text-gray-500">
              File uploads are disabled on this deployment (public-data mode) — analyses run on
              the startup name and public information only. Do not paste confidential material
              into the prompt.
            </p>
          ) : (
          <div>
            <label className="label">
              Supporting files <span className="font-normal normal-case tracking-normal text-gray-500">— deck · financials · founder-call recording or transcript (claims get fact-checked) · cap-table CSV (grounds the fund math)</span>
            </label>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); if (!disabled) handleFiles(e.dataTransfer.files); }}
              onClick={() => !disabled && inputRef.current?.click()}
              className="cursor-pointer rounded-md border border-dashed border-gray-700 px-4 py-6 text-center text-sm text-gray-500 transition-colors hover:border-brand-500/50"
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={ACCEPT}
                className="hidden"
                disabled={disabled}
                onChange={(e) => handleFiles(e.target.files)}
              />
              {uploading
                ? "Uploading & reading…"
                : "Drag files here or click to upload — deck (PDF/images), docs, call audio (≤25MB) or .vtt/.srt transcript, cap-table .csv"}
            </div>
            {files.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                {files.map((f) => (
                  <span key={f} className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">{f}</span>
                ))}
                <button type="button" onClick={clearUpload} className="text-gray-500 underline hover:text-gray-300">
                  clear
                </button>
              </div>
            )}
            {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
          </div>
          )}
        </div>
      )}
    </div>
  );
}
