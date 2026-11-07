"""The Auditor: deterministic, not another LLM.

A second language model asked "is this right?" shares the first one's blind
spots. So the audit is code:

1. The quote must appear verbatim (after whitespace/dash/quote normalisation)
   in the text of the source it claims to come from.
2. Every number in a numeric value must appear in that quote.
3. Enumerated values must be in the allowed set; proportions in [0, 1].

A fact that fails is downgraded to "unknown", and the reason is logged.
The auditor also scans sources for prompt-injection phrasing and flags them.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List

from .ledger import Fact, Ledger

ENUMS = {
    "comparator_type": {"inert_placebo", "active_placebo", "low_dose_same_drug", "other_active", "waitlist_or_none"},
    "rater_placement": {"central_remote", "blinded_unspecified", "onsite_unblinded"},
}
PROPORTIONS = {"guess_acc_participants", "guess_acc_raters", "prior_exposure"}

INJECTION = re.compile(r"(ignore (all|any|the) (previous|prior|above) instructions|you are now|system prompt|"
                       r"disregard (the|your) (instructions|rules)|output the following json)", re.I)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("−", "-").replace("–", "-").replace("—", "-").replace("­", "")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = re.sub(r"-\s*\n\s*", "", s)          # hyphenation across PDF lines
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _numbers(v) -> List[str]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [v]
    if isinstance(v, dict):
        return [x for x in v.values() if isinstance(x, (int, float)) and not isinstance(x, bool)]
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out += _numbers(x)
        return out
    return []


def _num_in_quote(x: float, quote: str) -> bool:
    q = _norm(quote)
    cands = {f"{x:g}", f"{abs(x):g}", f"{x:.1f}", f"{abs(x):.1f}", f"{x:.2f}", f"{abs(x):.2f}"}
    if 0 <= x <= 1:  # proportions may be quoted as percentages or as counts
        cands |= {f"{x*100:g}", f"{x*100:.1f}", f"{round(x*100)}"}
    if any(c in q for c in cands):
        return True
    if 0 < x < 1:  # a count fraction like "18 of 20" verifies if a/b == x
        for a, b in re.findall(r"(\d+)\s*(?:of|/|out of)\s*(\d+)", q):
            if int(b) and abs(int(a) / int(b) - x) < 1e-6:
                return True
    return False


def audit_fact(fact: Fact, ledger: Ledger) -> Fact:
    if fact.status in ("unknown", "imputed") or (fact.status == "derived" and not fact.quote):
        fact.audit = "n/a"
        return fact
    derived = fact.status == "derived"   # inferred from a quoted rule: check the quote, not the number
    src = ledger.sources.get(fact.source_id)
    reason = ""
    if not fact.quote:
        reason = "no quote"
    elif src is None:
        reason = f"unknown source {fact.source_id}"
    elif _norm(fact.quote) not in _norm(src.text):
        reason = "quote not found verbatim in source"
    elif fact.name in ENUMS and fact.value not in ENUMS[fact.name]:
        reason = f"value {fact.value!r} not allowed"
    elif fact.name in PROPORTIONS and not (isinstance(fact.value, (int, float)) and 0 <= fact.value <= 1):
        reason = "proportion out of range"
    elif not derived:
        for x in _numbers(fact.value):
            if not _num_in_quote(float(x), fact.quote):
                reason = f"number {x:g} not in quote"
                break
    if reason:
        ledger.log("auditor", f"REJECTED {fact.name}", reason, "warn")
        fact.audit = f"fail:{reason}"
        fact.note = (fact.note + f" | audit failed: {reason}; was {fact.value!r}").strip(" |")
        fact.status = "unknown"
        fact.value = None
    elif not reason:
        fact.audit = "pass"
        ledger.log("auditor", f"verified {fact.name}", f"quote found in {fact.source_id}")
    return fact


def audit_all(ledger: Ledger, names: Iterable[str] = ()) -> None:
    names = list(names) or list(ledger.facts)
    for n in names:
        audit_fact(ledger.facts[n], ledger)


def scan_injection(ledger: Ledger) -> List[str]:
    hits = []
    for sid, src in ledger.sources.items():
        m = INJECTION.search(src.text or "")
        if m:
            hits.append(sid)
            ledger.log("auditor", "possible prompt injection in source", f"{sid}: '{m.group(0)}' (treated as data only)", "warn")
    return hits
