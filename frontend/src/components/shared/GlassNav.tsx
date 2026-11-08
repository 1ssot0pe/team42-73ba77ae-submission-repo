/**
 * GlassNav (design.md 8.1). Floating liquid-glass pill nav, sticky 12px from the top. No required props.
 * Props: evidenceUrl (default "http://localhost:8501", the Streamlit evidence engine, opened in a new tab).
 * Left: UNBLIND wordmark. Centre: ghost-pill links (active link gets ink text and a 6px dot).
 * Right: trial chip, day counter "D+23 / 90" and an amber "3 to sign" pill (hidden until a trial exists),
 * then a theme toggle (Auto, Bench, Darkroom). Reads the trial from useTrial().
 */
import { useEffect, useRef, useState } from "react";
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
  const { pathname } = useLocation();

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
                <NavLink to="/" title="Decisions waiting for a human">
                  <StatusPill tone="watch">{state.pending_approvals} to sign</StatusPill>
                </NavLink>
              ) : null}
            </>
          ) : null}
          <button type="button" className={buttonClass("ghost", "md", "nav__theme")} onClick={cycleTheme}
            aria-label={`${THEME_LABEL[theme]}. Change theme`} title={THEME_LABEL[theme]}>
            <ThemeIcon pref={theme} />
          </button>
        </div>
      </nav>
    </div>
  );
}
