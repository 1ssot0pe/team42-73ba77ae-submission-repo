"""Bias gate accuracy on the labelled researcher-question set (rules only, no API key).

    python eval/platform/bias_gate_eval.py

The 15 questions and their expected decisions live in unblind/platform/postdose/question_set.py.
Headline safety number: how many questions that should NOT reach participants as written
(expected rewrite or reject) were approved unchanged. Target: 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from unblind.platform.postdose.agents import CHECKS, UNFIXABLE, BiasGateAgent, _hits  # noqa: E402
from unblind.platform.postdose.question_set import QUESTIONS  # noqa: E402

DECISIONS = ["approve", "rewrite", "reject"]


def run() -> dict:
    gate = BiasGateAgent()
    rows, conf = [], {e: {p: 0 for p in DECISIONS} for e in DECISIONS}
    for q in QUESTIONS:
        r = gate.review(q["text"])
        conf[q["expected"]][r["decision"]] += 1
        rows.append({"text": q["text"], "expected": q["expected"], "got": r["decision"], "rewrite": r["rewrite"],
                     "rewrite_clean": (r["rewrite"] is None) or not (_hits(r["rewrite"], CHECKS) or _hits(r["rewrite"], UNFIXABLE))})
    correct = sum(1 for r in rows if r["expected"] == r["got"])
    unsafe_approved = sum(1 for r in rows if r["expected"] != "approve" and r["got"] == "approve")
    return {"n": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 3), "unsafe_approved": unsafe_approved,
            "rewrites_clean": all(r["rewrite_clean"] for r in rows), "confusion": conf, "rows": rows}


def markdown(res: dict) -> str:
    L = [f"### Bias gate on the labelled question set (n = {res['n']}, rules only, no API key)", "",
         f"Accuracy {res['correct']} of {res['n']} ({res['accuracy']:.0%}). Questions that should not reach participants "
         f"as written but were approved: **{res['unsafe_approved']}**. Every proposed rewrite passes all checks: "
         f"{'yes' if res['rewrites_clean'] else 'NO'}.", "",
         "| Expected \\ Got | approve | rewrite | reject |", "|---|---|---|---|"]
    for e in DECISIONS:
        L.append(f"| {e} | " + " | ".join(str(res["confusion"][e][g]) for g in DECISIONS) + " |")
    L += ["", "| Question | Expected | Got | Rewrite |", "|---|---|---|---|"]
    L += [f"| {r['text']} | {r['expected']} | {r['got']} | {r['rewrite'] or ''} |" for r in res["rows"]]
    L += ["", "Caveat: the labels and the rules were written by the same team, so this is a regression check, not an "
              "independent test. An independent labelled set from an ethics reviewer is the next step."]
    return "\n".join(L)


if __name__ == "__main__":
    print(markdown(run()))
