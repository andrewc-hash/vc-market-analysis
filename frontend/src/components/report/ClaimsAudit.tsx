"use client";

import type { CallClaimsAudit } from "@/lib/api";

interface Props {
  audit: CallClaimsAudit | null | undefined;
}

// Status chips: color + label (never color-only; the word carries the meaning).
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
    return <p className="text-sm text-gray-500">No call-claim audit for this run (upload a call recording or transcript with the startup).</p>;
  }
  const c = audit!.counts || {};

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Claims the founder made on the uploaded call, cross-examined against the public
        record and the deck. Verdicts are pipeline-validated —{" "}
        <span className="text-emerald-300">{c.verified ?? 0} verified</span> ·{" "}
        <span className="text-red-300">{c.contradicted ?? 0} contradicted</span> ·{" "}
        <span className="text-amber-300">{c["vendor-only"] ?? 0} vendor-only</span> ·{" "}
        <span className="text-gray-400">{c.unsupported ?? 0} unsupported</span>
        {c.deck_conflicts ? <> · <span className="text-red-300">{c.deck_conflicts} deck conflict(s)</span></> : null}.
      </p>

      {claims.map((cl, i) => {
        const st = STATUS_STYLE[cl.status] ?? STATUS_STYLE.unsupported;
        return (
          <div key={i} className="rounded-md border border-gray-800 bg-gray-900/40 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-200">{cl.claim}</div>
                {cl.quote && (
                  <div className="mt-1 text-xs italic text-gray-500">
                    “{cl.quote}”{cl.timestamp ? <span className="not-italic tabular-nums"> — {cl.timestamp}</span> : null}
                  </div>
                )}
              </div>
              <span className={`shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${st.cls}`}>
                {st.label}
              </span>
            </div>
            {cl.evidence && <p className="mt-1.5 text-xs text-gray-400">{cl.evidence}</p>}
            {cl.deck_conflict && (
              <p className="mt-1 rounded bg-red-950/30 px-2 py-1 text-xs text-red-300">
                Deck conflict: {cl.deck_conflict}
              </p>
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
