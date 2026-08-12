"use client";

// Homegrown toast layer (no dependency) — console-voice notifications for mutations
// (star / rename / delete / re-run / download / copy). Mounted by the /app console
// only; useToast() degrades to a NO-OP when no provider exists so /demo and /preview
// can render ReportViewer without crashing (they simply skip the notifications).

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export type ToastVariant = "success" | "error" | "info";
type ToastFn = (message: string, variant?: ToastVariant) => void;

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

const ToastContext = createContext<ToastFn | null>(null);

/** Push a toast. Safe anywhere — a no-op outside <ToastProvider> (e.g. /demo). */
export function useToast(): ToastFn {
  return useContext(ToastContext) ?? noop;
}
const noop: ToastFn = () => {};

// Variant accents in the console voice: mono micro-label + a thin color spine.
const ACCENT: Record<ToastVariant, { label: string; bar: string; text: string }> = {
  success: { label: "OK", bar: "bg-emerald-500", text: "text-emerald-400" },
  error: { label: "Error", bar: "bg-rose-500", text: "text-rose-400" },
  info: { label: "Note", bar: "bg-brand-500", text: "text-brand-300" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  const push = useCallback<ToastFn>(
    (message, variant = "info") => {
      const id = ++idRef.current;
      setToasts((ts) => [...ts, { id, message, variant }].slice(-4)); // cap the stack
      window.setTimeout(() => dismiss(id), 3500);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      {/* Stack sits ABOVE the HelpGuide "?" pill (fixed bottom-4 right-4 h-9 z-40). */}
      <div className="no-print pointer-events-none fixed bottom-16 right-4 z-[60] flex w-72 flex-col items-end gap-2">
        {toasts.map((t) => {
          const a = ACCENT[t.variant];
          return (
            <button
              key={t.id}
              onClick={() => dismiss(t.id)}
              className="toast-card pointer-events-auto flex w-full overflow-hidden rounded-lg border border-gray-800 bg-gray-900 text-left shadow-pop"
              title="Dismiss"
            >
              <span className={`w-0.5 shrink-0 self-stretch ${a.bar}`} aria-hidden />
              <span className="px-3 py-2.5">
                <span className={`block font-mono text-[9px] font-medium uppercase tracking-[0.16em] ${a.text}`}>
                  {a.label}
                </span>
                <span className="mt-0.5 block text-[12.5px] leading-snug text-gray-200">{t.message}</span>
              </span>
            </button>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
