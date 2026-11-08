/**
 * TrialLost: shown by TrialProvider in place of the page when the server no longer has the current trial
 * (confirmed by a second check). Minimal error state built from the shared EmptyState and Button.
 * Props: onStartNew (clears the stored trial id and goes to the start page).
 */
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

export function TrialLost({ trialId, onStartNew }: { trialId: string | null; onStartNew: () => void }) {
  return (
    <main className="page" role="alert">
      <EmptyState
        center
        title={trialId ? `Trial ${trialId} has expired` : "This trial has expired"}
        message="This trial is no longer on the server. Simulated trials are kept for a limited time. Start a new trial."
        action={<Button variant="filled" onClick={onStartNew}>Start a new trial</Button>}
      />
    </main>
  );
}
