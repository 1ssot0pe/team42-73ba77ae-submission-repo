/**
 * Toasts (design.md 8.20). Floating glass pills, bottom right above the dock, 4 seconds, mono action label.
 * ToastProvider props: children. Wrap the app once.
 * useToast() returns toast(message, tone?) where tone is "info" (default) | "good" | "watch" | "alert".
 *   Example: toast("Approved · protocol v2 saved", "good"). Text is shown uppercase.
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

export type ToastTone = "info" | "good" | "watch" | "alert";
interface ToastItem { id: number; message: string; tone: ToastTone }
type ToastFn = (message: string, tone?: ToastTone) => void;

const ToastContext = createContext<ToastFn | null>(null);
const DURATION_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const toast = useCallback<ToastFn>((message, tone = "info") => {
    const id = next.current++;
    setItems((xs) => [...xs.slice(-3), { id, message, tone }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), DURATION_MS);
  }, []);

  const value = useMemo(() => toast, [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone} glass glass--float glass--strong glass--enter`}>
            <span className="toast__dot" aria-hidden="true" />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** Returns toast(message, tone?). Safe outside a provider (logs to the console instead). */
export function useToast(): ToastFn {
  const ctx = useContext(ToastContext);
  return ctx ?? ((m: string) => console.info("[toast]", m));
}
