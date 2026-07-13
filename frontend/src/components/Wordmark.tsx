// The Prospectus identity, defined once and reused in every header + the landing hero
// (previously the logo markup was copy-pasted across page/demo/docs and drifted).

export function Mark({ className = "h-5 w-5" }: { className?: string }) {
  // Azure rounded square + a faceted diamond — a "prospectus / seal of rigor" mark.
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-md bg-brand-600 ${className}`}>
      <svg viewBox="0 0 24 24" className="h-1/2 w-1/2" fill="none" aria-hidden="true">
        <path d="M12 3 L21 12 L12 21 L3 12 Z" fill="#ffffff" fillOpacity="0.95" />
        <path d="M12 8 L16 12 L12 16 L8 12 Z" fill="#2563eb" />
      </svg>
    </span>
  );
}

export function Wordmark({
  href = "/",
  markClass = "h-5 w-5",
  textClass = "text-sm",
  showText = true,
}: {
  href?: string | null;
  markClass?: string;
  textClass?: string;
  showText?: boolean;
}) {
  const inner = (
    <span className="flex items-center gap-2.5">
      <Mark className={markClass} />
      {showText && (
        <span className={`font-semibold tracking-tight text-gray-100 ${textClass}`}>Prospectus</span>
      )}
    </span>
  );
  return href ? (
    <a href={href} className="flex items-center" aria-label="Prospectus home">
      {inner}
    </a>
  ) : (
    inner
  );
}
