"""Orchestrator. Runs the agents, decides what to do when a step comes back
empty, derives standardised effects in plain code, applies the calibration,
and stops at a human sign-off gate.

    report = run("NCT01234567", on_event=print)
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import model, net, rules, sources
from .agents import BlindingHunter, DesignExtractor, Hunter, OutcomeExtractor, Resolver
from .audit import audit_fact, scan_injection
from .ledger import Fact, Ledger, unknown

LIMITATIONS = [
    "Reverse causation: patients who improve may guess 'drug' because they improved. The correction then removes "
    "some real effect, so the corrected value is best read as a conservative bound, not the true effect.",
    "Cross-trial confounding: trials with better blinding may differ in drug, dose, population or era.",
    "A low-dose comparator is also pharmacology: a smaller gap mixes better blinding with real dose-response.",
    "Extrapolation: few trials sit near zero unblinding, so the intercept is least certain exactly where it matters.",
    "The tool estimates expectancy contamination. It does not predict what a future trial will show.",
]


@dataclass
class Report:
    input: str
    nct: Optional[str]
    title: str
    drug: List[str]
    in_domain: bool
    facts: Dict[str, Any]
    sources: Dict[str, Any]
    trace: List[Dict[str, Any]]
    calibration: str
    design_model: str
    fit_primary: Optional[Dict[str, Any]]
    fit_sensitivity: Optional[Dict[str, Any]]
    correction: Optional[Dict[str, Any]]
    counterfactuals: List[Dict[str, Any]]
    warnings: List[str]
    limitations: List[str] = field(default_factory=lambda: list(LIMITATIONS))
    status: str = "AWAITING HUMAN SIGN-OFF: instrument reading, not a verdict"

    def digest(self) -> str:
        core = json.dumps({"facts": self.facts, "correction": self.correction, "cf": self.counterfactuals},
                          sort_keys=True, default=str)
        return hashlib.sha256(core.encode()).hexdigest()[:16]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


def _registry_facts(L: Ledger, study: dict) -> dict:
    s = sources.study_summary(study)
    sid = f"ctgov:{s['nct']}"
    reg_text = L.sources[sid].text
    endpoint = {"scale": None, "week": None, "measure": ""}
    if s["primary_outcomes"]:
        po = s["primary_outcomes"][0]
        endpoint = rules.parse_endpoint(po.get("measure", ""), po.get("timeFrame", ""))
        endpoint["measure"] = po.get("measure", "")
        line = next((ln for ln in reg_text.splitlines() if ln.startswith("Primary outcome:")), "")
        L.put(audit_fact(Fact("primary_endpoint", endpoint, "observed", line, sid, "resolver",
                              f"{len(s['primary_outcomes'])} primary outcome(s) registered; first used"), L))
        # numbers in the endpoint (week) are in the line; scale string isn't numeric
    else:
        L.put(unknown("primary_endpoint", "resolver", "no primary outcome registered"))
    if s["enrollment"]:
        line = next((ln for ln in reg_text.splitlines() if ln.startswith("Enrollment:")), "")
        L.put(audit_fact(Fact("enrollment", int(s["enrollment"]), "observed", line, sid, "resolver"), L))
    return endpoint


def _derive_effect(L: Ledger, endpoint: dict) -> None:
    """Plain code: MD + CI + arm Ns -> Hedges' g and its SE. Sign: positive = drug better."""
    e = L.get("effect")
    if not e:
        L.put(unknown("g", "statistician", "no effect size")); return
    lib = rules.lower_is_better(endpoint.get("scale"))
    ns = L.get("arm_ns")
    ns_status = "observed"
    if not ns:
        n = L.get("enrollment")
        if n:
            ns = (n // 2, n - n // 2)
            ns_status = "imputed"
            L.put(Fact("arm_ns", list(ns), "imputed", "", "", "statistician", "enrollment split evenly (arm sizes not found)"))
    if e["kind"] == "md":
        if "lo" not in e or not ns:
            L.put(unknown("g", "statistician", "mean difference without CI or arm sizes cannot be standardised")); return
        se_md = abs(e["hi"] - e["lo"]) / 3.92
        n1, n2 = ns
        sd = se_md / math.sqrt(1 / n1 + 1 / n2)
        d = e["est"] / sd
        if lib:
            d = -d
        J = 1 - 3 / (4 * (n1 + n2) - 9)
        g = J * d
        se_g = math.sqrt((n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2)))
        note = (f"MD {e['est']} (CI {e['lo']} to {e['hi']}) -> SD {sd:.2f} via arm sizes {n1}/{n2}"
                f"{' (imputed)' if ns_status == 'imputed' else ''}; sign flipped because lower {endpoint.get('scale')} is better" if lib else "")
        status = "derived" if ns_status == "observed" else "imputed"
    else:
        g = abs(e["est"])
        n1, n2 = ns if ns else (30, 30)
        se_g = math.sqrt((n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2)))
        note = "reported standardised effect; sign assumed to favour the drug"
        status = "derived" if ns else "imputed"
    L.put(Fact("g", round(g, 3), status, "", "", "statistician", note))
    L.put(Fact("se_g", round(se_g, 3), status, "", "", "statistician", "SE of Hedges' g"))


def _derive_u(L: Ledger, dm: model.DesignModel) -> None:
    acc = L.get("guess_acc_participants")
    src = "participants"
    if acc is None:
        acc = L.get("guess_acc_raters"); src = "raters"
    if acc is not None:
        u = model.u_from_accuracy(float(acc))
        L.put(Fact("u", round(u, 3), "derived", "", "", "statistician",
                   f"u = 2 x {src} guess accuracy {acc:.2f} - 1 (observed blinding data)"))
        L.put(Fact("u_sd", 0.05, "derived", "", "", "statistician", "measurement noise allowance"))
        return
    comp = L.get("comparator_type")
    pe = L.get("prior_exposure")
    u, sd = dm.predict(comp, pe)
    L.put(Fact("u", round(u, 3), "imputed", "", "", "statistician",
               f"IMPUTED from design (comparator={comp or 'unknown -> assumed inert placebo'}, "
               f"prior exposure={'unknown' if pe is None else pe}) using {dm.source}"))
    L.put(Fact("u_sd", round(sd, 3), "imputed", "", "", "statistician", "wide interval because u is imputed"))


def run(raw: str, on_event: Optional[Callable] = None, calibration: str = "auto") -> Report:
    L = Ledger()
    if on_event:
        L.on_event(on_event)
    warnings: List[str] = []
    L.log("orchestrator", "start", f"input: {raw[:120]!r}")

    # 1. resolve -----------------------------------------------------------
    r = Resolver(L).run(raw)
    study = r.study
    endpoint: dict = {"scale": None, "week": None, "measure": ""}
    title = ""
    if study:
        reg = sources.registry_source(study)
        L.add_source(reg)
        res = sources.registry_results_source(study)
        if res and res.text:
            L.add_source(res)
            L.log("orchestrator", "registry has posted results", "will check them before the paper", "decision")
        endpoint = _registry_facts(L, study)
        title = sources.study_summary(study)["title"]
    elif r.nct:
        warnings.append(f"Registry record for {r.nct} could not be fetched; working from the paper only.")
    if r.alternatives:
        warnings.append("Input matched several trials; check the chosen one: alternatives " + ", ".join(r.alternatives))
    if not study and not r.pasted and not r.paper_hit:
        warnings.append("Nothing could be resolved from this input. Try an NCT ID, a DOI, or paste the abstract.")

    # domain check
    blob = " ".join(s.text[:20000] for s in L.sources.values()) + " " + (json.dumps(r.paper_hit) if r.paper_hit else "")
    drugs = rules.detect_drugs(blob)
    in_domain = bool(drugs)
    aliases = sum((rules.PSYCHEDELICS[d] for d in drugs), [])
    if not in_domain:
        warnings.append("No psychedelic intervention detected. The calibration was fitted on psychedelic trials; "
                        "any correction for this trial is outside the fitted domain and shown for illustration only.")
        L.log("orchestrator", "out of domain", "no psychedelic detected; continuing with a loud warning", "warn")
    if any(d in rules.NON_HALLUCINOGENIC for d in drugs):
        warnings.append("Non-hallucinogenic compound: almost no completed trials sit at this end of the curve, "
                        "so uncertainty is widest here.")

    # 2. hunt the paper ----------------------------------------------------
    paper = Hunter(L).find_paper(r) if (r.nct or r.paper_hit) else None
    if r.pasted:
        L.log("orchestrator", "using pasted text as a primary source", level="decision")

    # 3-5. extractors -------------------------------------------------------
    result_ids = [sid for sid, s in L.sources.items() if s.kind in ("registry-results", "paper", "paper-abstract", "pasted")]
    design_ids = [sid for sid, s in L.sources.items() if s.kind in ("registry", "paper", "paper-abstract", "pasted")]
    if study and not endpoint.get("scale"):
        L.log("outcome", "registered endpoint has no recognised scale", "matching on timepoint only", "warn")
    if not study:
        # no registration to check against: try to read the endpoint from the paper itself
        for sid in result_ids:
            m = re.search(r"primary (?:outcome|end ?point)[^.]{0,160}", L.sources[sid].text, re.I)
            if m:
                endpoint = rules.parse_endpoint(m.group(0), m.group(0))
                L.log("outcome", "no registry record; primary endpoint read from the paper instead",
                      f"{endpoint}", "warn")
                warnings.append("Primary endpoint taken from the paper, not the registration: cannot rule out outcome switching.")
                break
    OutcomeExtractor(L).run(endpoint, result_ids)
    DesignExtractor(L).run(design_ids, study, aliases)
    if L.status("rater_placement") != "observed" and study:
        s = sources.study_summary(study)
        if "OUTCOMES_ASSESSOR" in s["who_masked"]:
            line = next((ln for ln in L.sources[f"ctgov:{s['nct']}"].text.splitlines() if ln.startswith("Masking:")), "")
            L.put(audit_fact(Fact("rater_placement", "blinded_unspecified", "observed", line, f"ctgov:{s['nct']}",
                                  "design", "registry lists outcomes assessor as masked"), L))
    BlindingHunter(L).run(paper, study)

    inj = scan_injection(L)
    if inj:
        warnings.append(f"Possible prompt-injection text found in {', '.join(inj)}; it was treated as data and every claim was quote-checked.")

    # 6. statistics in plain code -----------------------------------------
    rows, cal_label = model.load_calibration(calibration)
    dm = model.design_model(rows)
    from .synthetic import fill_imputed
    rows = fill_imputed([dict(x) for x in rows], dm)
    _derive_effect(L, endpoint)
    _derive_u(L, dm)
    fit_p = model.fit_metareg(rows, label="primary: observed blinding only")
    fit_s = model.fit_metareg(rows, label="sensitivity: incl. imputed blinding", use_imputed=True)
    fit = fit_p or fit_s
    if fit_p is None:
        warnings.append("Too few calibration trials with observed blinding; using the sensitivity fit (includes imputed values).")
    L.log("statistician", "calibration fitted", f"{cal_label}; k={fit.k if fit else 0}", "decision")
    if "SYNTHETIC" in cal_label:
        warnings.append("Calibration is SYNTHETIC. Numbers demonstrate the method only; they are not real-world estimates.")

    correction = None
    central = L.get("rater_placement") == "central_remote"
    if fit and L.get("g") is not None:
        correction = model.correct(fit, L.get("g"), L.get("se_g"), L.get("u"), L.get("u_sd"), central)
        correction = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in correction.items()}
        correction["u_status"] = L.status("u")
        if correction["extrapolated"]:
            warnings.append("This trial's unblinding lies outside the range seen in the calibration data: extrapolated.")
        L.log("statistician", "correction applied",
              f"g {L.get('g')} -> {correction['corrected']} (95% interval {correction['lo']} to {correction['hi']})", "decision")
    else:
        L.log("statistician", "no correction possible", "effect size unknown; design advice still available", "warn")

    # 7. counterfactuals ---------------------------------------------------
    design = {"comparator_type": L.get("comparator_type") or "inert_placebo",
              "prior_exposure": L.get("prior_exposure"), "central": int(central)}
    u_act = L.get("u") if L.status("u") == "derived" else None
    cfs = model.counterfactuals(fit, dm, design, u_act) if fit else []
    if cfs:
        top = cfs[0]
        verdict = (f"reduces expected bias by {top['bias_reduction']:+.3f} g" if top["bias_reduction"] > 0
                   else "no single change is predicted to reduce bias")
        L.log("advisor", "ranked design changes", f"top: {top['change']} ({verdict})", "decision")

    L.log("orchestrator", "done", "awaiting human sign-off")
    facts = {k: asdict(v) for k, v in L.facts.items()}
    return Report(
        input=raw, nct=r.nct, title=title, drug=drugs, in_domain=in_domain, facts=facts,
        sources={k: v.brief() for k, v in L.sources.items()},
        trace=[asdict(e) for e in L.trace], calibration=cal_label, design_model=dm.source,
        fit_primary=fit_p.summary() if fit_p else None, fit_sensitivity=fit_s.summary() if fit_s else None,
        correction=correction, counterfactuals=cfs, warnings=warnings)
