/**
 * Extra API calls kept apart from api.ts so that file stays untouched.
 * runEvidence (Evidence studio) aborts after 55 s by default (the live server's limit) and throws EvidenceTimeout.
 * stepTrial (trial clock) is a single, unretried POST with a long timeout: a slow step must not be sent twice.
 */
import { api, ApiError } from "./api";
import type { EvidenceReport, StepResult } from "./types";
import type { Health } from "./api";

export class EvidenceTimeout extends Error {
  constructor() {
    super("The analysis took too long.");
    this.name = "EvidenceTimeout";
  }
}

export interface RunEvidenceOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function runEvidence(input: string, opts: RunEvidenceOptions = {}): Promise<EvidenceReport> {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, opts.timeoutMs ?? 55000);
  const onOuterAbort = () => ctrl.abort();
  opts.signal?.addEventListener("abort", onOuterAbort);
  try {
    const r = await fetch("/api/evidence/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input }),
      signal: ctrl.signal,
    });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      let detail = text;
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
      } catch {
        /* not JSON */
      }
      throw new ApiError(r.status, detail);
    }
    const body: unknown = await r.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new ApiError(502, "Unexpected response");
    return body as EvidenceReport;
  } catch (e) {
    if (timedOut) throw new EvidenceTimeout();
    throw e;
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onOuterAbort);
  }
}

export const health = (): Promise<Health> => api.health();

export interface StepTrialOptions {
  /** Give up after this long (default 120 s). The step may still finish on the server. */
  timeoutMs?: number;
  /** Abort from outside, for example on unmount. */
  signal?: AbortSignal;
}

/**
 * POST /api/trials/{id}/step once, with no automatic retries. api.step gives up after 65 s and a slow step
 * on a cold server can take longer, so the trial clock uses this instead. A retry is the caller's choice and
 * must first check the trial's day (api.state) so a step that did run is not sent again.
 * Errors are ApiError: status 0 for a network error, a timeout or an outside abort.
 */
export async function stepTrial(id: string, days: number, opts: StepTrialOptions = {}): Promise<StepResult> {
  const timeoutMs = opts.timeoutMs ?? 120_000;
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onOuterAbort = () => ctrl.abort();
  if (opts.signal?.aborted) ctrl.abort();
  else opts.signal?.addEventListener("abort", onOuterAbort);
  try {
    let r: Response;
    try {
      r = await fetch(`/api/trials/${encodeURIComponent(id)}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days }),
        signal: ctrl.signal,
      });
    } catch {
      if (timedOut) throw new ApiError(0, `The server did not answer within ${Math.round(timeoutMs / 1000)} seconds`);
      if (ctrl.signal.aborted) throw new ApiError(0, "The request was cancelled");
      throw new ApiError(0, "Could not reach the server");
    }
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      let detail = text || r.statusText;
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
      } catch {
        /* not JSON */
      }
      const missing = r.status === 404 && /trial not found|^no trial\b/i.test(detail.trim());
      throw new ApiError(r.status, detail, missing);
    }
    const body: unknown = await r.json().catch(() => null);
    if (!body || typeof body !== "object" || !("state" in body)) throw new ApiError(502, "Unexpected response");
    return body as StepResult;
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onOuterAbort);
  }
}
