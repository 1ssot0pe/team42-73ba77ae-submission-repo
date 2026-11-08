/**
 * Button (design-v2.md Controls). Filled is the one ink pill per page; outline and ghost are quiet text buttons.
 * Props: variant "filled" (the one primary action per region) | "outline" (secondary) | "ghost" (inline, nav);
 *        size "md" (36px, default) | "dock" (40px) | "sm" (30px);
 *        busy (disables and shows busyLabel, default "Agents working…"); plus every native <button> prop.
 * buttonClass(variant, size) returns the class string for links styled as buttons.
 */
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "filled" | "outline" | "ghost";
export type ButtonSize = "md" | "dock" | "sm";

export function buttonClass(variant: ButtonVariant = "outline", size: ButtonSize = "md", extra = ""): string {
  return ["btn", `btn--${variant}`, size !== "md" ? `btn--${size}` : "", extra].filter(Boolean).join(" ");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** true while the request runs: disables the button and swaps the label */
  busy?: boolean;
  busyLabel?: string;
}

/** A pill button. Defaults to type="button" and the outline variant. */
export function Button({ variant = "outline", size = "md", busy = false, busyLabel = "Agents working…",
  className = "", disabled, children, type = "button", ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} disabled={disabled || busy}
      aria-busy={busy || undefined} {...rest}>
      {busy ? busyLabel : children}
    </button>
  );
}

/** Small play / pause glyph for the dock's Play button. */
export function PlayGlyph({ playing = false }: { playing?: boolean }) {
  return playing ? (
    <svg className="btn__glyph" viewBox="0 0 10 10" aria-hidden="true"><rect x="1" y="1" width="3" height="8" fill="currentColor" /><rect x="6" y="1" width="3" height="8" fill="currentColor" /></svg>
  ) : (
    <svg className="btn__glyph" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z" fill="currentColor" /></svg>
  );
}
