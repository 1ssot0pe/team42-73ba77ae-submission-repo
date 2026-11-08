/**
 * VerticalStepper (design-v2.md Structure). Sits on the right of the project workspace, sticky below the nav.
 * One 1px line with a dot per stage: filled ink is done, a ring is current, hollow is upcoming.
 * Hover or focus on a stage shows a small flat card with the stage name, its status note and the trial day.
 * Below 900px it becomes a horizontal row of dots under the nav (labels hidden, the card still shows).
 * Props: stages (from deriveStages), activeId (the stage being viewed, which may differ from the
 * trial's current stage), onSelect (called with the stage id on click).
 */
import { useId } from "react";
import type { StageId, StageInfo } from "./stages";
import "../../styles/stepper.css";

export interface VerticalStepperProps {
  stages: StageInfo[];
  activeId: StageId;
  onSelect: (id: StageId) => void;
}

const STATUS_WORD: Record<StageInfo["status"], string> = { done: "done", current: "current stage", upcoming: "upcoming" };

export function VerticalStepper({ stages, activeId, onSelect }: VerticalStepperProps) {
  const base = useId();
  return (
    <nav className="stepper" aria-label="Trial stages">
      <ol className="stepper__list" role="list">
        {stages.map((s) => {
          const active = s.id === activeId;
          const tipId = `${base}-${s.id}`;
          return (
            <li key={s.id} className={`stepper__item stepper__item--${s.status}${active ? " is-active" : ""}`}>
              <button type="button" className="stepper__btn" onClick={() => onSelect(s.id)}
                aria-current={active ? "step" : undefined} aria-describedby={tipId}>
                <span className="stepper__dot" aria-hidden="true" />
                <span className="stepper__label">{s.label}</span>
                <span className="visually-hidden">, {STATUS_WORD[s.status]}</span>
              </button>
              <span id={tipId} role="tooltip" className="stepper__card">
                <span className="stepper__card-title">{s.label}</span>
                <span className="stepper__card-note">{s.note}</span>
                {s.day != null ? <span className="stepper__card-day">Day {s.day}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default VerticalStepper;
