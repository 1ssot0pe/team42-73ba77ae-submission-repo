"""Offline tests for the post-dosing module (no API key, no network, SYNTHETIC data only).

Plan section 10: no question is released before the primary lock; leading or unblinding
questions are rewritten or rejected; non-consenting participants are never asked or
exported; the export has no names or phone numbers; the report cannot be finalised
without a named sign-off. Plus contract checks.
"""
import json
import tempfile
import uuid
from pathlib import Path

import pytest

from unblind.platform.core import TRIALS
from unblind.platform.master.orchestrator import Master
from unblind.platform.postdose.agents import CHECKS, UNFIXABLE, BiasGateAgent, _hits
from unblind.platform.postdose.question_set import QUESTIONS

LEADING_Q = "How intense were the visuals during your psilocybin session?"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("UNBLIND_OFFLINE", "1")          # rules only: deterministic even if a teammate has a key set


def tid():
    return "TEST-PD-" + uuid.uuid4().hex[:6]


def approve_all_but(m, keep=("report_signoff", "harmonised_export")):
    for a in m.ctx.approvals.pending():
        if a["action"].get("type") not in keep:
            m.decide(a["id"], "Test Reviewer", "approved")


def run_to_close(m, approve=True):
    for _ in range(100):
        if approve:
            approve_all_but(m)
        m.step(1)
        if m.rec["phase"] == "closed":
            break


def new_master(consent_off=0):
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    for p in m.rec["enrolled"][:consent_off]:
        p["consents"]["data_sharing"] = False
    return m


# --------------------------------------------------------------------------- contract
def test_real_module_replaces_stub():
    m = Master(tid(), use_stub_predose=True)
    assert m.module_status["postdose"] == "real"
    v = m.module_view("postdose")
    assert v["module"] == "postdose" and v["title"]
    assert set(v) <= {"module", "title", "kpis", "cards", "charts", "tables", "forms", "status"}
    assert any("SYNTHETIC" in c["title"] or "SYNTHETIC" in c["body"] for c in v["cards"])


def test_kpis_have_contract_shape():
    m = new_master()
    run_to_close(m)
    for k in m.modules["postdose"].kpis(m.rec):
        assert {"label", "value", "baseline", "unit", "note", "bottleneck_id"} <= set(k)


def test_record_never_contains_allocation_after_close():
    m = new_master()
    run_to_close(m)
    assert '"arm"' not in json.dumps(m.rec, default=str)


# --------------------------------------------------------------------------- bias gate
def test_gate_matches_every_label_in_the_question_set():
    gate = BiasGateAgent()
    for q in QUESTIONS:
        assert gate.review(q["text"])["decision"] == q["expected"], q["text"]


def test_leading_or_unblinding_questions_are_never_approved_as_written():
    gate = BiasGateAgent()
    for q in [q for q in QUESTIONS if q["check"] != "none"]:
        r = gate.review(q["text"])
        assert r["decision"] in ("rewrite", "reject"), q["text"]
        assert r["reasons"], "every rewrite or rejection must give a reason"
        if r["decision"] == "rewrite":
            assert not _hits(r["rewrite"], CHECKS) and not _hits(r["rewrite"], UNFIXABLE), r["rewrite"]


def test_rejected_question_is_logged_and_reported_to_master():
    m = new_master()
    res = m.module_action("postdose", "ask_question", {"question": "Have you had any thoughts of suicide since the session?"})
    assert res["decision"] == "reject"
    assert any(x["kind"] == "question_rejected" and x["to"] == "master" for x in m.rec["messages"])
    assert not m.ctx.approvals.pending("postdose"), "a rejected question must not reach the ethics queue"


def test_no_question_is_released_before_the_primary_lock():
    m = new_master()
    m.module_action("postdose", "ask_question", {"question": LEADING_Q, "researcher": "Dr Test"})
    q = m.rec["research_questions"][0]
    assert q["status"] == "awaiting_ethics"
    approve_all_but(m)                                    # ethics approves straight away, before any dosing
    assert q["status"] == "approved_held"
    while m.rec.get("primary_lock_day") is None and m.rec["phase"] != "closed":
        m.step(1)
        if m.rec.get("primary_lock_day") is None:
            assert q["status"] == "approved_held" and q["asked"] == 0
            assert not m.rec["followups"], "follow-ups start only after the lock"
    m.step(1)
    assert q["status"] == "answered" and q["released_day"] >= m.rec["primary_lock_day"]


# --------------------------------------------------------------------------- consent and export
def test_non_consenting_participants_are_never_asked_or_exported():
    m = new_master(consent_off=3)
    refusers = {p["id"] for p in m.rec["enrolled"][:3]}
    m.module_action("postdose", "ask_question", {"question": "How would you describe your sleep over the past two weeks?"})
    run_to_close(m)
    q = m.rec["research_questions"][0]
    assert q["skipped_no_consent"] == 3 and q["asked"] == len(m.rec["enrolled"]) - 3
    exp = next(a for a in m.ctx.approvals.pending() if a["action"]["type"] == "harmonised_export")
    m.decide(exp["id"], "Data Steward", "approved")
    ex = m.rec["exports"]
    assert ex["status"] == "exported" and ex["n_excluded_no_consent"] > 0
    text = (TRIALS / ex["files"][0]).read_text(encoding="utf-8")
    from unblind.platform.postdose.agents import _salt, pseudonym
    salt = _salt(m.rec["trial_id"])
    for pid in refusers:
        assert pseudonym(pid, salt) not in text


def test_export_has_no_names_phone_numbers_or_raw_ids_and_needs_approval():
    m = new_master()
    run_to_close(m)
    assert m.rec["exports"]["status"] == "awaiting_approval", "the export must wait for a human"
    exp = next(a for a in m.ctx.approvals.pending() if a["action"]["type"] == "harmonised_export")
    m.decide(exp["id"], "Data Steward", "approved")
    text = (TRIALS / m.rec["exports"]["files"][0]).read_text(encoding="utf-8")
    header = text.splitlines()[0].split(",")
    assert "name" not in header and "phone" not in header
    for p in m.rec["enrolled"]:
        assert p["id"] not in text and p["name"] not in text


# --------------------------------------------------------------------------- report sign-off
def test_report_cannot_be_finalised_without_a_named_sign_off():
    m = new_master()
    run_to_close(m)
    r = m.rec["report"]
    assert r["status"] == "draft" and r["markdown"].startswith("# FDA blinding report")
    assert not m.module_action("postdose", "sign_off", {"reviewer": ""})["ok"]
    assert not m.module_action("postdose", "sign_off", {"reviewer": "   "})["ok"]
    assert m.rec["report"]["status"] == "draft"
    with pytest.raises(ValueError):
        m.decide(r["approval_id"], "", "approved")
    assert m.module_action("postdose", "sign_off", {"reviewer": "Dr Named Person"})["ok"]
    assert m.rec["report"]["status"] == "final" and m.rec["report"]["signed_by"] == "Dr Named Person"


def test_report_has_every_required_section():
    m = new_master()
    run_to_close(m)
    r = m.rec["report"]
    for key in ("effect", "blinding", "alerts", "decisions", "checklist", "limitations", "digest", "markdown"):
        assert key in r
    assert any("Reverse causation" in x for x in r["limitations"])
    assert "SYNTHETIC" in r["markdown"]


# --------------------------------------------------------------------------- the science
def test_within_trial_estimate_is_less_biased_than_naive_in_the_planted_world():
    from eval.platform.effect_recovery import TRUTH, simulate
    tmp = Path(tempfile.mkdtemp())
    runs = [simulate(s, 120, "planted", tmp) for s in range(6)]
    naive = sum(r["reported"]["md"] for r in runs) / len(runs)
    within = [r["within_trial"]["md"] for r in runs if r["within_trial"] and r["within_trial"]["md"] is not None]
    assert len(within) >= 4
    assert abs(sum(within) / len(within) - TRUTH) < abs(naive - TRUTH)
