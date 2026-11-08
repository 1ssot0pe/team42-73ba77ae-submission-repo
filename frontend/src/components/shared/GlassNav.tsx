/**
 * GlassNav (design-v2.md). The top nav, and the only glass element in the app. Sticky at the top.
 * Left: the Parallax wordmark (links to /).
 * 600px and wider: inline Home, Evidence studio and Trials with an active state, then a small
 * overflow button (three dots) that opens a flat panel with the theme control and a "Developer"
 * switch. With Developer on, the panel also shows the trial ID, Gemini on or off and the real or
 * stub status of each module.
 * Under 600px: only the wordmark and a "Menu" text button. Menu opens a flat full width panel under
 * the bar (canvas background, hairline, no glass) with the three links, the theme control and the
 * Developer switch (and its details when on).
 * Both panels close on Escape (focus returns to their button), outside clicks and route changes.
 * Labels never truncate. Props: evidenceUrl is accepted for compatibility and no longer used.
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
const phoneLinkClass = ({ isActive }: { isActive: boolean }) => `nav-phone__link${isActive ? " is-active" : ""}`;

const PHONE_QUERY = "(max-width: 599.98px)";

interface DevDetailsProps {
  trialId: string | null | undefined;
  gemini: boolean | null;
  modules: [string, string][];
}

function DevDetails({ trialId, gemini, modules }: DevDetailsProps) {
  return (
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
  );
}

type Which = "more" | "phone" | null;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function GlassNav(_props: GlassNavProps = {}) {
  const { trialId, state } = useTrialSnapshot();
  const [theme, setTheme] = useState<ThemePref>(getThemePref);
  const [dev, setDev] = useDeveloper();
  const [open, setOpen] = useState<Which>(null);
  const [healthGemini, setHealthGemini] = useState<boolean | null>(null);
  const moreBtnRef = useRef<HTMLButtonElement>(null);
  const morePanelRef = useRef<HTMLDivElement>(null);
  const phoneBtnRef = useRef<HTMLButtonElement>(null);
  const phonePanelRef = useRef<HTMLDivElement>(null);
  const morePanelId = useId();
  const phonePanelId = useId();
  const { pathname } = useLocation();

  const openRef = useRef<Which>(null);
  openRef.current = open;

  const close = useCallback((returnFocus: boolean) => {
    const cur = openRef.current;
    setOpen(null);
    if (returnFocus) (cur === "phone" ? phoneBtnRef.current : moreBtnRef.current)?.focus();
  }, []);

  // Panels close whenever the route changes.
  useEffect(() => { setOpen(null); }, [pathname]);

  // Crossing the 600px breakpoint closes whichever panel no longer has a visible button.
  useEffect(() => {
    if (!open || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(PHONE_QUERY);
    const onChange = () => {
      if ((open === "phone" && !mq.matches) || (open === "more" && mq.matches)) setOpen(null);
    };
    onChange();
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const panel = open === "phone" ? phonePanelRef : morePanelRef;
    const btn = open === "phone" ? phoneBtnRef : moreBtnRef;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close(true); }
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (panel.current?.contains(t) || btn.current?.contains(t)) return;
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

  const toggle = (which: Exclude<Which, null>) => setOpen((cur) => (cur === which ? null : which));

  const gemini = state ? state.gemini : healthGemini;
  const modules: [string, string][] = state ? Object.entries(state.module_status ?? {}) : [];

  const settings = (
    <>
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
          <DevDetails trialId={trialId} gemini={gemini} modules={modules} />
        </>
      ) : null}
    </>
  );

  return (
    <header className="nav-wrap glass-nav">
      <nav className="nav" aria-label="Main">
        <NavLink to="/" className="nav__mark">Parallax</NavLink>
        <div className="nav__links">
          <NavLink to="/" end className={linkClass}>Home</NavLink>
          <NavLink to="/studio" className={linkClass}>Evidence studio</NavLink>
          <NavLink to="/trials" className={linkClass}>Trials</NavLink>
        </div>
        <div className="nav__more">
          <button type="button" ref={moreBtnRef} className="nav__more-btn" aria-label="More options"
            aria-haspopup="dialog" aria-expanded={open === "more"} aria-controls={morePanelId}
            onClick={() => toggle("more")}>
            <MoreIcon />
          </button>
          <div id={morePanelId} ref={morePanelRef} className="nav-menu" role="dialog" aria-label="More options"
            hidden={open !== "more"}>
            {open === "more" ? settings : null}
          </div>
        </div>
        <button type="button" ref={phoneBtnRef} className="nav__menu-btn"
          aria-expanded={open === "phone"} aria-controls={phonePanelId} onClick={() => toggle("phone")}>
          Menu
        </button>
        <div id={phonePanelId} ref={phonePanelRef} className="nav-phone" hidden={open !== "phone"}>
          <ul className="nav-phone__links">
            <li><NavLink to="/" end className={phoneLinkClass}>Home</NavLink></li>
            <li><NavLink to="/studio" className={phoneLinkClass}>Evidence studio</NavLink></li>
            <li><NavLink to="/trials" className={phoneLinkClass}>Trials</NavLink></li>
          </ul>
          <hr className="nav-menu__rule nav-phone__rule" />
          <div className="nav-phone__settings">{open === "phone" ? settings : null}</div>
        </div>
      </nav>
    </header>
  );
}
