/**
 * TrialBridge: lets UI outside the workspace's TrialProvider (the nav's Developer panel) read the open trial,
 * and lets the workspace notice when the provider has swapped its children for TrialLost.
 *
 * The TrialProvider (trial.tsx, not ours to edit) renders TrialLost in place of its children once the server
 * confirms a trial is gone. <TrialBridge> sits inside the provider: while it is mounted it publishes
 * {trialId, state}; when the provider replaces it with TrialLost it unmounts, and onGone(true) tells the
 * workspace that the trial was lost (the provider itself is still mounted, so nothing else explains it).
 */
import { useEffect, useSyncExternalStore } from "react";
import { useTrial } from "./trial";
import type { TrialState } from "./types";

export interface TrialSnapshot {
  trialId: string | null;
  state: TrialState | null;
}

const EMPTY: TrialSnapshot = { trialId: null, state: null };
let snapshot: TrialSnapshot = EMPTY;
const listeners = new Set<() => void>();

function publish(next: TrialSnapshot) {
  if (next.trialId === snapshot.trialId && next.state === snapshot.state) return;
  snapshot = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The trial open in the workspace, or {null, null} when no workspace is open. Safe anywhere. */
export function useTrialSnapshot(): TrialSnapshot {
  return useSyncExternalStore(subscribe, () => snapshot, () => EMPTY);
}

/** Mount inside a TrialProvider. onGone(true) fires when the provider unmounts it (the trial was lost). */
export function TrialBridge({ onGone }: { onGone?: (gone: boolean) => void }) {
  const { trialId, state } = useTrial();

  useEffect(() => {
    publish({ trialId, state });
  }, [trialId, state]);

  useEffect(() => {
    onGone?.(false);
    return () => {
      publish(EMPTY);
      onGone?.(true);
    };
  }, [onGone]);

  return null;
}
