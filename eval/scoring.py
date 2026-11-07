"""Field-level scoring against a hand-verified gold file (shared by extraction_eval
and baseline_vs_pipeline).

Gold file columns: nct, field, gold_value, quote, source_url, verified_by

* gold_value "NR" means a careful human found the value NOT REPORTED in any
  source the pipeline could reach. The right answer is then to abstain.
* Rows with an empty verified_by, or a verified_by starting with "EXAMPLE",
  are skipped: the gold set must be human-verified.
* Numbers are compared as reported in the source (same units and sign as the
  paper or registry, e.g. a MADRS mean difference of -6.2).
"""
from __future__ import annotations

import csv
import math
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

FIELDS = ["effect_est", "effect_lo", "effect_hi", "comparator_type", "rater_placement",
          "guess_acc_participants", "guess_acc_raters", "prior_exposure"]
PROPORTION_FIELDS = {"guess_acc_participants", "guess_acc_raters", "prior_exposure"}
EFFECT_FIELDS = {"effect_est", "effect_lo", "effect_hi"}
CATEGORICAL_FIELDS = {"comparator_type", "rater_placement"}
TOL = {**{f: 0.02 for f in PROPORTION_FIELDS}, **{f: 0.05 for f in EFFECT_FIELDS}}
GOLD_HEADER = ["nct", "field", "gold_value", "quote", "source_url", "verified_by"]
NR = {"nr", "not reported", "unknown", "none", "na", "n/a"}


def load_gold(path: Path) -> Tuple[List[dict], List[str]]:
    rows, problems = [], []
    with path.open(newline="") as f:
        rd = csv.DictReader(f)
        missing = [c for c in GOLD_HEADER if c not in (rd.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: missing columns {missing}; expected {GOLD_HEADER}")
        for i, r in enumerate(rd, start=2):
            r = {k: (v or "").strip() for k, v in r.items()}
            vb = r["verified_by"]
            if not vb or vb.upper().startswith("EXAMPLE"):
                problems.append(f"line {i}: skipped ({'no verified_by' if not vb else 'EXAMPLE row'})")
                continue
            if r["field"] not in FIELDS:
                problems.append(f"line {i}: unknown field {r['field']!r} skipped")
                continue
            if r["gold_value"] == "":
                problems.append(f"line {i}: empty gold_value skipped (use NR for 'not reported')")
                continue
            if r["gold_value"].lower() not in NR and not r["quote"]:
                problems.append(f"line {i}: gold value without a supporting quote (kept, but please add one)")
            rows.append(r)
    return rows, problems


def is_nr(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in NR)


def match(field: str, pred, gold: str) -> bool:
    """pred and gold are both non-missing."""
    if field in CATEGORICAL_FIELDS:
        return str(pred).strip().lower() == gold.strip().lower()
    try:
        p, g = float(pred), float(gold)
    except (TypeError, ValueError):
        return False
    if field in PROPORTION_FIELDS:
        if p > 1.0 + 1e-9:            # tolerate a percentage given where a proportion was asked
            p = p / 100.0
        if g > 1.0 + 1e-9:
            g = g / 100.0
    return abs(p - g) <= TOL[field] + 1e-9


def report_predictions(report: dict) -> Dict[str, Tuple[Optional[object], str]]:
    """Map a pipeline report's facts to {field: (value or None, audit)}."""
    facts = report.get("facts", {}) or {}

    def val(name):
        f = facts.get(name)
        if not f or f.get("status") == "unknown" or f.get("value") is None:
            return None, (f or {}).get("audit", "") or ""
        return f["value"], f.get("audit", "") or ""

    out = {}
    eff, eaudit = val("effect")
    for fld, key in (("effect_est", "est"), ("effect_lo", "lo"), ("effect_hi", "hi")):
        v = eff.get(key) if isinstance(eff, dict) else None
        # a failed audit is reported on every effect field; a pass only where a number was given
        out[fld] = (v, eaudit if (v is not None or eaudit.startswith("fail")) else "")
    for fld in ("comparator_type", "rater_placement", "guess_acc_participants", "guess_acc_raters", "prior_exposure"):
        out[fld] = val(fld)
    return out


def score_rows(gold: List[dict], preds: Dict[str, Dict[str, Tuple[Optional[object], str]]]) -> List[dict]:
    """One row per gold cell with the outcome class.

    outcome is one of: correct, correct_abstain, wrong, miss (abstained but gold has a value),
    false_positive (answered but gold is NR), no_run (no prediction for this trial)."""
    out = []
    for g in gold:
        nct, fld, gv = g["nct"], g["field"], g["gold_value"]
        if nct not in preds:
            out.append({**g, "pred": "", "audit": "", "outcome": "no_run"})
            continue
        pv, audit = preds[nct].get(fld, (None, ""))
        if is_nr(gv):
            outcome = "correct_abstain" if pv is None else "false_positive"
        elif pv is None:
            outcome = "miss"
        else:
            outcome = "correct" if match(fld, pv, gv) else "wrong"
        out.append({**g, "pred": "" if pv is None else pv, "audit": audit, "outcome": outcome})
    return out


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def summarise(scored: Iterable[dict]) -> "OrderedDict[str, dict]":
    by = OrderedDict((f, []) for f in FIELDS)
    rows = [r for r in scored if r["outcome"] != "no_run"]
    for r in rows:
        by[r["field"]].append(r)
    by["ALL FIELDS"] = rows
    out = OrderedDict()
    for f, rs in by.items():
        if not rs:
            continue
        n = len(rs)
        c = sum(r["outcome"] in ("correct", "correct_abstain") for r in rs)
        answered = [r for r in rs if r["outcome"] in ("correct", "wrong", "false_positive")]
        has_gold = [r for r in rs if not is_nr(r["gold_value"])]
        unknowns = [r for r in rs if r["outcome"] in ("miss", "correct_abstain")]
        audited = [r for r in rs if str(r.get("audit", "")).startswith(("pass", "fail"))]
        lo, hi = wilson(c, n)
        out[f] = {
            "n": n, "accuracy": c / n, "acc_lo": lo, "acc_hi": hi,
            "coverage": len(answered) / n,
            "precision": (sum(r["outcome"] == "correct" for r in answered) / len(answered)) if answered else float("nan"),
            "recall": (sum(r["outcome"] == "correct" for r in has_gold) / len(has_gold)) if has_gold else float("nan"),
            "wrong": sum(r["outcome"] == "wrong" for r in rs),
            "false_positive": sum(r["outcome"] == "false_positive" for r in rs),
            "n_unknown": len(unknowns),
            "unknown_miss_share": (sum(r["outcome"] == "miss" for r in unknowns) / len(unknowns)) if unknowns else float("nan"),
            "audit_pass": (sum(str(r["audit"]).startswith("pass") for r in audited) / len(audited)) if audited else float("nan"),
            "n_audited": len(audited),
        }
    return out


def pct(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}%"


def summary_table(S: "OrderedDict[str, dict]") -> Tuple[List[str], List[List[str]]]:
    header = ["field", "n", "accuracy (95% Wilson)", "coverage", "precision", "recall", "wrong", "answered when NR",
              "unknowns", "of which gold had a value (miss)", "audit pass (n audited)"]
    rows = []
    for f, d in S.items():
        rows.append([f"**{f}**" if f == "ALL FIELDS" else f, d["n"],
                     f"{pct(d['accuracy'])} ({pct(d['acc_lo'])} to {pct(d['acc_hi'])})",
                     pct(d["coverage"]), pct(d["precision"]), pct(d["recall"]), d["wrong"], d["false_positive"],
                     d["n_unknown"], pct(d["unknown_miss_share"]), f"{pct(d['audit_pass'])} ({d['n_audited']})"])
    return header, rows


def write_rows_csv(path: Path, scored: List[dict]) -> None:
    cols = ["nct", "field", "gold_value", "pred", "outcome", "audit", "quote", "source_url", "verified_by"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in scored:
            w.writerow(r)
