/**
 * Create a trial: a small, flat, accessible modal. Name plus a starting point (blank or a demo template).
 * Templates come from api.protocols(); when the API is down only Blank is offered and the examples are disabled.
 * On create: projects.create, then navigate to /trials/<id>/draft.
 */
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../../api";
import { projects, type ProjectTemplate } from "../../store/projects";
import type { ProtocolSummary } from "../../types";

interface Option {
  id: ProjectTemplate;
  label: string;
  match: RegExp;
}

const EXAMPLES: Option[] = [
  { id: "psilocybin", label: "Example: psilocybin for TRD", match: /psilocybin/i },
  { id: "mdma", label: "Example: MDMA for PTSD", match: /mdma/i },
];

function findProtocol(list: ProtocolSummary[] | null, re: RegExp): ProtocolSummary | null {
  if (!list) return null;
  return list.find((p) => re.test(p.name) || re.test(p.title ?? "")) ?? null;
}

export function CreateTrialDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const uid = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [template, setTemplate] = useState<ProjectTemplate>("blank");
  const [protocols, setProtocols] = useState<ProtocolSummary[] | null>(null);
  const [apiDown, setApiDown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    setName("");
    setTemplate("blank");
    setError(null);
    setBusy(false);
    let live = true;
    api.protocols()
      .then((list) => { if (live) { setProtocols(Array.isArray(list) ? list : []); setApiDown(false); } })
      .catch(() => { if (live) { setProtocols(null); setApiDown(true); } });
    const back = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => nameRef.current?.focus());
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => {
      live = false;
      window.removeEventListener("keydown", onKey);
      back?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      let draft = "";
      if (template !== "blank") {
        const opt = EXAMPLES.find((o) => o.id === template);
        const proto = opt ? findProtocol(protocols, opt.match) : null;
        if (proto) draft = (await api.protocol(proto.name)).text ?? "";
      }
      const p = projects.create({ name: name.trim() || "Untitled trial", template, draft });
      onClose();
      navigate(`/trials/${p.id}/draft`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <div className="dlg-root">
      <div className="dlg-scrim" onClick={onClose} aria-hidden="true" />
      <div className="dlg" role="dialog" aria-modal="true" aria-labelledby={`${uid}-title`}>
        <form onSubmit={submit} className="dlg__form">
          <h2 id={`${uid}-title`} className="dlg__title">Create a trial</h2>

          <label className="dlg__field">
            <span className="dlg__label">Name</span>
            <input ref={nameRef} className="dlg__input" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="For example: Psilocybin for depression, phase 2" autoComplete="off" />
          </label>

          <fieldset className="dlg__field dlg__fieldset">
            <legend className="dlg__label">Starting point</legend>
            <label className="dlg__radio">
              <input type="radio" name={`${uid}-tpl`} checked={template === "blank"} onChange={() => setTemplate("blank")} />
              <span>Blank page</span>
            </label>
            {EXAMPLES.map((o) => {
              const available = !apiDown && (protocols === null || !!findProtocol(protocols, o.match));
              const disabled = apiDown || (protocols !== null && !available);
              return (
                <label key={o.id} className={`dlg__radio${disabled ? " is-disabled" : ""}`}>
                  <input type="radio" name={`${uid}-tpl`} checked={template === o.id} disabled={disabled}
                    onChange={() => setTemplate(o.id)} />
                  <span>{o.label}</span>
                  <span className="dlg__note">Demo template</span>
                </label>
              );
            })}
            {apiDown ? <p className="dlg__quiet">Examples need the trial server, which is not reachable. A blank page still works.</p> : null}
          </fieldset>

          {error ? <p className="dlg__error" role="alert">{error}</p> : null}

          <div className="dlg__actions">
            <button type="button" className="textbtn" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn--filled" disabled={busy}>{busy ? "Creating…" : "Create trial"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
