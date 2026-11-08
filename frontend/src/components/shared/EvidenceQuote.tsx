/**
 * EvidenceQuote (design.md 8.12). Shows where an extracted fact came from.
 * Props: quote (the source text, shown italic); source (optional tag such as "protocol v2" or "ctgov:NCT03866174").
 */
export interface EvidenceQuoteProps {
  quote: string;
  source?: string;
}

export function EvidenceQuote({ quote, source }: EvidenceQuoteProps) {
  return (
    <blockquote className="quote">
      <span className="quote__text">&ldquo;{quote}&rdquo;</span>
      {source ? <span className="quote__source">{source}</span> : null}
    </blockquote>
  );
}
