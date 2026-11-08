"""Run the whole post-dosing evaluation and write eval/platform/results.md (plus effect_recovery.json).

    python eval/platform/run_eval.py            # about 20 seconds, no API key, no network

Sections
  1. Effect recovery over 20 seeds: naive vs adjusted vs planted truth (and a 200-seed robustness check)
  2. Bias gate accuracy on the labelled question set
  3. End-to-end platform run to day 90: report, sign-off gate, consent filter, export completeness
Everything is SYNTHETIC.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("UNBLIND_OFFLINE", "1")       # deterministic: never call Gemini from the evaluation

from eval.platform import bias_gate_eval, effect_recovery  # noqa: E402

OUT = Path(__file__).resolve().parent


def end_to_end() -> dict:
    from unblind.platform.core import TRIALS
    from unblind.platform.master.orchestrator import Master
    m = Master("EVAL-E2E-" + uuid.uuid4().hex[:6], use_stub_predose=True)
    m.setup()
    withdrawn = m.rec["enrolled"][0]
    withdrawn["consents"]["data_sharing"] = False         # one SYNTHETIC participant without data-sharing consent
    m.module_action("postdose", "ask_question", {"question": "How intense were the visuals during your psilocybin session?",
                                                 "researcher": "eval"})
    early_release = None
    for _ in range(100):
        for a in m.ctx.approvals.pending():
            if a["action"].get("type") not in ("report_signoff", "harmonised_export"):
                m.decide(a["id"], "eval reviewer", "approved")
        if early_release is None and m.rec.get("primary_lock_day") is None:
            early_release = any(q["status"] in ("released", "answered") for q in m.rec["research_questions"])
        m.step(1)
        if m.rec["phase"] == "closed":
            break
    blank = m.module_action("postdose", "sign_off", {"reviewer": "  "})
    status_after_blank = m.rec["report"]["status"]
    m.module_action("postdose", "sign_off", {"reviewer": "eval signatory"})
    exp = next(a for a in m.ctx.approvals.pending() if a["action"]["type"] == "harmonised_export")
    m.decide(exp["id"], "eval data steward", "approved")
    ex = m.rec["exports"]
    text = (TRIALS / ex["files"][0]).read_text(encoding="utf-8")
    leaks = [p for p in m.rec["enrolled"]
             if (p.get("name") and p["name"] in text) or p["id"] in text or (p.get("phone") and p["phone"] in text)]
    with (TRIALS / ex["files"][0]).open(encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    q = m.rec["research_questions"][0]
    return {"module_status": m.module_status, "lock_day": m.rec.get("primary_lock_day"),
            "released_before_lock": bool(early_release), "blank_signoff_refused": not blank["ok"],
            "status_after_blank": status_after_blank, "final_status": m.rec["report"]["status"],
            "signed_by": m.rec["report"].get("signed_by"), "export_rows": ex["n_rows"],
            "withheld_no_consent": ex["n_excluded_no_consent"], "completeness": ex["completeness"],
            "identifier_leaks": len(leaks), "header": header, "question_asked": q["asked"],
            "question_skipped_no_consent": q["skipped_no_consent"],
            "checklist": [(c["item"], c["status"]) for c in m.rec["report"]["checklist"]]}


def e2e_markdown(e: dict) -> str:
    st = ", ".join(f"{k}: {v}" for k, v in e["module_status"].items())
    L = ["### End-to-end platform run to day 90 (SYNTHETIC)", "",
         f"Modules: {st}. With the stub dosing module there are no MADRS outcomes, so the effect section reads "
         "'not estimable'; with the real dosing module merged the same run produces the estimates.", "",
         "| Check | Result |", "|---|---|",
         f"| Primary endpoint locked | day {e['lock_day']} |",
         f"| Researcher question released before the lock | {'YES (bug)' if e['released_before_lock'] else 'no'} |",
         f"| Sign-off with a blank name refused | {'yes' if e['blank_signoff_refused'] else 'NO (bug)'}; status stayed '{e['status_after_blank']}' |",
         f"| Report status after a named sign-off | {e['final_status']} (signed by {e['signed_by']}) |",
         f"| Participant without data-sharing consent | not asked ({e['question_skipped_no_consent']} skipped, {e['question_asked']} asked); "
         f"{e['withheld_no_consent']} of their rows withheld from the export |",
         f"| Names, phone numbers or raw IDs in the export | {e['identifier_leaks']} found |",
         f"| Export rows / field completeness | {e['export_rows']} rows, {e['completeness']}% complete |",
         f"| Export columns | {', '.join(e['header'])} |", "",
         "FDA checklist on this run: " + "; ".join(f"{i} = {s.replace('_', ' ')}" for i, s in e["checklist"]) + "."]
    return "\n".join(L)


def interpretation(r20: dict, r200: dict) -> str:
    p, nb, rc = (r200["scenarios"][k] for k in ("planted", "no_bias", "reverse_causation"))
    small = r200["by_n"]["24"]["within_trial"]
    return "\n".join([
        "### What this means (read before quoting any number)", "",
        f"* **Naive is biased when blinding fails.** In the planted world the reported effect overstates the benefit by "
        f"{-p['reported']['bias']:.1f} points on average (truth 4), and its 95% interval contains the truth only "
        f"{p['reported']['coverage']:.0%} of the time ({r200['n_seeds']} seeds).",
        f"* **The within-trial estimate recovers the truth when its assumption holds.** Bias {p['within_trial']['bias']:+.2f}, "
        f"coverage {p['within_trial']['coverage']:.0%}. With no bias planted it stays close (bias {nb['within_trial']['bias']:+.2f}), "
        "so it does little harm to a clean trial.",
        f"* **It fails under reverse causation, in the direction we warned about.** When guesses follow improvement it "
        f"removes real benefit: bias {rc['within_trial']['bias']:+.2f} points (about half of the true 4), coverage "
        f"{rc['within_trial']['coverage']:.0%}. This is why the report calls the adjusted value a conservative bound.",
        f"* **The cross-trial calibration over-corrects on these trials.** Bias {p['cross_trial']['bias']:+.2f} in the planted "
        f"world and {nb['cross_trial']['bias']:+.2f} with no bias at all. It treats all unblinding as bias, and here people "
        "guess right from side effects even when their belief does not change their score. The calibration is also "
        "SYNTHETIC. We show it for transparency and do not use it as the headline adjusted value when the within-trial "
        "estimate exists.",
        f"* **Small trials cannot use the within-trial method.** With 24 participants it was estimable in "
        f"{small['n_estimable']} of {r200['n_seeds']} simulated trials, because the vault suppresses cells under 5. "
        "The report then says so instead of guessing.",
        "* The headline table uses 20 seeds as planned; the 200-seed run below agrees in direction and size.",
    ])


def robustness(r200: dict) -> str:
    L = [f"### Robustness: {r200['n_seeds']} seeds, n = {r200['n_participants']}", "",
         "| Scenario | Method | Estimable | Bias | RMSE | Coverage |", "|---|---|---|---|---|---|"]
    for sc, rows in r200["scenarios"].items():
        for mth in effect_recovery.METHODS:
            x = rows[mth]
            if x["n_estimable"]:
                L.append(f"| {sc} | {x['label']} | {x['n_estimable']} | {x['bias']:+.2f} | {x['rmse']:.2f} | {x['coverage']:.0%} |")
    return "\n".join(L)


def main() -> None:
    t = time.time()
    r20 = effect_recovery.run(20)
    r200 = effect_recovery.run(200)
    (OUT / "effect_recovery.json").write_text(json.dumps(r200, indent=1))
    gate = bias_gate_eval.run()
    e2e = end_to_end()
    md = "\n\n".join([
        "# Post-dosing evaluation (SYNTHETIC)",
        "Generated by `python eval/platform/run_eval.py` with no API key and no network. Every number below comes from "
        "the SYNTHETIC world simulator (planted truth: 4 MADRS points of benefit, expectancy 3, rater bias 2). "
        "None of it is evidence about real-world performance.",
        interpretation(r20, r200), effect_recovery.markdown(r20), robustness(r200),
        bias_gate_eval.markdown(gate), e2e_markdown(e2e),
        f"_Runtime {time.time() - t:.0f} s._"])
    (OUT / "results.md").write_text(md + "\n", encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
