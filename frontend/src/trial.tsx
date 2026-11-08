/**
 * TrialProvider: the one piece of shared app state (plan.md 6.2).
 *
 * useTrial() gives:
 *   trialId      current trial id, remembered in localStorage (try/catch), or null. A refresh, a second tab
 *                or a deep link reattaches to the same trial.
 *   state        latest TrialState from the API, or null
 *   tick         increments after every successful refresh/adopt; put it in useEffect deps to refetch
 *   setTrialId   switch trial (null clears it); triggers a refresh
 *   refresh      refetch /state (one request in flight at a time)
 *   adopt        accept a TrialState you already have (from step, decide or action responses) without refetching
 *   error        last refresh error message (backend down, etc.), or null
 *   lost         true once the server has confirmed twice that it no longer has the trial
 *
 * Resilience: api.ts retries transient failures. When a refresh still fails, the provider retries with
 * backoff (2 s doubling to 30 s) while the tab is visible, and resumes as soon as a refresh succeeds or
 * the tab becomes visible again. A "trial not found" 404 from any trial request is re-checked once with
 * GET /state after a short delay (another server instance may have it). Only if that also says "not
 * found" does the provider show TrialLost in place of the page, which stops polling and Play. The
 * stored trial id is never cleared by a failed request, only by the person (setTrialId / TrialLost).
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, errorText, onRetrying, onTrialMissing } from "./api";
import { useToast } from "./components/shared/Toast";
import { TrialLost } from "./components/shared/TrialLost";
import type { TrialState } from "./types";

const TRIAL_KEY = "unblind.trialId";
const RECHECK_MS = 1000;
const RECONNECT_TOAST_EVERY_MS = 10_000;
const STALE_AFTER_HIDDEN_MS = 10_000;

const backoffMs = (failures: number) => Math.min(30_000, 2000 * 2 ** Math.max(0, failures - 1));
const sleep = (ms: number) => new Promise<void>((res) => setTimeout(res, ms));

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
  lost: boolean;
}

const TrialContext = createContext<TrialContextValue | null>(null);

export function TrialProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [trialId, setTrialIdRaw] = useState<string | null>(readStoredId);
  const [state, setState] = useState<TrialState | null>(null);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [failures, setFailures] = useState(0);
  const [lost, setLost] = useState(false);

  const idRef = useRef(trialId); // the current id, for async callbacks that outlive a render
  const inflight = useRef<{ id: string; p: Promise<void> } | null>(null);
  const checking = useRef<string | null>(null);

  useEffect(() => {
    idRef.current = trialId;
  }, [trialId]);

  const healthy = useCallback((s: TrialState) => {
    setState(s);
    setError(null);
    setFailures(0);
    setLost(false);
    setTick((x) => x + 1);
  }, []);

  const failed = useCallback((e: unknown) => {
    setError(errorText(e));
    setFailures((n) => n + 1);
  }, []);

  const setTrialId = useCallback((id: string | null) => {
    writeStoredId(id);
    idRef.current = id;
    setTrialIdRaw(id);
    setLost(false);
    setError(null);
    setFailures(0);
    if (!id) setState(null);
  }, []);

  /** A request said the trial is not found. Ask once more before believing it. */
  const confirmLost = useCallback(async (id: string) => {
    if (checking.current === id) return;
    checking.current = id;
    try {
      await sleep(RECHECK_MS);
      if (idRef.current !== id) return;
      try {
        const s = await api.state(id);
        if (idRef.current === id) healthy(s);
      } catch (e) {
        if (idRef.current !== id) return;
        if (e instanceof ApiError && e.trialMissing) {
          setLost(true);
          setError(null);
        } else {
          failed(e);
        }
      }
    } finally {
      checking.current = null;
    }
  }, [healthy, failed]);

  const refresh = useCallback(async () => {
    const id = trialId;
    if (!id) {
      setState(null);
      return;
    }
    if (inflight.current?.id === id) return inflight.current.p; // never overlap
    const p = (async () => {
      try {
        const s = await api.state(id);
        if (idRef.current === id) healthy(s);
      } catch (e) {
        if (idRef.current !== id) return;
        // "trial not found" is handled by confirmLost (via onTrialMissing); never clear the id here
        if (!(e instanceof ApiError && e.trialMissing)) failed(e);
      }
    })();
    inflight.current = { id, p };
    try {
      await p;
    } finally {
      if (inflight.current?.p === p) inflight.current = null;
    }
  }, [trialId, healthy, failed]);

  const adopt = useCallback(
    (s: TrialState) => {
      if (s.trial_id !== idRef.current) {
        writeStoredId(s.trial_id);
        idRef.current = s.trial_id;
        setTrialIdRaw(s.trial_id);
      }
      healthy(s);
    },
    [healthy],
  );

  // load (and reload) the trial whenever the id changes
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // any trial request that gets "trial not found" (step in Play, kpis, decide...) triggers the re-check
  useEffect(() => onTrialMissing((id) => {
    if (id === idRef.current) void confirmLost(id);
  }), [confirmLost]);

  // a small, non-blocking "reconnecting" note while api.ts is retrying (at most every 10 s)
  useEffect(() => {
    let last = 0;
    return onRetrying((on) => {
      if (on && Date.now() - last > RECONNECT_TOAST_EVERY_MS) {
        last = Date.now();
        toast("Reconnecting…", "watch");
      }
    });
  }, [toast]);

  // while refreshes keep failing: retry with backoff, only while the tab is visible
  useEffect(() => {
    if (!failures || !trialId || lost) return;
    const timer = setTimeout(() => {
      if (document.visibilityState !== "hidden") void refresh();
    }, backoffMs(failures));
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        void refresh();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [failures, trialId, lost, refresh]);

  // back from a long time in the background (or another tab moved the trial on): catch up once
  useEffect(() => {
    if (!trialId || lost) return;
    let hiddenAt = 0;
    const onVis = () => {
      if (document.visibilityState === "hidden") hiddenAt = Date.now();
      else if (hiddenAt && Date.now() - hiddenAt > STALE_AFTER_HIDDEN_MS) void refresh();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [trialId, lost, refresh]);

  const startNew = useCallback(() => {
    setTrialId(null);
    navigate("/");
  }, [setTrialId, navigate]);

  const value = useMemo<TrialContextValue>(
    () => ({ trialId, state, tick, setTrialId, refresh, adopt, error, lost }),
    [trialId, state, tick, setTrialId, refresh, adopt, error, lost],
  );

  // When lost, the page (and with it the dock's Play loop and every per-page fetch) is unmounted.
  return (
    <TrialContext.Provider value={value}>
      {lost ? <TrialLost trialId={trialId} onStartNew={startNew} /> : children}
    </TrialContext.Provider>
  );
}

export function useTrial(): TrialContextValue {
  const ctx = useContext(TrialContext);
  if (!ctx) throw new Error("useTrial must be used inside <TrialProvider>");
  return ctx;
}
