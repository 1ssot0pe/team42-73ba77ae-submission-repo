"""Clients for the public sources the agents may use, each returning a Source
with plain text the auditor can verify quotes against, plus its licence.

ClinicalTrials.gov API v2   https://clinicaltrials.gov/api/v2/studies
Europe PMC REST            https://www.ebi.ac.uk/europepmc/webservices/rest/
Protocol PDFs              https://cdn.clinicaltrials.gov/large-docs/<last2>/<NCT>/<file>
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from . import net
from .ledger import Source

CTGOV = "https://clinicaltrials.gov/api/v2/studies"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

LICENCE_CTGOV = ("ClinicalTrials.gov (US NLM). Registry content is generally public domain; "
                 "see clinicaltrials.gov/about-site/terms-conditions")
LICENCE_CTGOV_DOC = ("Document posted on ClinicalTrials.gov by the sponsor. Used for "
                     "fact extraction with citation; check sponsor copyright before redistribution")


# --------------------------------------------------------------------------
# ClinicalTrials.gov
# --------------------------------------------------------------------------
def ctgov_study(nct: str) -> Dict[str, Any]:
    return json.loads(net.get(f"{CTGOV}/{nct}"))


def ctgov_search(term: str, page_size: int = 5, extra: str = "") -> List[Dict[str, Any]]:
    url = f"{CTGOV}?query.term={quote_plus(term)}&pageSize={page_size}{extra}"
    data = json.loads(net.get(url))
    return data.get("studies", [])


def _g(d: Any, *path, default=None):
    for p in path:
        if isinstance(d, dict):
            d = d.get(p)
        elif isinstance(d, list) and isinstance(p, int) and p < len(d):
            d = d[p]
        else:
            return default
    return d if d is not None else default


def study_summary(study: Dict[str, Any]) -> Dict[str, Any]:
    ps = study.get("protocolSection", {})
    return {
        "nct": _g(ps, "identificationModule", "nctId", default=""),
        "title": _g(ps, "identificationModule", "briefTitle", default=""),
        "official_title": _g(ps, "identificationModule", "officialTitle", default=""),
        "sponsor": _g(ps, "sponsorCollaboratorsModule", "leadSponsor", "name", default=""),
        "status": _g(ps, "statusModule", "overallStatus", default=""),
        "start": _g(ps, "statusModule", "startDateStruct", "date", default=""),
        "phases": _g(ps, "designModule", "phases", default=[]),
        "allocation": _g(ps, "designModule", "designInfo", "allocation", default=""),
        "masking": _g(ps, "designModule", "designInfo", "maskingInfo", "masking", default=""),
        "who_masked": _g(ps, "designModule", "designInfo", "maskingInfo", "whoMasked", default=[]),
        "enrollment": _g(ps, "designModule", "enrollmentInfo", "count"),
        "conditions": _g(ps, "conditionsModule", "conditions", default=[]),
        "interventions": [i.get("name", "") for i in _g(ps, "armsInterventionsModule", "interventions", default=[])],
        "arms": _g(ps, "armsInterventionsModule", "armGroups", default=[]),
        "primary_outcomes": _g(ps, "outcomesModule", "primaryOutcomes", default=[]),
        "has_results": bool(study.get("hasResults")),
        "large_docs": _g(study, "documentSection", "largeDocumentModule", "largeDocs", default=[]),
    }


def registry_source(study: Dict[str, Any]) -> Source:
    """Render the registry record (protocol part only) as auditable text."""
    s = study_summary(study)
    ps = study.get("protocolSection", {})
    lines = [f"Title: {s['title']}", f"Official title: {s['official_title']}",
             f"Sponsor: {s['sponsor']}", f"Status: {s['status']}",
             f"Phases: {', '.join(s['phases'])}", f"Allocation: {s['allocation']}",
             f"Masking: {s['masking']} ({', '.join(s['who_masked'])})",
             f"Enrollment: {s['enrollment']}", f"Conditions: {', '.join(s['conditions'])}"]
    for a in s["arms"]:
        lines.append(f"Arm: {a.get('label','')} [{a.get('type','')}]: {a.get('description','')}")
    for i in _g(ps, "armsInterventionsModule", "interventions", default=[]):
        lines.append(f"Intervention: {i.get('name','')} [{i.get('type','')}]: {i.get('description','')}")
    for o in s["primary_outcomes"]:
        lines.append(f"Primary outcome: {o.get('measure','')}. {o.get('description','')} Time frame: {o.get('timeFrame','')}")
    desc = _g(ps, "descriptionModule", "detailedDescription", default="") or _g(ps, "descriptionModule", "briefSummary", default="")
    if desc:
        lines.append(f"Description: {desc}")
    elig = _g(ps, "eligibilityModule", "eligibilityCriteria", default="")
    if elig:
        lines.append(f"Eligibility: {elig}")
    text = "\n".join(lines)
    return Source(id=f"ctgov:{s['nct']}", kind="registry",
                  url=f"https://clinicaltrials.gov/study/{s['nct']}",
                  licence=LICENCE_CTGOV, title=s["title"], text=text,
                  sections={"registry-protocol": text})


def registry_results_source(study: Dict[str, Any]) -> Optional[Source]:
    """Render posted results (if any) as auditable text: one line per analysis."""
    rs = study.get("resultsSection")
    if not rs:
        return None
    nct = _g(study, "protocolSection", "identificationModule", "nctId", default="")
    lines: List[str] = []
    groups = {}
    for om in _g(rs, "outcomeMeasuresModule", "outcomeMeasures", default=[]):
        for g in om.get("groups", []):
            groups[g.get("id")] = g.get("title", g.get("id"))
        head = f"Outcome [{om.get('type','')}]: {om.get('title','')}. Time frame: {om.get('timeFrame','')}. Units: {om.get('unitOfMeasure','')}"
        lines.append(head)
        for den in om.get("denoms", []):
            for c in den.get("counts", []):
                lines.append(f"  N analysed {groups.get(c.get('groupId'), c.get('groupId'))}: {c.get('value')}")
        for cl in om.get("classes", []):
            for cat in cl.get("categories", []):
                for m in cat.get("measurements", []):
                    lines.append(f"  {groups.get(m.get('groupId'), m.get('groupId'))}: {om.get('paramType','')} {m.get('value')} "
                                 f"(spread {m.get('spread','')}, {om.get('dispersionType','')})")
        for an in om.get("analyses", []):
            gs = " vs ".join(groups.get(g, g) for g in an.get("groupIds", []))
            lines.append(f"  Analysis ({gs}): {an.get('paramType','')} = {an.get('paramValue','')} "
                         f"({an.get('ciPctValue','95')}% CI {an.get('ciLowerLimit','')} to {an.get('ciUpperLimit','')}); "
                         f"p = {an.get('pValue','')}; method {an.get('statisticalMethod','')}")
    text = "\n".join(lines)
    return Source(id=f"ctgov-results:{nct}", kind="registry-results",
                  url=f"https://clinicaltrials.gov/study/{nct}?tab=results",
                  licence=LICENCE_CTGOV, title="Posted results", text=text,
                  sections={"results": text})


def protocol_pdf_urls(study: Dict[str, Any]) -> List[Dict[str, str]]:
    s = study_summary(study)
    nct = s["nct"]
    out = []
    for d in s["large_docs"]:
        fn = d.get("filename")
        if not fn or not nct:
            continue
        out.append({"label": d.get("label") or d.get("typeAbbrev", "document"),
                    "url": f"https://cdn.clinicaltrials.gov/large-docs/{nct[-2:]}/{nct}/{fn}",
                    "has_protocol": str(d.get("hasProtocol", "")), "has_sap": str(d.get("hasSap", ""))})
    # protocol first, then SAP
    out.sort(key=lambda d: (d["has_protocol"] != "True", d["has_sap"] != "True"))
    return out


def pdf_source(url: str, src_id: str, kind: str = "protocol", max_pages: int = 150) -> Source:
    from pypdf import PdfReader  # lazy import
    data = net.get(url, binary=True)
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n".join(pages)
    return Source(id=src_id, kind=kind, url=url, licence=LICENCE_CTGOV_DOC,
                  title=url.rsplit("/", 1)[-1], text=text, sections={kind: text})


# --------------------------------------------------------------------------
# Europe PMC
# --------------------------------------------------------------------------
def epmc_search(query: str, page_size: int = 8) -> List[Dict[str, Any]]:
    url = f"{EPMC}/search?query={quote_plus(query)}&format=json&resultType=core&pageSize={page_size}"
    data = json.loads(net.get(url))
    return _g(data, "resultList", "result", default=[]) or []


def _itertext(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_jats(xml_text: str) -> Dict[str, Any]:
    """Return {'title', 'licence', 'sections': {title: text}, 'supplements': [hrefs]}."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out: Dict[str, Any] = {"title": "", "licence": "", "sections": {}, "supplements": []}
    for el in root.iter():
        t = _local(el.tag)
        if t == "article-title" and not out["title"]:
            out["title"] = _itertext(el)
        elif t == "license" and not out["licence"]:
            href = el.attrib.get("{http://www.w3.org/1999/xlink}href", "")
            out["licence"] = (_itertext(el)[:200] + (f" ({href})" if href else "")).strip()
        elif t == "abstract" and "abstract" not in out["sections"]:
            out["sections"]["abstract"] = _itertext(el)
        elif t == "supplementary-material":
            href = el.attrib.get("{http://www.w3.org/1999/xlink}href", "")
            cap = _itertext(el)[:200]
            out["supplements"].append({"href": href, "caption": cap})
    body = None
    for el in root.iter():
        if _local(el.tag) == "body":
            body = el
            break

    def walk(sec, prefix=""):
        title_el = next((c for c in sec if _local(c.tag) == "title"), None)
        title = (prefix + " / " if prefix else "") + (_itertext(title_el) if title_el is not None else "untitled")
        own = []
        for c in sec:
            ct = _local(c.tag)
            if ct == "sec":
                walk(c, title)
            elif ct == "title":
                continue
            elif ct == "table-wrap":
                own.append(_table_text(c))
            else:
                own.append(_itertext(c))
        txt = " ".join(x for x in own if x).strip()
        if txt:
            key = title
            n = 2
            while key in out["sections"]:
                key = f"{title} ({n})"; n += 1
            out["sections"][key] = txt

    if body is not None:
        for c in body:
            if _local(c.tag) == "sec":
                walk(c)
            elif _local(c.tag) == "table-wrap":
                out["sections"][f"table {len(out['sections'])}"] = _table_text(c)
    # tables that live in floats-group / back matter
    for el in root.iter():
        if _local(el.tag) in ("floats-group", "app"):
            for tw in el.iter():
                if _local(tw.tag) == "table-wrap":
                    out["sections"][f"table {len(out['sections'])}"] = _table_text(tw)
    return out


def _table_text(tw) -> str:
    cap = ""
    rows = []
    for el in tw.iter():
        t = _local(el.tag)
        if t in ("caption", "label") and not cap:
            cap = _itertext(el)
        elif t == "tr":
            cells = [_itertext(c) for c in el if _local(c.tag) in ("td", "th")]
            rows.append(" | ".join(cells))
    return (f"Table: {cap}\n" if cap else "Table:\n") + "\n".join(rows)


def epmc_fulltext_source(hit: Dict[str, Any]) -> Source:
    pmcid = hit.get("pmcid")
    xml_text = net.get(f"{EPMC}/{pmcid}/fullTextXML")
    parsed = parse_jats(xml_text)
    lic = parsed["licence"] or (hit.get("license") or "Europe PMC open-access subset; licence not stated in XML")
    text = "\n\n".join(f"## {k}\n{v}" for k, v in parsed["sections"].items())
    src = Source(id=f"pmc:{pmcid}", kind="paper", url=f"https://europepmc.org/article/PMC/{pmcid}",
                 licence=lic, title=parsed["title"] or hit.get("title", ""), text=text,
                 sections=parsed["sections"])
    src.sections["_supplements"] = json.dumps(parsed["supplements"])
    return src


def epmc_abstract_source(hit: Dict[str, Any]) -> Source:
    pid = hit.get("pmid") or hit.get("id")
    abst = re.sub(r"<[^>]+>", " ", hit.get("abstractText", "") or "")
    abst = re.sub(r"\s+", " ", abst).strip()
    return Source(id=f"pmid:{pid}", kind="paper-abstract",
                  url=f"https://europepmc.org/article/MED/{pid}",
                  licence="Abstract via Europe PMC; publisher copyright, used for fact extraction with citation",
                  title=hit.get("title", ""), text=abst, sections={"abstract": abst})


def epmc_supplement_sources(pmcid: str, max_files: int = 6) -> List[Source]:
    """Europe PMC serves supplementary files for OA articles as a zip."""
    data = net.get(f"{EPMC}/{pmcid}/supplementaryFiles", binary=True)
    out: List[Source] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return out
    for name in zf.namelist()[: max_files * 3]:
        low = name.lower()
        try:
            if low.endswith(".pdf"):
                from pypdf import PdfReader
                r = PdfReader(io.BytesIO(zf.read(name)))
                text = "\n".join((p.extract_text() or "") for p in r.pages[:80])
            elif low.endswith((".txt", ".csv", ".tsv", ".xml", ".htm", ".html")):
                text = zf.read(name).decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", text)
            elif low.endswith(".docx"):
                x = zipfile.ZipFile(io.BytesIO(zf.read(name))).read("word/document.xml").decode("utf-8", "replace")
                text = re.sub(r"<[^>]+>", " ", x)
            else:
                continue
        except Exception:
            continue
        text = re.sub(r"[ \t]+", " ", text)
        out.append(Source(id=f"supp:{pmcid}:{name}", kind="supplement",
                          url=f"https://europepmc.org/article/PMC/{pmcid}#supplementary-material",
                          licence="Supplement to an Europe PMC open-access article; same licence as article",
                          title=name, text=text, sections={"supplement": text}))
        if len(out) >= max_files:
            break
    return out
