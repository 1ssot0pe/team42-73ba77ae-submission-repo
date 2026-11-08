/**
 * Trial projects store.
 * Swap for the Postgres API later; keep this interface.
 *
 * Backed by localStorage. Every storage access is wrapped in try/catch so a blocked or full store
 * degrades to in-memory only instead of crashing the page.
 */

export type ProjectTemplate = "blank" | "psilocybin" | "mdma";
export type ProjectStatus = "draft" | "running" | "complete";

export interface Project {
  id: string;
  name: string;
  /** ISO timestamps */
  createdAt: string;
  updatedAt: string;
  template: ProjectTemplate;
  /** Protocol draft text written in the Draft stage */
  draft: string;
  /** Backend trial id once the trial is launched, else null */
  trialId: string | null;
  status: ProjectStatus;
}

export interface NewProject {
  name: string;
  template?: ProjectTemplate;
  draft?: string;
}

export interface ProjectStore {
  list(): Project[];
  get(id: string): Project | null;
  create(input: NewProject): Project;
  update(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>): Project | null;
  remove(id: string): void;
}

const KEY = "parallax.projects.v1";
let memory: Project[] | null = null;

function read(): Project[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        memory = parsed as Project[];
        return memory;
      }
    }
  } catch {
    /* blocked or corrupt: fall back to memory */
  }
  return memory ?? [];
}

function write(items: Project[]): void {
  memory = items;
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* blocked or full: memory only */
  }
  try {
    window.dispatchEvent(new CustomEvent("parallax:projects"));
  } catch {
    /* no window (tests) */
  }
}

function newId(): string {
  try {
    return `p-${crypto.randomUUID().slice(0, 8)}`;
  } catch {
    return `p-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export const projects: ProjectStore = {
  list() {
    return [...read()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  },
  get(id) {
    return read().find((p) => p.id === id) ?? null;
  },
  create(input) {
    const now = new Date().toISOString();
    const p: Project = {
      id: newId(),
      name: input.name.trim() || "Untitled trial",
      createdAt: now,
      updatedAt: now,
      template: input.template ?? "blank",
      draft: input.draft ?? "",
      trialId: null,
      status: "draft",
    };
    write([...read(), p]);
    return p;
  },
  update(id, patch) {
    let out: Project | null = null;
    const items = read().map((p) => {
      if (p.id !== id) return p;
      out = { ...p, ...patch, id: p.id, createdAt: p.createdAt, updatedAt: new Date().toISOString() };
      return out;
    });
    if (out) write(items);
    return out;
  },
  remove(id) {
    write(read().filter((p) => p.id !== id));
  },
};

/** Subscribe to changes made through this store (same tab). Returns an unsubscribe function. */
export function onProjectsChange(fn: () => void): () => void {
  const handler = () => fn();
  try {
    window.addEventListener("parallax:projects", handler);
    window.addEventListener("storage", handler);
  } catch {
    return () => {};
  }
  return () => {
    window.removeEventListener("parallax:projects", handler);
    window.removeEventListener("storage", handler);
  };
}
