/**
 * EmptyState and LoadingHairline (design.md 8.21).
 * EmptyState props: title (optional heading); message (one sentence: what will appear and how to start);
 *                   action (optional node, usually one filled Button); center (centre-align the content).
 * LoadingHairline props: active (show the 1px ink progress hairline under the nav). Pair with a button
 *                   label "Agents working…". No spinners.
 */
import type { ReactNode } from "react";

export interface EmptyStateProps {
  title?: string;
  message: string;
  action?: ReactNode;
  center?: boolean;
}

export function EmptyState({ title, message, action, center = false }: EmptyStateProps) {
  return (
    <div className={`empty${center ? " empty--center" : ""}`}>
      <SpecimenIcon />
      {title ? <h2 className="empty__title">{title}</h2> : null}
      <p className="empty__text">{message}</p>
      {action ? <div className="row">{action}</div> : null}
    </div>
  );
}

/** Small outline specimen dish icon. */
export function SpecimenIcon() {
  return (
    <svg className="empty__icon" viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden="true">
      <ellipse cx="18" cy="22" rx="14" ry="6" />
      <path d="M4 22v-4c0-3.3 6.3-6 14-6s14 2.7 14 6v4" />
      <circle cx="14" cy="21" r="1.4" />
      <circle cx="21" cy="23" r="1" />
      <circle cx="23" cy="20" r="0.8" />
    </svg>
  );
}

export function LoadingHairline({ active }: { active: boolean }) {
  if (!active) return null;
  return <div className="loading-hairline" role="progressbar" aria-label="Agents working" />;
}
