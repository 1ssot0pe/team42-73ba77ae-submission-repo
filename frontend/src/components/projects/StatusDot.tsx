/**
 * Status as a small coloured dot plus a word (design v2: no filled pills for status).
 * tone maps to the status tokens; the word always carries the meaning.
 */
import type { ReactNode } from "react";
import type { ProjectStatus } from "../../store/projects";

export type DotTone = "good" | "watch" | "alert" | "neutral";

export function StatusDot({ tone = "neutral", children, className = "" }: { tone?: DotTone; children: ReactNode; className?: string }) {
  return (
    <span className={`sdot sdot--${tone} ${className}`.trim()}>
      <span className="sdot__dot" aria-hidden="true" />
      <span className="sdot__word">{children}</span>
    </span>
  );
}

export const STATUS_WORD: Record<ProjectStatus, string> = { draft: "Draft", running: "Running", complete: "Complete" };
export const STATUS_TONE: Record<ProjectStatus, DotTone> = { draft: "neutral", running: "watch", complete: "good" };

export function ProjectStatusDot({ status }: { status: ProjectStatus }) {
  return <StatusDot tone={STATUS_TONE[status] ?? "neutral"}>{STATUS_WORD[status] ?? "Draft"}</StatusDot>;
}
