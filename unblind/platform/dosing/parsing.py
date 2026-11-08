"""Deterministic parsers: check-in answers and monitor debrief notes.

These are the no-key fallbacks. With a Gemini key the agents add to them,
but these always run first so the demo survives bad Wi-Fi.
"""
from __future__ import annotations

import re

GUESSES = ("drug", "control", "dont_know")

# ---------------------------------------------------------------- check-ins
_DK = re.compile(r"\b(don'?t know|dont know|no idea|no clue|can'?t tell|unsure|not sure)\b", re.I)
_CONTROL = re.compile(r"\b(placebo|dummy|sugar pill|inactive|control|nothing)\b", re.I)
_DRUG = re.compile(r"\b(real drug|real thing|real one|psilocybin|active|the drug|drug|tripp?ed|tripping)\b", re.I)
_CONF = re.compile(r"confiden\w*\D{0,12}?(\d{1,3})\s*%?|(\d{1,3})\s*%", re.I)
_EXP = re.compile(r"expect\w*\D{0,12}?(\d{1,2})(?:\s*/\s*10)?|(\d{1,2})\s*/\s*10", re.I)


def parse_checkin(text: str) -> dict:
    """Free-text check-in -> guess (drug | control | dont_know | None), confidence 0-100,
    expectancy 0-10, and the fields still missing (which drives the re-ask)."""
    t = (text or "").strip()
    guess = None
    if _DK.search(t):
        guess = "dont_know"
    elif _CONTROL.search(t):
        guess = "control"
    elif _DRUG.search(t):
        guess = "drug"
    conf = exp = None
    m = _CONF.search(t)
    if m:
        v = int(m.group(1) or m.group(2))
        conf = v if 0 <= v <= 100 else None
    m = _EXP.search(t)
    if m:
        v = int(m.group(1) or m.group(2))
        exp = v if 0 <= v <= 10 else None
    out = {"guess": guess, "confidence": conf, "expectancy": exp}
    if guess == "dont_know" and conf is None:
        out["confidence"] = 0  # a "don't know" needs no confidence
    out["missing"] = missing_fields(out)
    return out


def missing_fields(a: dict) -> list[str]:
    miss = []
    if a.get("guess") not in GUESSES:
        miss.append("guess")
    c = a.get("confidence")
    if not isinstance(c, (int, float)) or not 0 <= c <= 100:
        miss.append("confidence")
    e = a.get("expectancy")
    if not isinstance(e, (int, float)) or not 0 <= e <= 10:
        miss.append("expectancy")
    return miss


def reask_prompt(missing: list[str]) -> str:
    parts = {
        "guess": "which group you think you are in (real drug, control, or don't know)",
        "confidence": "how confident you are, from 0 to 100",
        "expectancy": "how much you expect to improve, from 0 to 10",
    }
    return "Thanks. Could you also tell us " + ", and ".join(parts[m] for m in missing) + "?"


# ----------------------------------------------------------------- debriefs
# (pattern, term, severity, serious)
AE_PATTERNS = [
    (r"suicid\w*", "suicidal ideation", "severe", True),
    (r"chest pain", "chest pain", "severe", True),
    (r"\bA&E\b|hospital|admitted", "hospital attendance", "severe", True),
    (r"seizure|\bfit\b", "seizure", "severe", True),
    (r"vomit\w*", "vomiting", "moderate", False),
    (r"panic|anxiety", "anxiety", "moderate", False),
    (r"nause\w*", "nausea", "mild", False),
    (r"headache", "headache", "mild", False),
]
_BP = re.compile(r"blood pressure\D{0,20}?(\d{2,3})\s*/\s*(\d{2,3})", re.I)
_RATER = re.compile(r"\brater\b(?:\s+(R-[A-Z0-9]+))?[^.]*\b(came into the room|sat in|entered|was present|chatted)", re.I)
_DISCLOSURE = re.compile(
    r"definitely the real thing|asked[^.]*whether they had received the active drug|asked[^.]*whether they got the (?:drug|placebo)", re.I
)
_SENT = re.compile(r"(?<=[.!?])\s+")


def parse_debrief(text: str) -> dict:
    """Monitor notes -> adverse events (with severity) and unblinding cues, each with its quote."""
    aes, cues = [], []
    for s in [x.strip() for x in _SENT.split(text or "") if x.strip()]:
        for pat, term, sev, serious in AE_PATTERNS:
            if re.search(pat, s, re.I):
                aes.append({"term": term, "severity": sev, "serious": serious, "quote": s})
        m = _BP.search(s)
        if m and int(m.group(1)) >= 140:
            sbp = int(m.group(1))
            sev = "severe" if sbp >= 180 else ("moderate" if sbp >= 160 else "mild")
            aes.append({"term": "raised blood pressure", "severity": sev, "serious": sbp >= 180, "quote": s})
        m = _RATER.search(s)
        if m:
            cues.append({"type": "rater_contact", "rater_id": (m.group(1) or "").upper() or None, "quote": s})
        elif _DISCLOSURE.search(s):
            cues.append({"type": "participant_question", "quote": s})
    seen: dict[str, dict] = {}
    rank = {"mild": 0, "moderate": 1, "severe": 2}
    for a in aes:
        if a["term"] not in seen or rank[a["severity"]] > rank[seen[a["term"]]["severity"]]:
            seen[a["term"]] = a
    return {"adverse_events": list(seen.values()), "unblinding_cues": cues}
