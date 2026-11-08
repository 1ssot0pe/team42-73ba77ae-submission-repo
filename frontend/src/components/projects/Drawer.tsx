/**
 * Right-hand drawer for details (design v2: details open in a drawer, not in stacked cards).
 * Flat surface, hairline left border, a dim scrim. Escape or the scrim closes it. Focus moves to the panel.
 */
import { useEffect, useRef, type ReactNode } from "react";

export interface DrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Drawer({ open, title, onClose, children }: DrawerProps) {
  const panel = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    back.current = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      back.current?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="drawer-root">
      <div className="drawer-scrim" onClick={onClose} aria-hidden="true" />
      <div className="drawer" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={panel}>
        <div className="drawer__head">
          <h2 className="drawer__title">{title}</h2>
          <button type="button" className="textbtn" onClick={onClose}>Close</button>
        </div>
        <div className="drawer__body">{children}</div>
      </div>
    </div>
  );
}
