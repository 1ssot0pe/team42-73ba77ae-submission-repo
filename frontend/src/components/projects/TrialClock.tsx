/**
 * Compact trial clock for the workspace header: "Advance a day" (the one primary pill) and a quiet
 * "Advance a week" text button. Calls api.step then adopt(result.state). A blocked step shows a quiet watch line.
 */
import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { TrialState } from "../../types";

export function TrialClock({ state }: { state: TrialState }) {
  const { adopt } = useTrial();
  const [busy, setBusy] = useState<1 | 7 | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const closed = state.phase === "closed";
  const blocked = state.blocked ?? null;

  const step = async (days: 1 | 7) => {
    setBusy(days);
    setError(null);
    try {
      const r = await api.step(state.trial_id, days);
      if (!alive.current) return;
      adopt(r.state);
      setNote(!r.advanced && r.blocked ? r.blocked : null);
    } catch (e) {
      if (alive.current) setError(errorText(e));
    } finally {
      if (alive.current) setBusy(null);
    }
  };

  const disabled = closed || !!blocked || busy !== null;
  const watch = note ?? blocked;

  return (
    <div className="clock">
      <div className="clock__controls">
        <button type="button" className="btn btn--filled btn--sm" disabled={disabled} onClick={() => void step(1)}
          title={closed ? "The trial is closed" : blocked ?? undefined}>
          {busy === 1 ? "Working…" : "Advance a day"}
        </button>
        <button type="button" className="textbtn" disabled={disabled} onClick={() => void step(7)}>
          {busy === 7 ? "Working…" : "Advance a week"}
        </button>
      </div>
      {closed ? <p className="clock__line">The trial is closed.</p> : null}
      {!closed && watch ? (
        <p className="clock__line clock__line--watch" role="status" title={watch}>
          <span className="sdot sdot--watch"><span className="sdot__dot" aria-hidden="true" /></span>
          <span>{summariseBlock(watch, state.pending_approvals)}</span>
        </p>
      ) : null}
      {error ? <p className="clock__line clock__line--alert" role="alert">{error}</p> : null}
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
