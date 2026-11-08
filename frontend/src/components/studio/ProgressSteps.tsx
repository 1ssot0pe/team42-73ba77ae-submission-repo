/**
 * ProgressSteps: an honest working indicator while the evidence pipeline runs.
 * Steps advance on a timer; the last step never shows as done, because only the response ends the run.
 */
import { useEffect, useState } from "react";

export const STEPS = [
  "Resolving",
  "Finding the paper",
  "Choosing the registered endpoint",
  "Hunting blinding data",
  "Checking quotes",
  "Calculating",
];

export function ProgressSteps({ intervalMs = 5000 }: { intervalMs?: number }) {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setCurrent((c) => Math.min(c + 1, STEPS.length - 1)), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return (
    <div className="studio-progress" role="status" aria-live="polite">
      <ol className="studio-progress__list">
        {STEPS.map((s, i) => {
          const state = i < current ? "done" : i === current ? "current" : "todo";
          return (
            <li key={s} className={`studio-progress__step studio-progress__step--${state}`}>
              <span className="studio-progress__dot" aria-hidden="true" />
              <span>{s}</span>
              <span className="visually-hidden">{state === "done" ? " (done)" : state === "current" ? " (working)" : ""}</span>
            </li>
          );
        })}
      </ol>
      <p className="studio-small studio-muted">This can take up to a minute.</p>
    </div>
  );
}
