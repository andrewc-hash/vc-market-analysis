"use client";

import { useEffect, useState } from "react";
import type { DimensionWeights as DW, ResearchRequest } from "@/lib/api";
import { deriveScope, fetchConfig } from "@/lib/api";
import ThesisBiasToggle from "./ThesisBiasToggle";
import DimensionWeightsPanel from "./DimensionWeights";
import FocalStartupPanel, { type FocalState } from "./FocalStartupPanel";
import { Icon } from "./icons";
import {
  isFundProfileSet,
  loadFundProfile,
  saveFundProfile,
  summarizeFundProfile,
  type FundProfile,
} from "@/lib/fundProfile";

// The three console mode views. This is presentation-only preconfiguration:
// "sector"  → focal panel hidden; submits exactly the old focal-OFF payload.
// "vc"      → focal panel pinned ON in VC mode (Target Deal).
// "founder" → focal panel pinned ON in Founder mode (name required).
export type FormMode = "sector" | "vc" | "founder";

interface Props {
  onSubmit: (req: ResearchRequest) => void;
  isLoading: boolean;
  mode: FormMode;
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

export default function ResearchForm({ onSubmit, isLoading, mode }: Props) {
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
  // The mode view pins the focal panel's state: hidden in a sector scan, always-on
  // otherwise (page.tsx keys the form by mode, so this init is authoritative).
  const [focal, setFocal] = useState<FocalState>({
    enabled: mode !== "sector",
    analysisMode: mode === "founder" ? "founder" : "vc",
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
  // Workspace fund profile (localStorage). Read ONCE at mount — page.tsx keys the form
  // by mode, so every mode view remounts the form and re-reads a fresh copy. When a
  // valid profile exists it prefills + enables fund economics and the card collapses to
  // an "applied" summary; per-run adjustments NEVER write back to the profile.
  const [profile, setProfile] = useState<FundProfile | null>(null);
  // Card variant when a profile is applied: collapsed summary / expanded per-run editor /
  // opted out for this run (with undo). null = no profile → the card behaves as before.
  const [fundVariant, setFundVariant] = useState<"applied" | "adjust" | "off" | null>(null);
  // Quiet confirmation after "Save as workspace profile" (no-profile path only).
  const [profileJustSaved, setProfileJustSaved] = useState(false);
  useEffect(() => {
    const p = loadFundProfile();
    if (isFundProfileSet(p)) {
      setProfile(p);
      setFund({ enabled: true, ...p });
      setFundVariant("applied");
    }
  }, []);
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
  // VC mode with the panel ON but nothing attached silently degrades to a plain sector
  // scan — legal, but surprising. Warn instead of blocking.
  const vcUnnamed = focal.enabled && focal.analysisMode === "vc" && !focal.focalStartup.trim() && !focal.uploadId;
  // Fund Economics ON without a fund size is silently dropped at submit (fund size is
  // the master gate for the fund-math engine) — warn so the Fund Fit panel isn't missed.
  const fundSizeMissing = fund.enabled && !(parseFloat(fund.fundSize) > 0);

  // Card kickers renumber when the focal card is hidden (sector scans have no card 02).
  const kick =
    mode === "sector"
      ? { scope: "01 · Scope", target: "", params: "02 · Parameters", weights: "03 · Weights", fund: "04 · Fund economics" }
      : {
          target: mode === "founder" ? "01 · Your startup" : "01 · Target startup",
          scope: "02 · Scope",
          params: "03 · Parameters",
          weights: "04 · Weights",
          fund: "05 · Fund economics",
        };

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
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-stretch">
        {/* ── Startup card FIRST in vc/founder — those modes start with a company;
            the market prompt derives from it. Hidden in a sector scan. ── */}
        {mode !== "sector" && (
          <div className="card flex flex-col">
            <div className="kicker mb-2">{kick.target}</div>
            <FocalStartupPanel
              value={focal}
              onChange={setFocal}
              disabled={isLoading || deriving}
              uploadsEnabled={uploadsEnabled}
              pinned
            />
          </div>
        )}

        {/* ── Market Analysis Prompt ── */}
        <div className={`card flex flex-col ${mode === "sector" ? "lg:col-span-2" : ""}`}>
          <div className="mb-3">
            <div className="kicker">{kick.scope}</div>
            <h2 className="mt-0.5 text-base font-semibold text-gray-100">Market Analysis Prompt</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              {hasFocal
                ? "Optional — leave blank and click below to auto-identify the market from the startup."
                : mode !== "sector"
                  ? "Optional once the startup is named — its market can be auto-identified. Or describe the market yourself."
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

          {/* Generate-the-prompt lives WITH the prompt box (vc/founder): derive from the
              startup's name + materials, review, then launch. */}
          {mode !== "sector" && !prompt.trim() && (
            <div className="mt-3">
              <button
                type="button"
                onClick={handleDerive}
                disabled={deriving || !hasFocal}
                className="btn-secondary w-full justify-center"
              >
                <Icon name="map" className="h-3.5 w-3.5" />
                {deriving ? "Generating market prompt…" : "Generate market prompt from startup"}
              </button>
              {!hasFocal ? (
                <p className="mt-2 text-[11px] text-gray-500">
                  Name the startup in card 01 to enable generation.
                </p>
              ) : !focal.uploadId ? (
                <p className="mt-2 text-[11px] text-amber-400/90">
                  Recommended: attach the deck or docs in card 01 before generating — the prompt is
                  grounded in a name search and your attached materials.
                </p>
              ) : null}
            </div>
          )}
        </div>

        {/* ── Card 3 · Analysis Parameters ── */}
        <div className="card">
          <div className="kicker">{kick.params}</div>
          <h2 className="mb-4 mt-0.5 text-base font-semibold text-gray-100">Analysis Parameters</h2>
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

        {/* ── Card · Evaluation Dimension Weights ── */}
        <div className="card">
          <div className="kicker mb-2">{kick.weights}</div>
          <DimensionWeightsPanel weights={weights} onChange={setWeights} />
        </div>

        {/* ── Fund Economics (optional) · powers the fund-math engine.
               With a workspace fund profile applied the card collapses to a summary;
               "Adjust for this run" expands the normal editor (per-run only, never
               written back), "Run without fund math" opts out with an undo. ── */}
        {profile && fundVariant === "applied" ? (
          <div className="card lg:col-span-2">
            <div className="kicker">{kick.fund}</div>
            <p className="mt-2 flex items-start gap-2 text-sm text-gray-200">
              <Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
              <span>Fund profile applied — {summarizeFundProfile(profile)}</span>
            </p>
            <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
              <button
                type="button"
                onClick={() => setFundVariant("adjust")}
                className="text-brand-300 transition-colors hover:text-brand-200"
              >
                Adjust for this run
              </button>
              <button
                type="button"
                onClick={() => {
                  setFund((f) => ({ ...f, enabled: false }));
                  setFundVariant("off");
                }}
                className="text-gray-500 transition-colors hover:text-gray-300"
              >
                Run without fund math
              </button>
            </div>
          </div>
        ) : profile && fundVariant === "off" ? (
          <div className="card lg:col-span-2">
            <div className="kicker">{kick.fund}</div>
            <p className="mt-2 text-xs text-gray-500">
              Fund math is off for this run — the report will skip the Fund Fit panel.{" "}
              <button
                type="button"
                onClick={() => {
                  setFund({ enabled: true, ...profile });
                  setFundVariant("applied");
                }}
                className="text-brand-300 transition-colors hover:text-brand-200"
              >
                Undo
              </button>
            </p>
          </div>
        ) : (
        <div className="card lg:col-span-2">
        <div className="flex items-center justify-between">
          <div>
            <div className="kicker">{kick.fund}</div>
            <h2 className="mt-0.5 text-base font-semibold text-gray-100">Fund Economics <span className="text-xs font-normal text-gray-500">· optional</span></h2>
            <p className="mt-0.5 text-xs text-gray-500">
              {profile && fundVariant === "adjust"
                ? "Adjusting this run only — the workspace fund profile is unchanged."
                : "Add your fund profile to compute “does this return my fund?” — turns of the fund, required exit, and IRR, all in code."}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={fund.enabled}
            onClick={() => setFund((f) => ({ ...f, enabled: !f.enabled }))}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${fund.enabled ? "bg-brand-600" : "bg-gray-700"}`}
          >
            <span className={`absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${fund.enabled ? "translate-x-5" : "translate-x-0.5"}`} />
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
                  onChange={(e) => {
                    setFund((f) => ({ ...f, [key]: e.target.value }));
                    if (profileJustSaved) setProfileJustSaved(false);
                  }}
                  className="input-field"
                />
              </div>
            ))}
            <p className="col-span-2 text-[11px] text-gray-500 sm:col-span-3 lg:col-span-5">
              Only fund size is required. Missing post-money is inferred from stage; missing hold is stage-defaulted.
              Amounts in $M. Reconciles with the report&rsquo;s net-of-dilution range (same haircut, shown as dollars and turns).
            </p>
            {!profile && parseFloat(fund.fundSize) > 0 && (
              <div className="col-span-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 sm:col-span-3 lg:col-span-5">
                <button
                  type="button"
                  onClick={() => {
                    saveFundProfile({
                      fundSize: fund.fundSize,
                      check: fund.check,
                      post: fund.post,
                      ownership: fund.ownership,
                      years: fund.years,
                    });
                    setProfileJustSaved(true);
                  }}
                  className="text-xs text-brand-300 transition-colors hover:text-brand-200"
                >
                  Save as workspace profile
                </button>
                {profileJustSaved && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-gray-500">
                    <Icon name="check" className="h-3 w-3 text-emerald-400" />
                    Saved — auto-applies to future analyses.
                  </span>
                )}
              </div>
            )}
          </div>
        )}
        </div>
        )}
      </div>

      {/* ── Primary action bar — the form's single point of departure ── */}
      <div className="mt-6 flex flex-col gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 text-xs text-gray-500">
          {founderNeedsName && !isLoading ? (
            <span className="text-amber-400">Founder mode needs your startup&apos;s name — add it in &ldquo;Your Startup&rdquo;.</span>
          ) : vcUnnamed && !isLoading ? (
            <span className="text-amber-400">No target named — this will run as a plain sector scan. Add the startup&apos;s name (or attach files), or use Sector Scan instead.</span>
          ) : fundSizeMissing && !isLoading ? (
            <span className="text-amber-400">Fund Economics is on but fund size is empty — the Fund Fit panel won&apos;t render. Add the fund size ($M), or switch it off.</span>
          ) : needsDerive ? (
            <span>No prompt yet — generate it from your startup in the Scope card, or write your own.</span>
          ) : (
            <span>Runs in under an hour · saves to History automatically · progress streams live.</span>
          )}
        </div>
        <button type="submit" disabled={isLoading || !prompt.trim() || founderNeedsName} className="btn-primary shrink-0 px-8">
          {isLoading ? "Pipeline running…" : "Launch analysis"}
        </button>
      </div>
    </form>
  );
}
