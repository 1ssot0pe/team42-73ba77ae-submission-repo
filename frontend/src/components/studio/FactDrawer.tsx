/**
 * FactDrawer: a flat right-hand panel showing one fact's quote and source.
 * Escape or the close button closes it. Focus moves to the close button on open, is kept inside
 * while open, and returns to the element that opened it on close.
 */
import { useEffect, useRef } from "react";
import type { FactRow } from "./report";

const STATUS_WORD: Record<string, string> = {
  observed: "Observed",
  derived: "Derived",
  imputed: "Estimated",
  unknown: "Not found",
};

export function statusTone(status: string): "good" | "watch" | "neutral" {
  if (status === "observed" || status === "derived") return "good";
  if (status === "imputed") return "watch";
  return "neutral";
}

export function StatusDot({ tone, children }: { tone: "good" | "watch" | "alert" | "neutral"; children: React.ReactNode }) {
  return (
    <span className={`studio-status studio-status--${tone}`}>
      <span className="studio-status__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

export function statusWord(status: string): string {
  return STATUS_WORD[status] ?? (status ? status[0].toUpperCase() + status.slice(1) : "Unknown");
}

export function FactDrawer({ fact, onClose }: { fact: FactRow | null; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!fact) return;
    opener.current = document.activeElement;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panel.current) return;
      const items = panel.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled])");
      if (items.length === 0) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      const el = opener.current;
      if (el instanceof HTMLElement) el.focus();
    };
  }, [fact, onClose]);

  if (!fact) return null;
  return (
    <>
      <div className="studio-scrim" onClick={onClose} aria-hidden="true" />
      <div className="studio-drawer" role="dialog" aria-modal="true" aria-labelledby="studio-drawer-title" ref={panel}>
        <div className="studio-drawer__head">
          <h2 id="studio-drawer-title" className="studio-drawer__title">{fact.label}</h2>
          <button ref={closeBtn} type="button" className="studio-text-btn" onClick={onClose}>Close</button>
        </div>
        <p className="studio-drawer__value">{fact.value}</p>
        <p className="studio-small">
          <StatusDot tone={statusTone(fact.status)}>{statusWord(fact.status)}</StatusDot>
          {fact.audit === "pass" ? <span className="studio-muted"> · quote checked against the source</span> : null}
          {fact.audit.startsWith("fail") ? <span className="studio-muted"> · quote check failed</span> : null}
        </p>
        {fact.quote ? (
          <blockquote className="studio-quote">&ldquo;{fact.quote}&rdquo;</blockquote>
        ) : (
          <p className="studio-muted">No quote: this value was not read directly from a source.</p>
        )}
        {fact.note ? <p className="studio-small studio-muted">{fact.note}</p> : null}
        {fact.sourceUrl ? (
          <p className="studio-small">
            <span className="studio-label">Source</span>
            <a href={fact.sourceUrl} target="_blank" rel="noreferrer" className="studio-link">
              {fact.sourceTitle || fact.sourceId || fact.sourceUrl}
            </a>
            {fact.sourceId ? <span className="studio-muted studio-break"> {fact.sourceId}</span> : null}
          </p>
        ) : fact.sourceId ? (
          <p className="studio-small"><span className="studio-label">Source</span>{fact.sourceId}</p>
        ) : null}
      </div>
    </>
  );
}
