/**
 * Extra API calls for the Evidence studio. Kept apart from api.ts so that file stays untouched.
 * runEvidence aborts after 55 s by default (the live server's limit) and throws EvidenceTimeout.
 */
import { api, ApiError } from "./api";
import type { EvidenceReport, Health } from "./types";

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
