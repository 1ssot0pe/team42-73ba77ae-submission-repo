/**
 * PhaseTrack: retired in design v2. The horizontal phase bar and day ruler are gone; the workspace
 * uses the VerticalStepper instead. Kept as a no-op so existing imports still compile.
 */
import type { TrialState } from "../../types";

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function PhaseTrack(_props: { state: TrialState }) {
  return null;
}
