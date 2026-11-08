/**
 * GlassNav (design-v2.md). The top nav, and the only glass element in the app. Sticky at the top.
 * Left: the Parallax wordmark (links to /). Then Home, Evidence studio and Trials with an active state.
 * Right: a small overflow button (three dots) that opens a flat panel with the theme toggle and a
 * "Developer" switch. With Developer on, the panel also shows the trial ID, Gemini on or off and the
 * real or stub status of each module. The panel closes on Escape (focus returns to the button),
 * outside clicks and route changes. Fits at 390px wide without horizontal scroll.
 * Props: evidenceUrl is accepted for compatibility and no longer used.
 */
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "../../api";
import { useDeveloper } from "../../dev";
import { useTrialSnapshot } from "../../trialBridge";
import { moduleLabel } from "./format";
import { StatusPill } from "./Pills";
import { applyTheme, getThemePref, type ThemePref } from "./theme";

const NEXT_THEME: Record<ThemePref, ThemePref> = { auto: "light", light: "dark", dark: "auto" };
const THEME_WORD: Record<ThemePref, string> = { auto: "System", light: "Light", dark: "Dark" };

export interface GlassNavProps {
  evidenceUrl?: string;
}

function MoreIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="3" cy="8" r="1.4" fill="currentColor" />
      <circle cx="8" cy="8" r="1.4" fill="currentColor" />
      <circle cx="13" cy="8" r="1.4" fill="currentColor" />
    </svg>
  );
}

const linkClass = ({ isActive }: { isActive: boolean }) => `nav__link${isActive ? " is-active" : ""}`;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function GlassNav(_props: GlassNavProps = {}) {
  const { trialId, state } = useTrialSnapshot();
  const [theme, setTheme] = useState<ThemePref>(getThemePref);
  const [dev, setDev] = useDeveloper();
  const [open, setOpen] = useState(false);
  const [healthGemini, setHealthGemini] = useState<boolean | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const { pathname } = useLocation();

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) btnRef.current?.focus();
  }, []);

  // The panel closes whenever the route changes.
  useEffect(() => { setOpen(false); }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close(true); }
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (panelRef.current?.contains(t) || btnRef.current?.contains(t)) return;
      close(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open, close]);

  // Without a trial state, ask the backend whether Gemini is on (only while developer details are visible).
  useEffect(() => {
    if (!open || !dev || state) return;
    let live = true;
    api.health()
      .then((h) => { if (live) setHealthGemini(Boolean(h.gemini)); })
      .catch(() => { if (live) setHealthGemini(null); });
    return () => { live = false; };
  }, [open, dev, state]);

  const cycleTheme = () => {
    const next = NEXT_THEME[theme];
    applyTheme(next);
    setTheme(next);
  };

  const gemini = state ? state.gemini : healthGemini;
  const modules = state ? Object.entries(state.module_status ?? {}) : [];

  return (
    <header className="nav-wrap glass-nav">
      <nav className="nav" aria-label="Main">
        <NavLink to="/" className="nav__mark">Parallax</NavLink>
        <div className="nav__links">
          <NavLink to="/" end className={linkClass}>Home</NavLink>
          <NavLink to="/studio" className={linkClass}>
            <span className="nav__long">Evidence&nbsp;</span>studio
          </NavLink>
          <NavLink to="/trials" className={linkClass}>Trials</NavLink>
        </div>
        <div className="nav__more">
          <button type="button" ref={btnRef} className="nav__more-btn" aria-label="More options"
            aria-haspopup="dialog" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((o) => !o)}>
            <MoreIcon />
          </button>
          <div id={panelId} ref={panelRef} className="nav-menu" role="dialog" aria-label="More options" hidden={!open}>
            <button type="button" className="nav-menu__row nav-menu__btn" onClick={cycleTheme}
              aria-label={`Theme: ${THEME_WORD[theme]}. Change theme`}>
              <span>Theme</span>
              <span className="nav-menu__value">{THEME_WORD[theme]}</span>
            </button>
            <label className="nav-menu__row switch">
              <span>Developer</span>
              <input type="checkbox" role="switch" checked={dev} onChange={(e) => setDev(e.target.checked)} />
            </label>
            {dev ? (
              <>
                <hr className="nav-menu__rule" />
                <dl className="nav-menu__dev">
                  <div>
                    <dt>Trial</dt>
                    <dd>{trialId ? <span className="t-id">{trialId}</span> : "None"}</dd>
                  </div>
                  <div>
                    <dt>Gemini</dt>
                    <dd>
                      {gemini == null ? "Unknown" : (
                        <StatusPill tone={gemini ? "good" : "neutral"}>{gemini ? "On" : "Off, rule-based mode"}</StatusPill>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Modules</dt>
                    <dd>
                      {modules.length === 0 ? "No trial yet" : (
                        <span className="nav-menu__mods">
                          {modules.map(([m, s]) => (
                            <StatusPill key={m} tone={s === "real" ? "good" : "neutral"}>
                              {moduleLabel(m)}: {s === "real" ? "real" : "stub"}
                            </StatusPill>
                          ))}
                        </span>
                      )}
                    </dd>
                  </div>
                </dl>
              </>
            ) : null}
          </div>
        </div>
      </nav>
    </header>
  );
}
