"""Human sign-off gate.

Nothing leaves UNBLIND as a recommendation, and nothing enters the real
calibration corpus, without a named reviewer approving it. Decisions are
appended to data/signoffs.jsonl with the report digest, so any later change
to the report is detectable.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Optional

from .pipeline import Report

DATA = Path(__file__).resolve().parent.parent / "data"
LOG = DATA / "signoffs.jsonl"
CORPUS = DATA / "calibration_real.csv"
CORPUS_FIELDS = ["trial_id", "provenance", "drug", "comparator_type", "central", "prior_exposure",
                 "g", "se_g", "u", "u_sd", "u_status", "approved", "reviewer", "digest"]


def record(report: Report, reviewer: str, decision: str, comment: str = "",
           add_to_corpus: bool = False) -> dict:
    if not reviewer.strip():
        raise ValueError("a named reviewer is required")
    if decision not in ("approve", "reject", "needs-changes"):
        raise ValueError("decision must be approve | reject | needs-changes")
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "reviewer": reviewer.strip(), "decision": decision,
             "comment": comment, "nct": report.nct, "digest": report.digest(),
             "calibration": report.calibration, "added_to_corpus": False}
    if decision == "approve" and add_to_corpus:
        entry["added_to_corpus"] = _add_row(report, reviewer)
    DATA.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _fact(report: Report, k: str):
    f = report.facts.get(k) or {}
    return None if f.get("status") == "unknown" else f.get("value")


def _add_row(report: Report, reviewer: str) -> bool:
    g, se = _fact(report, "g"), _fact(report, "se_g")
    if g is None or se is None or not report.nct:
        return False
    if report.nct.startswith("NCT999999") or not report.in_domain:
        return False   # invented test fixtures and out-of-domain trials never enter the corpus
    u_status = (report.facts.get("u") or {}).get("status")
    row = {"trial_id": report.nct, "provenance": "REAL (pipeline-extracted, human-approved)",
           "drug": "+".join(report.drug), "comparator_type": _fact(report, "comparator_type") or "",
           "central": int(_fact(report, "rater_placement") == "central_remote"),
           "prior_exposure": _fact(report, "prior_exposure") if _fact(report, "prior_exposure") is not None else "",
           "g": g, "se_g": se,
           "u": _fact(report, "u") if u_status == "derived" else "",
           "u_sd": _fact(report, "u_sd") if u_status == "derived" else "",
           "u_status": "observed" if u_status == "derived" else "missing",
           "approved": "yes", "reviewer": reviewer, "digest": report.digest()}
    new = not CORPUS.exists()
    rows = []
    if not new:
        rows = [r for r in csv.DictReader(CORPUS.open()) if r.get("trial_id") != report.nct]
    rows.append(row)
    with CORPUS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CORPUS_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return True
