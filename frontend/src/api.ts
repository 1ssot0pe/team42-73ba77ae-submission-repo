/**
 * Typed client for every endpoint in plan.md 5.1 (backend/main.py). Paths are relative, so the
 * Vite dev server proxies /api to the backend (VITE_API_TARGET, default http://127.0.0.1:8000).
 * Errors throw ApiError with the HTTP status and the server's detail message.
 */
import type {
  ActionResult,
  Approval,
  BottlenecksFile,
  CreateTrialBody,
  DecideResult,
  EventsQuery,
  EvidenceReport,
  Health,
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

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    const text = await r.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown = {}) => j<T>(path, { method: "POST", body: JSON.stringify(body) });

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
  /** days is clamped to 1..30 by the server */
  step: (id: string, days: number) => post<StepResult>(`${t(id)}/step`, { days }),
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
  evidence: (input: string) => post<EvidenceReport>("/api/evidence/run", { input }),
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
  if (e instanceof ApiError) return e.detail || `Request failed (${e.status})`;
  if (e instanceof Error) return e.message;
  return String(e);
}
