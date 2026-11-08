/**
 * Defensive reading of a module view model (MODULE_CONTRACT.md, VIEW MODEL). Every key is optional and values
 * may be numbers, strings or null, so each helper here turns "whatever came back" into a safe, typed shape.
 *
 * Beyond the contract, the real dosing view also sends, per chart:
 *   markers:  [{x, label}]          vertical event lines (drift alerts, approved actions)
 *   y_domain: [lo, hi] | null       fixed y axis range
 *   a constant "reference" series   e.g. {key: "Alarm line"} with the same value on every row
 * and we also accept threshold (number), thresholds / reference_lines ([{y, label}]) and y_label.
 */
import type { CardTone, Kpi } from "../../types";

export type Scalar = string | number | boolean | null;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : typeof v === "number" || typeof v === "boolean" ? String(v) : fallback;
const num = (v: unknown): number | null => {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
};
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

/** Any cell value as something React can print. Objects and lists become compact text. */
export function toScalar(v: unknown): Scalar {
  if (v === null || v === undefined) return null;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return v;
  if (Array.isArray(v)) return v.map((x) => (isObj(x) || Array.isArray(x) ? JSON.stringify(x) : str(x))).join(", ");
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

/* ------------------------------------------------------------------ KPIs */
export function readKpis(v: unknown): Kpi[] {
  return arr(v).filter(isObj).filter((k) => str(k.label) !== "").map((k) => ({
    label: str(k.label),
    value: typeof k.value === "number" || typeof k.value === "string" ? k.value : null,
    baseline: typeof k.baseline === "number" || typeof k.baseline === "string" ? k.baseline : null,
    // "n/a %" reads badly: drop the unit when there is no value yet.
    unit: (typeof k.value === "number" || typeof k.value === "string") ? str(k.unit) || undefined : undefined,
    note: str(k.note) || undefined,
    bottleneck_id: str(k.bottleneck_id) || null,
  }));
}

/* ------------------------------------------------------------------ cards */
export interface Card {
  title: string;
  body: string;
  tone: CardTone;
}
const TONES: CardTone[] = ["info", "warn", "good", "bad"];

export function readCards(v: unknown): Card[] {
  return arr(v).filter(isObj).map((c) => {
    const t = str(c.tone).toLowerCase();
    const tone: CardTone = (TONES as string[]).includes(t) ? (t as CardTone)
      : t === "critical" || t === "alert" || t === "error" ? "bad"
      : t === "watch" || t === "warning" ? "warn" : "info";
    return { title: str(c.title), body: str(toScalar(c.body)), tone };
  }).filter((c) => c.title || c.body);
}

/* ------------------------------------------------------------------ charts */
export interface ChartSeries {
  key: string;
  label: string;
}
export interface RefLine {
  y: number;
  label: string;
}
export interface Marker {
  x: number | string;
  label: string;
}
export interface Chart {
  title: string;
  x: string;
  series: ChartSeries[];
  data: Array<Record<string, number | string | null>>;
  refs: RefLine[];
  markers: Marker[];
  yDomain: [number, number] | null;
  yLabel: string;
}

const REF_LABEL = /expected|alarm|threshold|reference|target|limit|chance|baseline|line/i;

/** A series is a reference line when every row has the same value and its name says so. */
function constantValue(data: Array<Record<string, unknown>>, key: string): number | null {
  let seen: number | null = null;
  let count = 0;
  for (const row of data) {
    const n = num(row[key]);
    if (n === null) continue;
    if (seen !== null && Math.abs(n - seen) > 1e-9) return null;
    seen = n;
    count++;
  }
  return count > 0 ? seen : null;
}

export function readCharts(v: unknown): Chart[] {
  return arr(v).filter(isObj).map((c, ci) => {
    const x = str(c.x) || "day";
    const data = arr(c.data).filter(isObj).map((row) => {
      const out: Record<string, number | string | null> = {};
      for (const [k, val] of Object.entries(row)) {
        out[k] = typeof val === "number" ? (Number.isFinite(val) ? val : null)
          : typeof val === "string" ? (k === x ? val : num(val) ?? null)
          : null;
      }
      return out;
    });
    let series: ChartSeries[] = arr(c.series).map((s) =>
      isObj(s) ? { key: str(s.key), label: str(s.label) || str(s.key) } : { key: str(s), label: str(s) },
    ).filter((s) => s.key !== "" && s.key !== x);
    // No series given: plot every numeric key except x.
    if (series.length === 0 && data.length > 0) {
      const keys = new Set<string>();
      for (const row of data) for (const [k, val] of Object.entries(row)) if (k !== x && typeof val === "number") keys.add(k);
      series = [...keys].map((k) => ({ key: k, label: k }));
    }

    const refs: RefLine[] = [];
    const t = num(c.threshold);
    if (t !== null) refs.push({ y: t, label: `Threshold ${t}` });
    for (const r of [...arr(c.thresholds), ...arr(c.reference_lines), ...arr(c.refs)]) {
      if (isObj(r)) {
        const y = num(r.y ?? r.value);
        if (y !== null) refs.push({ y, label: str(r.label) || `Threshold ${y}` });
      } else {
        const y = num(r);
        if (y !== null) refs.push({ y, label: `Threshold ${y}` });
      }
    }
    // Constant "reference" series (the dosing view sends its expected and alarm lines this way).
    {
      series = series.filter((s) => {
        if (!REF_LABEL.test(s.label) && !REF_LABEL.test(s.key)) return true;
        const y = constantValue(data, s.key);
        if (y === null) return true;
        refs.push({ y, label: `${s.label} ${Number.isInteger(y) ? y : Number(y.toFixed(3))}` });
        return false;
      });
    }

    const markers: Marker[] = [];
    for (const m of arr(c.markers)) {
      if (!isObj(m)) continue;
      const mx = num(m.x) ?? (str(m.x) || null);
      if (mx === null) continue;
      markers.push({ x: mx, label: str(m.label) });
    }

    const d = arr(c.y_domain);
    const lo = num(d[0]);
    const hi = num(d[1]);
    const yDomain: [number, number] | null = lo !== null && hi !== null && hi > lo ? [lo, hi] : null;

    return {
      title: str(c.title) || `Chart ${ci + 1}`,
      x,
      series,
      data,
      refs,
      markers,
      yDomain,
      yLabel: str(c.y_label),
    };
  });
}

/* ------------------------------------------------------------------ tables */
export interface Table {
  title: string;
  columns: string[];
  rows: Scalar[][];
}

export function readTables(v: unknown): Table[] {
  return arr(v).filter(isObj).map((t) => {
    let columns = arr(t.columns).map((c) => (isObj(c) ? str(c.label ?? c.key ?? c.name) : str(c)));
    const rawRows = arr(t.rows);
    // Rows may be dicts instead of lists: read them by column name (or take their keys as columns).
    if (columns.length === 0) {
      const first = rawRows.find(isObj);
      if (first) columns = Object.keys(first);
    }
    const rows = rawRows.map((r) => {
      if (Array.isArray(r)) return r.map(toScalar);
      if (isObj(r)) return columns.map((c) => toScalar(r[c]));
      return [toScalar(r)];
    });
    const width = Math.max(columns.length, ...rows.map((r) => r.length), 0);
    while (columns.length < width) columns.push("");
    return { title: str(t.title), columns, rows: rows.map((r) => (r.length < width ? [...r, ...Array(width - r.length).fill(null)] : r)) };
  });
}

/* ------------------------------------------------------------------ forms */
export interface FormField {
  name: string;
  label: string;
  type: "text" | "number" | "select" | "textarea" | "checkbox";
  options: string[];
  placeholder: string;
  help: string;
  initial: string | boolean;
}
export interface Form {
  id: string;
  title: string;
  action: string;
  description: string;
  submitLabel: string;
  fields: FormField[];
}

const FIELD_TYPES = ["text", "number", "select", "textarea", "checkbox"] as const;

export function readForms(v: unknown): Form[] {
  return arr(v).filter(isObj).map((f, fi) => {
    const fields: FormField[] = arr(f.fields).filter(isObj).map((x) => {
      const raw = str(x.type).toLowerCase();
      const options = arr(x.options).map((o) => (isObj(o) ? str(o.value ?? o.label) : str(toScalar(o))));
      let type: FormField["type"] = (FIELD_TYPES as readonly string[]).includes(raw) ? (raw as FormField["type"])
        : raw === "boolean" || raw === "bool" ? "checkbox"
        : raw === "int" || raw === "float" ? "number"
        : raw === "long_text" || raw === "longtext" ? "textarea" : "text";
      if (type === "select" && options.length === 0) type = "text";
      const def = x.default ?? x.value;
      const initial: string | boolean = type === "checkbox" ? def === true || def === "true"
        : def !== undefined && def !== null ? str(toScalar(def))
        : type === "select" ? options[0] ?? "" : "";
      return {
        name: str(x.name) || `field_${fi}`,
        label: str(x.label) || str(x.name),
        type,
        options,
        placeholder: str(x.placeholder),
        help: str(x.help),
        initial,
      };
    }).filter((x) => x.name);
    return {
      id: str(f.id) || str(f.action) || `form_${fi}`,
      title: str(f.title) || "Form",
      action: str(f.action),
      description: str(f.description ?? f.body),
      submitLabel: str(f.submit_label) || "Submit",
      fields,
    };
  }).filter((f) => f.action !== "");
}

/** Form values to an action payload: number fields become numbers, empty number fields are left out. */
export function toPayload(fields: FormField[], values: Record<string, string | boolean>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) {
    const val = values[f.name] ?? f.initial;
    if (f.type === "checkbox") out[f.name] = val === true;
    else if (f.type === "number") {
      const n = num(val);
      if (n !== null) out[f.name] = n;
    } else out[f.name] = typeof val === "string" ? val : String(val);
  }
  return out;
}
