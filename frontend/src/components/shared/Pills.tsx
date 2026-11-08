/**
 * StatusPill and DecisionPill (design.md 8.15, Section 3 status tints).
 * StatusPill props: tone "good" | "watch" | "alert" | "neutral" | "outline" | "ink" (default neutral);
 *                   size "md" | "lg"; attention (filled pill for watch or alert); children is the word
 *                   (colour is never the only signal). Renders a coloured dot plus the word by default.
 * DecisionPill props: decision "eligible" | "excluded" | "needs_clinician"; size.
 * SpecimenTag props: label (default "Synthetic"): a quiet sentence-case note for charts.
 * toneForStatus(word) maps common states (approved, pending, missing, high...) to a tone.
 */
import type { ReactNode } from "react";
import type { ScreeningDecision } from "../../types";

export type Tone = "good" | "watch" | "alert" | "neutral" | "outline" | "ink";

export interface StatusPillProps {
  tone?: Tone;
  size?: "md" | "lg";
  children: ReactNode;
  title?: string;
  className?: string;
  /** Show a filled pill instead of a dot, for a status that needs a human (watch or alert tones only). */
  attention?: boolean;
}

/** Status as a small coloured dot plus a word. A filled pill only when `attention` is set on watch or alert. */
export function StatusPill({ tone = "neutral", size = "md", children, title, className = "", attention = false }: StatusPillProps) {
  const filled = attention && (tone === "watch" || tone === "alert");
  const cls = `pill pill--${tone}${size === "lg" ? " pill--lg" : ""}${filled ? " pill--attention" : ""} ${className}`.trim();
  return (
    <span className={cls} title={title}>
      <span className="pill__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

const DECISION: Record<ScreeningDecision, { tone: Tone; word: string }> = {
  eligible: { tone: "good", word: "Eligible" },
  needs_clinician: { tone: "watch", word: "Needs clinician" },
  excluded: { tone: "alert", word: "Excluded" },
};

export interface DecisionPillProps {
  decision: ScreeningDecision | string;
  size?: "md" | "lg";
}

/** Eligible (good), Needs clinician (watch), Excluded (alert). Follow it with the reasons. */
export function DecisionPill({ decision, size = "md" }: DecisionPillProps) {
  const d = DECISION[decision as ScreeningDecision] ?? { tone: "neutral" as Tone, word: decision.replace(/_/g, " ") };
  return <StatusPill tone={d.tone} size={size}>{d.word}</StatusPill>;
}

/** The small "Synthetic" note on charts. Sentence case, 12px smoke, no hatching. */
export function SpecimenTag({ label = "Synthetic" }: { label?: string }) {
  const text = label === label.toUpperCase() ? label.charAt(0) + label.slice(1).toLowerCase() : label;
  return <span className="synthetic-note">{text}</span>;
}

/** Map a status word to a tint. Unknown words are neutral. */
export function toneForStatus(word: string | null | undefined): Tone {
  const w = (word || "").toLowerCase();
  if (["present", "eligible", "approved", "signed", "done", "good", "real", "low", "pass", "ok", "complete", "completed"].includes(w)) return "good";
  if (["pending", "needs_clinician", "needs clinician", "medium", "warn", "watch", "scheduled", "waiting"].includes(w)) return "watch";
  if (["missing", "excluded", "high", "rejected", "alert", "bad", "critical", "drift", "fail", "failed", "missed"].includes(w)) return "alert";
  return "neutral";
}
