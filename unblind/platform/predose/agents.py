"""Pre-dosing agents (Danny). Protocol parser (Phase 1), co-designer (Phase 2).

Rules first, Gemini as an optional refinement. Every Gemini answer is validated
(allowed value, and the quote must appear verbatim in the protocol) before use.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

from ... import model as ubmodel          # existing UNBLIND model (calibration, counterfactuals)
from ..core import Ctx, TrialRecord, digest
from ..world import PTSD_INDICATIONS

M = "predose"
SITES = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]
COMPARATORS = ["inert_placebo", "active_placebo", "low_dose_same_drug", "other_active"]
RATER_MODELS = ["onsite", "central_remote"]
PRIOR_USE_POLICIES = ["stratify", "ignore", "exclude"]


def _sentences(text): return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 3]


def _find(text, pattern):  # first sentence matching pattern, for evidence quotes
    rx = re.compile(pattern, re.I); return next((s for s in _sentences(text) if rx.search(s)), None)


# ---------------------------------------------------------------------------
# Phase 1: protocol parser
# ---------------------------------------------------------------------------
DRUG_RX = r"\b(psilocybin|mdma|lsd|5-meo-dmt|dmt|ayahuasca|zalsupindole)\b"
SCALES = {"madrs": "MADRS", "caps-5": "CAPS-5", "ham-d": "HAM-D", "qids": "QIDS", "pcl-5": "PCL-5"}
SCALE_RX = r"\b(MADRS|CAPS-5|HAM-D|QIDS|PCL-5)\b"
FLAG_PATTERNS = {
    "two_monitors": r"\btwo (session |trained )?monitors\b",
    "physician_15min": r"physician[^.]*\b15 minutes",
    "followup_12m": r"\b12[- ]months?\b|\b52 weeks\b",
    "factorial": r"factorial",
    "abuse_potential": r"\babuse\b",
}


def _defaults(text: str) -> dict:
    return {
        "title": "Untitled protocol", "drug": "unknown", "indication": "unknown", "comparator": "inert_placebo",
        "rater_model": "onsite", "prior_use_policy": "ignore", "sites": list(SITES), "n_target": 60,
        "primary_endpoint": {"scale": "MADRS", "week": 6}, "eligibility": {"inclusion": [], "exclusion": []},
        "has_blinding_questionnaire": False, "has_expectancy_measure": False,
        "design_flags": {k: False for k in list(FLAG_PATTERNS) + ["raters_attend_sessions"]},
        "evidence": {}, "text": text or "",
    }


def _eligibility(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"inclusion": [], "exclusion": []}
    mode = None
    for line in (text or "").splitlines():
        s = line.strip()
        if re.search(r"inclusion criteria", s, re.I):
            mode = "inclusion"
        elif re.search(r"exclusion criteria", s, re.I):
            mode = "exclusion"
        elif s.startswith("#"):
            mode = None
        elif mode and re.match(r"^[-*•]\s+", s):
            out[mode].append(re.sub(r"^[-*•]\s+", "", s))
    return out


def _raters_attend(text: str) -> Optional[str]:
    for s in _sentences(text):
        if (re.search(r"\braters?\b", s, re.I) and re.search(r"present|attend|sits? in", s, re.I)
                and re.search(r"session", s, re.I) and not re.search(r"\b(do|does|will) not attend", s, re.I)):
            return s
    return None


class ProtocolParser:
    name = "protocol parser"

    def run(self, text: str, ctx: Ctx) -> dict:
        """Rules first, then optional Gemini refinement. Never raises on odd input."""
        try:
            p = self._rules(text or "")
        except Exception as e:  # odd input must never break the trial
            p = _defaults(text or "")
            ctx.rec.event(self.name, f"could not read the protocol ({type(e).__name__}); using defaults", "warn", M)
        try:
            self._gemini(p, ctx)
        except Exception as e:
            ctx.rec.event(self.name, f"Gemini refinement skipped ({type(e).__name__})", "warn", M)
        ctx.rec.event(self.name, f"parsed '{p['title']}': {p['drug']}, {p['comparator']}, raters {p['rater_model']}, "
                                 f"prior use {p['prior_use_policy']}, n={p['n_target']}, primary "
                                 f"{p['primary_endpoint']['scale']} week {p['primary_endpoint']['week']}", "decision", M)
        return p

    # ------------------------------------------------------------------ rules
    def _rules(self, text: str) -> dict:
        p = _defaults(text)
        ev: Dict[str, str] = p["evidence"]
        low = text.lower()

        title = next((ln.strip().lstrip("#").strip() for ln in text.splitlines() if ln.strip().lstrip("#").strip()), "")
        if title:
            p["title"] = title

        m = re.search(DRUG_RX, text, re.I)
        if m:
            p["drug"] = m.group(1).lower()
            ev["drug"] = _find(text, re.escape(m.group(1)))

        for pat, ind in ((r"treatment-resistant", "treatment-resistant depression"),
                         (r"\bptsd\b|post-traumatic", "ptsd"), (r"depress", "major depressive disorder")):
            if re.search(pat, low):
                p["indication"] = ind
                ev["indication"] = _find(text, pat)
                break

        for pat, comp in ((r"niacin|diphenhydramine|methylphenidate|active placebo", "active_placebo"),
                          (r"low[- ]dose|\b1\s?mg\b", "low_dose_same_drug"),
                          (r"escitalopram|sertraline", "other_active")):
            q = _find(text, pat)
            if q:
                p["comparator"], ev["comparator"] = comp, q
                break
        else:
            q = _find(text, r"placebo")
            if q:
                ev["comparator"] = q

        q = _find(text, r"central(ised|ized)? blinded raters?|remote raters?|videoconferenc")
        if q:
            p["rater_model"], ev["rater_model"] = "central_remote", q
        else:
            q = _find(text, r"\braters?\b|administered by|assessor")
            if q:
                ev["rater_model"] = q

        q = _find(text, r"stratif\w*[^.]*\b(prior|psychedelic)")
        if q:
            p["prior_use_policy"], ev["prior_use_policy"] = "stratify", q
        else:
            elig = _eligibility(text)
            hit = next((x for x in elig["exclusion"] if re.search(r"psychedelic|hallucinogen", x, re.I)), None)
            q = hit or _find(text, r"exclud\w*[^.]*prior psychedelic")
            if q:
                p["prior_use_policy"], ev["prior_use_policy"] = "exclude", q

        q = _find(text, r"\bguess|blinding (questionnaire|integrity|assessment|index)")
        if q:
            p["has_blinding_questionnaire"], ev["has_blinding_questionnaire"] = True, q
        q = _find(text, r"expectan")
        if q:
            p["has_expectancy_measure"], ev["has_expectancy_measure"] = True, q

        m = re.search(r"\b(\d{1,5})\s+(participants|patients|adults)\b", text, re.I)
        if m:
            p["n_target"] = int(m.group(1))
            ev["n_target"] = _find(text, re.escape(m.group(0)))

        prim = _find(text, r"primary (outcome|endpoint)")
        if prim:
            sm = re.search(SCALE_RX, prim, re.I)
            wm = re.search(r"\bweek\s*(\d+)", prim, re.I)
            if sm:
                p["primary_endpoint"]["scale"] = SCALES[sm.group(1).lower()]
            if wm:
                p["primary_endpoint"]["week"] = int(wm.group(1))
            if sm or wm:
                ev["primary_endpoint"] = prim
        if "primary_endpoint" not in ev:
            sm = re.search(SCALE_RX, text, re.I)
            if sm:
                p["primary_endpoint"]["scale"] = SCALES[sm.group(1).lower()]
                ev["primary_endpoint"] = _find(text, SCALE_RX)

        letters = sorted(set(re.findall(r"\bSite ([ABC])\b", text)))
        if letters:
            p["sites"] = [s for s in SITES if s[5] in letters]
            ev["sites"] = _find(text, r"\bSite [ABC]\b")

        p["eligibility"] = _eligibility(text)
        if p["eligibility"]["inclusion"] or p["eligibility"]["exclusion"]:
            ev["eligibility"] = _find(text, r"inclusion criteria|exclusion criteria")

        for flag, pat in FLAG_PATTERNS.items():
            q = _find(text, pat)
            if q:
                p["design_flags"][flag], ev[f"design_flags.{flag}"] = True, q
        q = _raters_attend(text)
        if q and FIXES["central_raters"][2] not in text:   # an approved central-rater amendment supersedes older sentences
            p["design_flags"]["raters_attend_sessions"], ev["design_flags.raters_attend_sessions"] = True, q

        p["evidence"] = {k: v for k, v in ev.items() if v}
        return p

    # ------------------------------------------------------------------ Gemini (optional)
    def _gemini(self, p: dict, ctx: Ctx) -> None:
        llm = ctx.llm
        if llm is None or not llm.available():
            return
        got = llm.ask_json(
            "Read this clinical trial protocol. For each field choose exactly one allowed value and give the "
            "sentence from the protocol that supports it, copied verbatim. If the protocol does not say, use null.",
            p["text"],
            '{"comparator": {"value": "inert_placebo|active_placebo|low_dose_same_drug|other_active", "quote": ""}, '
            '"rater_model": {"value": "onsite|central_remote", "quote": ""}, '
            '"prior_use_policy": {"value": "stratify|ignore|exclude", "quote": ""}}')
        if not isinstance(got, dict):
            return
        allowed = {"comparator": COMPARATORS, "rater_model": RATER_MODELS, "prior_use_policy": PRIOR_USE_POLICIES}
        for field, ok in allowed.items():
            item = got.get(field)
            if not isinstance(item, dict):
                continue
            val, quote = item.get("value"), str(item.get("quote") or "").strip()
            if val is None:
                continue
            if val not in ok or not quote or quote not in p["text"]:
                ctx.rec.event(self.name, f"ignored Gemini's {field}='{val}': value not allowed or quote not found "
                                         "in the protocol", "info", M)
                continue
            if val != p[field]:
                ctx.rec.event(self.name, f"Gemini changed {field} from {p[field]} to {val}, quoting: \"{quote[:200]}\"",
                              "decision", M)
                p[field] = val
                p["evidence"][field] = quote


# ---------------------------------------------------------------------------
# Phase 2: protocol co-designer (risk, FDA July 2026 checklist, fixes, versions)
# ---------------------------------------------------------------------------
CHECKLIST = [
    ("blinding_questionnaire", "Blinding questionnaire (participants and raters guess allocation)", lambda p: p.get("has_blinding_questionnaire")),
    ("expectancy_measure", "Expectancy measured before randomisation and at end of treatment", lambda p: p.get("has_expectancy_measure")),
    ("central_raters", "Central blinded raters who do not attend dosing sessions",
     lambda p: p.get("rater_model") == "central_remote" and not p.get("design_flags", {}).get("raters_attend_sessions")),
    ("alternative_control", "Alternative or active control considered (not only inert placebo)", lambda p: p.get("comparator") != "inert_placebo"),
    ("durability", "12-week double-blind efficacy then about 12-month follow-up with retreatment criteria", lambda p: p.get("design_flags", {}).get("followup_12m")),
    ("monitors", "Two session monitors and a physician able to attend within 15 minutes",
     lambda p: p.get("design_flags", {}).get("two_monitors") and p.get("design_flags", {}).get("physician_15min")),
    ("factorial", "Factorial design considered to separate therapy from drug effect", lambda p: p.get("design_flags", {}).get("factorial")),
    ("abuse_potential", "Abuse-potential assessment planned", lambda p: p.get("design_flags", {}).get("abuse_potential")),
]
CHECK_PATTERNS = {"blinding_questionnaire": r"guess|blinding", "expectancy_measure": r"expectan", "central_raters": r"rater|assessor",
                  "alternative_control": r"placebo|comparator|control", "durability": r"follow[- ]up|month",
                  "monitors": r"monitor|facilitator|physician", "factorial": r"factorial", "abuse_potential": r"abuse"}

PRESENT_PATTERNS = {"central_raters": r"central(ised|ized)? blinded raters?|remote raters?|videoconferenc"}

FIXES = {  # fix id -> (title, structured change, sentence appended to the protocol text)
    "central_raters": ("Move outcome raters to central, remote, blinded assessment",
        {"rater_model": "central_remote", "design_flags.raters_attend_sessions": False},
        "Outcome ratings will be performed by central blinded raters by videoconference; raters will not attend dosing sessions."),
    "blinding_questionnaire": ("Add the UNBLIND-BLIND-1 guess questionnaire for participants and raters", {"has_blinding_questionnaire": True},
        "Participants and raters will guess allocation (drug, control, don't know) with confidence after dosing and at weeks 1, 3 and 6."),
    "expectancy_measure": ("Measure expectancy before randomisation and at end of treatment", {"has_expectancy_measure": True},
        "Participant expectancy (0 to 10) will be recorded before randomisation and at the end of treatment."),
    "alternative_control": ("Use a low dose of the same drug as comparator", {"comparator": "low_dose_same_drug"},
        "The comparator arm will receive a low dose of the study drug (1 mg)."),
    "stratify_prior_use": ("Stratify randomisation by prior psychedelic use", {"prior_use_policy": "stratify"},
        "Randomisation will be stratified by site and prior psychedelic use (naive or experienced)."),
}
FIXABLE_CHECKS = ("central_raters", "blinding_questionnaire", "expectancy_measure", "alternative_control")
SIM_WINDOW_DAYS = 90       # the simulated trial closes on day 90 (master.CLOSE_DAY)
DOSING_DAYS = 20           # Enroller staggers dosing over days 1 to 20 (dosing_day = 1 + i % DOSING_DAYS)
# The primary locks the day after the last participant's primary visit, which must be before close-out:
# DOSING_DAYS + 7 * week + 1 <= SIM_WINDOW_DAYS - 1 gives week <= 9 (week 9: last visit day 83, lock day 84).
SIM_MAX_PRIMARY_WEEK = (SIM_WINDOW_DAYS - 1 - DOSING_DAYS) // 7
WINDOW_ROW = "durability"  # the checklist row about timing of efficacy carries the note


def primary_week(p: dict) -> int:
    try:
        return int((p.get("primary_endpoint") or {}).get("week") or 6)
    except (TypeError, ValueError):
        return 6


def window_note(p: dict) -> str:
    """Plain-language note when the primary endpoint falls outside the 90-day simulation window, else ''."""
    wk = primary_week(p)
    if wk <= SIM_MAX_PRIMARY_WEEK:
        return ""
    return (f"Primary endpoint at week {wk} is outside the {SIM_WINDOW_DAYS}-day simulation window: the primary "
            f"result cannot lock before close-out (weeks 1 to {SIM_MAX_PRIMARY_WEEK} fit).")


def new_version(rec: TrialRecord, why: str, changes: List[str]) -> dict:
    text = rec["protocol"].get("text", "")
    v = {"version": len(rec["protocol_versions"]) + 1, "day": rec["day"], "digest": digest(text),
         "why": why, "changes": list(changes), "text": text}
    rec["protocol_versions"].append(v)
    return v


def _set(p: dict, key: str, value: Any) -> None:
    """Apply one structured change; supports dotted keys such as design_flags.raters_attend_sessions."""
    if "." in key:
        head, tail = key.split(".", 1)
        p.setdefault(head, {})
        _set(p[head], tail, value)
    else:
        p[key] = value


def _get(p: dict, key: str, default: Any = None) -> Any:
    """Read one structured value; mirrors _set (dotted keys such as design_flags.raters_attend_sessions)."""
    if "." in key:
        head, tail = key.split(".", 1)
        sub = p.get(head)
        return _get(sub, tail, default) if isinstance(sub, dict) else default
    return p.get(key, default)


def protocol_base(rec: TrialRecord) -> dict:
    """What an approval was proposed against: the current protocol digest and version number."""
    return {"base_digest": digest((rec.get("protocol") or {}).get("text", "")),
            "base_version": (rec.get("protocol_versions") or [{}])[-1].get("version")}


def protocol_changed_since(rec: TrialRecord, action: dict, allow_fixes: bool = False) -> bool:
    """True when the protocol changed after the approval was proposed. With allow_fixes, versions made by other
    approved fixes do not count (fixes only append their own sentence, so they never overwrite each other)."""
    base = action.get("base_digest")
    if not base or base == digest((rec.get("protocol") or {}).get("text", "")):
        return False
    if not allow_fixes:
        return True
    since = [v for v in rec.get("protocol_versions") or [] if (v.get("version") or 0) > (action.get("base_version") or 0)]
    return any(not v.get("fix") for v in since)


def fix_satisfied(p: dict, fid: str) -> bool:
    """True when every structured change of FIXES[fid] already has that value in the protocol."""
    return all(_get(p, k) == v for k, v in FIXES[fid][1].items())


def _fix_in_flight(rec: TrialRecord, fid: str) -> bool:
    """An approval for this fix was approved but its approval_decided message has not been handled yet."""
    return any(m["kind"] == "approval_decided" and not m["delivered"] and m["to"] == M
               and isinstance(m.get("payload"), dict) and m["payload"].get("status") == "approved"
               and (m["payload"].get("action") or {}).get("fix") == fid for m in rec["messages"])


class ProtocolCoDesigner:
    name = "protocol co-designer"

    def __init__(self):
        rows, self.cal_label = ubmodel.load_calibration()          # SYNTHETIC until real trials are approved
        self.dm = ubmodel.design_model(rows)
        from ...synthetic import fill_imputed
        rows = fill_imputed([dict(r) for r in rows], self.dm)
        self.fit = ubmodel.fit_metareg(rows) or ubmodel.fit_metareg(rows, use_imputed=True)

    def _design(self, p):
        pe = {"stratify": 0.4, "ignore": 0.5, "exclude": 0.0}.get(p.get("prior_use_policy", "ignore"), 0.5)
        return {"comparator_type": p.get("comparator", "inert_placebo"), "prior_exposure": pe,
                "central": int(p.get("rater_model") == "central_remote")}

    def risk(self, p):
        d = self._design(p)
        u, usd = self.dm.predict(d["comparator_type"], d["prior_exposure"])
        b = self.fit.coef.get("u", 0.0) if self.fit else 0.0
        c = self.fit.coef.get("central", 0.0) if self.fit else 0.0
        bias = b * u - c * (1 - d["central"])
        band = "high" if u >= 0.6 else "medium" if u >= 0.35 else "low"
        return {"u": round(u, 3), "u_sd": round(usd, 3), "expected_bias_g": round(bias, 3), "band": band,
                "calibration": self.cal_label, "design_model": self.dm.source}

    def checklist(self, p) -> List[dict]:
        out = []
        text = p.get("text", "")
        for cid, item, test in CHECKLIST:
            present = bool(test(p))
            ev = ""
            if present:   # quote the sentence that satisfies the item, not the first sentence that mentions the topic
                if cid in FIXES and FIXES[cid][2] in text:
                    ev = FIXES[cid][2]
                elif cid in PRESENT_PATTERNS:
                    ev = _find(text, PRESENT_PATTERNS[cid]) or ""
            ev = ev or _find(text, CHECK_PATTERNS[cid]) or ""
            out.append({"id": cid, "item": item, "present": present, "evidence": ev[:300],
                        "note": "" if present else "Missing or not stated in the protocol"})
        extra = window_note(p)
        if extra:
            row = next(r for r in out if r["id"] == WINDOW_ROW)
            row["note"] = f"{row['note']}. {extra}" if row["note"] else extra
        return out

    def draft_section(self, p):
        rater = ("central blinded raters by videoconference who do not attend dosing sessions" if p.get("rater_model") == "central_remote"
                 else "raters (currently on site; we recommend central blinded raters)")
        return "\n".join([
            "## Blinding and expectancy",
            "Allocation is concealed by stratified permuted-block randomisation (site x prior psychedelic use) held in a sealed vault.",
            f"Primary outcome ({p['primary_endpoint']['scale']}, week {p['primary_endpoint']['week']}) is scored by {rater}.",
            "Blinding integrity: participants and raters complete the UNBLIND-BLIND-1 guess item (drug, control, don't know) with confidence "
            "(0 to 100) after dosing and at weeks 1, 3 and 6. Blinding indices (Bang) are monitored per site and per rater during the trial, "
            "and a drift alert triggers a documented human decision.",
            "Expectancy: participants rate expected improvement (0 to 10) before randomisation, after dosing and at end of treatment.",
            "Analysis: the primary effect is reported alongside an expectancy-adjusted range with stated assumptions.",
        ])

    def review(self, rec: TrialRecord, ctx: Ctx, reason: str = "design review") -> dict:
        p = rec["protocol"]
        risk = self.risk(p)
        checklist = self.checklist(p)
        model_fixes = ubmodel.counterfactuals(self.fit, self.dm, self._design(p)) if self.fit else []
        missing = {c["id"] for c in checklist if not c["present"]}
        proposed = [f for f in FIXABLE_CHECKS if f in missing]
        if p.get("prior_use_policy") != "stratify":
            proposed.append("stratify_prior_use")
        ok = sum(c["present"] for c in checklist)

        rejected = sorted({a["action"].get("fix") for a in rec["approvals"] if a["module"] == M
                           and a["action"].get("type") == "apply_fix" and a["status"] == "rejected"
                           and a["action"].get("fix") in FIXES and not fix_satisfied(p, a["action"]["fix"])})
        prev = rec.get("design_review") or {}
        expired = {e.get("fix") for e in prev.get("expired_fixes") or []}
        dr = {"risk": risk, "checklist": checklist, "model_fixes": model_fixes, "proposed_fixes": proposed,
              "rejected_fixes": rejected,
              "blinding_section_md": self.draft_section(p),
              "baseline_risk": prev.get("baseline_risk", risk),
              "baseline_checklist_ok": prev.get("baseline_checklist_ok", ok)}
        for k, v in prev.items():   # keep state other agents keep here (pending_drift, participant_unblinding_notes, ...)
            dr.setdefault(k, v)
        rec["design_review"] = dr
        rec.event(self.name, f"{reason}: u={risk['u']} ({risk['band']}), expected bias {risk['expected_bias_g']} g, "
                             f"FDA checklist {ok}/{len(CHECKLIST)}, {len(proposed)} fix{'' if len(proposed) == 1 else 'es'} proposed", "decision", M)
        note, wk = window_note(p), primary_week(p)
        dr["window_note"] = note or None                       # the UI renders this; the checklist row carries it too
        if note and dr.get("window_flagged_week") != wk:      # say it once per primary week, not on every re-check
            dr["window_flagged_week"] = wk
            rec.event(self.name, f"{note} Noted on the FDA checklist (durability row); change the primary week in "
                                 "the protocol to run the full trial.", "decision", M)
        elif not note:
            dr.pop("window_flagged_week", None)

        pending = {a["action"].get("fix") for a in ctx.approvals.pending(M) if a["action"].get("type") == "apply_fix"}
        held = []
        for fid in proposed:
            if fid in pending or fid in rejected:   # a human already said no: do not ask again
                continue
            if fid in expired:                      # expired when dosing started: changes now go through amendments
                continue
            if fix_satisfied(p, fid) or _fix_in_flight(rec, fid):   # already in the protocol, or approved and about to apply
                continue
            if rec.get("enrolled"):                 # dosing has started: design fixes are closed, amendments only
                held.append(fid)
                continue
            title, _change, sentence = FIXES[fid]
            ctx.approvals.request(self.name, M, f"Protocol fix: {title}",
                                  "The co-designer found this missing against the FDA July 2026 guidance or the blinding "
                                  "risk model. Approving adds the sentence below, saves a new protocol version and re-checks.",
                                  {"type": "apply_fix", "fix": fid, **protocol_base(rec)},
                                  evidence={"sentence_to_add": sentence})
        if held:
            rec.event(self.name, f"participants are enrolled, so {len(held)} design fix{'' if len(held) == 1 else 'es'} "
                                 f"({', '.join(held)}) not asked as a design change; edit the protocol to propose an "
                                 "amendment instead", "info", M)
        return dr

    def apply_fix(self, rec: TrialRecord, ctx: Ctx, fid: str, approver: str, amendment_site: Optional[str] = None) -> dict:
        title, change, sentence = FIXES[fid]
        p = rec["protocol"]
        for k, v in change.items():
            _set(p, k, v)
        p["text"] = (p.get("text", "").rstrip() + "\n" + sentence + "\n")
        if amendment_site:
            what, why = f"amendment '{fid}' (after drift at {amendment_site})", f"amendment approved by {approver}: {title}"
        elif rec.get("enrolled"):
            what, why = (f"fix '{fid}' as a protocol amendment (participants are enrolled)",
                         f"amendment (fix) approved by {approver}: {title}")
        else:
            what, why = f"fix '{fid}'", f"fix approved by {approver}: {title}"
        v = new_version(rec, why, [sentence])
        v["fix"] = fid
        rec.event(self.name, f"applied {what} as protocol version {v['version']}", "decision", M)
        dr = self.review(rec, ctx, reason=f"re-check after version {v['version']}")
        ctx.bus.post(M, "master", "protocol_amended", {"fix": fid, "version": v["version"], "risk": dr["risk"]},
                     f"Protocol version {v['version']}: {title}")
        return dr


# ---------------------------------------------------------------------------
# Phase 3: recruitment ads, pre-screening, clinician approval, enrolment
# ---------------------------------------------------------------------------
def flesch(text):
    words = re.findall(r"[A-Za-z']+", text); sents = max(1, len(re.findall(r"[.!?]+", text)))
    syl = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower())) - (1 if w.lower().endswith("e") and len(w) > 3 else 0)) for w in words)
    return 0.0 if not words else round(206.835 - 1.015 * (len(words) / sents) - 84.6 * (syl / len(words)), 1)


PROMISE_RX = re.compile(r"\bcures?\b|will help you|guaranteed", re.I)
COMPARISON_RX = re.compile(r"placebo|comparison|by chance", re.I)
SENSATIONAL_RX = re.compile(r"magic mushroom|\btrips?\b|tripping", re.I)
CHANNELS = ["GP and clinic referral", "Opt-in national research registries", "Patient charities", "Hospital noticeboards"]
PARKED = ("Behavioural ad targeting by health or drug-use interests is parked: special category data under UK GDPR; "
          "ad platforms restrict health targeting.")
PLAIN_INDICATION = {
    "treatment-resistant depression": "depression that has not got better after at least two treatments",
    "major depressive disorder": "depression",
    "ptsd": "post-traumatic stress disorder (PTSD)",
}


class RecruitmentAgent:
    name = "recruitment ad writer"

    def run(self, rec: TrialRecord, ctx: Ctx) -> dict:
        p = rec["protocol"]
        cond = PLAIN_INDICATION.get(p.get("indication", ""), "the condition this study is about")
        wk = int(p.get("primary_endpoint", {}).get("week", 6))
        texts = [
            (f"Are you an adult aged 18 to 65 with {cond}? We are running a research study of a new medicine given with "
             f"talking support. You will be put in one of two groups by chance. One group gets the study medicine and the "
             f"other gets a comparison. You will not know which group you are in. The study lasts about 12 weeks, with 8 "
             f"visits. Taking part may not help you. Ask your GP or visit our study page to find out more."),
            (f"Help us test a new treatment for {cond}. This is a study, not a treatment service. Half of the people in it "
             f"get the study medicine and half get a comparison, chosen by chance. You need to come to 8 visits over about "
             f"12 weeks and answer short text messages. We cannot say if it will work for you. Talk to your GP to see if you can take part."),
            (f"Research study for adults with {cond}. What is involved: one dosing day with a trained team, then check-ins "
             f"and visits for about 12 weeks (8 visits in total). The main result is measured at week {wk}. You may get "
             f"the study medicine or a comparison, by chance. Nobody can promise it will make you feel better. You can "
             f"stop at any time."),
        ]
        ads = []
        for i, t in enumerate(texts, 1):
            ads.append({"id": f"AD-{i}", "text": t, "reading_ease": flesch(t),
                        "checks": {"no_promise_of_benefit": not PROMISE_RX.search(t),
                                   "mentions_comparison": bool(COMPARISON_RX.search(t)),
                                   "no_sensational_terms": not SENSATIONAL_RX.search(t)}})
        r = rec["recruitment"]
        r.update(ads=ads, channels=list(CHANNELS), parked=PARKED)
        r.setdefault("funnel", {"applied": 0, "auto_eligible": 0, "auto_excluded": 0, "needs_clinician": 0, "enrolled": 0})
        r.setdefault("fairness", [])
        r.setdefault("strata", {})
        passed = sum(all(a["checks"].values()) for a in ads)
        rec.event(self.name, f"drafted {len(ads)} ads (reading ease {', '.join(str(a['reading_ease']) for a in ads)}; "
                             f"{passed}/{len(ads)} pass all checks) for {len(CHANNELS)} channels; ads need ethics approval. "
                             "Behavioural health targeting parked (UK GDPR special category data)", "decision", M)
        return r


CRITERIA = [  # id, label, rule, why
    ("age", "Age", "18 to 65", "Typical adult trial range"),
    ("uk_mobile", "UK mobile", "+44 7 number", "Check-ins run through the UK chatbot"),
    ("diagnosis", "Diagnosis", "Follows the protocol indication: MDD or TRD for depression (TRD needs at least 2 failed "
     "antidepressants); PTSD for PTSD", "Matches the protocol population"),
    ("psychosis_bipolar", "Psychosis, personal bipolar", "Exclude", "Safety; standard psychedelic exclusion"),
    ("cardio", "Uncontrolled cardiovascular condition", "Exclude", "Blood pressure rises during sessions"),
    ("pregnancy", "Pregnancy or breastfeeding", "Exclude", "Safety"),
    ("lithium", "Lithium", "Exclude", "Interaction risk"),
    ("ssri_snri", "SSRI or SNRI", "Needs clinician (washout decision)", "Clinical judgement"),
    ("recent_psychedelic", "Psychedelic use in last 12 months", "Exclude", "Recent exposure confounds"),
    ("earlier_psychedelic", "Earlier psychedelic use", "Allowed, recorded for stratification", "Balance, do not exclude"),
    ("visits", "Can attend visits", "Required", "8 in-person visits"),
    ("free_text", "Free-text disclosure", "Needs clinician, with the quoted sentence", "Never auto-include a disclosed risk"),
    ("consent", "Consent to chatbot check-ins", "Required", "The standard measurement depends on it"),
]
DISCLOSURE = re.compile(r"bipolar|psychos|psychotic|schizo|cardiolog|heart|blood pressure|pregnan|suicid|self[- ]harm|seizure|epilep", re.I)
SSRI_SNRI = re.compile(r"\bssri\b|\bsnri\b|sertraline|escitalopram|citalopram|fluoxetine|paroxetine|venlafaxine|duloxetine", re.I)
DEPRESSION_DX = ("major depressive disorder", "treatment-resistant depression")
PTSD_DX = ("post-traumatic stress disorder", "ptsd")
AGE_BANDS = [("18-30", 18, 30), ("31-45", 31, 45), ("46-65", 46, 65), ("65+", 66, 200)]
CRITERION_LABEL = {c[0]: c[1] for c in CRITERIA}


def _public(a: dict) -> dict:
    """What agents may see of an applicant: never keys starting with '_' (synthetic ground truth)."""
    return {k: v for k, v in a.items() if not str(k).startswith("_")}


class PreScreeningAgent:
    name = "pre-screening agent"

    def __init__(self):
        self._llm_cache: Dict[str, Optional[str]] = {}

    def screen_one(self, applicant: dict, protocol: dict, ctx: Ctx) -> dict:
        a = _public(applicant)
        excl: List[tuple] = []   # (criterion, reason)
        flags: List[tuple] = []
        evidence: List[dict] = []

        age = a.get("age")
        if age is None:
            flags.append(("age", "Age not stated"))
        elif not 18 <= int(age) <= 65:
            excl.append(("age", f"Age {age} is outside 18 to 65"))

        phone = re.sub(r"[\s()-]", "", str(a.get("phone") or ""))
        if not phone:
            flags.append(("uk_mobile", "No mobile number given"))
        elif not phone.startswith("+447"):
            excl.append(("uk_mobile", "Not a UK mobile (+44 7) number; check-ins run through the UK chatbot"))

        ind = str(protocol.get("indication") or "").strip().lower()
        dx = a.get("self_reported_diagnosis")
        if ind in DEPRESSION_DX:
            if dx is None:
                flags.append(("diagnosis", "Diagnosis not stated"))
            elif dx not in DEPRESSION_DX:
                excl.append(("diagnosis", f"Diagnosis '{dx}' does not match the protocol population"))
            elif ind == "treatment-resistant depression":
                fails = a.get("failed_antidepressants")
                if fails is None:
                    flags.append(("diagnosis", "Number of failed antidepressants not stated"))
                elif int(fails) < 2:
                    excl.append(("diagnosis", f"{fails} failed antidepressants; treatment-resistant depression needs at least 2"))
        elif ind in PTSD_INDICATIONS:     # the TRD rule (failed antidepressants) does not apply to PTSD
            if dx is None:
                flags.append(("diagnosis", "Diagnosis not stated"))
            elif str(dx).strip().lower() not in PTSD_DX:
                excl.append(("diagnosis", f"Diagnosis '{dx}' does not match the protocol population (PTSD)"))
        elif dx is not None:
            flags.append(("diagnosis", f"Diagnosis '{dx}' needs a clinician check against the protocol population ({ind or 'unknown'})"))

        if a.get("history_psychosis") or a.get("history_bipolar"):
            excl.append(("psychosis_bipolar", "Personal history of psychosis or bipolar disorder"))
        if a.get("cardiovascular_condition"):
            excl.append(("cardio", "Cardiovascular condition"))
        if a.get("pregnant_or_breastfeeding"):
            excl.append(("pregnancy", "Pregnant or breastfeeding"))
        med = str(a.get("current_medication") or "")
        if re.search(r"lithium", med, re.I):
            excl.append(("lithium", "Currently taking lithium"))
        if SSRI_SNRI.search(med):
            flags.append(("ssri_snri", f"Taking {med}: clinician decides on washout"))

        prior = a.get("prior_psychedelic_use")
        if prior and prior != "never":
            months = a.get("months_since_last_psychedelic")
            if months is None:
                flags.append(("recent_psychedelic", "Psychedelic use reported but timing not stated"))
            elif int(months) <= 12:
                excl.append(("recent_psychedelic", f"Psychedelic use {months} months ago (within 12 months)"))

        if a.get("can_attend_8_visits") is False:
            excl.append(("visits", "Cannot attend the 8 in-person visits"))
        elif a.get("can_attend_8_visits") is None:
            flags.append(("visits", "Ability to attend visits not stated"))
        if a.get("consents_to_chatbot_checkins") is False:
            excl.append(("consent", "No consent to chatbot check-ins"))
        elif a.get("consents_to_chatbot_checkins") is None:
            flags.append(("consent", "Consent to chatbot check-ins not stated"))

        free = str(a.get("free_text") or "")
        quote = self._disclosure(free, ctx)
        if quote:
            flags.append(("free_text", "Free text discloses a possible safety risk"))
            evidence.append({"criterion": "free_text", "quote": quote})

        decision = "excluded" if excl else "needs_clinician" if flags else "eligible"
        hits = [c for c, _ in excl + flags]
        return {"decision": decision, "reasons": [r for _, r in excl + flags],
                "criteria_hit": list(dict.fromkeys(hits)), "evidence": evidence}

    def _disclosure(self, free: str, ctx: Ctx) -> Optional[str]:
        if not free.strip():
            return None
        if DISCLOSURE.search(free):
            return next((s for s in _sentences(free) if DISCLOSURE.search(s)), free.strip())
        llm = ctx.llm
        if llm is None or not llm.available():
            return None
        if free not in self._llm_cache:
            got = llm.ask_json(
                "This is free text from someone applying to a psychedelic drug trial. Does it disclose a condition "
                "relevant to their safety (psychosis, bipolar disorder, heart or blood pressure problems, pregnancy, "
                "suicidal thoughts or self-harm, seizures)? If yes, copy the sentence verbatim.",
                free, '{"discloses": true, "condition": "", "quote": ""}')
            q = str((got or {}).get("quote") or "").strip()
            self._llm_cache[free] = q if (got or {}).get("discloses") is True and q and q in free else None
        return self._llm_cache[free]

    def run(self, rec: TrialRecord, ctx: Ctx, applicants: List[dict]) -> dict:
        p = rec["protocol"]
        for app in applicants:
            rec["applicants"].append(dict(app, screening=self.screen_one(app, p, ctx)))
        apps = rec["applicants"]
        dec = [x["screening"]["decision"] for x in apps]
        f = rec["recruitment"].setdefault("funnel", {})
        f.update(applied=len(apps), auto_eligible=dec.count("eligible"), auto_excluded=dec.count("excluded"),
                 needs_clinician=dec.count("needs_clinician"), enrolled=len(rec["enrolled"]))
        rec["recruitment"]["fairness"] = self.fairness(apps)
        rec.event(self.name, f"screened {len(applicants)} applicants: {f['auto_eligible']} eligible, {f['auto_excluded']} "
                             f"excluded, {f['needs_clinician']} need a clinician (every disclosed risk is flagged with its quote)",
                  "decision", M)
        for g in rec["recruitment"]["fairness"]:
            if g["flag"]:
                rec.event(self.name, g["note"], "warn", M)
        return f

    @staticmethod
    def fairness(apps: List[dict]) -> List[dict]:
        def band(age):
            return next((b for b, lo, hi in AGE_BANDS if lo <= int(age) <= hi), None) if age is not None else None

        out = []
        for by, key in (("age band", lambda x: band(x.get("age"))), ("country", lambda x: x.get("country") or "unknown")):
            groups: Dict[str, List[dict]] = {}
            for x in apps:
                k = key(x)
                if k is not None:
                    groups.setdefault(k, []).append(x)
            rows = []
            for k, xs in groups.items():
                el = sum(x["screening"]["decision"] == "eligible" for x in xs)
                rows.append({"group": k, "n": len(xs), "eligible": el, "rate_pct": round(100 * el / len(xs), 1)})
            order = [b for b, _, _ in AGE_BANDS] if by == "age band" else sorted(groups)
            rows.sort(key=lambda r: order.index(r["group"]) if r["group"] in order else 99)
            spread = round(max(r["rate_pct"] for r in rows) - min(r["rate_pct"] for r in rows), 1) if rows else 0.0
            driver, note = None, ""
            if spread > 20:
                low = min(rows, key=lambda r: r["rate_pct"])["group"]
                counts: Dict[str, int] = {}
                for x in groups[low]:
                    if x["screening"]["decision"] != "eligible":
                        for c in x["screening"]["criteria_hit"]:
                            counts[c] = counts.get(c, 0) + 1
                driver = max(counts, key=counts.get) if counts else None
                note = (f"Eligibility differs by {by}: {spread} points between groups. Lowest is '{low}', mainly because of "
                        f"the '{CRITERION_LABEL.get(driver, driver)}' criterion.")
            out.append({"by": by, "rows": rows, "spread_pts": spread, "flag": spread > 20, "driver": driver, "note": note})
        return out


class Enroller:
    name = "enrolment agent"

    def run(self, rec: TrialRecord, ctx: Ctx, approval: dict) -> List[dict]:
        if rec["enrolled"]:
            return rec["enrolled"]
        include_flagged = "include flagged" in str(approval.get("comment") or "").lower()
        pool = [a for a in rec["applicants"] if a["screening"]["decision"] == "eligible"]
        if include_flagged:   # only those flagged purely for a medication washout decision, never a free-text disclosure
            pool += [a for a in rec["applicants"] if a["screening"]["decision"] == "needs_clinician"
                     and a["screening"]["criteria_hit"] == ["ssri_snri"]]
        p = rec["protocol"]
        sites = p.get("sites") or SITES
        n_target = int(p.get("n_target") or 60)
        enrolled = []
        for i, a in enumerate(pool[:n_target]):
            site = a.get("nearest_site") if a.get("nearest_site") in sites else sites[i % len(sites)]
            prior = a.get("prior_psychedelic_use", "never")
            enrolled.append({"id": a["id"], "name": a["name"], "site": site,
                             "stratum": f"{site}|{'naive' if prior == 'never' else 'experienced'}",
                             "prior_psychedelic_use": prior, "dosing_day": 1 + (i % DOSING_DAYS),
                             "consents": {"checkins": bool(a.get("consents_to_chatbot_checkins")),
                                          "data_sharing": bool(a.get("consents_to_data_sharing"))}})
        counts = ctx.vault.randomise(enrolled, "stratum")    # allocation stays in the vault; we keep counts only
        rec["enrolled"] = enrolled
        rec["recruitment"]["strata"] = counts
        rec["recruitment"].setdefault("funnel", {})["enrolled"] = len(enrolled)
        rec.event(self.name, f"enrolled {len(enrolled)} of {len(pool)} approved applicants (target {n_target})"
                             f"{' including washout-only flagged' if include_flagged else ''}, approved by {approval.get('reviewer')}",
                  "decision", M)
        rec.event(self.name, f"randomised 1:1 within {len(counts)} strata in the sealed vault (agents never see allocation)",
                  "decision", M)
        ctx.bus.post(M, "master", "enrolment_complete", {"n": len(enrolled), "strata": counts},
                     f"{len(enrolled)} participants enrolled and randomised")
        return enrolled


# ---------------------------------------------------------------------------
# Phase 4: measurement planner (UNBLIND-BLIND-1 instruments and the shared schedule)
# ---------------------------------------------------------------------------
INSTRUMENTS = [
    {"id": "UB1-EXP0", "who": "participant", "questions": ["How much do you expect to improve? (0 to 10)"], "timepoints": ["before randomisation"], "purpose": "Baseline expectancy (FDA July 2026)"},
    {"id": "UB1-PG", "who": "participant", "questions": ["Which group do you think you are in? (drug, control, don't know)", "How sure are you? (0 to 100)", "How much do you expect to improve? (0 to 10)"], "timepoints": ["dosing +1", "week 1", "week 3", "week {primary}"], "purpose": "Participant blinding and expectancy"},
    {"id": "UB1-RG", "who": "rater", "questions": ["Which group do you think this participant is in?", "How sure are you? (0 to 100)"], "timepoints": ["week 1", "week 3", "week {primary}"], "purpose": "Rater blinding (central raters)"},
    {"id": "UB1-MD", "who": "monitor", "questions": ["Free-text debrief: effects, adverse events, anything that could reveal the arm"], "timepoints": ["dosing day"], "purpose": "Safety and unblinding cues"},
    {"id": "MADRS", "who": "rater", "questions": ["MADRS total (0 to 60)"], "timepoints": ["baseline", "week 1", "week 3", "week {primary}"], "purpose": "Primary outcome"},
    {"id": "UB1-FU", "who": "participant", "questions": ["Follow-up check-in and end-of-treatment guess and expectancy"], "timepoints": ["week 8", "week 12"], "purpose": "Durability and end-of-treatment blinding"},
]


OUTCOME_TIMEPOINTS = ["baseline", "week 1", "week 3", "week {primary}"]
OUTCOME_INSTRUMENTS = {   # protocol primary scale -> the outcome instrument in the plan (MADRS is the default)
    "MADRS": {"id": "MADRS", "who": "rater", "questions": ["MADRS total (0 to 60)"],
              "timepoints": OUTCOME_TIMEPOINTS, "purpose": "Primary outcome"},
    "CAPS-5": {"id": "CAPS-5", "who": "rater",
               "questions": ["CAPS-5 total severity (0 to 80): a clinician interview about how often and how badly "
                             "PTSD symptoms affected the participant (unwanted memories and nightmares, avoiding "
                             "reminders, low mood and negative thoughts, feeling on edge or jumpy)"],
               "timepoints": OUTCOME_TIMEPOINTS, "purpose": "Primary outcome"},
    "HAM-D": {"id": "HAM-D", "who": "rater", "questions": ["HAM-D total (17 items, 0 to 52)"],
              "timepoints": OUTCOME_TIMEPOINTS, "purpose": "Primary outcome"},
}


def outcome_instrument(scale: Optional[str]) -> dict:
    """The outcome instrument for the protocol's primary scale; MADRS when the scale is MADRS or not supported."""
    return copy.deepcopy(OUTCOME_INSTRUMENTS.get(str(scale or "").strip().upper(), OUTCOME_INSTRUMENTS["MADRS"]))


def _timepoint_day(label: str) -> int:
    """Day relative to the participant's dosing day: -1 before randomisation or baseline, 0 dosing day,
    1 the day after, 7 * N for week N."""
    if label in ("before randomisation", "baseline"):
        return -1
    if label == "dosing day":
        return 0
    m = re.fullmatch(r"dosing \+(\d+)", label)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"week (\d+)", label)
    if m:
        return 7 * int(m.group(1))
    raise ValueError(f"unknown timepoint label {label!r}")


def plan_instruments(primary_week: int, scale: Optional[str] = None) -> List[dict]:
    """INSTRUMENTS for one protocol: human labels in `timepoints` and, 1:1 with them, integer days relative to
    the dosing day in `timepoints_days`. '{primary}' becomes the protocol's primary week. The outcome instrument
    (MADRS by default) is swapped for the protocol's primary scale, e.g. CAPS-5 for PTSD; its position is kept."""
    out = []
    for ins in INSTRUMENTS:
        if ins["id"] == "MADRS":
            ins = outcome_instrument(scale)
        labels = list(dict.fromkeys(t.format(primary=primary_week) for t in ins["timepoints"]))
        d = copy.deepcopy(ins)
        d["timepoints"] = labels
        d["timepoints_days"] = [_timepoint_day(t) for t in labels]
        out.append(d)
    return out


SCHEDULE_KINDS = ("dosing_session", "monitor_debrief", "participant_checkin", "rater_assessment", "followup")


def _letter(j: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (spreadsheet style), so any number of sites gets a distinct letter."""
    out = ""
    j += 1
    while j:
        j, r = divmod(j - 1, 26)
        out = chr(65 + r) + out
    return out


def rater_ids(enrolled: List[dict], protocol_sites: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Two rater ids per site, lettered A, B, C... in the order the protocol lists its sites; any enrolled site
    the protocol does not list is lettered after those, in sorted order. The letter is a position, not the site's
    own name: a protocol with only Site A and Site C gives Site C the ids R-B1/R-B2. For the default sites
    ("Site A (London)", "Site B (Manchester)", "Site C (Bristol)") this gives R-A1/R-A2, R-B1/R-B2, R-C1/R-C2."""
    sites = list(dict.fromkeys(protocol_sites or []))
    sites += sorted({p["site"] for p in enrolled} - set(sites))
    return {s: ["R-" + _letter(j) + "1", "R-" + _letter(j) + "2"] for j, s in enumerate(sites)}


def build_schedule(rec):
    wk = int(rec["protocol"].get("primary_endpoint", {}).get("week", 6))
    outcome = outcome_instrument(rec["protocol"].get("primary_endpoint", {}).get("scale"))["id"]
    raters = rater_ids(rec["enrolled"], rec["protocol"].get("sites"))          # e.g. R-A1, R-B2
    sched = []
    for i, p in enumerate(rec["enrolled"]):
        d, pid, site = p["dosing_day"], p["id"], p["site"]
        rid = raters[site][i % 2]

        def add(kind, day, owner, instrument, **extra):
            sched.append({"id": f"{pid}-{kind}-{day}", "participant": pid, "site": site, "day": day, "kind": kind,
                          "owner": owner, "instrument": instrument, "status": "scheduled", **extra})
        add("dosing_session", d, "dosing", "session")
        add("monitor_debrief", d, "dosing", "UB1-MD")
        add("participant_checkin", d + 1, "dosing", "UB1-PG")
        for w in sorted({1, 3, wk}):
            add("rater_assessment", d + 7 * w, "dosing", f"{outcome}+UB1-RG", rater_id=rid, visit_week=w)
            add("participant_checkin", d + 7 * w, "dosing", "UB1-PG", visit_week=w)
        for w in (8, 12):
            add("followup", d + 7 * w, "postdose", "UB1-FU", visit_week=w)
    return sched


class MeasurementPlanner:
    name = "measurement planner"

    def run(self, rec: TrialRecord, ctx: Ctx) -> List[dict]:
        if rec["schedule"]:          # dosing and postdose own the statuses once the schedule exists
            rec.event(self.name, "schedule already exists; not rebuilt", "info", M)
            return rec["schedule"]
        wk = int(rec["protocol"].get("primary_endpoint", {}).get("week", 6))
        scale = rec["protocol"].get("primary_endpoint", {}).get("scale")
        instruments = plan_instruments(wk, scale)
        outcome = outcome_instrument(scale)["id"]
        rec["measurement_plan"] = {"standard": "UNBLIND-BLIND-1", "instruments": instruments, "primary_week": wk}
        rec["schedule"] = build_schedule(rec)
        n = len(rec["enrolled"])
        by: Dict[str, int] = {}
        for s in rec["schedule"]:
            by[s["kind"]] = by.get(s["kind"], 0) + 1
        guesses = by.get("participant_checkin", 0) + by.get("rater_assessment", 0)
        if outcome != str(scale or "").strip().upper():
            rec.event(self.name, f"primary scale '{scale}' has no outcome instrument here; using {outcome} as the "
                                 "default outcome measure", "warn", M)
        rec.event(self.name, f"built the UNBLIND-BLIND-1 plan ({len(instruments)} instruments, outcome {outcome} at "
                             f"primary week {wk}) and "
                             f"{len(rec['schedule'])} scheduled tasks for {n} participants "
                             f"({', '.join(f'{k} {v}' for k, v in by.items())}); "
                             f"{round(guesses / n, 1) if n else 0} blinding check-ins per participant", "decision", M)
        return rec["schedule"]
