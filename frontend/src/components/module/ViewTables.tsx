/**
 * ViewTables: the tables from a module view model through the shared LedgerTable (design.md 8.11).
 * Numbers are right-aligned in mono by LedgerTable; ID and day columns are also set in mono.
 * Wide tables scroll inside their own container, never the page.
 * Props: tables (normalised Table[]).
 */
import { LedgerTable, type LedgerColumn } from "../shared";
import type { Table } from "./normalise";

const MONO_COL = /^(day|d\+|participant|participant id|rater|rater id|id|registry|approval|site id|week|visit week)$/i;

export function ViewTables({ tables }: { tables: Table[] }) {
  return (
    <div className="mtables">
      {tables.map((t, i) => {
        const cols: LedgerColumn[] = t.columns.map((c, ci) => {
          const vals = t.rows.map((r) => r[ci]).filter((v) => v !== null && v !== "");
          const numeric = vals.length > 0 && vals.every((v) => typeof v === "number");
          return { label: c, align: numeric ? "right" : "left", mono: MONO_COL.test(c.trim()) || numeric || undefined };
        });
        return (
          <LedgerTable key={`${t.title}-${i}`} title={t.title || undefined} columns={cols} rows={t.rows}
            empty="No rows yet. Advance the trial to fill this table." maxHeight={420} />
        );
      })}
    </div>
  );
}
