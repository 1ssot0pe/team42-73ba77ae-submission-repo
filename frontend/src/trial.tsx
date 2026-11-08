/**
 * TrialProvider: the one piece of shared app state (plan.md 6.2).
 *
 * useTrial() gives:
 *   trialId      current trial id, remembered in localStorage (try/catch), or null
 *   state        latest TrialState from the API, or null
 *   tick         increments after every successful refresh/adopt; put it in useEffect deps to refetch
 *   setTrialId   switch trial (null clears it); triggers a refresh
 *   refresh      refetch /state; if the server no longer knows the trial (404), clears it
 *   adopt        accept a TrialState you already have (from step, decide or action responses) without refetching
 *   error        last refresh error message (backend down, etc.), or null
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, errorText } from "./api";
import type { TrialState } from "./types";

const TRIAL_KEY = "unblind.trialId";

function readStoredId(): string | null {
  try {
    return localStorage.getItem(TRIAL_KEY);
  } catch {
    return null;
  }
}

function writeStoredId(id: string | null): void {
  try {
    if (id) localStorage.setItem(TRIAL_KEY, id);
    else localStorage.removeItem(TRIAL_KEY);
  } catch {
    /* storage blocked: keep it in memory only */
  }
}

export interface TrialContextValue {
  trialId: string | null;
  state: TrialState | null;
  tick: number;
  setTrialId: (id: string | null) => void;
  refresh: () => Promise<void>;
  adopt: (s: TrialState) => void;
  error: string | null;
}

const TrialContext = createContext<TrialContextValue | null>(null);

export function TrialProvider({ children }: { children: ReactNode }) {
  const [trialId, setTrialIdRaw] = useState<string | null>(readStoredId);
  const [state, setState] = useState<TrialState | null>(null);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const setTrialId = useCallback((id: string | null) => {
    writeStoredId(id);
    setTrialIdRaw(id);
    if (!id) setState(null);
  }, []);

  const refresh = useCallback(async () => {
    if (!trialId) {
      setState(null);
      return;
    }
    try {
      const s = await api.state(trialId);
      setState(s);
      setError(null);
      setTick((x) => x + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        // server restarted: the in-memory trial is gone
        setTrialId(null);
        setState(null);
        setError(null);
      } else {
        setError(errorText(e));
      }
    }
  }, [trialId, setTrialId]);

  const adopt = useCallback(
    (s: TrialState) => {
      if (s.trial_id !== trialId) {
        writeStoredId(s.trial_id);
        setTrialIdRaw(s.trial_id);
      }
      setState(s);
      setError(null);
      setTick((x) => x + 1);
    },
    [trialId],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<TrialContextValue>(
    () => ({ trialId, state, tick, setTrialId, refresh, adopt, error }),
    [trialId, state, tick, setTrialId, refresh, adopt, error],
  );

  return <TrialContext.Provider value={value}>{children}</TrialContext.Provider>;
}

export function useTrial(): TrialContextValue {
  const ctx = useContext(TrialContext);
  if (!ctx) throw new Error("useTrial must be used inside <TrialProvider>");
  return ctx;
}
