"use client";

// The /app operator-console chrome: fixed left sidebar (view nav + owner chip) and a slim
// top bar (backend status + API key). Used ONLY by /app — the landing, /demo and /docs
// keep their marketing top-nav. Purely presentational: page.tsx owns the view state
// machine and passes `active` + `onNavigate`; the wordmark and "Home" both go home.

import { useEffect, useState, type ReactNode } from "react";
import { Mark } from "@/components/Wordmark";
import { Icon, type IconName } from "@/components/icons";
import { checkHealth, getStoredApiKey, setStoredApiKey } from "@/lib/api";

const SIDEBAR_BG = "bg-[#05070d]";

// The console's client-side views (page.tsx owns the state machine; the shell only
// paints active states and reports clicks). "home" doubles as the History surface.
export type ConsoleView = "home" | "sector" | "vc" | "founder" | "fund" | "tracked";

const WORKSPACE_ITEMS: { view: ConsoleView; label: string; icon: IconName }[] = [
  { view: "home", label: "Home", icon: "home" },
];

// Audience-labeled sections: a fund's surfaces and a founder's surface are different
// jobs — the sidebar says so instead of making users infer it.
// Verb-first labels: a nav item should say what clicking it DOES, not the feature's codename.
const INVESTOR_ITEMS: { view: ConsoleView; label: string; icon: IconName }[] = [
  { view: "vc", label: "Evaluate a Startup", icon: "target" },
  { view: "sector", label: "Analyze a Market", icon: "map" },
  { view: "tracked", label: "Tracked Deals", icon: "history" },
  { view: "fund", label: "My Fund", icon: "briefcase" },
];

const FOUNDER_ITEMS: { view: ConsoleView; label: string; icon: IconName }[] = [
  { view: "founder", label: "Evaluate My Startup", icon: "user" },
];

function NavButton({
  icon,
  label,
  active = false,
  collapsed,
  href,
  onClick,
}: {
  icon: IconName;
  label: string;
  active?: boolean;
  collapsed: boolean;
  href?: string;
  onClick?: () => void;
}) {
  const base = `group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 transition-colors ${
    active
      ? "bg-brand-600/15 text-brand-300"
      : "text-gray-500 hover:bg-gray-900 hover:text-gray-200"
  }`;
  const inner = (
    <>
      {/* hard "you are here" edge — also carries the active state on the collapsed rail */}
      {active && <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-brand-500" />}
      <Icon name={icon} className="h-4 w-4 shrink-0" />
      <span
        className={`${collapsed ? "hidden" : "hidden lg:inline"} font-mono text-[10.5px] font-medium uppercase tracking-[0.14em]`}
      >
        {label}
      </span>
    </>
  );
  return href ? (
    <a href={href} className={base} title={label}>
      {inner}
    </a>
  ) : (
    <button onClick={onClick} className={base} title={label}>
      {inner}
    </button>
  );
}

export default function ConsoleShell({
  children,
  active,
  onNavigate,
}: {
  children: ReactNode;
  // null = no view highlighted (a report is open or a run is in progress).
  active: ConsoleView | null;
  onNavigate: (view: ConsoleView) => void;
}) {
  const [collapsed, setCollapsedState] = useState(false);
  // Remembered chrome preference (post-mount read keeps SSR markup stable).
  useEffect(() => {
    try {
      if (localStorage.getItem("prospectus-sidebar-collapsed") === "1") setCollapsedState(true);
    } catch { /* private mode */ }
  }, []);
  const setCollapsed = (next: boolean | ((c: boolean) => boolean)) => {
    setCollapsedState((c) => {
      const v = typeof next === "function" ? next(c) : next;
      try { localStorage.setItem("prospectus-sidebar-collapsed", v ? "1" : "0"); } catch { /* ignore */ }
      return v;
    });
  };
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");

  // One probe on mount only — the chip reports readiness, it is not a monitor.
  useEffect(() => {
    let alive = true;
    checkHealth().then((ok) => {
      if (alive) setHealth(ok ? "ok" : "down");
    });
    return () => {
      alive = false;
    };
  }, []);

  // <lg the sidebar is always an icon rail; the chevron collapses it on lg too.
  const asideWidth = collapsed ? "w-14" : "w-14 lg:w-[230px]";
  const mainPad = collapsed ? "pl-14" : "pl-14 lg:pl-[230px]";

  return (
    <div className="min-h-screen bg-gray-950 print:bg-white">
      {/* ── Left sidebar ─────────────────────────────────────────────── */}
      <aside
        className={`no-print fixed inset-y-0 left-0 z-30 flex flex-col border-r border-gray-800/80 ${SIDEBAR_BG} ${asideWidth} transition-[width] duration-150`}
      >
        {/* Wordmark */}
        <div className={`flex h-14 items-center border-b border-gray-800/60 ${collapsed ? "justify-center px-0" : "justify-center px-0 lg:justify-between lg:px-4"}`}>
          <button
            onClick={() => onNavigate("home")}
            aria-label="Prospectus — console home"
            className="flex items-center gap-2.5"
          >
            <Mark className="h-6 w-6" />
            <span
              className={`${collapsed ? "hidden" : "hidden lg:inline"} text-sm font-semibold tracking-tight text-gray-100`}
            >
              Prospectus
            </span>
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`${collapsed ? "hidden" : "hidden lg:flex"} h-6 w-6 items-center justify-center rounded text-gray-600 transition-colors hover:bg-gray-900 hover:text-gray-300`}
          >
            <Icon name="chevron" className="h-3.5 w-3.5 rotate-90" />
          </button>
        </div>

        {/* Nav */}
        <nav className={`flex-1 space-y-0.5 overflow-y-auto py-3 ${collapsed ? "px-2" : "px-2 lg:px-3"}`}>
          <div className={`${collapsed ? "hidden" : "hidden lg:block"} px-2.5 pb-1.5 pt-1 font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-gray-600`}>
            Workspace
          </div>
          {WORKSPACE_ITEMS.map((it) => (
            <NavButton
              key={it.view}
              icon={it.icon}
              label={it.label}
              active={active === it.view}
              collapsed={collapsed}
              onClick={() => onNavigate(it.view)}
            />
          ))}

          <div className="my-3 border-t border-gray-800/60" />

          <div className={`${collapsed ? "hidden" : "hidden lg:block"} px-2.5 pb-1.5 font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-gray-600`}>
            Investor
          </div>
          {INVESTOR_ITEMS.map((it) => (
            <NavButton
              key={it.view}
              icon={it.icon}
              label={it.label}
              active={active === it.view}
              collapsed={collapsed}
              onClick={() => onNavigate(it.view)}
            />
          ))}

          <div className="my-3 border-t border-gray-800/60" />

          <div className={`${collapsed ? "hidden" : "hidden lg:block"} px-2.5 pb-1.5 font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-gray-600`}>
            Founder
          </div>
          {FOUNDER_ITEMS.map((it) => (
            <NavButton
              key={it.view}
              icon={it.icon}
              label={it.label}
              active={active === it.view}
              collapsed={collapsed}
              onClick={() => onNavigate(it.view)}
            />
          ))}

          <div className="my-3 border-t border-gray-800/60" />

          <div className={`${collapsed ? "hidden" : "hidden lg:block"} px-2.5 pb-1.5 font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-gray-600`}>
            Resources
          </div>
          <NavButton icon="grid" label="Examples" collapsed={collapsed} href="/demo" />
          <NavButton icon="doc" label="Docs" collapsed={collapsed} href="/docs" />
          <NavButton icon="presentation" label="Intro Deck" collapsed={collapsed} href="/deck.html" />

          {/* Expand affordance when collapsed on lg */}
          <button
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            className={`${collapsed ? "lg:flex" : "hidden"} mt-3 hidden w-full items-center justify-center rounded-md py-2 text-gray-600 transition-colors hover:bg-gray-900 hover:text-gray-300`}
          >
            <Icon name="chevron" className="h-3.5 w-3.5 -rotate-90" />
          </button>
        </nav>

        {/* Owner chip */}
        <div className={`border-t border-gray-800/60 py-3 ${collapsed ? "px-2" : "px-2 lg:px-4"}`}>
          <div className={`flex items-center gap-2.5 ${collapsed ? "justify-center" : "justify-center lg:justify-start"}`}>
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-500/40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <div className={`${collapsed ? "hidden" : "hidden lg:block"} min-w-0`}>
              <div className="truncate text-[12px] font-medium text-gray-300">Prospectus Console</div>
              <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-gray-600">Local workspace</div>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main area ────────────────────────────────────────────────── */}
      <div className={`${mainPad} bg-atmosphere min-h-screen transition-[padding] duration-150 print:bg-none print:pl-0`}>
        {/* Slim top bar: system status + API key */}
        <div className="no-print sticky top-0 z-20 flex h-12 items-center justify-end gap-2 border-b border-gray-800/70 bg-gray-950/85 px-4 backdrop-blur">
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] ${
              health === "ok"
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-400"
                : health === "down"
                  ? "border-amber-900/60 bg-amber-950/30 text-amber-400"
                  : "border-gray-800 bg-gray-900/60 text-gray-500"
            }`}
            title="Backend health (checked on load)"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                health === "ok" ? "bg-emerald-500" : health === "down" ? "bg-amber-500" : "animate-pulse bg-gray-600"
              }`}
            />
            {health === "ok" ? "Pipeline ready" : health === "down" ? "Backend unreachable" : "Checking"}
          </span>
          <button
            onClick={() => {
              const next = window.prompt("API key for this deployment (leave empty to clear):", getStoredApiKey());
              if (next !== null) setStoredApiKey(next.trim());
            }}
            title="Set the X-API-Key used for requests (required on secured deployments)"
            aria-label="Set API key"
            className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-200"
          >
            <Icon name="key" className="h-4 w-4" />
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}
