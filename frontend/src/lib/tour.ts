// Client-side fallback for the Present-mode tour: builds the same beat list the
// backend emits, from merged_report alone, so Present works on /demo fixtures and
// History runs that predate the `tour` artifact.

import type { FinalReport, TourStep } from "./api";

interface Beat {
  id: string;
  title: string;
  section: number;
  visual: TourStep["visual"];
}

const BEATS: Beat[] = [
  { id: "verdict", title: "The Investment Take", section: 0, visual: "none" },
  { id: "repositioning", title: "Strategic Repositioning", section: 0.5, visual: "none" },
  { id: "why_now", title: "Why Now", section: 2, visual: "none" },
  { id: "field", title: "The Field", section: 3, visual: "map" },
  { id: "scores", title: "The Scorecard", section: 7, visual: "scorecard" },
  { id: "money", title: "The Money", section: 6, visual: "ledger" },
  { id: "risks", title: "What Would Make Us Wrong", section: 11, visual: "none" },
  { id: "returns", title: "Return Math", section: 12, visual: "fundfit" },
  { id: "beliefs", title: "What We Must Believe", section: 12, visual: "none" },
];

/** Split merged_report on the canonical `## N. Name` headers → section number → body. */
function splitSections(md: string): Record<string, string> {
  const out: Record<string, string> = {};
  const headers = Array.from(md.matchAll(/^##\s+(.+)$/gm));
  headers.forEach((m, i) => {
    const num = m[1].match(/^(\d+(?:\.\d+)?)[.\s]/)?.[1];
    if (!num || out[num] !== undefined) return;
    const start = (m.index ?? 0) + m[0].length;
    const end = headers[i + 1]?.index ?? md.length;
    out[num] = md.slice(start, end);
  });
  return out;
}

/** First 1–2 prose sentences of a section body, stripped of markdown chrome.
 * List-only sections (e.g. risks, What We Must Believe) fall back to the first
 * top-level list items. */
function firstSentences(body: string, n = 2): string {
  const lines = body.split("\n");
  const prose: string[] = [];
  for (const line of lines) {
    const t = line.trim();
    if (!t || /^(#|\||>|[-*+]\s|\d+\.\s|-{3,}|_{3,})/.test(t)) {
      if (prose.length) break;
      continue;
    }
    prose.push(t);
  }
  // A bare lead-in line ("What Would Make Us Wrong:") isn't a summary — take the list.
  let source = prose;
  if (prose.join(" ").length < 40) {
    const listItems: string[] = [];
    for (const line of lines) {
      const item = line.trim().match(/^(?:[-*+]|\d+\.)\s+(.+)$/);
      if (item && !/^(?:[-*+]|\d+\.)\s/.test(item[1])) listItems.push(item[1]);
      if (listItems.length >= n) break;
    }
    if (listItems.length) source = listItems;
  }
  const text = source
    .slice(0, n)
    .join(" ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  // Token-based sentence split (no lookbehind — es5 target): a sentence ends on a
  // word ending in .!? (decimals like "$1.5B" never end a token with punctuation).
  const sentences: string[] = [];
  let buf = "";
  for (const word of text.split(" ")) {
    buf = buf ? `${buf} ${word}` : word;
    if (/[.!?]["')\]]*$/.test(word)) {
      sentences.push(buf);
      buf = "";
      if (sentences.length >= n) break;
    }
  }
  if (sentences.length < n && buf) sentences.push(buf);
  return sentences.slice(0, n).join(" ").trim();
}

/** Body of a `### <name>` subsection within a section body, or null when absent. */
function subsection(body: string, name: string): string | null {
  const m = body.match(new RegExp(`^###\\s+.*${name}.*$`, "m"));
  if (!m || m.index == null) return null;
  const rest = body.slice(m.index + m[0].length);
  const end = rest.search(/^#{2,3}\s/m);
  return end >= 0 ? rest.slice(0, end) : rest;
}

export function buildFallbackTour(report: FinalReport): TourStep[] {
  const md = report.merged_report || report.synthesis || "";
  if (!md) return [];
  const sections = splitSections(md);
  const steps: TourStep[] = [];

  for (const beat of BEATS) {
    const body = sections[String(beat.section)];
    if (body === undefined) continue;

    let summary: string;
    if (beat.id === "beliefs") {
      const sub = subsection(body, "What We Must Believe");
      if (sub === null) continue;
      summary = firstSentences(sub);
    } else if (beat.id === "verdict" && report.recommended_pick) {
      summary = `Recommended pick: ${report.recommended_pick}. ${firstSentences(body, 1)}`.trim();
    } else {
      summary = firstSentences(body);
    }
    if (!summary) continue;

    steps.push({
      id: beat.id,
      title: beat.title,
      summary,
      section: beat.section,
      visual: beat.visual,
      source: "fallback",
    });
  }
  return steps;
}
