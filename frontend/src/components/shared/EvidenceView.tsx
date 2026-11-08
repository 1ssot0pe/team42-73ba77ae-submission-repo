/**
 * EvidenceView: renders free-form evidence (an approval's `evidence`, an alert's `evidence`) without knowing its shape.
 * Props: evidence (string | string[] | object | object[]); source (optional tag for quotes); maxItems (default 20).
 *  - a string becomes an EvidenceQuote
 *  - a list of strings becomes a mono list (diff lines starting with + or - are tinted)
 *  - a list of {quote} objects becomes EvidenceQuotes; other objects become one summary line each
 *  - an object shows each key as a label with its value rendered by the same rules
 */
import type { ReactNode } from "react";
import { EvidenceQuote } from "./EvidenceQuote";
import { humanise } from "./format";

export interface EvidenceViewProps {
  evidence: unknown;
  source?: string;
  maxItems?: number;
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function scalar(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number" || typeof v === "string") return String(v);
  if (Array.isArray(v)) return v.map(scalar).join(", ");
  if (isObj(v)) return Object.entries(v).map(([k, x]) => `${k}: ${scalar(x)}`).join("; ");
  return String(v);
}

/** One readable line for an object row, e.g. an applicant: "APP-0012 Sam K.: reason; reason". */
function summarise(o: Record<string, unknown>): string {
  const head = [o.id, o.name ?? o.title].filter(Boolean).join(" ");
  const screening = isObj(o.screening) ? o.screening : null;
  const reasons = screening && Array.isArray(screening.reasons) ? (screening.reasons as unknown[]).map(scalar).join("; ") : "";
  if (head && reasons) return `${head}: ${reasons}`;
  if (head) {
    const rest = Object.entries(o).filter(([k]) => !["id", "name", "title"].includes(k)).slice(0, 4)
      .map(([k, v]) => `${k} ${scalar(v)}`).join(", ");
    return rest ? `${head}: ${rest}` : head;
  }
  return scalar(o);
}

function quotesIn(o: Record<string, unknown>): string | null {
  return typeof o.quote === "string" ? o.quote : null;
}

function render(ev: unknown, source: string | undefined, maxItems: number, depth: number): ReactNode {
  if (ev === null || ev === undefined || ev === "") return null;
  if (typeof ev === "string") return <EvidenceQuote quote={ev} source={source} />;
  if (typeof ev === "number" || typeof ev === "boolean") return <span className="t-mono">{scalar(ev)}</span>;

  if (Array.isArray(ev)) {
    if (ev.length === 0) return <span className="t-body-sm c-ash">None</span>;
    const shown = ev.slice(0, maxItems);
    const more = ev.length - shown.length;
    if (shown.every((x) => isObj(x) && quotesIn(x))) {
      return (
        <div className="evidence">
          {shown.map((x, i) => {
            const o = x as Record<string, unknown>;
            const src = typeof o.source === "string" ? o.source : typeof o.criterion === "string" ? o.criterion : source;
            return <EvidenceQuote key={i} quote={quotesIn(o) as string} source={src} />;
          })}
          {more > 0 ? <span className="t-caption c-ash">and {more} more</span> : null}
        </div>
      );
    }
    return (
      <ul className="evidence__list">
        {shown.map((x, i) => {
          const line = typeof x === "string" ? x : isObj(x) ? summarise(x) : scalar(x);
          const cls = typeof x === "string" && /^\+(?!\+\+)/.test(x) ? "diff-add"
            : typeof x === "string" && /^-(?!--)/.test(x) ? "diff-del" : undefined;
          return <li key={i} className={cls}>{line}</li>;
        })}
        {more > 0 ? <li className="c-ash">and {more} more</li> : null}
      </ul>
    );
  }

  if (isObj(ev)) {
    const q = quotesIn(ev);
    if (q) return <EvidenceQuote quote={q} source={typeof ev.source === "string" ? ev.source : source} />;
    const entries = Object.entries(ev).filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (depth > 2) return <span className="t-mono">{scalar(ev)}</span>;
    return (
      <div className="evidence">
        {entries.map(([k, v]) => (
          <div key={k} className="stack stack--tight">
            <span className="evidence__key">{humanise(k)}</span>
            {render(v, source, maxItems, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  return <span className="t-mono">{scalar(ev)}</span>;
}

export function EvidenceView({ evidence, source, maxItems = 20 }: EvidenceViewProps) {
  return <>{render(evidence, source, maxItems, 0)}</>;
}

/** True when there is something worth showing. */
export function hasEvidence(ev: unknown): boolean {
  if (ev === null || ev === undefined || ev === "") return false;
  if (Array.isArray(ev)) return ev.length > 0;
  if (isObj(ev)) return Object.values(ev).some((v) => hasEvidence(v));
  return true;
}
