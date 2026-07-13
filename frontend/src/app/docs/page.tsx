import type { Metadata } from "next";
import { Icon, type IconName } from "@/components/icons";
import { Wordmark } from "@/components/Wordmark";

export const metadata: Metadata = {
  title: "Docs — Prospectus",
  description: "What you get, why the numbers hold up, and how to run it.",
};

// Static, VC-facing documentation. Benefit-first, plain language, no engineering jargon.

const Card = ({ icon, title, children }: { icon: IconName; title: string; children: React.ReactNode }) => (
  <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-500/10 text-brand-300">
        <Icon name={icon} className="h-3.5 w-3.5" />
      </span>
      <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
    </div>
    <p className="mt-2 text-[13px] leading-relaxed text-gray-400">{children}</p>
  </div>
);

const Row = ({ n, title, children }: { n: string; title: string; children: React.ReactNode }) => (
  <div className="flex gap-4 border-b border-gray-800 py-4 last:border-0">
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-brand-500/40 bg-brand-500/10 text-xs font-semibold tabular-nums text-brand-300">{n}</span>
    <div>
      <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
      <p className="mt-1 text-[13px] leading-relaxed text-gray-400">{children}</p>
    </div>
  </div>
);

const K = ({ children }: { children: React.ReactNode }) => <span className="font-medium text-gray-200">{children}</span>;

// One stage on the agent roadmap: model chip + what it consumes / produces.
const RoadStage = ({ role, model, inputs, outputs, note, accent = false, last = false }: {
  role: string; model: string; inputs: string; outputs: string; note?: string; accent?: boolean; last?: boolean;
}) => (
  <div className="relative flex gap-4">
    <div className="flex flex-col items-center">
      <span className={`z-10 mt-1 h-3 w-3 shrink-0 rounded-full ring-4 ring-gray-950 ${accent ? "bg-brand-500" : "bg-gray-600"}`} />
      {!last && <span className="w-px flex-1 bg-gray-800" aria-hidden />}
    </div>
    <div className={`mb-4 w-full rounded-lg border p-3.5 ${accent ? "border-brand-500/40 bg-brand-500/5" : "border-gray-800 bg-gray-900"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className={`text-sm font-semibold ${accent ? "text-brand-300" : "text-gray-100"}`}>{role}</h3>
        <span className="rounded-md border border-gray-800 bg-gray-950/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-gray-500">{model}</span>
      </div>
      <div className="mt-2 grid gap-1.5 text-[12.5px] leading-relaxed sm:grid-cols-2">
        <div><div className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Takes in</div><div className="text-gray-400">{inputs}</div></div>
        <div><div className="text-[10px] font-semibold uppercase tracking-wide text-brand-400/80">Hands off</div><div className="text-gray-300">{outputs}</div></div>
      </div>
      {note && <p className="mt-2 border-t border-gray-800 pt-2 text-[11.5px] text-gray-500">{note}</p>}
    </div>
  </div>
);

const SeatItem = ({ children }: { children: React.ReactNode }) => (
  <li className="flex gap-2 text-[12.5px] leading-relaxed text-gray-400">
    <span className="mt-0.5 text-brand-400">·</span>
    <span>{children}</span>
  </li>
);

export default function DocsPage() {
  return (
    <>
      <header className="no-print sticky top-0 z-30 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <Wordmark href="/" />
          <nav className="flex items-center gap-1 text-[13px]">
            <a href="/app" className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100">Open the app</a>
            <a href="/demo" className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100">
              Examples
              <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        <div className="mb-10">
          <div className="kicker">Documentation</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-gray-100">
            A first-pass IC memo on any market, <span className="text-brand-400">in 20 minutes</span>.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-gray-400">
            Name a sector — or a specific company — and get the document an associate would take a week to draft:
            the field mapped and ranked, the financials benchmarked by stage, the return math worked, and a
            recommendation at a price. Every number checkable back to its source.
          </p>
        </div>

        {/* WHAT YOU GET */}
        <div className="kicker">What you get</div>
        <h2 className="mb-4 mt-1 text-xl font-semibold tracking-tight text-gray-100">The deliverable</h2>
        <div className="card space-y-3 text-[13px] leading-relaxed text-gray-400">
          <p>
            <K>A 13-section memo that leads with the verdict</K> — top pick and INVEST / WATCH / PASS at a stated
            valuation, the one non-consensus insight, the single variable the bet turns on, and a dated prediction
            you can hold it to. Then market sizing built bottoms-up (accounts × ACV, not a Gartner quote), incumbent
            threat with a window clock, startup profiles, team assessment, risks with kill criteria, and
            probability-weighted return scenarios anchored to real acquisition precedents.
          </p>
          <p>
            <K>The instrument panel beside it:</K> a 2×2 market map with the white space marked · a weighted scorecard
            (your weights, applied exactly) with the a16z moat breakdown · letter grades per startup · the financial
            ledger with every metric flagged against its stage benchmark · exit precedents · and a fund-fit panel.
          </p>
          <p>
            <K>Exports built to be forwarded:</K> a full PDF with every visual, a one-page tear sheet for the partner
            meeting, Markdown, and raw JSON. Every run is saved to History and can be re-run later to see what changed.
          </p>
        </div>

        {/* AGENT ROADMAP */}
        <div className="mt-10">
          <div className="kicker">The agent roadmap</div>
          <h2 className="mb-4 mt-1 text-xl font-semibold tracking-tight text-gray-100">How the answer gets made</h2>

          <div className="mb-4 rounded-lg border border-dashed border-gray-700 bg-gray-900/40 p-3.5">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">You provide</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11px]">
              {["A market prompt — or just a startup name", "Pitch deck / docs", "Founder-call recording or transcript",
                "Cap-table CSV", "Weights · stage · geography · Bear/Base/Bull", "Fund size + check (optional)"].map((t) => (
                <span key={t} className="rounded-md border border-gray-800 bg-gray-900 px-2 py-0.5 text-gray-400">{t}</span>
              ))}
            </div>
          </div>

          <RoadStage role="1 · Intake" model="parsing · transcription · vision"
            inputs="Whatever you attached — decks (even image-only), docs, call audio, the cap-table CSV."
            outputs="Clean source material: the deck as text, the founder's claims pulled from the call with timestamps, real round terms from the cap table — plus the market scope, auto-derived if you left the prompt blank." />
          <RoadStage role="2 · Researcher" model="Gemini 2.5 Pro · live web"
            inputs="The scoped assignment, your materials, and the founder claims to check."
            outputs="A dated, source-linked brief: 6–8 startups profiled with financials, incumbents and their roadmaps, regulation, the acquisition tape, and a verdict on each founder claim — 35–45 searches, fresh-news pass on every company."
            note="Facts only, no opinions. If it isn't found here, it can't appear in the memo — nothing downstream can search." />
          <RoadStage role="3 · Two analysts, in parallel" model="Gemini 2.5 Pro ∥ Claude Sonnet 4.6"
            inputs="The identical brief — independently, neither sees the other."
            outputs="Two competing full analyses, each with raw 0–100 scores per company per dimension, a thesis, and return scenarios. Bear case argued first." />
          <RoadStage role="4 · Referee" model="GPT-4.1 · up to 3 rounds" accent
            inputs="Both analyses, side by side."
            outputs="Their genuine disagreements, sent back to both analysts to re-argue until they converge."
            note="The referee never scores — disagreement between two different AI vendors is the error-detection step a single chatbot doesn't have." />
          <RoadStage role="5 · Compile + compute" model="Gemini 2.5 Pro + code" last
            inputs="The converged analyses, plus the numbers software computed from them: reconciled scores, your weights applied, return ranges, fund math, claim verdicts."
            outputs="One memo where every figure matches the computed artifacts — plus the map, ledger, grades, and a methodology section stating what was and wasn't checked." />

          <div className="rounded-lg border border-brand-500/30 bg-brand-500/5 p-3.5">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-brand-300">You get</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11px]">
              {["Verdict-first memo", "Scored market map", "Weighted scorecard + moats", "Letter grades", "Ledger · scenarios · exit precedents",
                "Fund-fit panel", "Founder-claim audit", "PDF · tear sheet · Markdown · JSON", "Re-runnable history"].map((t) => (
                <span key={t} className="rounded-md border border-brand-500/30 bg-gray-900 px-2 py-0.5 text-gray-300">{t}</span>
              ))}
            </div>
          </div>
        </div>

        {/* TWO SEATS — VC vs Founder */}
        <div className="mt-10">
          <div className="kicker">Two seats at the table</div>
          <h2 className="mb-1 mt-1 text-xl font-semibold tracking-tight text-gray-100">Same engine, opposite questions</h2>
          <p className="mb-4 text-[13px] text-gray-500">
            Both modes run the same research and debate. What changes is <K>whose decision the memo serves</K> —
            and that rewrites the verdict, the return math, and which sections exist at all.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <div className="kicker text-brand-300">VC · Evaluate a target</div>
              <h3 className="mb-2 mt-1 text-sm font-semibold text-gray-100">&ldquo;Should I write a check into this company — at what price?&rdquo;</h3>
              <ul className="space-y-1.5">
                <SeatItem><K>Verdict:</K> INVEST / WATCH / PASS at or below a stated valuation, anchored to the company&rsquo;s last-round terms.</SeatItem>
                <SeatItem><K>The deal vs the field:</K> your target is ranked inside its real competitive field — and when it isn&rsquo;t the #1-quality asset, the memo must argue price-adjusted return vs the better company (quality rank ≠ best investment).</SeatItem>
                <SeatItem><K>Return math is the buyer&rsquo;s:</K> the deal&rsquo;s own probability-weighted scenarios at its entry price — plus turns-of-your-fund and required exit when you add your fund&rsquo;s numbers.</SeatItem>
                <SeatItem><K>On WATCH/PASS:</K> a &ldquo;Deal Path&rdquo; — the measurable, dated conditions that would change the answer, and the price at which today&rsquo;s evidence would clear.</SeatItem>
              </ul>
            </div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <div className="kicker text-brand-300">Founder · Test my startup</div>
              <h3 className="mb-2 mt-1 text-sm font-semibold text-gray-100">&ldquo;Should I keep building this — and will it raise?&rdquo;</h3>
              <ul className="space-y-1.5">
                <SeatItem><K>Verdict:</K> two calls, not one — &ldquo;Investor check: fundable today?&rdquo; and &ldquo;Founder call: BUILD / KEEP GOING / PIVOT / STOP&rdquo; — with whether weak scores are stage-normal or genuinely alarming.</SeatItem>
                <SeatItem><K>A founder-only section (§0.5):</K> a repositioning plan — 2–4 moves aimed at your weakest <i>computed</i> scores, exactly one &ldquo;what NOT to change&rdquo;, a sequenced 90-day plan, and the fastest self-runnable signal to quit.</SeatItem>
                <SeatItem><K>Return math is YOUR raise:</K> round size, target post-money benchmarked to named comps, implied dilution and your ownership after, conditions a lead will require to close — never a competitor&rsquo;s multiple dressed up as yours.</SeatItem>
                <SeatItem><K>Your materials get audited:</K> deck stats and call claims are verified against the public record — including what the deck contradicts about itself.</SeatItem>
              </ul>
            </div>
          </div>
          <p className="mt-3 text-[12px] text-gray-500">
            In both modes your company is always scored — never dropped as &ldquo;too early&rdquo; — and its data
            confidence is labeled rather than hidden.
          </p>
        </div>

        {/* WHY TRUST */}
        <div className="mt-10">
          <div className="kicker">Why the numbers hold up</div>
          <h2 className="mb-4 mt-1 text-xl font-semibold tracking-tight text-gray-100">Built to be audited, not just read</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Card icon="check" title="Two analysts argue before you read anything">
              Two independent AI analysts — on different providers (Google and Anthropic) — write competing analyses
              from the same research, and a third-party referee forces them to resolve every disagreement before the
              memo is compiled. Where one model hallucinates, the other contests it.
            </Card>
            <Card icon="key" title="Software does the math, not the AI">
              Rankings, return ranges, dilution, multiples, grades, and fund math are calculated by code from the
              analysts&rsquo; raw inputs. That&rsquo;s why the scorecard never contradicts the map, the headline return
              always equals its own scenario table, and your weight sliders have an exact effect.
            </Card>
            <Card icon="clock" title="Researched live, dated, and linked">
              35–45 web searches per run with a fresh-news pass on every startup — so last month&rsquo;s round or
              acquisition is in the memo. Citations are taken from the actual searches (fabricated links can&rsquo;t
              survive), and a &ldquo;Data as of&rdquo; badge warns when evidence is stale.
            </Card>
            <Card icon="alert" title="It tells you what it doesn't know">
              Undisclosed metrics say &ldquo;Not Disclosed&rdquo; — never a guess. Thin-data companies get approximate
              (≈) scores instead of false precision, and every memo ends with what was and was not diligenced.
            </Card>
          </div>
        </div>

        {/* DIFFERENTIATORS */}
        <div className="mt-10">
          <div className="kicker">What a chatbot can&rsquo;t do</div>
          <h2 className="mb-4 mt-1 text-xl font-semibold tracking-tight text-gray-100">Three things you won&rsquo;t get from ChatGPT</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card icon="alert" title="It cross-examines the founder">
              Upload the pitch-call recording. Every factual claim — ARR, pilots, pedigree — is pulled out with its
              timestamp and checked against the public record <i>and</i> the deck. Contradictions are flagged, with
              the conflicting source.
            </Card>
            <Card icon="key" title="It answers for YOUR fund">
              Give it your fund size and check (plus the cap table for real entry terms): it computes your ownership
              at exit, turns-of-fund, the exact exit needed to return the fund, and net IRR. The same deal is a pass
              at $500M AUM and a fund-maker at $50M.
            </Card>
            <Card icon="refresh" title="It grades its own past calls">
              Re-run any saved memo months later: it shows who entered, who got acquired, what re-priced — and grades
              its own dated predictions as validated, broken, or pending. Ask a chatbot to do that.
            </Card>
          </div>
        </div>

        {/* HOW TO RUN */}
        <div className="mt-10">
          <div className="kicker">Running it</div>
          <h2 className="mb-4 mt-1 text-xl font-semibold tracking-tight text-gray-100">Three ways in, one form</h2>
          <div className="card">
            <Row n="1" title="Pick your seat">
              <K>Sector scan</K> — describe a market, get the field mapped and ranked. <K>Evaluate a target</K> — name
              a company; it&rsquo;s ranked inside its real competitive field with a verdict at a price.
              <K> Founder mode</K> — test your own startup: a build/pass call, a repositioning plan aimed at your
              weakest scores, and your fundraise math.
            </Row>
            <Row n="2" title="Attach what you have (optional)">
              Deck (image-only PDFs are read fine), docs, the founder-call recording or transcript, a cap-table CSV,
              your fund size and check. Stealth companies work — leave the prompt blank and it identifies the market
              from the startup for you to confirm. Set weights, stage, geography, and a Bear / Base / Bull posture.
            </Row>
            <Row n="3" title="Launch, then read verdict-first">
              ~15–25 minutes; you can watch the analysts debate live. The memo opens on the call, not the throat-
              clearing. Download the PDF or tear sheet, or re-run it next quarter to see what changed.
            </Row>
          </div>
        </div>

        {/* BOUNDARY */}
        <div className="mt-10 rounded-lg border border-amber-900/40 bg-amber-950/15 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-300">
            <Icon name="alert" className="h-4 w-4" />
            What this is not
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-amber-200/70">
            Decision-support, not investment advice — a first-pass screen, not diligence. Figures come from public
            sources and can be wrong; verify anything material. Returns are scenario multiples (gross unless labeled
            net). References, legal, and private financials are not checked. Every memo states this about itself.
          </p>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <a href="/demo" className="btn-primary">See three real memos</a>
          <a href="/app" className="btn-secondary">Run your own</a>
        </div>

        <footer className="mt-12 border-t border-gray-800 pt-5 text-center text-xs text-gray-500">
          Decision-support only — not investment advice.
          <span className="mx-2 text-gray-700">|</span>
          <a href="/terms" className="underline hover:text-gray-300">Terms of Use</a>
        </footer>
      </main>
    </>
  );
}
