/**
 * Compact trial clock for the workspace header: "Advance a day" (the one primary pill), then quiet text
 * buttons for "Advance a week" and Play / Pause.
 *
 * Advancing time never freezes the page. While a step runs, only the step controls are disabled and a status
 * line reads "Advancing day N…" with an elapsed-seconds counter; after 20 s it adds "This is taking longer
 * than usual". The step uses stepTrial (one POST, 120 s, no automatic retry). On failure the line offers
 * Retry, which first reads the trial's day: if the day already moved past the day the step started from,
 * the step did run, so that state is adopted instead of stepping again.
 *
 * Play loops 1-day steps until paused, blocked, closed or an error; Pause takes effect after the current step.
 * A blocked step shows one short watch line (summariseBlock). On unmount the in-flight request is aborted
 * and no state is set afterwards.
 */
import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorText, whenVisible } from "../../api";
import { stepTrial } from "../../api-extra";
import { useTrial } from "../../trial";
import type { StepResult, TrialState } from "../../types";
import "../../styles/clock.css";

const PLAY_DAYS = 1;
const PLAY_GAP_MS = 300;
const SLOW_AFTER_S = 20;
const STEP_TIMEOUT_MS = 120_000;

/** A step or a pre-retry check in flight. */
interface Run {
  kind: "step" | "check";
  days: number;
  /** The day the step started from. */
  from: number;
  /** The day being advanced to. */
  target: number;
  startedAt: number;
}

interface Failure {
  message: string;
  days: number;
  from: number;
}

export function TrialClock({ state }: { state: TrialState }) {
  const { adopt } = useTrial();
  const [run, setRun] = useState<Run | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [pausing, setPausing] = useState(false);

  const alive = useRef(true);
  const playRef = useRef(false);
  const ctrlRef = useRef<AbortController | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Unmount: stop Play, abort the in-flight request (which clears its timeout), never set state again.
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      playRef.current = false;
      ctrlRef.current?.abort();
      ctrlRef.current = null;
    };
  }, []);

  // A new trial in the same clock: stop Play and forget the old trial's lines.
  useEffect(() => {
    playRef.current = false;
    setFailure(null);
    setNote(null);
  }, [state.trial_id]);

  // Elapsed-seconds counter while something is in flight. The interval is cleared when the run ends or on unmount.
  useEffect(() => {
    if (!run) return;
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - run.startedAt) / 1000)));
    tick();
    const h = window.setInterval(tick, 1000);
    return () => window.clearInterval(h);
  }, [run]);

  const closed = state.phase === "closed";
  const blocked = state.blocked ?? null;

  /** One POST. Returns the result, or null on failure (the failure line is shown) or after unmount. */
  const sendStep = async (days: number, from: number): Promise<StepResult | null> => {
    const s = stateRef.current;
    const id = s.trial_id;
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    setFailure(null);
    setRun({ kind: "step", days, from, target: Math.min(from + days, s.close_day), startedAt: Date.now() });
    try {
      const r = await stepTrial(id, days, { timeoutMs: STEP_TIMEOUT_MS, signal: ctrl.signal });
      if (!alive.current) return null;
      adopt(r.state);
      setNote(!r.advanced && r.blocked ? r.blocked : null);
      return r;
    } catch (e) {
      if (!alive.current || ctrl.signal.aborted) return null; // aborted from here only on unmount
      // stepTrial cannot reach api.ts's trial-missing listeners; a state read can, so TrialProvider notices.
      if (e instanceof ApiError && e.trialMissing) void api.state(id).catch(() => undefined);
      setFailure({ message: errorText(e), days, from });
      return null;
    } finally {
      if (ctrlRef.current === ctrl) ctrlRef.current = null;
      if (alive.current) setRun(null);
    }
  };

  const advance = (days: number) => {
    if (run || playRef.current) return;
    void sendStep(days, stateRef.current.day);
  };

  /** Retry without double-advancing: read the trial first and only send again if the day has not moved. */
  const retry = async () => {
    const f = failure;
    if (!f || run) return;
    const s = stateRef.current;
    setFailure(null);
    setRun({ kind: "check", days: f.days, from: f.from, target: Math.min(f.from + f.days, s.close_day), startedAt: Date.now() });
    let fresh: TrialState;
    try {
      fresh = await api.state(s.trial_id);
    } catch (e) {
      if (!alive.current) return;
      setRun(null);
      setFailure({ ...f, message: errorText(e) });
      return;
    }
    if (!alive.current) return;
    adopt(fresh);
    setRun(null);
    if (fresh.day > f.from) {
      setNote(null); // the step ran on the server after all: keep its result, do not step again
      return;
    }
    await sendStep(f.days, f.from);
  };

  /** Re-read the trial and drop the error line, without stepping. */
  const dismiss = async () => {
    setFailure(null);
    try {
      const fresh = await api.state(stateRef.current.trial_id);
      if (alive.current) adopt(fresh);
    } catch {
      /* the provider's own refresh reports a lasting problem */
    }
  };

  const play = async () => {
    if (playRef.current || run) return;
    playRef.current = true;
    setPlaying(true);
    setPausing(false);
    setNote(null);
    let from = stateRef.current.day;
    try {
      while (playRef.current && alive.current) {
        await whenVisible(); // Play waits while the tab is in the background
        if (!playRef.current || !alive.current) break;
        const s = stateRef.current;
        if (s.phase === "closed" || s.blocked) break;
        const r = await sendStep(PLAY_DAYS, Math.max(from, s.day));
        if (!r || !r.advanced || r.state.phase === "closed" || r.state.blocked) break;
        from = r.state.day;
        await new Promise((res) => setTimeout(res, PLAY_GAP_MS));
      }
    } finally {
      playRef.current = false;
      if (alive.current) {
        setPlaying(false);
        setPausing(false);
      }
    }
  };

  const pause = () => {
    playRef.current = false;
    setPausing(true);
  };

  const stepDisabled = closed || !!blocked || run !== null || playing || failure !== null;
  const playDisabled = closed || !!blocked || run !== null || failure !== null;
  const why = closed ? "The trial is closed" : blocked ?? undefined;
  const watch = note ?? blocked;
  const slow = run !== null && elapsed >= SLOW_AFTER_S;

  return (
    <div className="clock">
      <div className="clock__controls">
        {/* Filled only when it can be pressed; while the trial waits on sign-offs the page's one filled button is the decision. */}
        <button type="button" className={`btn ${blocked || closed ? "btn--outline" : "btn--filled"} btn--sm`} disabled={stepDisabled} onClick={() => advance(1)} title={why}>
          Advance a day
        </button>
        <button type="button" className="textbtn" disabled={stepDisabled} onClick={() => advance(7)} title={why}>
          Advance a week
        </button>
        {playing ? (
          <button type="button" className="textbtn" aria-pressed="true" disabled={pausing} onClick={pause}>
            {pausing ? "Pausing after this day" : "Pause"}
          </button>
        ) : (
          <button type="button" className="textbtn" aria-pressed="false" disabled={playDisabled} onClick={() => void play()}
            title={why ?? "Advance one day at a time until paused"}>
            Play
          </button>
        )}
      </div>

      {run ? (
        <p className="clock__line clock__progress" role="status">
          <span className="sdot sdot--neutral clock__pulse"><span className="sdot__dot" aria-hidden="true" /></span>
          <span>
            {run.kind === "check"
              ? "Checking the trial day…"
              : run.target < 1
                ? "Preparing for dosing…"
                : <>{run.days === 1 ? "Advancing day " : "Advancing to day "}<span className="num">{run.target}</span>…</>}
          </span>
          <span className="num clock__elapsed" aria-hidden="true">{elapsed} s</span>
          {slow ? <span className="clock__slow">This is taking longer than usual.</span> : null}
        </p>
      ) : null}

      {closed ? <p className="clock__line">The trial is closed.</p> : null}
      {!closed && !run && watch ? (
        <p className="clock__line clock__line--watch" role="status" title={watch}>
          <span className="sdot sdot--watch"><span className="sdot__dot" aria-hidden="true" /></span>
          <span>{summariseBlock(watch, state.pending_approvals)}</span>
        </p>
      ) : null}
      {failure ? (
        <p className="clock__line clock__line--alert" role="alert">
          <span className="sdot sdot--alert"><span className="sdot__dot" aria-hidden="true" /></span>
          <span>{failure.message}</span>
          <button type="button" className="textbtn" onClick={() => void retry()}>Retry</button>
          <button type="button" className="textbtn" onClick={() => void dismiss()}>Dismiss</button>
        </p>
      ) : null}
    </div>
  );
}

/** One short line instead of the server's full list of blockers (the full text stays in the title tooltip). */
function summariseBlock(text: string, pending: number): string {
  if (pending > 0) {
    return `Waiting for a human: ${pending} ${pending === 1 ? "decision" : "decisions"} to sign in this stage.`;
  }
  const first = text.split(/[;\n]/)[0].trim();
  return first.length > 120 ? `${first.slice(0, 117)}...` : first;
}
