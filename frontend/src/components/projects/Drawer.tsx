/**
 * Right-hand drawer for details (design v2: details open in a drawer, not in stacked cards).
 *
 * <Drawer open onClose title width?>  an accessible modal dialog rendered into document.body:
 *   role="dialog", aria-modal, labelled by its title; focus moves in on open, Tab and Shift+Tab cycle
 *   inside, Escape or the scrim closes, focus returns to the element that opened it; body scroll is
 *   locked while it is open. Flat eggshell surface with a hairline left border, full width on phones.
 * <DetailsButton>  the quiet "View ..." text button that opens a drawer.
 * <DetailsDrawer label title>  a DetailsButton and its Drawer in one, holding its own open state.
 *   The children mount only while the drawer is open.
 * <DetailsRow>  a wrapping row of DetailsDrawer buttons under a section.
 */
import { useCallback, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "../../styles/drawer.css";

export interface DrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Panel width in px on wide screens (default 480). Always capped at the viewport width. */
  width?: number;
  /** Optional line under the title, in smoke. */
  subtitle?: ReactNode;
}

const FOCUSABLE = [
  "a[href]", "area[href]", "button:not([disabled])", "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])", "textarea:not([disabled])", "iframe", "summary",
  "[contenteditable=true]", "[tabindex]:not([tabindex='-1'])",
].join(",");

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => {
    if (el.closest("[inert]")) return false;
    const style = window.getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none") return false;
    return el.getClientRects().length > 0;
  });
}

/** Body scroll lock shared by every open drawer, so overlapping drawers restore correctly. */
let locks = 0;
let saved: { overflow: string; paddingRight: string } | null = null;
function lockScroll() {
  if (locks++ > 0) return;
  const body = document.body;
  saved = { overflow: body.style.overflow, paddingRight: body.style.paddingRight };
  const bar = window.innerWidth - document.documentElement.clientWidth;
  body.style.overflow = "hidden";
  if (bar > 0) body.style.paddingRight = `${bar}px`;
}
function unlockScroll() {
  if (--locks > 0 || !saved) return;
  document.body.style.overflow = saved.overflow;
  document.body.style.paddingRight = saved.paddingRight;
  saved = null;
}

export function Drawer({ open, title, onClose, children, width = 480, subtitle }: DrawerProps) {
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    lockScroll();
    // Focus the panel itself first, so a screen reader announces the dialog's title; Tab then
    // reaches the close button and the body.
    panel.current?.focus({ preventScroll: true });

    const onKey = (e: KeyboardEvent) => {
      const el = panel.current;
      if (!el) return;
      if (e.key === "Escape") {
        e.stopPropagation();
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables(el);
      if (items.length === 0) {
        e.preventDefault();
        el.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const inside = active instanceof Node && el.contains(active);
      if (e.shiftKey) {
        if (!inside || active === first || active === el) {
          e.preventDefault();
          last.focus();
        }
      } else if (!inside || active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    // Focus that escapes (a click on the scrim, a programmatic focus elsewhere) is pulled back in.
    const onFocusIn = (e: FocusEvent) => {
      const el = panel.current;
      if (el && e.target instanceof Node && !el.contains(e.target)) el.focus({ preventScroll: true });
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("focusin", onFocusIn);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("focusin", onFocusIn);
      unlockScroll();
      const back = opener.current;
      opener.current = null;
      if (back && back.isConnected) back.focus({ preventScroll: true });
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <div className="pdr-root">
      <div className="pdr-scrim" onClick={onClose} aria-hidden="true" />
      <div className="pdr" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} ref={panel}
        style={{ ["--pdr-w" as string]: `${width}px` }}>
        <div className="pdr__head">
          <div className="pdr__heading">
            <h2 className="pdr__title" id={titleId}>{title}</h2>
            {subtitle ? <p className="pdr__sub">{subtitle}</p> : null}
          </div>
          <button type="button" className="pdr-btn pdr__close" onClick={onClose}>Close</button>
        </div>
        <div className="pdr__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

export interface DetailsButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  /** A short count or note after the label, in smoke (for example "7 tables"). */
  meta?: ReactNode;
}

/** A quiet text button for "View ..." details. Not a pill: pills are for the one primary action. */
export function DetailsButton({ children, meta, className, type = "button", ...rest }: DetailsButtonProps) {
  return (
    <button type={type} className={["pdr-btn", className].filter(Boolean).join(" ")} aria-haspopup="dialog" {...rest}>
      <span className="pdr-btn__label">{children}</span>
      {meta !== undefined && meta !== null && meta !== "" ? <span className="pdr-btn__meta">{meta}</span> : null}
    </button>
  );
}

export interface DetailsDrawerProps {
  /** Button text, for example "View screening ledger". */
  label: string;
  /** Drawer title, for example "Screening ledger". */
  title: string;
  meta?: ReactNode;
  subtitle?: ReactNode;
  width?: number;
  children: ReactNode;
}

/** A DetailsButton and its Drawer, with its own open state. */
export function DetailsDrawer({ label, title, meta, subtitle, width, children }: DetailsDrawerProps) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <DetailsButton meta={meta} aria-expanded={open} onClick={() => setOpen(true)}>{label}</DetailsButton>
      <Drawer open={open} onClose={close} title={title} subtitle={subtitle} width={width}>{children}</Drawer>
    </>
  );
}

/** A wrapping row of details buttons. */
export function DetailsRow({ children, label = "Details" }: { children: ReactNode; label?: string }) {
  return <div className="pdr-row" role="group" aria-label={label}>{children}</div>;
}
