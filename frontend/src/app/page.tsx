import { Icon, type IconName } from "@/components/icons";
import { Wordmark } from "@/components/Wordmark";

// The front door. Static, backend-free — greets a visitor, states what Prospectus is,
// and routes them to a live memo (/demo), the console (/app), or the docs.

const Trust = ({ icon, title, children }: { icon: IconName; title: string; children: React.ReactNode }) => (
  <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-500/10 text-brand-300">
        <Icon name={icon} className="h-3.5 w-3.5" />
      </span>
      <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
    </div>
    <p className="mt-2 text-[13px] leading-relaxed text-gray-400">{children}</p>
  </div>
);

export default function Landing() {
  return (
    <>
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <Wordmark href="/" />
          <nav className="flex items-center gap-1 text-[13px]">
            <a href="/demo" className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100">Examples</a>
            <a href="/docs" className="rounded-md px-2.5 py-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-100">Docs</a>
            <a href="/app" className="ml-1 rounded-md bg-brand-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-brand-500">Open the app</a>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-3xl px-4 pb-14 pt-20 text-center">
          <div className="mb-5 flex justify-center">
            <Wordmark href={null} markClass="h-11 w-11" showText={false} />
          </div>
          <div className="kicker text-center">Institutional market analysis, on demand</div>
          <h1 className="mt-2 font-serif text-4xl font-semibold leading-tight tracking-tight text-gray-100 sm:text-5xl">
            The first-pass prospectus <span className="text-brand-400">on any market.</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-gray-400">
            Name a sector — or a single startup — and Prospectus returns the document an associate
            would take a week to draft: the field mapped and ranked, financials benchmarked by stage,
            the return math worked, and a recommendation at a price. In about 20 minutes.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <a href="/demo" className="btn-primary">See a live memo</a>
            <a href="/app" className="btn-secondary">Open the app</a>
          </div>
          <p className="mt-3 text-xs text-gray-600">No sign-up to explore the examples · decision-support, not investment advice</p>
        </section>

        {/* What you get */}
        <section className="mx-auto max-w-4xl px-4 pb-14">
          <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
            <div className="kicker">The deliverable</div>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-gray-300">
              A 13-section, <span className="font-medium text-gray-100">verdict-first memo</span> — top pick and
              INVEST / WATCH / PASS at a stated valuation, the one non-consensus insight, and a dated prediction —
              beside a live instrument panel: a 2×2 market map, a weighted scorecard with the a16z moat breakdown,
              per-startup letter grades, a stage-benchmarked financial ledger, exit precedents, and a fund-fit panel.
              Export a full PDF, a one-page tear sheet, Markdown, or JSON.
            </p>
          </div>
        </section>

        {/* Why trust it */}
        <section className="mx-auto max-w-4xl px-4 pb-16">
          <div className="mb-4 text-center">
            <div className="kicker text-center">Why the numbers hold up</div>
            <h2 className="mt-1 text-xl font-semibold tracking-tight text-gray-100">Built to be audited, not just read</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Trust icon="check" title="Two AIs argue before you read a word">
              Independent analysts on different providers (Google and Anthropic) write competing analyses; a third-party
              referee forces every disagreement to resolution. Where one model hallucinates, the other contests it.
            </Trust>
            <Trust icon="key" title="Software does the math, not the AI">
              Rankings, return ranges, dilution, multiples, grades, and fund math are computed in code from the analysts&rsquo;
              raw inputs — so the scorecard can&rsquo;t contradict the map and your weights have an exact effect.
            </Trust>
            <Trust icon="clock" title="Researched live, dated, and linked">
              35–45 web searches per run with a fresh-news pass on every startup, citations taken from the actual searches,
              and a &ldquo;Data as of&rdquo; badge that flags stale evidence.
            </Trust>
            <Trust icon="alert" title="It tells you what it doesn't know">
              Undisclosed metrics say &ldquo;Not Disclosed,&rdquo; thin-data companies get approximate scores, and every
              memo ends with what was and wasn&rsquo;t diligenced.
            </Trust>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a href="/demo" className="btn-primary">Explore three real memos</a>
            <a href="/docs" className="btn-secondary">How it works</a>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-gray-800">
          <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-xs text-gray-500 sm:flex-row">
            <Wordmark href="/" markClass="h-4 w-4" textClass="text-xs" />
            <div>
              Decision-support only — not investment advice.
              <span className="mx-2 text-gray-700">|</span>
              <a href="/terms" className="underline hover:text-gray-300">Terms of Use</a>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
