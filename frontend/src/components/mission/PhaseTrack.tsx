/**
 * PhaseTrack (design.md 8.3, L2 glass). Segmented phase pills (done: graphite with a check; current: ink fill;
 * upcoming: ash), then a day ruler from D0 to close_day with a hairline per day and a taller tick every 7 days
 * (W1 to W12). The current day is a 2px ink needle that turns amber when the trial is blocked, with the reason
 * to its right. Props: state (TrialState).
 */
import type { CSSProperties } from "react";
import { PHASES, type Phase, type TrialState } from "../../types";
import { formatDay } from "../shared";

const PHASE_LABEL: Record<Phase, string> = {
  design: "Design",
  recruitment: "Recruitment",
  dosing: "Dosing",
  "follow-up": "Follow-up",
  "close-out": "Close-out",
  closed: "Closed",
};

function CheckGlyph() {
  return (
    <svg className="mc-phase__check" viewBox="0 0 10 10" aria-hidden="true">
      <path d="M1.5 5.2l2.2 2.2L8.5 2.6" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

export function PhaseTrack({ state }: { state: TrialState }) {
  const close = state.close_day || 90;
  const current = Math.max(0, PHASES.indexOf(state.phase));
  const finished = state.phase === "closed";
  const day = Math.max(0, Math.min(close, state.day));
  const pct = (day / close) * 100;
  const weeks = Array.from({ length: Math.floor(close / 7) }, (_, i) => i + 1);
  const blocked = state.blocked;
  const needleStyle = { "--mc-needle": `${pct}%` } as CSSProperties;

  return (
    <section className="mc-track glass glass--enter" aria-label="Trial phase and day">
      <ol className="mc-phases" role="list">
        {PHASES.map((p, i) => {
          const status = i < current || (finished && i === current) ? "done" : i === current ? "current" : "next";
          return (
            <li key={p} className={`mc-phase mc-phase--${status}`} aria-current={status === "current" ? "step" : undefined}>
              {status === "done" ? <CheckGlyph /> : null}
              {PHASE_LABEL[p]}
              {status === "done" ? <span className="visually-hidden"> (done)</span> : null}
            </li>
          );
        })}
      </ol>

      <div className="mc-ruler" style={needleStyle}>
        <div className="mc-ruler__days" aria-hidden="true" />
        {weeks.map((w) => (
          <span key={w} className={`mc-ruler__week${w % 2 ? " mc-ruler__week--odd" : ""}`}
            style={{ left: `${((w * 7) / close) * 100}%` }} aria-hidden="true">
            <span className="mc-ruler__wlabel">W{w}</span>
          </span>
        ))}
        <span className="mc-ruler__end mc-ruler__end--start" aria-hidden="true">D0</span>
        <span className="mc-ruler__end mc-ruler__end--stop" aria-hidden="true">D{close}</span>
        <div className={`mc-needle${blocked ? " mc-needle--blocked" : ""}`} role="img"
          aria-label={`Current day ${formatDay(state.day)} of ${close}${blocked ? `. Blocked: ${blocked}` : ""}`}>
          <span className="mc-needle__day">{state.day < 1 ? "Setup" : formatDay(state.day)}</span>
        </div>
      </div>

      {blocked ? (
        <p className="mc-track__blocked" title={blocked}>
          <span className="mc-track__dot" aria-hidden="true" />
          {blocked}
        </p>
      ) : (
        <p className="mc-track__status">
          <span className="num">{formatDay(state.day)}</span> of <span className="num">{close}</span> days
          {state.primary_lock_day ? <> · primary endpoint locked <span className="num">{formatDay(state.primary_lock_day)}</span></> : null}
        </p>
      )}
    </section>
  );
}
