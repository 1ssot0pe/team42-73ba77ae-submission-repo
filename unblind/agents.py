"""The agents. Each has one job, its own tools, and only the data it needs.

Resolver          any handle -> a registered trial (or pasted-text-only mode)
Hunter            finds the publication; reformulates queries on a miss
OutcomeExtractor  picks the effect that matches the REGISTERED primary endpoint
DesignExtractor   comparator, rater placement, prior exposure. Results-blind:
                  sentences with effect statistics are redacted before it reads.
BlindingHunter    guess-accuracy data: paper -> supplement -> protocol PDF,
                  chosen at runtime by what is available and what failed
Auditor           (audit.py) deterministic verbatim-quote check

Each extractor tries Gemini first when GEMINI_API_KEY is set, audits the
answer, and falls back to deterministic rules for anything that fails.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import llm, net, rules, sources
from .audit import audit_fact, _norm
from .ledger import Fact, Ledger, Source, unknown

NCT_RX = re.compile(r"\bNCT\d{8}\b", re.I)
DOI_RX = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
PMCID_RX = re.compile(r"\bPMC\d{5,9}\b", re.I)
PMID_RX = re.compile(r"^\s*(?:pmid:?\s*)?(\d{6,9})\s*$", re.I)
CONDITIONS = ["treatment-resistant depression", "major depressive disorder", "depression", "ptsd",
              "post-traumatic stress", "alcohol use disorder", "anxiety", "smoking", "tobacco",
              "anorexia", "ocd", "obsessive", "cancer", "bipolar", "migraine", "cluster headache"]


def _locate(quote: str, ledger: Ledger, prefer: str = "") -> Optional[str]:
    """Which source actually contains this quote? (re-attributes LLM mistakes)"""
    q = _norm(quote)
    if not q:
        return None
    if prefer in ledger.sources and q in _norm(ledger.sources[prefer].text):
        return prefer
    for sid, s in ledger.sources.items():
        if q in _norm(s.text):
            return sid
    return None


def _source_of(text_quote: str, ledger: Ledger, default: str) -> str:
    return _locate(text_quote, ledger, default) or default


# ===========================================================================
@dataclass
class Resolved:
    kind: str                         # nct | doi | pmcid | pmid | text | none
    nct: Optional[str] = None
    study: Optional[dict] = None
    paper_hit: Optional[dict] = None
    pasted: Optional[Source] = None
    alternatives: List[str] = field(default_factory=list)


class Resolver:
    name = "resolver"

    def __init__(self, ledger: Ledger):
        self.L = ledger

    def run(self, raw: str) -> Resolved:
        raw = (raw or "").strip()
        if not raw:
            self.L.log(self.name, "empty input", level="error")
            return Resolved("none")
        if len(raw) > 200_000:
            raw = raw[:200_000]
            self.L.log(self.name, "input truncated to 200k chars", level="warn")

        ncts = list(dict.fromkeys(m.upper() for m in NCT_RX.findall(raw)))
        if ncts:
            if len(ncts) > 1:
                self.L.log(self.name, "several NCT IDs in input", f"using {ncts[0]}; others: {', '.join(ncts[1:])}", "decision")
            kind = "nct" if len(raw) < 80 else "text"
            pasted = self._pasted(raw) if kind == "text" else None
            return self._from_nct(ncts[0], kind, pasted, ncts[1:])

        m = DOI_RX.search(raw)
        if m and len(raw) < 300:
            doi = m.group(1).rstrip(".,;)")
            self.L.log(self.name, "input looks like a DOI", doi, "decision")
            return self._from_paper_query(f'DOI:"{doi}"', "doi")
        m = PMCID_RX.search(raw)
        if m and len(raw) < 80:
            self.L.log(self.name, "input looks like a PMCID", m.group(0), "decision")
            return self._from_paper_query(f"PMCID:{m.group(0).upper()}", "pmcid")
        m = PMID_RX.match(raw)
        if m:
            self.L.log(self.name, "input looks like a PubMed ID", m.group(1), "decision")
            return self._from_paper_query(f"EXT_ID:{m.group(1)} AND SRC:MED", "pmid")

        # free text: a pasted abstract/paragraph, or a short description
        pasted = self._pasted(raw) if len(raw) >= 200 else None
        self.L.log(self.name, "free text input", "pasted document" if pasted else "short description; searching the registry", "decision")
        return self._from_text(raw, pasted)

    # ---------------------------------------------------------------------
    def _pasted(self, raw: str) -> Source:
        src = Source(id="pasted:input", kind="pasted", url="(pasted by user)",
                     licence="Supplied by the user at runtime", title="Pasted text", text=raw,
                     sections={"pasted": raw})
        self.L.add_source(src)
        return src

    def _from_nct(self, nct: str, kind: str, pasted=None, alts=()) -> Resolved:
        try:
            study = sources.ctgov_study(nct)
            s = sources.study_summary(study)
            self.L.log(self.name, f"registry record found for {nct}", s["title"][:120])
            return Resolved(kind, nct, study, None, pasted, list(alts))
        except net.NetError as e:
            self.L.log(self.name, f"registry lookup failed for {nct}", str(e), "warn")
            return Resolved(kind, nct, None, None, pasted, list(alts))

    def _from_paper_query(self, q: str, kind: str) -> Resolved:
        try:
            hits = sources.epmc_search(q, page_size=3)
        except net.NetError as e:
            self.L.log(self.name, "literature lookup failed", str(e), "warn")
            return Resolved(kind)
        if not hits:
            self.L.log(self.name, "no paper found for that identifier", q, "warn")
            return Resolved(kind)
        hit = hits[0]
        self.L.log(self.name, "paper found", hit.get("title", "")[:120])
        blob = json.dumps(hit)
        ncts = list(dict.fromkeys(x.upper() for x in NCT_RX.findall(blob)))
        if not ncts and hit.get("pmcid") and hit.get("isOpenAccess") == "Y":
            try:
                src = sources.epmc_fulltext_source(hit)
                ncts = list(dict.fromkeys(x.upper() for x in NCT_RX.findall(src.text)))
            except net.NetError:
                pass
        if ncts:
            self.L.log(self.name, "paper names its registration", ncts[0], "decision")
            r = self._from_nct(ncts[0], kind)
            r.paper_hit = hit
            return r
        self.L.log(self.name, "paper does not cite an NCT ID; continuing without registry record",
                   "primary endpoint cannot be cross-checked against registration", "warn")
        return Resolved(kind, None, None, hit)

    def _from_text(self, raw: str, pasted: Optional[Source]) -> Resolved:
        drugs = rules.detect_drugs(raw)
        conds = [c for c in CONDITIONS if c in raw.lower()][:2]
        terms = []
        if drugs:
            terms.append(" OR ".join(drugs[:2]))
        if conds:
            terms.append(conds[0])
        if not terms:
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", raw)[:8]]
            terms = [" ".join(words[:5])] if words else []
        if not terms:
            self.L.log(self.name, "could not make a search query from the input", level="error")
            return Resolved("text", pasted=pasted)
        q = " AND ".join(f"({t})" for t in terms)
        try:
            hits = sources.ctgov_search(q, page_size=5)
        except net.NetError as e:
            self.L.log(self.name, "registry search failed", str(e), "warn")
            return Resolved("text", pasted=pasted)
        if not hits:
            self.L.log(self.name, "registry search returned nothing", q, "warn")
            return Resolved("text", pasted=pasted)
        summaries = [sources.study_summary(h) for h in hits]
        # prefer randomised, completed, with results
        def score(s):
            return (s["allocation"] == "RANDOMIZED") * 2 + (s["status"] == "COMPLETED") + s["has_results"]
        best = max(range(len(hits)), key=lambda i: score(summaries[i]))
        chosen = summaries[best]
        alts = [s["nct"] for i, s in enumerate(summaries) if i != best]
        self.L.log(self.name, f"query '{q}' matched {len(hits)} trials", f"chose {chosen['nct']} ({chosen['title'][:80]}); "
                   f"alternatives {', '.join(alts)}. A human should confirm this match.", "decision")
        return Resolved("text", chosen["nct"], hits[best], None, pasted, alts)


# ===========================================================================
class Hunter:
    name = "hunter"

    def __init__(self, ledger: Ledger):
        self.L = ledger

    def find_paper(self, r: Resolved) -> Optional[Source]:
        if r.paper_hit:
            return self._load(r.paper_hit)
        if not r.nct:
            return None
        s = sources.study_summary(r.study) if r.study else {"nct": r.nct, "title": "", "sponsor": "", "interventions": [], "conditions": []}
        title_kw = " ".join(w for w in re.findall(r"[A-Za-z][A-Za-z-]{4,}", s["title"])[:6])
        drug = " OR ".join(rules.detect_drugs(" ".join(s["interventions"]) + " " + s["title"])[:2])
        cond = (s["conditions"] or [""])[0]
        strategies = [
            ("registry ID cited anywhere in the paper", f'"{r.nct}"'),
            ("title keywords + sponsor", f'TITLE:({title_kw}) AND "{s["sponsor"]}"' if title_kw and s["sponsor"] else ""),
            ("drug + condition + randomised", f'({drug}) AND "{cond}" AND (randomized OR randomised) AND PUB_TYPE:"Journal Article"' if drug and cond else ""),
        ]
        for why, q in strategies:
            if not q:
                continue
            try:
                hits = sources.epmc_search(q, page_size=8)
            except net.NetError as e:
                self.L.log(self.name, f"search failed ({why})", str(e), "warn")
                continue
            hits = [h for h in hits if not re.search(r"protocol|review|meta-analys|commentary|letter", (h.get("title") or ""), re.I)
                    or r.nct.lower() in json.dumps(h).lower()]
            if not hits:
                self.L.log(self.name, f"no usable hits via {why}", "reformulating the query", "decision")
                continue
            best = max(hits, key=lambda h: self._score(h, r.nct, s))
            sc = self._score(best, r.nct, s)
            if sc < 2:
                self.L.log(self.name, f"best hit via {why} scored too low ({sc})", (best.get("title") or "")[:100], "decision")
                continue
            self.L.log(self.name, f"publication found via {why}", f"{(best.get('title') or '')[:100]} ({best.get('pubYear')})", "decision")
            return self._load(best)
        self.L.log(self.name, "no publication found", "will rely on registry and protocol documents only", "warn")
        return None

    def _score(self, h: dict, nct: str, s: dict) -> int:
        sc = 0
        blob = json.dumps(h).lower()
        if nct.lower() in blob:
            sc += 4
        tw = set(w.lower() for w in re.findall(r"[A-Za-z]{5,}", s.get("title", "")))
        hw = set(w.lower() for w in re.findall(r"[A-Za-z]{5,}", h.get("title") or ""))
        if tw:
            sc += int(4 * len(tw & hw) / len(tw))
        if re.search(r"randomi[sz]ed|placebo", blob):
            sc += 1
        return sc

    def _load(self, hit: dict) -> Source:
        if hit.get("pmcid") and hit.get("isOpenAccess") == "Y":
            try:
                src = sources.epmc_fulltext_source(hit)
                self.L.add_source(src)
                self.L.log(self.name, "full text fetched (open access)", src.id)
                return src
            except (net.NetError, Exception) as e:
                self.L.log(self.name, "full text fetch failed; falling back to abstract", str(e)[:120], "decision")
        src = sources.epmc_abstract_source(hit)
        self.L.add_source(src)
        self.L.log(self.name, "only the abstract is available (not open access)", src.id, "decision")
        return src


# ===========================================================================
def _fact_from_llm(name: str, item: Any, ledger: Ledger, agent: str, default_src: str) -> Optional[Fact]:
    if not isinstance(item, dict) or item.get("value") in (None, "", []):
        return None
    quote = (item.get("quote") or "").strip()
    sid = _source_of(quote, ledger, item.get("source_id") or default_src)
    return Fact(name, item["value"], "observed", quote, sid, agent, item.get("note", "") or "via Gemini")


def _bundle(ledger: Ledger, ids: List[str], transform=None) -> str:
    parts = []
    for sid in ids:
        s = ledger.sources.get(sid)
        if not s:
            continue
        t = transform(s.text) if transform else s.text
        parts.append(f"[source_id: {sid}]\n{t}")
    return "\n\n".join(parts)


class OutcomeExtractor:
    name = "outcome"

    def __init__(self, ledger: Ledger):
        self.L = ledger

    def run(self, endpoint: dict, src_ids: List[str]) -> None:
        self.L.log(self.name, "checking the registered primary endpoint before choosing a number",
                   f"scale={endpoint.get('scale')}, week={endpoint.get('week')}", "decision")
        if llm.available():
            got = llm.ask_json(
                "Find the BETWEEN-GROUP effect for the trial's primary endpoint: "
                f"scale {endpoint.get('scale')}, timepoint week {endpoint.get('week')}, measure '{endpoint.get('measure','')}'. "
                "Prefer intention-to-treat over completers. Report a mean difference with its 95% CI (kind 'md'), "
                "or a standardised effect such as Cohen's d / Hedges' g (kind 'smd'). Also give the number analysed "
                "in the drug arm and comparator arm if stated. List other candidate numbers you rejected and why.",
                _bundle(self.L, src_ids),
                '{"effect": {"kind": "md|smd|null", "est": 0.0, "lo": null, "hi": null, "quote": "", "source_id": ""}, '
                '"arm_ns": {"value": [0, 0], "quote": "", "source_id": ""}, "rejected": ["..."]}')
            if got:
                e = got.get("effect") or {}
                if e.get("kind") in ("md", "smd") and isinstance(e.get("est"), (int, float)):
                    val = {"kind": e["kind"], "est": float(e["est"])}
                    if e["kind"] == "md" and isinstance(e.get("lo"), (int, float)) and isinstance(e.get("hi"), (int, float)):
                        val.update(lo=float(e["lo"]), hi=float(e["hi"]))
                    f = _fact_from_llm("effect", {"value": val, "quote": e.get("quote"), "source_id": e.get("source_id")},
                                       self.L, self.name, src_ids[0] if src_ids else "")
                    if f and audit_fact(f, self.L).status == "observed":
                        f.note = "; ".join(got.get("rejected") or [])[:300]
                        self.L.put(f)
                n = got.get("arm_ns") or {}
                if isinstance(n.get("value"), list) and len(n["value"]) == 2 and all(isinstance(x, int) for x in n["value"]):
                    f = _fact_from_llm("arm_ns", n, self.L, self.name, src_ids[0] if src_ids else "")
                    if f and audit_fact(f, self.L).status == "observed":
                        self.L.put(f)
        if self.L.status("effect") != "observed":
            self._rules(endpoint, src_ids)

    def _rules(self, endpoint: dict, src_ids: List[str]) -> None:
        best: Optional[Tuple[int, rules.Cand, str]] = None
        n_seen = 0
        for sid in src_ids:
            s = self.L.sources.get(sid)
            if not s:
                continue
            for sc, c in rules.effect_candidates(s.text, endpoint):
                n_seen += 1
                if best is None or sc > best[0]:
                    best = (sc, c, sid)
        if best is None or best[0] < 2:
            self.L.log(self.name, "no between-group effect matching the registered endpoint",
                       f"{n_seen} candidate numbers seen, none acceptable", "warn")
            self.L.put(unknown("effect", self.name, f"{n_seen} candidates rejected"))
            return
        sc, c, sid = best
        self.L.log(self.name, f"chose effect from {sid}", f"score {sc}: {c.note}; {n_seen - 1} other candidates rejected", "decision")
        f = Fact("effect", c.value, "observed", c.quote, sid, self.name, f"rule match ({c.note})")
        self.L.put(audit_fact(f, self.L))
        for sid in src_ids:
            s = self.L.sources.get(sid)
            if s and self.L.status("arm_ns") != "observed":
                c2 = rules.arm_ns(s.text)
                if c2:
                    self.L.put(audit_fact(Fact("arm_ns", c2.value, "observed", c2.quote, sid, self.name), self.L))


class DesignExtractor:
    """Never sees results: every sentence with effect statistics is redacted first."""
    name = "design"

    def __init__(self, ledger: Ledger):
        self.L = ledger

    def run(self, src_ids: List[str], study: Optional[dict], drug_aliases: List[str]) -> None:
        redacted_total = 0

        def blind(t):
            nonlocal redacted_total
            out, n = rules.results_blind(t)
            redacted_total += n
            return out

        bundle = _bundle(self.L, src_ids, blind)
        self.L.log(self.name, "results firewall applied", f"{redacted_total} sentences with effect statistics redacted before reading", "decision")

        if llm.available():
            got = llm.ask_json(
                "Extract trial DESIGN facts only. comparator_type must be one of: inert_placebo, active_placebo "
                "(a different psychoactive drug used to mimic effects, e.g. niacin, diphenhydramine, methylphenidate), "
                "low_dose_same_drug, other_active (an established treatment such as escitalopram), waitlist_or_none. "
                "rater_placement must be one of: central_remote (outcome raters remote/central, not present at dosing, blinded), "
                "blinded_unspecified (raters described as blinded, placement not stated), onsite_unblinded. "
                "prior_exposure is the PROPORTION (0-1) of participants with any previous psychedelic use, or 0 if the "
                "sample was required to be naive.",
                bundle,
                '{"comparator_type": {"value": null, "quote": "", "source_id": ""}, '
                '"rater_placement": {"value": null, "quote": "", "source_id": ""}, '
                '"prior_exposure": {"value": null, "quote": "", "source_id": ""}}')
            if got:
                for k in ("comparator_type", "rater_placement", "prior_exposure"):
                    f = _fact_from_llm(k, got.get(k), self.L, self.name, src_ids[0] if src_ids else "")
                    if f and audit_fact(f, self.L).status == "observed":
                        self.L.put(f)

        # rule fallbacks, field by field
        if self.L.status("comparator_type") != "observed":
            c = None
            sid = ""
            if study:
                c = rules.comparator_from_arms(sources.study_summary(study)["arms"], drug_aliases)
                sid = f"ctgov:{sources.study_summary(study)['nct']}"
            if c is None:
                for s_id in src_ids:
                    s = self.L.sources.get(s_id)
                    if s:
                        c = rules.comparator_from_text(rules.results_blind(s.text)[0], drug_aliases)
                        if c:
                            sid = s_id
                            break
            if c:
                self.L.put(audit_fact(Fact("comparator_type", c.value, "observed", c.quote, sid, self.name, c.note), self.L))
            else:
                self.L.put(unknown("comparator_type", self.name, "no comparator arm description found"))
        if self.L.status("rater_placement") != "observed":
            for s_id in src_ids:
                s = self.L.sources.get(s_id)
                c = rules.rater_placement(rules.results_blind(s.text)[0]) if s else None
                if c:
                    self.L.put(audit_fact(Fact("rater_placement", c.value, "observed", c.quote, s_id, self.name), self.L))
                    break
            else:
                self.L.put(unknown("rater_placement", self.name, "rater arrangement not described"))
        if self.L.status("prior_exposure") not in ("observed", "derived"):
            elig = ""
            if study:
                elig = (study.get("protocolSection", {}).get("eligibilityModule", {}) or {}).get("eligibilityCriteria", "")
            for s_id in src_ids:
                s = self.L.sources.get(s_id)
                if not s:
                    continue
                c = rules.prior_exposure(rules.results_blind(s.text)[0], elig if s.kind == "registry" else "")
                if c:
                    st = "derived" if c.note.startswith("derived") else "observed"
                    self.L.put(audit_fact(Fact("prior_exposure", c.value, st, c.quote, s_id, self.name, c.note), self.L))
                    break
            else:
                self.L.put(unknown("prior_exposure", self.name, "prior psychedelic use not reported"))


class BlindingHunter:
    name = "blinding"

    def __init__(self, ledger: Ledger):
        self.L = ledger

    def _scan(self, src: Source) -> bool:
        """Try to read guess-accuracy data from one source. True if found."""
        found = False
        if llm.available():
            got = llm.ask_json(
                "Did this trial assess blinding integrity (asking participants and/or raters to guess which arm a "
                "participant was in)? If results are given, report the PROPORTION (0-1) of guesses that matched the "
                "actual allocation, separately for participants and for raters. Use the overall figure across arms if "
                "given; otherwise the drug arm, and say which in note. Also report whether the document says such an "
                "assessment was PLANNED.",
                f"[source_id: {src.id}]\n{src.text}",
                '{"guess_acc_participants": {"value": null, "quote": "", "note": ""}, '
                '"guess_acc_raters": {"value": null, "quote": "", "note": ""}, '
                '"blinding_assessment_planned": {"value": null, "quote": ""}}')
            if got:
                for k in ("guess_acc_participants", "guess_acc_raters", "blinding_assessment_planned"):
                    f = _fact_from_llm(k, got.get(k), self.L, self.name, src.id)
                    if f and audit_fact(f, self.L).status == "observed":
                        self.L.put(f)
                        found = found or k != "blinding_assessment_planned"
        if not found:
            for c in rules.guess_accuracy(src.text):
                v = c.value
                who = "guess_acc_raters" if c.note == "raters" else "guess_acc_participants"
                if isinstance(v, tuple):  # Bang index
                    acc = (v[1] + 1) / 2
                    f = audit_fact(Fact(who, round(acc, 3), "derived", c.quote, src.id, self.name, f"from Bang index {v[1]}"), self.L)
                    self.L.put(f)
                    found = True
                    continue
                if self.L.status(who) != "observed":
                    f = audit_fact(Fact(who, round(v, 3), "observed", c.quote, src.id, self.name, "rule match; arm not disambiguated"), self.L)
                    if f.status == "observed":
                        self.L.put(f)
                        found = True
        if self.L.status("blinding_assessment_planned") != "observed":
            c = rules.blinding_planned(src.text)
            if c:
                self.L.put(audit_fact(Fact("blinding_assessment_planned", True, "observed", c.quote, src.id, self.name), self.L))
        return found

    def run(self, paper: Optional[Source], study: Optional[dict]) -> None:
        plan: List[Tuple[str, Any]] = []
        if paper is not None:
            plan.append(("paper", paper))
        for sid, s in list(self.L.sources.items()):
            if s.kind in ("pasted", "registry-results") and (paper is None or sid != paper.id):
                plan.append((s.kind, s))
        for kind, src in plan:
            self.L.log(self.name, f"looking for guess-accuracy data in the {kind}", src.id)
            if self._scan(src):
                self.L.log(self.name, f"blinding integrity found in the {kind}", level="decision")
                return
        # supplements: only reachable for open-access papers
        if paper is not None and paper.kind == "paper":
            pmcid = paper.id.split(":", 1)[1]
            self.L.log(self.name, "not in the main paper; trying the supplementary files", pmcid, "decision")
            try:
                for s in sources.epmc_supplement_sources(pmcid):
                    self.L.add_source(s)
                    if self._scan(s):
                        self.L.log(self.name, "blinding integrity found in a supplement", s.id, "decision")
                        return
            except net.NetError as e:
                self.L.log(self.name, "supplements unavailable", str(e), "warn")
        elif paper is not None:
            self.L.log(self.name, "paper is not open access, so supplements cannot be fetched", "skipping to protocol documents", "decision")
        # protocol PDF from the registry CDN
        if study:
            docs = sources.protocol_pdf_urls(study)
            if not docs:
                self.L.log(self.name, "no protocol documents posted on the registry", level="decision")
            for d in docs[:2]:
                self.L.log(self.name, "trying the protocol document", d["label"], "decision")
                try:
                    src = sources.pdf_source(d["url"], f"protocol:{d['url'].rsplit('/', 1)[-1]}")
                    self.L.add_source(src)
                    if self._scan(src):
                        return
                except Exception as e:
                    self.L.log(self.name, "protocol document unreadable", str(e)[:120], "warn")
        planned = self.L.status("blinding_assessment_planned") == "observed"
        msg = ("a blinding assessment was PLANNED but no result was found: possible selective reporting"
               if planned else "no blinding assessment found anywhere")
        self.L.log(self.name, msg, "switching strategy: unblinding will be imputed from design and labelled as such",
                   "warn" if planned else "decision")
        for k in ("guess_acc_participants", "guess_acc_raters"):
            if k not in self.L.facts:
                self.L.put(unknown(k, self.name, msg))
