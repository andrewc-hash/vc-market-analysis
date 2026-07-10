import type { TaskStatusResponse } from "@/lib/api";
import { reportGolden } from "./reportGolden";
import vcMedicalScribes from "./demo/vcMedicalScribes.json";
import founderNeuroscribe from "./demo/founderNeuroscribe.json";

// The public demo renders REAL multi-agent pipeline outputs (baked to JSON) — no backend,
// no API keys, no waiting, no cost. Three scenarios cover every mode of the product.

export interface DemoScenario {
  id: string;
  tag: string;
  title: string;
  subtitle: string;
  config: { sector: string; stage: string; mode: "VC" | "Founder"; target?: string };
  result: TaskStatusResponse;
}

function wrap(id: string, finalReport: unknown): TaskStatusResponse {
  return {
    task_id: id,
    status: "SUCCESS",
    current_phase: "compile_report",
    iterations_completed: 3,
    agent_logs: [],
    final_report: finalReport as Record<string, unknown>,
    error: null,
  };
}

export const demoScenarios: DemoScenario[] = [
  {
    id: "vc-sector",
    tag: "VC · Sector scan",
    title: "Analyze a sector",
    subtitle: "A full field of startups — scored, mapped on a 2×2, and ranked by a weighted index.",
    config: { sector: "AI Agent Security & Runtime Governance", stage: "Seed – Series B", mode: "VC" },
    result: reportGolden,
  },
  {
    id: "vc-target",
    tag: "VC · Track a target",
    title: "Sector + a specific startup",
    subtitle: "Force-include a named startup (Abridge) and rank it against the discovered field.",
    config: { sector: "AI Ambient Clinical Documentation", stage: "Series A", mode: "VC", target: "Abridge" },
    result: wrap("demo-vc-target", vcMedicalScribes),
  },
  {
    id: "founder",
    tag: "Founder · Test my startup",
    title: "Pitch your idea to the market",
    subtitle: "A stealth ICU-scribe scored at low confidence, centered with a build/pass verdict.",
    config: { sector: "AI Ambient Clinical Documentation", stage: "Seed", mode: "Founder", target: "NeuroScribe AI" },
    result: wrap("demo-founder", founderNeuroscribe),
  },
];
