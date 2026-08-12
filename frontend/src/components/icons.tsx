// Tiny local inline-SVG icon set (no dependency) — replaces emoji chrome.
// Stroke-based 24px glyphs; `filled` toggles fill for star/alert states.

export type IconName =
  | "menu"
  | "key"
  | "download"
  | "chevron"
  | "star"
  | "pencil"
  | "trash"
  | "x"
  | "check"
  | "alert"
  | "arrow-right"
  | "clock"
  | "refresh"
  | "play"
  | "plus"
  | "doc"
  | "grid"
  | "presentation"
  | "home"
  | "map"
  | "target"
  | "user"
  | "briefcase"
  | "history"
  | "copy";

const PATHS: Record<IconName, React.ReactNode> = {
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  key: (
    <>
      <circle cx="16.5" cy="7.5" r="4" />
      <path d="M13.7 10.3 4 20v-3h3v-3h2l1.6-1.6" />
    </>
  ),
  download: <path d="M12 3v12M6 11l6 6 6-6M5 21h14" />,
  chevron: <path d="M6 9l6 6 6-6" />,
  star: <path d="M12 3l2.7 5.6 6.1.8-4.5 4.2 1.1 6L12 16.7l-5.4 2.9 1.1-6L3.2 9.4l6.1-.8L12 3z" />,
  pencil: <path d="M4 20l4-1L19.5 7.5a2.12 2.12 0 0 0-3-3L5 16l-1 4z" />,
  trash: <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v5M14 11v5" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  check: <path d="M4 12l5 5L20 7" />,
  alert: <path d="M12 3 2 20h20L12 3zM12 9v5M12 17.2v.01" />,
  "arrow-right": <path d="M4 12h16M13 5l7 7-7 7" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </>
  ),
  refresh: <path d="M20 11a8 8 0 1 0-2.3 6.3M20 5v6h-6" />,
  play: <path d="M7 5l12 7-12 7V5z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  doc: <path d="M7 3h7l5 5v13H7V3zM14 3v5h5" />,
  grid: (
    <>
      <rect x="4" y="4" width="7" height="7" rx="1" />
      <rect x="13" y="4" width="7" height="7" rx="1" />
      <rect x="4" y="13" width="7" height="7" rx="1" />
      <rect x="13" y="13" width="7" height="7" rx="1" />
    </>
  ),
  presentation: <path d="M3 4h18M5 4v11h14V4M12 15v3M8 21l4-3 4 3" />,
  home: <path d="M3 11l9-8 9 8M5 9.5V21h14V9.5M9.5 21v-6h5v6" />,
  map: <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" />,
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4" />
      <path d="M12 11.9v.2" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 20.5c.8-3.6 3.9-5.5 7.5-5.5s6.7 1.9 7.5 5.5" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3" y="7.5" width="18" height="12.5" rx="2" />
      <path d="M9 7.5V5.5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12.5h18M12 11v3" />
    </>
  ),
  // Clock with a counter-clockwise arrow (the "Tracked" longitudinal view).
  history: (
    <>
      <path d="M3.2 12a8.8 8.8 0 1 0 2.6-6.2L3.2 8.4" />
      <path d="M3.2 3.4v5h5" />
      <path d="M12 7.6V12l3 2.2" />
    </>
  ),
  // Two offset sheets (the "copy to clipboard" verdict action).
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 4 3h9A1.5 1.5 0 0 1 14.5 4.5V5" />
    </>
  ),
};

export function Icon({
  name,
  className = "h-4 w-4",
  filled = false,
}: {
  name: IconName;
  className?: string;
  filled?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      {PATHS[name]}
    </svg>
  );
}
