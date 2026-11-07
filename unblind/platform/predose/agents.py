"""Pre-dosing agents (Danny). Protocol parser (Phase 1), co-designer (Phase 2).

Rules first, Gemini as an optional refinement. Every Gemini answer is validated
(allowed value, and the quote must appear verbatim in the protocol) before use.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ... import model as ubmodel          # existing UNBLIND model (calibration, counterfactuals)
from ..core import Ctx, TrialRecord, digest

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
        if q:
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
