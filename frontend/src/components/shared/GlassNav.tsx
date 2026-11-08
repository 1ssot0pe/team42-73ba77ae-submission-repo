/**
 * GlassNav (design.md 8.1). Floating liquid-glass pill nav, sticky 12px from the top. No required props.
 * Props: evidenceUrl (default "http://localhost:8501", the Streamlit evidence engine, opened in a new tab).
 * Left: UNBLIND wordmark. Centre: ghost-pill links (active link gets ink text and a 6px dot).
 * Right: trial chip, day counter "D+23 / 90" and an amber "3 to sign" pill (hidden until a trial exists),
 * then a theme toggle (Auto, Bench, Darkroom). Reads the trial from useTrial().
 * At 720px and below the links collapse into a "Menu" pill (last control in the nav) that opens a glass list.
 * The list is a sibling of the nav, never nested inside its glass (design.md 4: no glass on glass).
 * It closes on Escape (focus returns to the button), outside clicks, focus leaving it and route changes.
 */
import { useCallback, useEffect, useId, useRef, useState, type FocusEvent } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useTrial } from "../../trial";
import { buttonClass } from "./Button";
import { formatDay } from "./format";
import { StatusPill } from "./Pills";
import { applyTheme, getThemePref, type ThemePref } from "./theme";

const LINKS: Array<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "Mission control", end: true },
  { to: "/predose", label: "Pre-dosing" },
  { to: "/portal", label: "Volunteer portal" },
  { to: "/dosing", label: "Dosing" },
  { to: "/postdose", label: "Post-dosing" },
];

const NEXT_THEME: Record<ThemePref, ThemePref> = { auto: "light", light: "dark", dark: "auto" };
const THEME_LABEL: Record<ThemePref, string> = { auto: "Theme: follows system", light: "Theme: Bench (light)", dark: "Theme: Darkroom (dark)" };

function ThemeIcon({ pref }: { pref: ThemePref }) {
  if (pref === "light") {
    return (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
        <circle cx="8" cy="8" r="3" />
        <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
      </svg>
    );
  }
  if (pref === "dark") {
    return (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
        <path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 2.5v11a5.5 5.5 0 0 0 0-11z" fill="currentColor" />
    </svg>
  );
}

export interface GlassNavProps {
  evidenceUrl?: string;
}

export function GlassNav({ evidenceUrl = "http://localhost:8501" }: GlassNavProps) {
  const { state } = useTrial();
  const [theme, setTheme] = useState<ThemePref>(getThemePref);
  const linksRef = useRef<HTMLDivElement>(null);
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuId = useId();
  const { pathname } = useLocation();

  const closeMenu = useCallback((returnFocus: boolean) => {
    setMenuOpen(false);
    if (returnFocus) menuBtnRef.current?.focus();
  }, []);

  // The menu closes whenever the route changes.
  useEffect(() => { setMenuOpen(false); }, [pathname]);

  // While open: focus the first link, close on Escape (focus back to the button) and on outside clicks.
  useEffect(() => {
    if (!menuOpen) return;
    menuRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); closeMenu(true); }
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (menuRef.current?.contains(t) || menuBtnRef.current?.contains(t)) return;
      closeMenu(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [menuOpen, closeMenu]);

  // Tabbing out of the list (past the last link, or back past the button) closes it.
  const onMenuBlur = (e: FocusEvent<HTMLElement>) => {
    const next = e.relatedTarget as Node | null;
    if (!next) return;
    if (menuRef.current?.contains(next) || menuBtnRef.current?.contains(next)) return;
    setMenuOpen(false);
  };

  // On phones the links scroll sideways: keep the active one in view after each route change.
  useEffect(() => {
    const active = linksRef.current?.querySelector<HTMLElement>(".is-active");
    active?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pathname]);

  const cycleTheme = () => {
    const next = NEXT_THEME[theme];
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div className="nav-wrap">
      <nav className="nav glass glass--float" aria-label="Main">
        <NavLink to="/" className="nav__mark" aria-label="UNBLIND, mission control">UNBLIND</NavLink>
        <div className="nav__links" ref={linksRef}>
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}
              className={({ isActive }) => buttonClass("ghost", "md", `nav__link${isActive ? " is-active" : ""}`)}>
              {l.label}
            </NavLink>
          ))}
          <a className={buttonClass("ghost", "md", "nav__link")} href={evidenceUrl} target="_blank" rel="noopener">
            Evidence engine <span className="nav__ext" aria-hidden="true">&#8599;</span>
            <span className="visually-hidden">(opens in a new tab)</span>
          </a>
        </div>
        <div className="nav__meta">
          {state ? (
            <>
              <span className="nav__chip" title="Trial ID">{state.trial_id}</span>
              <span className="nav__day" title="Simulated trial day">{formatDay(state.day)} / {state.close_day}</span>
              {state.pending_approvals > 0 ? (
                <NavLink to="/" className="nav__sign" title="Decisions waiting for a human">
                  <StatusPill tone="watch">{state.pending_approvals} to sign</StatusPill>
                </NavLink>
              ) : null}
            </>
          ) : null}
          <button type="button" className={buttonClass("ghost", "md", "nav__theme")} onClick={cycleTheme}
            aria-label={`${THEME_LABEL[theme]}. Change theme`} title={THEME_LABEL[theme]}>
            <ThemeIcon pref={theme} />
          </button>
          <button type="button" ref={menuBtnRef} className={buttonClass("outline", "md", "nav__menu-btn")}
            aria-expanded={menuOpen} aria-controls={menuId} onClick={() => setMenuOpen((o) => !o)}
            onBlur={menuOpen ? onMenuBlur : undefined}>
            <span className="nav__menu-glyph" aria-hidden="true" />
            Menu
          </button>
        </div>
      </nav>
      <div id={menuId} ref={menuRef} className="nav-menu glass glass--float glass--strong" hidden={!menuOpen}
        onBlur={onMenuBlur}>
        <ul className="nav-menu__list" aria-label="Pages">
          {LINKS.map((l) => (
            <li key={l.to}>
              <NavLink to={l.to} end={l.end} onClick={() => setMenuOpen(false)}
                className={({ isActive }) => buttonClass("ghost", "md", `nav-menu__link${isActive ? " is-active" : ""}`)}>
                {l.label}
              </NavLink>
            </li>
          ))}
          <li>
            <a className={buttonClass("ghost", "md", "nav-menu__link")} href={evidenceUrl} target="_blank" rel="noopener"
              onClick={() => setMenuOpen(false)}>
              Evidence engine <span className="nav__ext" aria-hidden="true">&#8599;</span>
              <span className="visually-hidden">(opens in a new tab)</span>
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}
