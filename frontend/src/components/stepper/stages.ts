/**
 * Workspace stages and how their completion is derived from the trial state.
 * Shared contract between the VerticalStepper (shell) and the project workspace (pages).
 */
import type { Phase, TrialState } from "../../types";

export type StageId = "draft" | "design-review" | "recruitment" | "screening" | "dosing" | "follow-up" | "report";
export type StageStatus = "done" | "current" | "upcoming";

export interface StageInfo {
  id: StageId;
  label: string;
  status: StageStatus;
  /** Short plain-language status, e.g. "Done", "In progress", "Not started", "Waiting for sign-off" */
  note: string;
  /** Trial day to show in the hover card, or null before launch */
  day: number | null;
}

export const STAGES: Array<{ id: StageId; label: string }> = [
  { id: "draft", label: "Draft" },
  { id: "design-review", label: "Design review" },
  { id: "recruitment", label: "Recruitment" },
  { id: "screening", label: "Screening" },
  { id: "dosing", label: "Dosing" },
  { id: "follow-up", label: "Follow-up" },
  { id: "report", label: "Report" },
];

export function isStageId(s: string | undefined): s is StageId {
  return !!s && STAGES.some((x) => x.id === s);
}

const PHASE_ORDER: Phase[] = ["design", "recruitment", "dosing", "follow-up", "close-out", "closed"];

/** Index of the stage the trial is currently in (0 = Draft). */
export function currentStageIndex(launched: boolean, state: TrialState | null): number {
  if (!launched) return 0;
  if (!state) return 1;
  const p = Math.max(0, PHASE_ORDER.indexOf(state.phase));
  const signed = state.report_status?.status === "signed";
  if (p >= 4) return signed ? STAGES.length : 6; // close-out or closed: report
  if (p === 3) {
    const locked = state.primary_lock_day != null && state.day >= state.primary_lock_day;
    return locked ? 6 : 5;
  }
  if (p === 2) return 4;
  // Before dosing the backend reports phase "design" or "recruitment" at day -1 while the
  // pre-dosing sign-offs are open. Treat open sign-offs with nobody enrolled as Design review.
  const enrolled = state.counts?.enrolled ?? 0;
  if (p === 0 || (state.pending_approvals > 0 && enrolled === 0)) return 1;
  return enrolled > 0 ? 3 : 2;
}

/** Status for every stage. Pass launched = project has a trialId. */
export function deriveStages(launched: boolean, state: TrialState | null): StageInfo[] {
  const cur = currentStageIndex(launched, state);
  const day = state && state.day >= 0 ? state.day : null;
  const report = state?.report_status;
  return STAGES.map((s, i) => {
    const status: StageStatus = i < cur ? "done" : i === cur ? "current" : "upcoming";
    let note = status === "done" ? "Done" : status === "current" ? "In progress" : "Not started";
    if (s.id === "draft" && status === "current") note = "Writing";
    if (s.id === "report" && report && report.status !== "none") note = report.label || note;
    return { ...s, status, note, day: launched ? day : null };
  });
}
