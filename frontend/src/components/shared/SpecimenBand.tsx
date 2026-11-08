/**
 * SpecimenBand (design.md 8.2). Full-width hatched band directly under the nav, on every page. Never dismissible.
 * Props (all optional): label (default "SYNTHETIC SPECIMEN"); message (default the standard synthetic sentence);
 *        variant "synthetic" (default) | "stub" (for a module that is still a labelled STUB).
 */
export interface SpecimenBandProps {
  label?: string;
  message?: string;
  variant?: "synthetic" | "stub";
}

const DEFAULT_MESSAGE =
  "People, sites and raters are simulated so the whole trial can run in minutes. No real patient data.";

export function SpecimenBand({ label = "SYNTHETIC SPECIMEN", message = DEFAULT_MESSAGE, variant = "synthetic" }: SpecimenBandProps) {
  return (
    <div className={`band${variant === "stub" ? " band--stub" : ""}`} role="note" aria-label={label}>
      <div className="band__inner">
        <span className="band__label">{label}</span>
        <span className="band__text">{message}</span>
      </div>
    </div>
  );
}
