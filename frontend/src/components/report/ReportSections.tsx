"use client";

import { forwardRef, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
}

interface Section {
  id: string;
  title: string;
  body: string;
}

function parseSections(md: string): Section[] {
  const out: Section[] = [];
  let title: string | null = null;
  let body: string[] = [];
  const flush = () => {
    if (title !== null) out.push({ id: `sec-${out.length}`, title, body: body.join("\n") });
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
    <div className="flex gap-6">
      {/* sticky section nav (on the paper sheet — light) */}
      <nav className="sticky top-4 hidden h-fit w-44 shrink-0 lg:block">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Contents</div>
        <ul className="space-y-1 border-l border-slate-200 text-xs">
          {sections.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => jump(s.id)}
                className={`block w-full truncate pl-3 text-left transition-colors ${
                  active === s.id
                    ? "-ml-px border-l-2 border-blue-700 font-semibold text-blue-800"
                    : "text-slate-500 hover:text-slate-800"
                }`}
                title={s.title}
              >
                {s.title}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* report body */}
      <div ref={ref} className="min-w-0 flex-1">
        {sections.map((s) => (
          <section key={s.id} id={s.id} className="scroll-mt-4 border-b border-slate-100 pb-6 pt-2">
            <h2 className="mb-3 font-serif text-xl font-semibold text-slate-900">{s.title}</h2>
            <article className="report-prose max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
            </article>
          </section>
        ))}
      </div>
    </div>
  );
});

export default ReportSections;
