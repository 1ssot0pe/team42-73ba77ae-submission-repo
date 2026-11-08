/**
 * ViewForm (design.md 8.18): a module form as an L1b paper document with generic inputs
 * (text, number, select, textarea, checkbox). Submit calls api.action(trialId, module, form.action, values),
 * then adopt(res.state) and a toast with result.message, or the error when ok is false.
 * The last result stays printed under the button, because some actions answer with a follow-up question.
 * Props: module (module id); form (a normalised Form).
 */
import { useState, type FormEvent } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import { Button, useToast } from "../shared";
import { toPayload, type Form } from "./normalise";

export interface ViewFormProps {
  module: string;
  form: Form;
}

type Result = { ok: boolean; text: string };

function optionLabel(o: string): string {
  if (o === "") return "Not set";
  if (o === "dont_know") return "Don't know";
  return o.replace(/_/g, " ");
}

export function ViewForm({ module, form }: ViewFormProps) {
  const { trialId, adopt } = useTrial();
  const toast = useToast();
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  const valueOf = (name: string, initial: string | boolean, options?: string[]) => {
    const v = values[name] ?? initial;
    // A select whose options changed since the user picked: fall back to the first option.
    if (options && options.length > 0 && typeof v === "string" && !options.includes(v)) return options[0];
    return v;
  };
  const set = (name: string, v: string | boolean) => setValues((xs) => ({ ...xs, [name]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialId || busy) return;
    const current: Record<string, string | boolean> = {};
    for (const f of form.fields) current[f.name] = valueOf(f.name, f.initial, f.type === "select" ? f.options : undefined);
    setBusy(true);
    try {
      const res = await api.action(trialId, module, form.action, toPayload(form.fields, current));
      if (res.state) adopt(res.state);
      const r = res.result ?? {};
      const ok = r.ok !== false && !r.error;
      const text = (typeof r.message === "string" && r.message) || (typeof r.error === "string" && r.error) || (ok ? "Done" : "The module did not accept this");
      setResult({ ok, text });
      toast(text, ok ? "good" : "alert");
    } catch (err) {
      const text = errorText(err);
      setResult({ ok: false, text });
      toast(text, "alert");
    } finally {
      setBusy(false);
    }
  }

  const fid = (name: string) => `mf-${module}-${form.id}-${name}`;

  return (
    <form className="paper mform" onSubmit={submit} aria-label={form.title}>
      <div className="mform__head">
        <div className="eyebrow">Form · {form.action.replace(/_/g, " ")}</div>
        <h3 className="mform__title">{form.title}</h3>
        {form.description ? <p className="mform__desc">{form.description}</p> : null}
      </div>
      <div className="mform__fields">
        {form.fields.map((f) => {
          const id = fid(f.name);
          if (f.type === "checkbox") {
            return (
              <div key={f.name} className="field mform__field mform__field--wide">
                <label className="checkbox" htmlFor={id}>
                  <input id={id} type="checkbox" checked={valueOf(f.name, f.initial) === true}
                    onChange={(e) => set(f.name, e.target.checked)} />
                  {f.label}
                </label>
                {f.help ? <span className="field__help">{f.help}</span> : null}
              </div>
            );
          }
          const v = valueOf(f.name, f.initial, f.type === "select" ? f.options : undefined);
          const sv = typeof v === "string" ? v : "";
          return (
            <div key={f.name} className={`field mform__field${f.type === "textarea" || f.label.length > 60 ? " mform__field--wide" : ""}`}>
              <label className="field__label" htmlFor={id}>{f.label}</label>
              {f.type === "select" ? (
                <select id={id} className="select" value={sv} onChange={(e) => set(f.name, e.target.value)}>
                  {f.options.map((o) => <option key={o} value={o}>{optionLabel(o)}</option>)}
                </select>
              ) : f.type === "textarea" ? (
                <textarea id={id} className="textarea" value={sv} placeholder={f.placeholder}
                  onChange={(e) => set(f.name, e.target.value)} />
              ) : (
                <input id={id} className={`input${f.type === "number" ? " mform__num" : ""}`}
                  type={f.type === "number" ? "number" : "text"} inputMode={f.type === "number" ? "decimal" : undefined}
                  step={f.type === "number" ? "any" : undefined}
                  value={sv} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
              )}
              {f.help ? <span className="field__help">{f.help}</span> : null}
            </div>
          );
        })}
      </div>
      <div className="mform__foot">
        <Button type="submit" variant="filled" busy={busy} busyLabel="Agents working…" disabled={!trialId}>
          {form.submitLabel}
        </Button>
        {result ? (
          <p className={`mform__result mform__result--${result.ok ? "good" : "alert"}`} role="status">
            <span className="mform__result-word">{result.ok ? "Accepted" : "Not accepted"}</span>
            {result.text}
          </p>
        ) : null}
      </div>
    </form>
  );
}
