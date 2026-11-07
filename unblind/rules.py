"""Deterministic extraction rules.

These run with no API key, so the demo never depends on an LLM being up.
They are deliberately conservative: when a pattern is ambiguous the rule
returns nothing, and the pipeline records "unknown" rather than guessing.
Every candidate carries the exact sentence it came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

PSYCHEDELICS = {
    "psilocybin": ["psilocybin", "comp360", "psilocin"],
    "mdma": ["mdma", "midomafetamine", "3,4-methylenedioxymethamphetamine"],
    "lsd": ["lsd", "lysergic acid diethylamide", "mm120", "mm-120"],
    "dmt": ["dmt", "dimethyltryptamine", "spl026"],
    "5-meo-dmt": ["5-meo-dmt", "gh001", "bpl-003", "mebufotenin"],
    "ayahuasca": ["ayahuasca"],
    "ibogaine": ["ibogaine"],
    "mescaline": ["mescaline"],
    "zalsupindole": ["zalsupindole", "dlx-001", "dlx001"],
    "ketamine": ["ketamine", "esketamine"],
}
NON_HALLUCINOGENIC = {"zalsupindole"}

ACTIVE_PLACEBOS = ["niacin", "nicotinic acid", "diphenhydramine", "methylphenidate", "dextroamphetamine",
                   "midazolam", "dextromethorphan", "lorazepam", "active placebo", "ephedrine", "caffeine"]
OTHER_ACTIVE = ["escitalopram", "sertraline", "ssri", "venlafaxine", "esketamine", "ketamine", "naltrexone"]

LOWER_IS_BETTER = ["madrs", "ham-d", "hamd", "hdrs", "grid-hamd", "caps", "caps-5", "qids", "bdi",
                   "phq", "gad", "audit", "heavy drinking", "drinking days", "pcl", "ybocs", "y-bocs",
                   "hads", "stai", "cigarettes"]
SCALES = ["MADRS", "GRID-HAMD", "HAM-D", "HAMD", "HDRS", "CAPS-5", "CAPS", "QIDS-SR", "QIDS", "BDI-II",
          "BDI", "PHQ-9", "GAD-7", "PCL-5", "Y-BOCS", "YBOCS", "HADS", "STAI", "AUDIT", "percent heavy drinking days"]

NUM = r"[-−–]?\s?\d+(?:\.\d+)?"


def norm_num(s: str) -> float:
    return float(s.replace("−", "-").replace("–", "-").replace(" ", ""))


# ----------------------------------------------------------------------------
# sentences, keeping exact substrings so quotes verify verbatim
# ----------------------------------------------------------------------------
_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(\[])|\n+")


def sentences(text: str) -> List[str]:
    out = []
    for s in _SPLIT.split(text or ""):
        s = s.strip()
        if 8 <= len(s) <= 1500:
            out.append(s)
    return out


def find(text: str, pattern: str, flags=re.I) -> Iterable[Tuple[re.Match, str]]:
    rx = re.compile(pattern, flags)
    for s in sentences(text):
        for m in rx.finditer(s):
            yield m, s


# ----------------------------------------------------------------------------
# results firewall for the Design agent
# ----------------------------------------------------------------------------
EFFECT_LANGUAGE = re.compile(
    r"(p\s*[<=>≤]\s*0?\.\d|95\s*%\s*CI|confidence interval|mean difference|difference (of|in|between)|"
    r"effect size|cohen|hedges|change from baseline|least[- ]squares|LS mean|reduction (of|in)|"
    r"response rate|remission rate|responders?|statistically significant|significantly (greater|lower|higher|reduced|improved)|"
    r"favou?r(ed|ing)|outperform|superior to|odds ratio|hazard ratio)", re.I)


def results_blind(text: str) -> Tuple[str, int]:
    """Drop every sentence that talks about effect statistics. Returns (text, n_redacted)."""
    keep, dropped = [], 0
    for s in sentences(text):
        if EFFECT_LANGUAGE.search(s):
            dropped += 1
        else:
            keep.append(s)
    return "\n".join(keep), dropped


# ----------------------------------------------------------------------------
# drug / domain
# ----------------------------------------------------------------------------
def detect_drugs(text: str) -> List[str]:
    low = (text or "").lower()
    found = []
    for k, aliases in PSYCHEDELICS.items():
        if any(re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", low) for a in aliases):
            found.append(k)
    if "5-meo-dmt" in found and "dmt" in found:
        found.remove("dmt")
    return found


# ----------------------------------------------------------------------------
# comparator
# ----------------------------------------------------------------------------
@dataclass
class Cand:
    value: object
    quote: str
    note: str = ""


def comparator_from_arms(arms: List[dict], drug_aliases: List[str]) -> Optional[Cand]:
    comp_types = {"PLACEBO_COMPARATOR", "ACTIVE_COMPARATOR", "SHAM_COMPARATOR", "NO_INTERVENTION"}
    for a in arms:
        label = a.get("label", "") or ""
        desc = a.get("description", "") or ""
        typ = a.get("type", "") or ""
        blob = f"{label} {desc}".lower()
        is_comp = typ in comp_types or re.search(r"placebo|control|comparator|low[- ]dose", blob)
        if not is_comp:
            continue
        quote = f"Arm: {label} [{typ}]: {desc}"
        if typ == "NO_INTERVENTION" or "waitlist" in blob or "wait-list" in blob:
            return Cand("waitlist_or_none", quote)
        hits = [p for p in ACTIVE_PLACEBOS if re.search(r"(?<![a-z])" + re.escape(p), blob)]
        if hits:
            hit = hits[0]
            return Cand("active_placebo", quote, f"active placebo: {hit}")
        if any(re.search(r"(?<![a-z])" + re.escape(d) + r"(?![a-z])", blob) for d in drug_aliases):
            dose = re.search(r"(\d+(?:\.\d+)?)\s*(mg/kg|mg|µg|mcg|ug)", blob)
            return Cand("low_dose_same_drug", quote, f"dose {dose.group(0)}" if dose else "dose not stated")
        if any(o in blob for o in OTHER_ACTIVE):
            return Cand("other_active", quote)
        if "placebo" in blob or typ == "PLACEBO_COMPARATOR":
            return Cand("inert_placebo", quote)
    return None


def comparator_from_text(text: str, drug_aliases: List[str]) -> Optional[Cand]:
    for m, s in find(text, r"((?<![a-z])active placebo|niacin|diphenhydramine|methylphenidate|midazolam|dextromethorphan)"):
        return Cand("active_placebo", s, m.group(1))
    for m, s in find(text, r"(low[- ]dose|very low dose|(\d+(?:\.\d+)?)\s*mg)[^.]{0,40}(" +
                     "|".join(map(re.escape, drug_aliases or ["psilocybin"])) + r")[^.]{0,60}(control|comparator|condition|arm)"):
        return Cand("low_dose_same_drug", s, m.group(1))
    for m, s in find(text, r"(inactive|inert|identical[- ]appearing|matched)\s+placebo|placebo[- ]controlled|received placebo"):
        return Cand("inert_placebo", s)
    return None


# ----------------------------------------------------------------------------
# raters
# ----------------------------------------------------------------------------
RATER_CENTRAL = (r"(central(?:i[sz]ed)?|remote|independent|external)\s+(?:and\s+)?(?:blinded\s+|masked\s+)?"
                 r"(?:clinical\s+)?(?:raters?|assessors?|evaluators?|ratings?)|"
                 r"(?:raters?|assessors?)[^.]{0,80}(?:video|telephone|remotely|not present|unaware of|did not (?:attend|participate))|"
                 r"video[- ]?conferenc[^.]{0,60}(?:rat|assess)")
RATER_BLINDED = r"(?:blinded|masked|blind)\s+(?:outcomes?\s+)?(?:raters?|assessors?|evaluators?)|(?:raters?|assessors?)\s+(?:were|was|remained)\s+(?:blinded|masked|blind)"


def rater_placement(text: str) -> Optional[Cand]:
    for m, s in find(text, RATER_CENTRAL):
        return Cand("central_remote", s)
    for m, s in find(text, RATER_BLINDED):
        return Cand("blinded_unspecified", s)
    return None


# ----------------------------------------------------------------------------
# blinding integrity (guess accuracy)
# ----------------------------------------------------------------------------
WHO_RATER = re.compile(r"\b(raters?|assessors?|therapists?|facilitators?|investigators?|monitors?|clinicians?|staff)\b", re.I)
GUESS = r"(correctly\s+(?:guess|identif|predict|judg)\w*|guess(?:ed|es)?\s+correctly|accurately\s+(?:guess|identif)\w*)"


def guess_accuracy(text: str) -> List[Cand]:
    out: List[Cand] = []
    pats = [
        r"(\d+(?:\.\d+)?)\s*%[^.;]{0,100}?" + GUESS,
        GUESS + r"[^.;]{0,100}?(\d+(?:\.\d+)?)\s*%",
    ]
    for p in pats:
        for m, s in find(text, p):
            pct = next((g for g in m.groups() if g and re.fullmatch(r"\d+(?:\.\d+)?", g)), None)
            if pct is None:
                continue
            v = float(pct) / 100
            if not 0 <= v <= 1:
                continue
            who = "raters" if WHO_RATER.search(s) else "participants"
            out.append(Cand(v, s, who))
    for m, s in find(text, r"(\d+)\s*(?:of|/|out of)\s*(\d+)[^.;]{0,80}?" + GUESS):
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < b and a <= b:
            out.append(Cand(a / b, s, "raters" if WHO_RATER.search(s) else "participants"))
    for m, s in find(text, r"(Bang(?:'s)?|James(?:'s)?)\s+(?:blinding\s+)?index[^.;]{0,60}?(" + NUM + ")"):
        bi = norm_num(m.group(2))
        if -1 <= bi <= 1:
            out.append(Cand(("bang_bi", bi), s, "raters" if WHO_RATER.search(s) else "participants"))
    # de-duplicate by sentence
    seen, uniq = set(), []
    for c in out:
        k = (c.quote, str(c.value))
        if k not in seen:
            seen.add(k); uniq.append(c)
    return uniq


def blinding_planned(text: str) -> Optional[Cand]:
    for m, s in find(text, r"(blinding (?:integrity|assessment|questionnaire|index)|guess[^.]{0,60}(?:assignment|allocation|treatment|condition|arm)|"
                           r"(?:assignment|allocation)[^.]{0,40}guess)"):
        return Cand(True, s)
    return None


# ----------------------------------------------------------------------------
# prior psychedelic exposure
# ----------------------------------------------------------------------------
PSY_WORDS = r"(psychedelic|hallucinogen|psilocybin|lsd|mdma|ecstasy|mushroom|ayahuasca|dmt)s?"


def prior_exposure(text: str, eligibility: str = "") -> Optional[Cand]:
    pats = [
        r"(\d+(?:\.\d+)?)\s*%[^.;]{0,80}?(?:prior|previous|previously|lifetime|past|history of)\s+[^.;]{0,30}?" + PSY_WORDS,
        r"(?:prior|previous|lifetime|past)\s+" + PSY_WORDS + r"\s+(?:use|experience|exposure)[^.;]{0,60}?(\d+(?:\.\d+)?)\s*%",
        r"(?:prior|previous|lifetime|past)\s+" + PSY_WORDS + r"\s+(?:use|experience|exposure)[^.;]{0,40}?\(\s*(\d+(?:\.\d+)?)\s*%\s*\)",
    ]
    for p in pats:
        for m, s in find(text, p):
            pct = next((g for g in m.groups() if g and re.fullmatch(r"\d+(?:\.\d+)?", g)), None)
            if pct is not None and 0 <= float(pct) <= 100:
                return Cand(float(pct) / 100, s)
    for m, s in find(text, r"(psychedelic|hallucinogen|psilocybin)[- ]na[iï]ve"):
        return Cand(0.0, s, "derived: sample described as naive")
    if eligibility:
        excl = re.split(r"exclusion criteria", eligibility, flags=re.I)
        if len(excl) > 1:
            for m, s in find(excl[1], r"(?:prior|previous|lifetime|any)\s+(?:use of\s+)?" + PSY_WORDS):
                return Cand(0.0, s, "derived: eligibility excluded prior use, sample treated as naive (approximation if the exclusion is time-limited)")
    return None


# ----------------------------------------------------------------------------
# primary endpoint + effect size
# ----------------------------------------------------------------------------
def parse_endpoint(measure: str, timeframe: str) -> dict:
    blob = f"{measure} {timeframe}"
    scale = next((sc for sc in SCALES if re.search(r"(?<![A-Za-z])" + re.escape(sc) + r"(?![A-Za-z])", blob, re.I)), None)
    if scale is None and re.search(r"montgomery", blob, re.I):
        scale = "MADRS"
    if scale is None and re.search(r"clinician[- ]administered ptsd", blob, re.I):
        scale = "CAPS-5"
    week = None
    m = re.search(r"(?:week|wk)\s*(\d+)", blob, re.I) or re.search(r"(\d+)\s*weeks?", blob, re.I)
    if m:
        week = int(m.group(1))
    else:
        d = re.search(r"day\s*(\d+)", blob, re.I)
        if d:
            week = round(int(d.group(1)) / 7)
    return {"scale": scale, "week": week}


def lower_is_better(scale: Optional[str]) -> bool:
    if not scale:
        return True
    return any(k in scale.lower() for k in LOWER_IS_BETTER)


MD_CI = (r"(" + NUM + r")\s*(?:points?)?\s*[,;]?\s*[\(\[]?\s*(?:95\s*%\s*(?:CI|confidence interval)|CI)\s*[:,=]?\s*\[?\(?\s*(" + NUM +
         r")\s*(?:to|,|;|–|—|\s-\s)\s*(" + NUM + r")")
SMD = r"(Cohen'?s\s*d|Hedges'?\s*g|effect size|SMD|standardi[sz]ed mean difference)\s*(?:\(d\))?\s*(?:of|=|was|:|,)?\s*(" + NUM + r")"


def effect_candidates(text: str, endpoint: dict) -> List[Tuple[int, Cand]]:
    out: List[Tuple[int, Cand]] = []
    scale, week = endpoint.get("scale"), endpoint.get("week")

    def score(s: str) -> Tuple[int, List[str]]:
        sc, why = 0, []
        if scale and re.search(re.escape(scale), s, re.I):
            sc += 3; why.append("scale matches registry")
        if week and re.search(r"(?:week|wk)\s*" + str(week) + r"(?!\d)|" + str(week) + r"\s*weeks?", s, re.I):
            sc += 3; why.append(f"week {week} matches registry")
        elif week and re.search(r"(?:week|wk)\s*\d+", s, re.I):
            sc -= 2; why.append("different timepoint")
        if re.search(r"primary", s, re.I):
            sc += 1; why.append("says primary")
        if re.search(r"intention[- ]to[- ]treat|\bITT\b|full analysis|\bmITT\b", s, re.I):
            sc += 1; why.append("ITT")
        if re.search(r"completer|per[- ]protocol", s, re.I):
            sc -= 2; why.append("completers/per-protocol")
        if re.search(r"difference|between|versus|\bvs\.?|compared", s, re.I):
            sc += 2; why.append("between-group")
        if re.search(r"within[- ]group|from baseline in the", s, re.I):
            sc -= 1
        return sc, why

    for m, s in find(text, MD_CI):
        est, lo, hi = norm_num(m.group(1)), norm_num(m.group(2)), norm_num(m.group(3))
        if not (min(lo, hi) - 1e-9 <= est <= max(lo, hi) + 1e-9):
            continue
        sc, why = score(s)
        out.append((sc, Cand({"kind": "md", "est": est, "lo": lo, "hi": hi}, s, "; ".join(why))))
    for m, s in find(text, SMD):
        v = norm_num(m.group(2))
        if abs(v) > 5:
            continue
        sc, why = score(s)
        out.append((sc - 1, Cand({"kind": "smd", "est": v}, s, "; ".join(why))))
    out.sort(key=lambda x: -x[0])
    return out


def arm_ns(text: str) -> Optional[Cand]:
    m = re.search(r"\(\s*n\s*=\s*(\d+)\s*\)[^.;]{0,120}?\(\s*n\s*=\s*(\d+)\s*\)", text or "", re.I)
    if m:
        return Cand((int(m.group(1)), int(m.group(2))), m.group(0))
    return None
