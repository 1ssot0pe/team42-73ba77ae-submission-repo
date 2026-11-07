"""Field-level accuracy of the UNBLIND agent pipeline against a hand-verified gold set.

    python eval/extraction_eval.py               # real: needs data/gold.csv (+ network or a warm cache)
    python eval/extraction_eval.py --fixtures    # offline end-to-end check on the INVENTED test trials
    python eval/extraction_eval.py --rerun       # ignore cached pipeline runs in eval/results/runs/

Gold file: data/gold.csv with columns nct, field, gold_value, quote, source_url, verified_by
(see eval/scoring.py for the rules, including gold_value "NR" = not reported).

Reports per field: accuracy (with a Wilson 95% interval, because n is small),
coverage (share answered, i.e. not 'unknown'), precision, recall, audit pass
rate, and how many of the agent's 'unknown' answers were honest abstentions
(gold also NR) versus misses (gold had a value).
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval import scoring  # noqa: E402
from eval.common import GOLD, GOLD_TEMPLATE, RESULTS, get_run, md_table, use_fixtures  # noqa: E402

# ---------------------------------------------------------------------------
# gold rows for the INVENTED fixture trials, read off tests/fixtures.py by hand
# ---------------------------------------------------------------------------
FX_PAPER = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9999901/fullTextXML (FIXTURE, invented)"
FX_SUPP = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9999901/supplementaryFiles (FIXTURE, invented)"
FX_REG1 = "https://clinicaltrials.gov/study/NCT99999901 (FIXTURE, invented)"
FX_REG2 = "https://clinicaltrials.gov/study/NCT99999902 (FIXTURE, invented)"
FX_BY = "fixture-truth: tests/fixtures.py (invented trial, not real data)"
PRIMARY_Q = ("The primary endpoint, the between-group difference in MADRS change from baseline at week 6 in the "
             "intention-to-treat population, was -6.2 (95% CI -9.4 to -3.0).")
FIXTURE_GOLD = [
    ("NCT99999901", "effect_est", "-6.2", PRIMARY_Q, FX_PAPER),
    ("NCT99999901", "effect_lo", "-9.4", PRIMARY_Q, FX_PAPER),
    ("NCT99999901", "effect_hi", "-3.0", PRIMARY_Q, FX_PAPER),
    ("NCT99999901", "comparator_type", "low_dose_same_drug",
     "Participants were randomly assigned to psilocybin 25 mg (n = 50) or psilocybin 1 mg (n = 49).", FX_PAPER),
    ("NCT99999901", "rater_placement", "central_remote",
     "Ratings were performed by central blinded raters via videoconference who were not present at dosing sessions.", FX_PAPER),
    ("NCT99999901", "guess_acc_participants", "0.78",
     "At the end of the study, 78% of participants correctly guessed their treatment allocation.", FX_SUPP),
    ("NCT99999901", "guess_acc_raters", "0.55", "Raters correctly guessed allocation in 55% of cases.", FX_SUPP),
    ("NCT99999901", "prior_exposure", "0.34", "Overall, 34% of participants reported prior psychedelic use.", FX_PAPER),
    # NCT99999902: registry + protocol only. No results anywhere.
    ("NCT99999902", "effect_est", "NR", "", FX_REG2),
    ("NCT99999902", "effect_lo", "NR", "", FX_REG2),
    ("NCT99999902", "effect_hi", "NR", "", FX_REG2),
    ("NCT99999902", "comparator_type", "inert_placebo", "Inactive placebo with therapy", FX_REG2),
    ("NCT99999902", "rater_placement", "blinded_unspecified", "Masking: QUADRUPLE (PARTICIPANT, OUTCOMES_ASSESSOR)", FX_REG2),
    ("NCT99999902", "guess_acc_participants", "NR", "", FX_REG2),
    ("NCT99999902", "guess_acc_raters", "NR", "", FX_REG2),
    # Judgement call, stated openly: excluding MDMA use "in the last 5 years" does not make the sample
    # psychedelic-naive, so a careful reader records the proportion as not reported.
    ("NCT99999902", "prior_exposure", "NR", "Prior use of MDMA in the last 5 years", FX_REG2),
]


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(scoring.GOLD_HEADER)
        w.writerow(["NCT99999901", "effect_est", "-6.2", PRIMARY_Q, FX_PAPER,
                    "EXAMPLE (invented fixture trial; delete this row, put your initials here for real rows)"])
        w.writerow(["NCT99999901", "guess_acc_participants", "0.78",
                    "At the end of the study, 78% of participants correctly guessed their treatment allocation.", FX_SUPP,
                    "EXAMPLE (invented fixture trial; delete this row, put your initials here for real rows)"])


def write_fixture_gold(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(scoring.GOLD_HEADER)
        for nct, fld, gv, q, url in FIXTURE_GOLD:
            w.writerow([nct, fld, gv, q, url, FX_BY])


# ---------------------------------------------------------------------------
def evaluate(gold_path: Path, out_md: Path, out_csv: Path, runs_dir: Path, rerun: bool, banner: str) -> "OrderedDict":
    gold, problems = scoring.load_gold(gold_path)
    for p in problems:
        print("gold:", p)
    if not gold:
        print(f"No usable (human-verified) rows in {gold_path}. Nothing to score.")
        return OrderedDict()
    ncts = list(dict.fromkeys(g["nct"] for g in gold))
    preds: Dict[str, Dict] = {}
    for nct in ncts:
        print(f"running pipeline on {nct} ...", flush=True)
        try:
            rep, _ = get_run(nct, rerun=rerun, base=runs_dir)
        except Exception as e:  # one trial must not sink the eval
            print(f"   pipeline failed on {nct}: {e}")
            continue
        preds[nct] = scoring.report_predictions(rep)
    scored = scoring.score_rows(gold, preds)
    S = scoring.summarise(scored)
    header, rows = scoring.summary_table(S)
    scoring.write_rows_csv(out_csv, scored)

    no_run = [r["nct"] for r in scored if r["outcome"] == "no_run"]
    detail = md_table(["nct", "field", "gold", "agent", "outcome", "audit"],
                      [[r["nct"], r["field"], r["gold_value"], r["pred"] if r["pred"] != "" else "unknown",
                        r["outcome"], r["audit"] or ""] for r in scored if r["outcome"] != "no_run"])
    md = f"""# Extraction accuracy: agent pipeline vs hand-verified gold

{banner}

Gold file: `{gold_path.relative_to(ROOT) if gold_path.is_relative_to(ROOT) else gold_path}`, {len(gold)} verified cells over {len(ncts)} trial(s).
Numeric fields match within ±0.02 (proportions) or ±0.05 (effects, in the units reported by the source);
categorical fields must match exactly. `NR` in the gold means not reported, so the right answer is to abstain.

{md_table(header, rows)}

How to read it
* **accuracy** counts a correct value or a correct abstention. The Wilson interval is wide because n is small.
* **coverage** is the share of cells where the agent gave a value instead of `unknown`.
* **answered when NR** is the dangerous error: a value where a careful human found none.
* **of which gold had a value (miss)**: of the agent's `unknown` answers, the share that were misses rather than
  honest abstentions.
* **audit pass** is the share of quote-audited facts that passed the verbatim check (audit.py). Facts derived in
  code without a quote are not audited.

## Cell by cell

{detail}
{"" if not no_run else chr(10) + "Trials with no pipeline run: " + ", ".join(sorted(set(no_run)))}
"""
    out_md.write_text(md)
    print(md_table(header, rows))
    print(f"\nwrote {out_md} and {out_csv}")
    return S


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Field-level extraction accuracy against data/gold.csv")
    ap.add_argument("--fixtures", action="store_true", help="offline end-to-end check on the invented fixture trials")
    ap.add_argument("--gold", default=str(GOLD))
    ap.add_argument("--rerun", action="store_true", help="re-run the pipeline even if a cached run exists")
    a = ap.parse_args(argv)
    RESULTS.mkdir(parents=True, exist_ok=True)

    if a.fixtures:
        cache = use_fixtures()
        gold_path = RESULTS / "fixture_gold.csv"
        write_fixture_gold(gold_path)
        print(f"fixture mode: offline, cache {cache}, gold {gold_path}")
        evaluate(gold_path, RESULTS / "extraction_eval_fixtures.md", RESULTS / "extraction_eval_fixtures_rows.csv",
                 Path(cache) / "runs", rerun=True,
                 banner="**FIXTURE RUN. Both trials are INVENTED test fixtures (tests/fixtures.py). This checks that the "
                        "evaluation runs end to end and that the scorer behaves; it says nothing about accuracy on real "
                        "papers.** Offline mode, no Gemini, so these are the deterministic rule extractors.")
        return 0

    gold_path = Path(a.gold)
    if not gold_path.exists():
        write_template(GOLD_TEMPLATE)
        print(f"{gold_path} not found.\n"
              f"Wrote a template to {GOLD_TEMPLATE} (header + 2 EXAMPLE rows from the invented fixture NCT99999901).\n"
              "To run the real evaluation: copy it to data/gold.csv, delete the EXAMPLE rows, and add one row per\n"
              "(trial, field) that a human has checked against the paper/registry, with the verbatim quote, the URL,\n"
              "and the checker's initials in verified_by. Use gold_value NR when the value is genuinely not reported.\n"
              "Tip: python eval/extraction_eval.py --fixtures runs the whole thing offline on invented trials.")
        return 0
    evaluate(gold_path, RESULTS / "extraction_eval.md", RESULTS / "extraction_eval_rows.csv", RESULTS / "runs",
             rerun=a.rerun,
             banner="Real trials. Gemini " + ("ON" if __import__("unblind.llm", fromlist=["x"]).available() else
                                              "OFF (deterministic rules only)") + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
