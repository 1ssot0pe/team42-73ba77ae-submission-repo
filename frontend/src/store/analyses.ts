/**
 * Evidence studio analyses store.
 * Swap for the Postgres API later; keep this interface.
 *
 * Backed by localStorage under "parallax.analyses.v1". Every storage access is wrapped in try/catch
 * so a blocked or full store degrades to in-memory only. Only the latest MAX analyses are kept.
 */
import type { EvidenceReport } from "../types";

export interface Analysis {
  id: string;
  input: string;
  title: string;
  /** ISO timestamp */
  createdAt: string;
  /** The raw report JSON from POST /api/evidence/run */
  report: EvidenceReport;
}

export interface NewAnalysis {
  id?: string;
  input: string;
  title?: string;
  report: EvidenceReport;
}

export interface AnalysisStore {
  /** Newest first */
  list(): Analysis[];
  get(id: string): Analysis | null;
  /** Creates, or replaces the analysis with the same id */
  save(input: NewAnalysis): Analysis;
  remove(id: string): void;
}

const KEY = "parallax.analyses.v1";
const MAX = 20;
let memory: Analysis[] | null = null;

function isAnalysis(v: unknown): v is Analysis {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  return typeof o.id === "string" && typeof o.input === "string" && typeof o.createdAt === "string";
}

function read(): Analysis[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        memory = parsed.filter(isAnalysis).map((a) => ({
          ...a,
          title: typeof a.title === "string" ? a.title : "",
          report: a.report && typeof a.report === "object" ? a.report : {},
        }));
        return memory;
      }
    }
  } catch {
    /* blocked or corrupt: fall back to memory */
  }
  return memory ?? [];
}

function newestFirst(items: Analysis[]): Analysis[] {
  return [...items].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

function write(items: Analysis[]): void {
  let kept = newestFirst(items).slice(0, MAX);
  memory = kept;
  // If the store is full, drop the oldest and try again until it fits or nothing is left.
  while (kept.length > 0) {
    try {
      localStorage.setItem(KEY, JSON.stringify(kept));
      break;
    } catch {
      kept = kept.slice(0, -1);
    }
  }
  if (kept.length === 0) {
    try {
      localStorage.setItem(KEY, "[]");
    } catch {
      /* blocked: memory only */
    }
  }
  try {
    window.dispatchEvent(new CustomEvent("parallax:analyses"));
  } catch {
    /* no window (tests) */
  }
}

function newId(): string {
  try {
    return `a-${crypto.randomUUID().slice(0, 8)}`;
  } catch {
    return `a-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export const analyses: AnalysisStore = {
  list() {
    return newestFirst(read());
  },
  get(id) {
    return read().find((a) => a.id === id) ?? null;
  },
  save(input) {
    const items = read();
    const existing = input.id ? items.find((a) => a.id === input.id) : undefined;
    const a: Analysis = {
      id: existing?.id ?? input.id ?? newId(),
      input: input.input,
      title: input.title ?? existing?.title ?? "",
      createdAt: existing?.createdAt ?? new Date().toISOString(),
      report: input.report,
    };
    write([...items.filter((x) => x.id !== a.id), a]);
    return a;
  },
  remove(id) {
    write(read().filter((a) => a.id !== id));
  },
};

/** Subscribe to changes made through this store (same tab and other tabs). Returns an unsubscribe function. */
export function onAnalysesChange(fn: () => void): () => void {
  const handler = () => fn();
  try {
    window.addEventListener("parallax:analyses", handler);
    window.addEventListener("storage", handler);
  } catch {
    return () => {};
  }
  return () => {
    window.removeEventListener("parallax:analyses", handler);
    window.removeEventListener("storage", handler);
  };
}
