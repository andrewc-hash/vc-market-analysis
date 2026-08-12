"use client";

// Themed confirm dialog — replaces window.confirm() so destructive actions read in
// the console voice. Escape + backdrop close; `busy` disables everything in-flight.

import { useEffect, type ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean; // rose confirm button (delete-class actions)
  busy?: boolean; // confirm in flight — lock the dialog
  onConfirm: () => void;
  onClose: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  busy = false,
  onConfirm,
  onClose,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  return (
    <div
      className="no-print fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4"
      onClick={() => !busy && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-gray-800 bg-gray-950 p-5 shadow-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="kicker">{destructive ? "Confirm · destructive" : "Confirm"}</div>
        <h3 className="mt-1 font-serif text-lg font-semibold text-gray-100">{title}</h3>
        {body && <div className="mt-2 text-[13px] leading-relaxed text-gray-400">{body}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="btn-secondary">
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={
              destructive
                ? "inline-flex items-center justify-center gap-2 rounded-md bg-rose-700 px-4 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/40 disabled:cursor-not-allowed disabled:opacity-40"
                : "btn-primary py-1.5"
            }
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
