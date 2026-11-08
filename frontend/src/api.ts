/**
 * Typed client for every endpoint in plan.md 5.1 (backend/main.py). Paths are relative, so the
 * Vite dev server proxies /api to the backend (VITE_API_TARGET, default http://127.0.0.1:8000).
 * Errors throw ApiError with the HTTP status (0 for network errors and timeouts) and the server's detail.
 *
 * Resilience (the backend runs as many short-lived Vercel instances, with cold starts and blips):
 * - every request has its own timeout (AbortController);
 * - transient failures are retried with exponential backoff and jitter (300 ms, 900 ms, 2.7 s), bounded:
 *   GETs retry on network errors, timeouts, 409, 429, 502, 503 and 504 (at most 4 attempts);
 *   POSTs retry only on network errors before a response and on 502 and 503 (at most 3 attempts);
 *   other 4xx are never retried;
 * - at most TRIAL_SLOTS requests to /api/trials/{id}/... are in flight at once; the rest queue;
 * - a 404 meaning "this trial is not on the server" is flagged (ApiError.trialMissing) and reported to
 *   onTrialMissing listeners. TrialProvider re-checks before declaring the trial lost.
 */
import type {
  ActionResult,
  Approval,
  BottlenecksFile,
  CreateTrialBody,
  DecideResult,
  EventsQuery,
  EvidenceReport,
  KpiMap,
  MessagesResponse,
  ModuleActionResult,
  ProtocolSummary,
  ProtocolText,
  RecordSectionName,
  RecordSections,
  StepResult,
  TrialEvent,
  TrialState,
  ViewModel,
} from "./types";

/** GET /api/health. The server now reports a count instead of the list of trial ids. */
export interface Health {
  ok: boolean;
  gemini: boolean;
  trial_count?: number;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string, public trialMissing = false) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/* ------------------------------------------------------------------ events for TrialProvider */
type MissingListener = (trialId: string) => void;
type RetryListener = (retrying: boolean) => void;
const missingListeners = new Set<MissingListener>();
const retryListeners = new Set<RetryListener>();
let retrying = 0;

/** Called with the trial id whenever a trial-scoped request gets "trial not found". Returns an unsubscribe. */
export function onTrialMissing(fn: MissingListener): () => void {
  missingListeners.add(fn);
  return () => { missingListeners.delete(fn); };
}

/** Called with true while at least one request is waiting to retry, false when none are. */
export function onRetrying(fn: RetryListener): () => void {
  retryListeners.add(fn);
  return () => { retryListeners.delete(fn); };
}

function setRetrying(delta: number): void {
  const before = retrying > 0;
  retrying = Math.max(0, retrying + delta);
  if (before !== retrying > 0) retryListeners.forEach((fn) => fn(retrying > 0));
}

/* ------------------------------------------------------------------ helpers */
const TRIAL_PATH = /^\/api\/trials\/([^/?]+)\//;
const BACKOFF_MS = [300, 900, 2700];
const GET_TIMEOUT_MS = 20_000;
const POST_TIMEOUT_MS = 65_000; // a 30-day step can run close to Vercel's 60 s maxDuration
const TRIAL_SLOTS = 2;

const sleep = (ms: number) => new Promise<void>((res) => setTimeout(res, ms));
const jitter = (ms: number) => Math.round(ms * (0.75 + Math.random() * 0.5));

/** The backend's "trial not found", or its older "no trial X in this server session; create one". */
function isTrialMissing(status: number, detail: string, path: string): boolean {
  return status === 404 && TRIAL_PATH.test(path) && /trial not found|^no trial\b/i.test(detail.trim());
}

/** Resolves once the tab is visible (immediately when it already is, or outside a browser). */
export function whenVisible(): Promise<void> {
  if (typeof document === "undefined" || document.visibilityState !== "hidden") return Promise.resolve();
  return new Promise((res) => {
    const on = () => {
      if (document.visibilityState !== "hidden") {
        document.removeEventListener("visibilitychange", on);
        res();
      }
    };
    document.addEventListener("visibilitychange", on);
  });
}

/* Concurrency limit for trial-scoped requests. A page refresh fires ~6 GETs at once; queue past TRIAL_SLOTS. */
let active = 0;
const queue: Array<() => void> = [];

async function acquire(): Promise<void> {
  if (active < TRIAL_SLOTS) {
    active++;
    return;
  }
  await new Promise<void>((res) => queue.push(res));
}

function release(): void {
  const next = queue.shift();
  if (next) next(); // hand the slot straight on
  else active--;
}

async function readDetail(r: Response): Promise<string> {
  const text = await r.text().catch(() => "");
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* not JSON */
  }
  return text || r.statusText;
}

interface Opts {
  method?: "GET" | "POST";
  body?: unknown;
  timeoutMs?: number;
}

/** One attempt. Network errors and timeouts become ApiError(0, ...). */
async function attempt(path: string, method: string, body: string | undefined, timeoutMs: number): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(path, { method, body, headers: { "Content-Type": "application/json" }, signal: ctrl.signal });
  } catch {
    throw ctrl.signal.aborted
      ? new ApiError(0, `The server did not answer within ${Math.round(timeoutMs / 1000)} seconds`)
      : new ApiError(0, "Could not reach the server");
  } finally {
    clearTimeout(timer);
  }
}

/** The one request helper: timeout, bounded retries with backoff, concurrency limit, trial-missing signal. */
async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const isGet = method === "GET";
  const body = isGet ? undefined : JSON.stringify(opts.body ?? {});
  const timeoutMs = opts.timeoutMs ?? (isGet ? GET_TIMEOUT_MS : POST_TIMEOUT_MS);
  const limited = TRIAL_PATH.test(path);
  const maxAttempts = isGet ? BACKOFF_MS.length + 1 : 3;

  for (let n = 1; ; n++) {
    let err: ApiError;
    let retryable: boolean;
    let retryAfterMs = 0;

    if (limited) await acquire();
    try {
      const r = await attempt(path, method, body, timeoutMs);
      if (r.ok) return (await r.json()) as T;
      const detail = await readDetail(r);
      const missing = isTrialMissing(r.status, detail, path);
      err = new ApiError(r.status, detail, missing);
      if (missing) {
        const id = decodeURIComponent(TRIAL_PATH.exec(path)![1]);
        missingListeners.forEach((fn) => fn(id));
      }
      // POSTs (step, decide, module actions, create) retry only on 502/503: the platform failed before
      // the function ran. Not on 504: on Vercel the function may still finish after the gateway gives up,
      // and the server's locked mutations prevent lost updates but do not de-duplicate a repeated step,
      // so retrying could advance the trial twice. GETs also retry 504, 409 and 429.
      retryable = (isGet ? [502, 503, 504, 409, 429] : [502, 503]).includes(r.status);
      const ra = Number(r.headers.get("Retry-After"));
      if (ra > 0 && ra <= 10) retryAfterMs = ra * 1000;
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
      err = e;
      // status 0: network error or timeout. A POST is retried only when fetch failed before any
      // response; a timed-out POST may have run on the server, so it is not repeated.
      retryable = isGet || !/did not answer/.test(e.detail);
    } finally {
      if (limited) release();
    }

    if (!retryable || n >= maxAttempts) throw err;
    setRetrying(1);
    try {
      await sleep(Math.max(retryAfterMs, jitter(BACKOFF_MS[n - 1] ?? BACKOFF_MS[BACKOFF_MS.length - 1])));
    } finally {
      setRetrying(-1);
    }
  }
}

const j = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body: unknown = {}, timeoutMs?: number) =>
  request<T>(path, { method: "POST", body, timeoutMs });

const enc = encodeURIComponent;
const t = (id: string) => `/api/trials/${enc(id)}`;

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  /* meta */
  health: () => j<Health>("/api/health"),
  bottlenecks: () => j<BottlenecksFile>("/api/bottlenecks"),
  protocols: () => j<ProtocolSummary[]>("/api/protocols"),
  protocol: (name: string) => j<ProtocolText>(`/api/protocols/${enc(name)}`),

  /* trials */
  createTrial: (b: CreateTrialBody) => post<TrialState>("/api/trials", b),
  trials: () => j<TrialState[]>("/api/trials"),
  state: (id: string) => j<TrialState>(`${t(id)}/state`),
  /** days is clamped to 1..30 by the server. Waits while the tab is hidden, so Play pauses in the background. */
  step: async (id: string, days: number) => {
    await whenVisible();
    return post<StepResult>(`${t(id)}/step`, { days });
  },
  setAutoApprove: (id: string, on: boolean) => post<TrialState>(`${t(id)}/auto_approve${qs({ on })}`),

  /** Fetch chosen record sections. Omit sections to get every allowed one. */
  record: <K extends RecordSectionName>(id: string, sections?: K[]) =>
    j<Partial<Pick<RecordSections, K>>>(`${t(id)}/record${qs({ sections: sections?.join(",") })}`),

  events: (id: string, q: EventsQuery = {}) =>
    j<TrialEvent[]>(`${t(id)}/events${qs({ since: q.since, module: q.module, level: q.level, limit: q.limit })}`),

  approvals: (id: string, status: "pending" | "all" = "pending") =>
    j<Approval[]>(`${t(id)}/approvals${qs({ status })}`),

  /** 400 if reviewer is empty; 404 if the approval is unknown or already decided */
  decide: (id: string, approvalId: string, reviewer: string, decision: "approved" | "rejected", comment = "") =>
    post<DecideResult>(`${t(id)}/approvals/${enc(approvalId)}`, { reviewer, decision, comment }),

  kpis: (id: string) => j<KpiMap>(`${t(id)}/kpis`),
  messages: (id: string) => j<MessagesResponse>(`${t(id)}/messages`),

  /* modules */
  view: (id: string, module: string) => j<ViewModel>(`${t(id)}/modules/${enc(module)}/view`),
  action: <R = ModuleActionResult>(id: string, module: string, action: string, payload: Record<string, unknown> = {}) =>
    post<ActionResult<R>>(`${t(id)}/modules/${enc(module)}/actions/${enc(action)}`, { payload }),

  /* evidence engine (existing pipeline; needs internet) */
  evidence: (input: string) => post<EvidenceReport>("/api/evidence/run", { input }, 180_000),
};

/* ------------------------------------------------------------------ reviewer name (localStorage) */
const REVIEWER_KEY = "unblind.reviewer";

export function getReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) || "";
  } catch {
    return "";
  }
}

export function setReviewer(name: string): void {
  try {
    localStorage.setItem(REVIEWER_KEY, name);
  } catch {
    /* storage blocked: the name lives only in component state */
  }
}

/** Plain-language message for a thrown error, for toasts and inline errors. */
export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.trialMissing) return "This trial is no longer on the server. Start a new trial.";
    if (e.status === 0) return `${e.detail}. Check your connection and try again.`;
    if (e.status >= 500) return `The server had a problem (${e.status}). Try again in a moment.`;
    if (e.status === 429) return "The server is busy. Try again in a moment.";
    return e.detail || `Request failed (${e.status})`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
