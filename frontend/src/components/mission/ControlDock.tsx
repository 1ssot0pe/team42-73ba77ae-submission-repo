/**
 * ControlDock (design.md 8.4, L3 floating glass pill at the bottom centre).
 * Left: Next day, +1 week, Play / Pause (2 days every 350 ms; stops when blocked, closed, on error, on a new
 * trial or on unmount: the useRef loop from plan.md 6.2), then the Auto-approve (demo) switch.
 * Right: trial id, Gemini on/off, module real/stub status and New trial. Wraps to rows on phones.
 * Publishes its height as --dock-h on <html> so the page and toasts keep clear of it.
 * Props: state (TrialState).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { StepResult, TrialState } from "../../types";
import { Button, PlayGlyph, StatusPill, moduleLabel, useToast } from "../shared";
import { useElementSize } from "./useElementSize";

const PLAY_DAYS = 2;
const PLAY_MS = 350;

export function ControlDock({ state }: { state: TrialState }) {
  const { trialId, adopt, setTrialId } = useTrial();
  const toast = useToast();
  const [busy, setBusy] = useState<"day" | "week" | "auto" | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const playing = useRef(false);
  const alive = useRef(true);
  const dock = useRef<HTMLDivElement>(null);
  const { height } = useElementSize(dock);

  // stop the loop on unmount
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; playing.current = false; };
  }, []);

  // stop the loop when the trial changes
  useEffect(() => {
    playing.current = false;
    setIsPlaying(false);
  }, [trialId]);

  // keep page content and toasts clear of the dock
  useEffect(() => {
    if (!height) return;
    const root = document.documentElement;
    root.style.setProperty("--dock-h", `${height}px`);
    return () => { root.style.removeProperty("--dock-h"); };
  }, [height]);

  const step = useCallback(async (days: number): Promise<StepResult | null> => {
    if (!trialId) return null;
    try {
      const r = await api.step(trialId, days);
      if (!alive.current) return null;
      adopt(r.state);
      if (!r.advanced && r.blocked) toast("Paused · waiting for a human", "watch");
      return r;
    } catch (e) {
      if (alive.current) toast(errorText(e), "alert");
      return null;
    }
  }, [trialId, adopt, toast]);

  const stepOnce = async (days: number, which: "day" | "week") => {
    setBusy(which);
    await step(days);
    if (alive.current) setBusy(null);
  };

  const play = async () => {
    playing.current = !playing.current;
    setIsPlaying(playing.current);
    while (playing.current && alive.current) {
      const r = await step(PLAY_DAYS);
      if (!r || !r.advanced || r.state.phase === "closed" || r.state.blocked) {
        playing.current = false;
        if (alive.current) setIsPlaying(false);
        if (r?.state.phase === "closed") toast("Trial closed · FDA blinding report waiting", "good");
        break;
      }
      await new Promise((res) => setTimeout(res, PLAY_MS));
    }
  };

  const toggleAuto = async (on: boolean) => {
    if (!trialId) return;
    setBusy("auto");
    try {
      const s = await api.setAutoApprove(trialId, on);
      if (!alive.current) return;
      adopt(s);
      toast(on ? "Auto-approve on (demo)" : "Auto-approve off", on ? "watch" : "info");
    } catch (e) {
      if (alive.current) toast(errorText(e), "alert");
    } finally {
      if (alive.current) setBusy(null);
    }
  };

  const newTrial = () => {
    playing.current = false;
    setIsPlaying(false);
    setTrialId(null);
  };

  const closed = state.phase === "closed";
  const blocked = Boolean(state.blocked);
  const stepDisabled = closed || blocked || isPlaying || busy !== null;
  const why = closed ? "The trial is closed" : blocked ? (state.blocked ?? "") : undefined;
  const modules = Object.entries(state.module_status);
  const nReal = modules.filter(([, s]) => s === "real").length;

  return (
    <div className="mc-dock-wrap">
      <div className="mc-dock glass glass--float" ref={dock} role="toolbar" aria-label="Trial controls">
        <div className="mc-dock__controls">
          <Button size="dock" busy={busy === "day"} busyLabel="Working…" disabled={stepDisabled} title={why}
            onClick={() => void stepOnce(1, "day")}>Next day</Button>
          <Button size="dock" busy={busy === "week"} busyLabel="Working…" disabled={stepDisabled} title={why}
            onClick={() => void stepOnce(7, "week")}>+1 week</Button>
          <Button size="dock" variant="filled" className="mc-dock__play" aria-pressed={isPlaying}
            disabled={!isPlaying && (closed || blocked || busy !== null)} title={why}
            onClick={() => void play()}>
            <PlayGlyph playing={isPlaying} />
            {isPlaying ? "Pause" : "Play"}
          </Button>
        </div>
        <span className="mc-dock__divider" aria-hidden="true" />
        <label className="switch switch--watch mc-dock__auto">
          <input type="checkbox" checked={state.auto_approve} disabled={busy === "auto"}
            onChange={(e) => void toggleAuto(e.target.checked)} />
          <span>Auto-approve (demo)</span>
        </label>
        <span className="mc-dock__divider mc-dock__divider--meta" aria-hidden="true" />
        <div className="mc-dock__meta">
          <span className="mc-dock__id" title="Trial ID">{state.trial_id}</span>
          <StatusPill tone={state.gemini ? "good" : "neutral"} title="Gemini enhancement; every agent also has a rule-based path">
            Gemini {state.gemini ? "on" : "off"}
          </StatusPill>
          {modules.map(([m, s]) => (
            <StatusPill key={m} className="mc-dock__mods-full" tone={s === "real" ? "outline" : "neutral"} title={`${moduleLabel(m)} module: ${s}`}>
              {moduleLabel(m)} {s}
            </StatusPill>
          ))}
          <StatusPill className="mc-dock__mods-short" tone="neutral"
            title={modules.map(([m, s]) => `${moduleLabel(m)}: ${s}`).join(", ")}>
            {modules.length - nReal > 0 ? `${modules.length - nReal} stub` : "All real"}
          </StatusPill>
          <Button size="sm" variant="ghost" onClick={newTrial}>New trial</Button>
        </div>
      </div>
    </div>
  );
}
