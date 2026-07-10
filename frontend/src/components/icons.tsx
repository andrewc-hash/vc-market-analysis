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
  | "refresh";

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
