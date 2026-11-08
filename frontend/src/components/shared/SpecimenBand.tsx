/**
 * SpecimenBand: retired in design v2. The synthetic notice is now one quiet line in the app footer,
 * so this renders nothing. Props are kept so existing pages still compile.
 */
export interface SpecimenBandProps {
  label?: string;
  message?: string;
  variant?: "synthetic" | "stub";
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function SpecimenBand(_props: SpecimenBandProps) {
  return null;
}
