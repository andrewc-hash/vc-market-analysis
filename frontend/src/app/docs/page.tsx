import type { Metadata } from "next";
import { Icon, type IconName } from "@/components/icons";

export const metadata: Metadata = {
  title: "Docs — VC Market Analysis Engine",
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

export default function DocsPage() {
  return (
    <>
      <header className="no-print sticky top-0 z-30 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <a href="/" className="flex items-center gap-2.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-sm bg-brand-600 text-[11px] font-bold leading-none text-white">V</span>
            <span className="text-sm font-semibold text-gray-100">VC Market Analysis</span>
            <span className="hidden text-[10px] font-medium uppercase tracking-[0.2em] text-gray-500 sm:inline">Engine</span>
          </a>
          <nav className="flex items-center gap-1 text-[13px]">
            <a href="/" className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100">New analysis</a>
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
          <a href="/" className="btn-secondary">Run your own</a>
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
