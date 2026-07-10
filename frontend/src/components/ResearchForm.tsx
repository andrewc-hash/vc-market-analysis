"use client";

import { useEffect, useState } from "react";
import type { DimensionWeights as DW, ResearchRequest } from "@/lib/api";
import { deriveScope, fetchConfig } from "@/lib/api";
import ThesisBiasToggle from "./ThesisBiasToggle";
import DimensionWeightsPanel from "./DimensionWeights";
import FocalStartupPanel, { type FocalState } from "./FocalStartupPanel";
import { Icon } from "./icons";

interface Props {
  onSubmit: (req: ResearchRequest) => void;
  isLoading: boolean;
}

const STAGES = [
  "All Stages",
  "Pre-Seed",
  "Seed",
  "Series A",
  "Series B",
  "Series C",
  "Growth",
];

const GEOGRAPHIES = [
  "Global",
  "US-Only",
  "EU-Only",
  "Asia-Pacific",
  "Israel",
];

export default function ResearchForm({ onSubmit, isLoading }: Props) {
  const [prompt, setPrompt] = useState("");
  const [sector, setSector] = useState("");
  const [stage, setStage] = useState("All Stages");
  const [geography, setGeography] = useState("Global");
  const [thesisBias, setThesisBias] = useState<"Bear" | "Base" | "Bull">("Base");
  const [weights, setWeights] = useState<DW>({
    financial_health: 20,
    defensibility: 30,
    market_urgency: 20,
    founder_market_fit: 15,
    regulatory_alignment: 15,
  });
  const [focal, setFocal] = useState<FocalState>({
    enabled: false,
    analysisMode: "vc",
    focalStartup: "",
    uploadId: "",
  });
  const [deriving, setDeriving] = useState(false);
  const [scopeAutoderived, setScopeAutoderived] = useState(false);
  const [rationale, setRationale] = useState("");
  const [deriveError, setDeriveError] = useState("");
  const [fund, setFund] = useState({
    enabled: false, fundSize: "", check: "", post: "", ownership: "", years: "",
  });
  // null = unknown (config not yet fetched) — the panel renders neither the dropzone
  // nor the public-data notice until the flag is known, so a public-data deployment
  // never flashes an upload invitation.
  const [uploadsEnabled, setUploadsEnabled] = useState<boolean | null>(null);
  useEffect(() => {
    fetchConfig().then((c) => setUploadsEnabled(c.uploads_enabled));
  }, []);

  // The focal startup only counts when its on/off switch is ON.
  const hasFocal = focal.enabled && !!(focal.focalStartup.trim() || focal.uploadId);
  // Confirm-first: when a startup is attached but no prompt is written, the next action is
  // to auto-identify the market (which the user then reviews/edits) — not to launch.
  const needsDerive = hasFocal && !prompt.trim();
  // Founder mode centers the report on a NAMED startup (the backend rejects it unnamed).
  const founderNeedsName = focal.enabled && focal.analysisMode === "founder" && !focal.focalStartup.trim();

  const handleDerive = async () => {
    setDeriving(true);
    setDeriveError("");
    try {
      const s = await deriveScope(focal.focalStartup.trim(), focal.uploadId);
      if (s.market_prompt) {
        setPrompt(s.market_prompt);
        if (s.sector) setSector(s.sector);
        setScopeAutoderived(true);
        setRationale(s.rationale || "");
      } else {
        setDeriveError("Couldn't identify a market from the startup — please describe it yourself.");
      }
    } catch (e) {
      setDeriveError(e instanceof Error ? e.message : "Scope derivation failed");
    } finally {
      setDeriving(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || founderNeedsName) return;
    // Fund-math is gated on fund size; include only the numeric fields the user filled.
    const num = (s: string) => {
      const n = parseFloat(s);
      return Number.isFinite(n) && n > 0 ? n : undefined;
    };
    const fundEconomics =
      fund.enabled && num(fund.fundSize)
        ? {
            fund_size_musd: num(fund.fundSize),
            check_size_musd: num(fund.check),
            entry_post_money_musd: num(fund.post),
            target_ownership_pct: num(fund.ownership),
            holding_years: num(fund.years),
          }
        : null;
    onSubmit({
      market_prompt: prompt,
      sector,
      stage,
      geography,
      thesis_bias: thesisBias,
      dimension_weights: weights,
      // A founder mode left selected behind an OFF panel must not reach the backend
      // (it would be rejected: founder mode requires the startup name).
      analysis_mode: focal.enabled ? focal.analysisMode : "vc",
      focal_startup: focal.enabled ? focal.focalStartup.trim() : "",
      focal_upload_id: focal.enabled ? focal.uploadId : "",
      scope_autoderived: scopeAutoderived,
      fund_economics: fundEconomics,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Card 1 · Market Analysis Prompt ── */}
        <div className="card flex flex-col">
          <div className="mb-3">
            <div className="kicker">01 · Scope</div>
            <h2 className="mt-0.5 text-base font-semibold text-gray-100">Market Analysis Prompt</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              {hasFocal
                ? "Optional — leave blank and click below to auto-identify the market from the startup."
                : "Describe the sector to analyze."}
            </p>
          </div>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              if (scopeAutoderived) setScopeAutoderived(false); // user has taken over authorship
            }}
            placeholder={
              hasFocal
                ? "Leave blank and click “Identify market” to derive this from the startup — or write your own."
                : "e.g., Analyze the AI Agent Security & Runtime Governance sector — focus on startups building inline sandboxing, NHI management, and deterministic policy enforcement for autonomous AI agents in enterprise environments."
            }
            className="input-field min-h-[11rem] flex-1 resize-none"
            required={!hasFocal}
            minLength={10}
            disabled={deriving}
          />
          {scopeAutoderived && prompt.trim() && (
            <p className="mt-2 flex items-start gap-1.5 rounded-md bg-brand-500/10 px-2.5 py-1.5 text-xs text-brand-300">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0" />
              <span>
                Auto-identified from {focal.focalStartup.trim() || "your startup"}
                {sector ? ` · sector: ${sector}` : ""} — edit above if needed.
                {rationale ? <span className="text-gray-500"> ({rationale})</span> : null}
              </span>
            </p>
          )}
          {deriveError && <p className="mt-2 text-xs text-red-400">{deriveError}</p>}

          {/* Primary action */}
          <div className="mt-4">
            {needsDerive ? (
              <button type="button" onClick={handleDerive} disabled={deriving} className="btn-primary w-full">
                {deriving ? "Identifying market…" : "Identify market from startup →"}
              </button>
            ) : (
              <button type="submit" disabled={isLoading || !prompt.trim() || founderNeedsName} className="btn-primary w-full">
                {isLoading ? "Pipeline Running…" : "Launch Market Analysis"}
              </button>
            )}
            {founderNeedsName && !isLoading && (
              <p className="mt-2 text-xs text-amber-400">
                Founder mode needs your startup&apos;s name — add it in “Target Startup Details”.
              </p>
            )}
          </div>
        </div>

        {/* ── Card 2 · Target Startup Details ── */}
        <div className="card">
          <div className="kicker mb-2">02 · Target startup</div>
          <FocalStartupPanel value={focal} onChange={setFocal} disabled={isLoading || deriving} uploadsEnabled={uploadsEnabled} />
        </div>

        {/* ── Card 3 · Metadata Controls ── */}
        <div className="card">
          <div className="kicker">03 · Parameters</div>
          <h2 className="mb-4 mt-0.5 text-base font-semibold text-gray-100">Metadata Controls</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="label">Sector Label</label>
              <input
                type="text"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                placeholder="e.g., AI Agent Security"
                className="input-field"
              />
            </div>
            <div>
              <label className="label">Investment Stage</label>
              <select value={stage} onChange={(e) => setStage(e.target.value)} className="select-field">
                {STAGES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Geopolitical Scope</label>
              <select value={geography} onChange={(e) => setGeography(e.target.value)} className="select-field">
                {GEOGRAPHIES.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-5">
            <ThesisBiasToggle value={thesisBias} onChange={setThesisBias} />
          </div>
        </div>

        {/* ── Card 4 · Evaluation Dimension Weights ── */}
        <div className="card">
          <div className="kicker mb-2">04 · Weights</div>
          <DimensionWeightsPanel weights={weights} onChange={setWeights} />
        </div>
      </div>

      {/* ── Fund Economics (optional) · powers the fund-math engine ── */}
      <div className="card mt-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="kicker">05 · Fund economics</div>
            <h2 className="mt-0.5 text-base font-semibold text-gray-100">Fund Economics <span className="text-xs font-normal text-gray-500">· optional</span></h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Add your fund profile to compute &ldquo;does this return my fund?&rdquo; — turns of the fund, required exit, and IRR, all in code.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={fund.enabled}
            onClick={() => setFund((f) => ({ ...f, enabled: !f.enabled }))}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${fund.enabled ? "bg-brand-600" : "bg-gray-700"}`}
          >
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${fund.enabled ? "translate-x-5" : "translate-x-0.5"}`} />
          </button>
        </div>
        {fund.enabled && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {([
              ["fundSize", "Fund size ($M)", "50", true],
              ["check", "Check ($M)", "2", false],
              ["post", "Entry post-money ($M)", "20", false],
              ["ownership", "Target ownership (%)", "10", false],
              ["years", "Hold to exit (yrs)", "7", false],
            ] as const).map(([key, label, ph, required]) => (
              <div key={key}>
                <label className="label">{label}{required ? " *" : ""}</label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  inputMode="decimal"
                  placeholder={ph}
                  value={fund[key]}
                  onChange={(e) => setFund((f) => ({ ...f, [key]: e.target.value }))}
                  className="input-field"
                />
              </div>
            ))}
            <p className="col-span-2 text-[11px] text-gray-500 sm:col-span-3 lg:col-span-5">
              Only fund size is required. Missing post-money is inferred from stage; missing hold is stage-defaulted.
              Amounts in $M. Reconciles with the report&rsquo;s net-of-dilution range (same haircut, shown as dollars and turns).
            </p>
          </div>
        )}
      </div>
    </form>
  );
}
