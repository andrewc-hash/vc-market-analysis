"use client";

import type { CallClaimsAudit } from "@/lib/api";

interface Props {
  audit: CallClaimsAudit | null | undefined;
}

// Status chips: color + label (never color-only; the word carries the meaning).
// Same chip anatomy as the shared .chip family (mono, tracked, hairline border).
const chipBase =
  "inline-flex shrink-0 items-center gap-1 rounded border px-2 py-[3px] font-mono text-[10px] font-medium uppercase tracking-[0.08em]";
const STATUS_STYLE: Record<string, { cls: string; label: string }> = {
  verified: { cls: "bg-emerald-950/40 text-emerald-300 border-emerald-900/60", label: "Verified" },
  contradicted: { cls: "bg-red-950/40 text-red-300 border-red-900/60", label: "Contradicted" },
  "vendor-only": { cls: "bg-amber-950/40 text-amber-300 border-amber-900/60", label: "Vendor-only" },
  unsupported: { cls: "bg-gray-800/60 text-gray-400 border-gray-700", label: "Unsupported" },
};

/** Founder-call claim audit: every claim the founder made on the uploaded call,
 * cross-examined in the pipeline against the public record + the deck. */
export default function ClaimsAudit({ audit }: Props) {
  const claims = audit?.claims ?? [];
  if (claims.length === 0) {
    return (
      <div className="empty-state">
        No call-claim audit for this run (upload a call recording or transcript with the startup).
      </div>
    );
  }
  const c = audit!.counts || {};

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Claims the founder made on the uploaded call, cross-examined against the public
        record and the deck. Verdicts are pipeline-validated.
      </p>

      {/* tally row — one semantic chip per status, deck conflicts last */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`${chipBase} ${STATUS_STYLE.verified.cls}`}>{c.verified ?? 0} verified</span>
        <span className={`${chipBase} ${STATUS_STYLE.contradicted.cls}`}>{c.contradicted ?? 0} contradicted</span>
        <span className={`${chipBase} ${STATUS_STYLE["vendor-only"].cls}`}>{c["vendor-only"] ?? 0} vendor-only</span>
        <span className={`${chipBase} ${STATUS_STYLE.unsupported.cls}`}>{c.unsupported ?? 0} unsupported</span>
        {c.deck_conflicts ? (
          <span className={`${chipBase} ${STATUS_STYLE.contradicted.cls}`}>{c.deck_conflicts} deck conflict(s)</span>
        ) : null}
      </div>

      {claims.map((cl, i) => {
        const st = STATUS_STYLE[cl.status] ?? STATUS_STYLE.unsupported;
        return (
          <div key={i} className="rounded-md border border-gray-800 bg-gray-900/40 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium leading-snug text-gray-200">{cl.claim}</div>
                {cl.quote && (
                  <div className="mt-1 text-xs italic leading-relaxed text-gray-500">
                    “{cl.quote}”
                    {cl.timestamp ? (
                      <span className="ml-1.5 font-mono text-[10.5px] not-italic tabular-nums text-gray-600">{cl.timestamp}</span>
                    ) : null}
                  </div>
                )}
              </div>
              <span className={`${chipBase} ${st.cls}`}>{st.label}</span>
            </div>
            {cl.evidence && <p className="mt-1.5 text-xs leading-relaxed text-gray-400">{cl.evidence}</p>}
            {cl.deck_conflict && (
              <div className="mt-2 border-l-2 border-red-500/60 bg-red-950/30 py-1.5 pl-2.5 pr-2 text-xs leading-relaxed text-red-300">
                <span className="mr-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.14em] text-red-400">
                  Deck conflict
                </span>
                {cl.deck_conflict}
              </div>
            )}
          </div>
        );
      })}
      <p className="text-[11px] text-gray-600">
        “Verified” requires an independent source; the founder&rsquo;s own site/deck counts as vendor-only.
        Absence of public evidence renders “unsupported”, never “contradicted”.
      </p>
    </div>
  );
}
