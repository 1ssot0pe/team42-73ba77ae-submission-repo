/**
 * LedgerTable (design.md 8.11). Taupe sheet, stone header, hairlines, numbers right-aligned in mono.
 * Props: columns (string[] or LedgerColumn[] with {label, align?: "left"|"right", mono?}); rows (cells may be
 *   strings, numbers, booleans, null or any React node; numbers are right-aligned automatically);
 *   title (optional heading inside the sheet); empty (message for no rows); maxHeight (px; sticky header scrolls).
 * Accepts a ViewTable directly: <LedgerTable {...table} />.
 */
import type { ReactNode } from "react";
import { formatNumber } from "./format";

export interface LedgerColumn {
  label: string;
  align?: "left" | "right";
  mono?: boolean;
}

export type LedgerCell = ReactNode;

export interface LedgerTableProps {
  columns: Array<string | LedgerColumn>;
  rows: LedgerCell[][];
  title?: string;
  empty?: string;
  maxHeight?: number;
}

function renderCell(c: LedgerCell): ReactNode {
  if (typeof c === "number") return formatNumber(c);
  if (typeof c === "boolean") return c ? "Yes" : "No";
  if (c === null || c === undefined || c === "") return "";
  return c;
}

export function LedgerTable({ columns, rows, title, empty = "Nothing to show yet.", maxHeight = 520 }: LedgerTableProps) {
  const cols: LedgerColumn[] = columns.map((c) => (typeof c === "string" ? { label: c } : c));
  return (
    <section className="ledger">
      {title ? <h3 className="ledger__title t-title">{title}</h3> : null}
      {rows.length === 0 ? (
        <p className="ledger__empty">{empty}</p>
      ) : (
        <div className="ledger__scroll" style={{ maxHeight }}>
          <table>
            <thead>
              <tr>
                {cols.map((c, i) => (
                  <th key={i} scope="col" className={c.align === "right" ? "is-num" : undefined}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((cell, ci) => {
                    const col = cols[ci];
                    const right = col?.align === "right" || (col?.align === undefined && typeof cell === "number");
                    const cls = [right ? "is-num" : "", col?.mono ? "is-mono" : ""].filter(Boolean).join(" ");
                    return <td key={ci} className={cls || undefined}>{renderCell(cell)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
