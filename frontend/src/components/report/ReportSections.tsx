"use client";

import { forwardRef, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
}

interface Section {
  id: string;
  title: string;   // full original heading
  num: string | null; // leading section number ("0", "0.5", "12"), if any
  heading: string; // title without the number prefix
  navLabel: string; // compact label for the contents rail (parentheticals stripped)
  body: string;
}

function parseSections(md: string): Section[] {
  const out: Section[] = [];
  let title: string | null = null;
  let body: string[] = [];
  const make = (t: string): Omit<Section, "id" | "body"> => {
    const m = /^(\d+(?:\.\d+)?)[.)]?\s+(.*)$/.exec(t);
    const num = m ? m[1] : null;
    const heading = m ? m[2] : t;
    // Rail label: drop parentheticals and the compiler's verdict clause after a colon/dash.
    const navLabel =
      heading.replace(/\s*\([^)]*\)/g, "").split(/:|\s—\s/)[0].replace(/\s{2,}/g, " ").trim() || heading;
    return { title: t, num, heading, navLabel };
  };
  const flush = () => {
    if (title !== null) out.push({ id: `sec-${out.length}`, ...make(title), body: body.join("\n") });
  };
  for (const line of (md || "").split("\n")) {
    const m = /^##\s+(.+?)\s*$/.exec(line); // h2 only ("## " — not ### / ####)
    if (m) {
      flush();
      title = m[1];
      body = [];
    } else if (title !== null) {
      body.push(line);
    } else if (line.trim()) {
      title = "Overview";
      body = [line];
    }
  }
  flush();
  return out;
}

/** Left column: the full report split into anchored sections + a sticky nav.
 *  Exposes its container via ref so the parent can scroll to a company profile. */
const ReportSections = forwardRef<HTMLDivElement, Props>(function ReportSections({ markdown }, ref) {
  const sections = useMemo(() => parseSections(markdown), [markdown]);
  const [active, setActive] = useState<string>("");
  const observer = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    observer.current?.disconnect();
    observer.current = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-10% 0px -70% 0px", threshold: 0 }
    );
    sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.current?.observe(el);
    });
    return () => observer.current?.disconnect();
  }, [sections]);

  if (!sections.length) {
    return <p className="text-sm text-slate-500">No report content.</p>;
  }

  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="flex gap-8">
      {/* sticky contents rail (on the paper sheet — light). top-0 (not top-4): the pane's
          own padding scrolls with content, so a positive offset pushed the rail below the
          section headers even at rest. pt-1 mirrors the body's first:pt-1 for one baseline. */}
      <nav className="sticky top-0 hidden h-fit w-52 shrink-0 pt-1 lg:block">
        <div className="mb-3.5 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Contents</div>
        <ul className="space-y-[7px] border-l border-slate-200 pl-0">
          {sections.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => jump(s.id)}
                className={`group -ml-px flex w-full items-baseline gap-2.5 border-l-2 pl-3 text-left transition-colors ${
                  active === s.id
                    ? "border-blue-700 text-blue-800"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
                title={s.title}
              >
                <span
                  className={`w-5 shrink-0 text-right font-mono text-[10px] tabular-nums ${
                    active === s.id ? "font-semibold text-blue-700" : "font-medium text-slate-400 group-hover:text-slate-500"
                  }`}
                >
                  {s.num ?? "—"}
                </span>
                <span
                  className={`text-[11.5px] leading-snug ${active === s.id ? "font-semibold" : "font-normal"}`}
                >
                  {s.navLabel}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* report body */}
      <div ref={ref} className="min-w-0 flex-1">
        {sections.map((s) => (
          <section key={s.id} id={s.id} data-secnum={s.num ?? ""} className="scroll-mt-4 border-b border-slate-200/80 py-9 first:pt-1 last:border-0">
            <header className="mb-5">
              {s.num !== null && (
                <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-700">
                  Section {s.num}
                </div>
              )}
              <h2 className="mt-1.5 max-w-[40ch] font-serif text-[23px] font-semibold leading-[1.25] tracking-tight text-slate-900">
                {s.heading}
              </h2>
            </header>
            <article className="report-prose max-w-[72ch]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
            </article>
          </section>
        ))}
      </div>
    </div>
  );
});

export default ReportSections;
