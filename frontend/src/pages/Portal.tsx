/**
 * Volunteer portal (plan.md 7.2, design.md Section 9). Centred two columns: the application form on paper |
 * the pre-screening result on strong glass. Sends {applicant: {...}} to the predose "apply" action; the keys
 * match the World applicant shape that PreScreeningAgent.screen_one reads.
 */
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { useTrial } from "../trial";
import type { Applicant } from "../types";
import { Button, EmptyState, SpecimenBand, buttonClass, dotJoin, useToast } from "../components/shared";
import { ScreeningResult } from "../components/predose/ScreeningResult";
import type { ApplyResult, PortalApplicant } from "../components/predose/types";
import "../styles/predose.css";

const DIAGNOSES: Array<{ value: string; label: string }> = [
  { value: "treatment-resistant depression", label: "Treatment-resistant depression" },
  { value: "major depressive disorder", label: "Major depressive disorder" },
  { value: "anxiety", label: "Anxiety" },
  { value: "none", label: "None" },
];
const PRIOR: Array<{ value: PortalApplicant["prior_psychedelic_use"]; label: string }> = [
  { value: "never", label: "Never" },
  { value: "once", label: "Once" },
  { value: "several times", label: "Several times" },
];

interface FormState {
  name: string;
  age: string;
  phone: string;
  diagnosis: string;
  failed: string;
  medication: string;
  prior: PortalApplicant["prior_psychedelic_use"];
  months: string;
  psychosis: boolean;
  bipolar: boolean;
  heart: boolean;
  pregnant: boolean;
  visits: boolean;
  checkins: boolean;
  sharing: boolean;
  free: string;
}

/** A synthetic profile that passes every rule, so a judge only needs to change one thing. */
const DEMO: FormState = {
  name: "Sam Taylor",
  age: "34",
  phone: "+44 7700 900123",
  diagnosis: "treatment-resistant depression",
  failed: "2",
  medication: "none",
  prior: "never",
  months: "",
  psychosis: false,
  bipolar: false,
  heart: false,
  pregnant: false,
  visits: true,
  checkins: true,
  sharing: true,
  free: "",
};

/** Blank stays missing (the agent then asks a clinician); call only after validate() passed. */
function num(s: string): number | null {
  const t = s.trim();
  return t ? Number.parseInt(t, 10) : null;
}

type NumField = "age" | "failed" | "months";
const NUM_ERRORS: Record<NumField, string> = {
  age: "Enter your age as a number",
  failed: "Enter the number of antidepressants as a whole number",
  months: "Enter the months since last use as a whole number",
};

/** Non-empty numeric fields must be whole numbers, so "thirty" never reaches the agent as "not stated". */
function validate(f: FormState): Partial<Record<NumField, string>> {
  const out: Partial<Record<NumField, string>> = {};
  const check = (k: NumField, v: string) => {
    const t = v.trim();
    if (t && !/^\d+$/.test(t)) out[k] = NUM_ERRORS[k];
  };
  check("age", f.age);
  check("failed", f.failed);
  if (f.prior !== "never") check("months", f.months);
  return out;
}

function toApplicant(f: FormState): PortalApplicant {
  return {
    name: f.name.trim(),
    age: num(f.age),
    phone: f.phone.trim(),
    self_reported_diagnosis: f.diagnosis,
    failed_antidepressants: num(f.failed),
    current_medication: f.medication.trim() || "none",
    prior_psychedelic_use: f.prior,
    months_since_last_psychedelic: f.prior === "never" ? null : num(f.months),
    history_psychosis: f.psychosis,
    history_bipolar: f.bipolar,
    cardiovascular_condition: f.heart,
    pregnant_or_breastfeeding: f.pregnant,
    can_attend_8_visits: f.visits,
    consents_to_chatbot_checkins: f.checkins,
    consents_to_data_sharing: f.sharing,
    free_text: f.free.trim(),
  };
}

export default function Portal() {
  const { trialId, adopt } = useTrial();
  const toast = useToast();
  const [f, setF] = useState<FormState>(DEMO);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Applicant | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<NumField, string>>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((x) => ({ ...x, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!trialId) return;
    const errs = validate(f);
    setFieldErrors(errs);
    const first = (Object.keys(errs) as NumField[])[0];
    if (first) {
      document.getElementById(`portal-${first}`)?.focus();
      return;
    }
    setBusy(true);
    setServerError(null);
    try {
      const applicant = toApplicant(f);
      const res = await api.action<ApplyResult>(trialId, "predose", "apply", { applicant: { ...applicant } });
      adopt(res.state);
      if (!res.result.ok) {
        const msg = res.result.error || "The application could not be screened";
        setResult(null);
        setServerError(msg);
        toast(msg, "alert");
        return;
      }
      setResult(res.result.applicant);
      const d = res.result.applicant.screening.decision;
      toast(dotJoin("Screened", res.result.applicant.id, d.replace(/_/g, " ")), d === "eligible" ? "good" : d === "excluded" ? "alert" : "watch");
    } catch (err) {
      setResult(null);
      setServerError(errorText(err));
      toast(errorText(err), "alert");
    } finally {
      setBusy(false);
    }
  };

  if (!trialId) {
    return (
      <>
        <SpecimenBand />
        <main className="page">
          <header className="section">
            <div className="eyebrow">Volunteer portal</div>
            <h1 className="t-display">Apply to the study</h1>
          </header>
          <EmptyState title="No trial yet"
            message="Create a trial in Mission control first. Applications are screened against that trial's protocol."
            action={<Link className={buttonClass("filled")} to="/">Go to Mission control</Link>} />
        </main>
      </>
    );
  }

  const check = (k: "psychosis" | "bipolar" | "heart" | "pregnant" | "visits" | "checkins" | "sharing", label: string) => (
    <label className="checkbox">
      <input type="checkbox" checked={f[k]} onChange={(e) => set(k, e.target.checked)} />
      {label}
    </label>
  );

  return (
    <>
      <SpecimenBand />
      <main className="page portal">
        <header className="section portal__head">
          <div className="eyebrow">{dotJoin("Volunteer portal", trialId, "Synthetic")}</div>
          <h1 className="t-display">Apply to the study</h1>
          <p className="t-body-lg c-smoke">Fill in the form and the pre-screening agent decides at once, with its reasons.</p>
        </header>

        <div className="portal__grid">
          <form className="paper portal__form" onSubmit={submit} noValidate>
            <p className="portal__warning" role="note">
              <span className="t-label">Synthetic demo.</span> Do not enter real personal or health information.
            </p>

            <label className="field">
              <span className="field__label">Name</span>
              <input className="input" value={f.name} autoComplete="off" onChange={(e) => set("name", e.target.value)} />
            </label>
            <div className="portal__pair">
              <label className="field">
                <span className="field__label">Age (years)</span>
                <input id="portal-age" className="input num" inputMode="numeric" value={f.age} onChange={(e) => set("age", e.target.value)}
                  aria-invalid={fieldErrors.age ? true : undefined} aria-describedby={fieldErrors.age ? "portal-age-error" : undefined} />
                {fieldErrors.age ? <span className="portal__field-error" id="portal-age-error" role="alert">{fieldErrors.age}</span> : null}
              </label>
              <label className="field">
                <span className="field__label">Mobile</span>
                <input className="input num" inputMode="tel" value={f.phone} autoComplete="off" onChange={(e) => set("phone", e.target.value)} />
                <span className="field__help">Check-ins run through a UK chatbot (+44 7).</span>
              </label>
            </div>
            <div className="portal__pair">
              <label className="field">
                <span className="field__label">Diagnosis</span>
                <select className="select" value={f.diagnosis} onChange={(e) => set("diagnosis", e.target.value)}>
                  {DIAGNOSES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </label>
              <label className="field">
                <span className="field__label">Failed antidepressants</span>
                <input id="portal-failed" className="input num" inputMode="numeric" value={f.failed} onChange={(e) => set("failed", e.target.value)}
                  aria-invalid={fieldErrors.failed ? true : undefined} aria-describedby={fieldErrors.failed ? "portal-failed-error" : undefined} />
                {fieldErrors.failed ? <span className="portal__field-error" id="portal-failed-error" role="alert">{fieldErrors.failed}</span> : null}
                <span className="field__help">How many you tried that did not help.</span>
              </label>
            </div>
            <label className="field">
              <span className="field__label">Current medication</span>
              <input className="input" value={f.medication} placeholder="none" onChange={(e) => set("medication", e.target.value)} />
            </label>
            <div className="portal__pair">
              <label className="field">
                <span className="field__label">Psychedelic use</span>
                <select className="select" value={f.prior} onChange={(e) => set("prior", e.target.value as FormState["prior"])}>
                  {PRIOR.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </label>
              {f.prior !== "never" ? (
                <label className="field">
                  <span className="field__label">Months since last use</span>
                  <input id="portal-months" className="input num" inputMode="numeric" value={f.months} onChange={(e) => set("months", e.target.value)}
                    aria-invalid={fieldErrors.months ? true : undefined} aria-describedby={fieldErrors.months ? "portal-months-error" : undefined} />
                  {fieldErrors.months ? <span className="portal__field-error" id="portal-months-error" role="alert">{fieldErrors.months}</span> : null}
                </label>
              ) : null}
            </div>

            <fieldset className="portal__checks">
              <legend className="field__label">History and practicalities</legend>
              {check("psychosis", "History of psychosis")}
              {check("bipolar", "History of bipolar disorder")}
              {check("heart", "Heart or blood pressure condition")}
              {check("pregnant", "Pregnant or breastfeeding")}
              {check("visits", "I can attend 8 in-person visits")}
              {check("checkins", "I consent to chatbot check-ins")}
              {check("sharing", "I consent to data sharing")}
            </fieldset>

            <label className="field">
              <span className="field__label">Anything else we should know?</span>
              <textarea className="textarea" rows={4} value={f.free} onChange={(e) => set("free", e.target.value)}
                placeholder="For example: I was diagnosed with bipolar disorder last year" />
              <span className="field__help">The agent reads this and flags any disclosed risk for a clinician, quoting you.</span>
            </label>

            <div className="row">
              <Button type="submit" variant="filled" busy={busy}>Apply</Button>
              <Button variant="ghost" onClick={() => { setF(DEMO); setResult(null); setFieldErrors({}); setServerError(null); }}>Reset form</Button>
            </div>
          </form>

          <ScreeningResult applicant={result} busy={busy} error={serverError} />
        </div>
      </main>
    </>
  );
}
