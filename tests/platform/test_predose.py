import random
import uuid

import pytest

from unblind.platform.core import DATA, ApprovalQueue, Ctx, MessageBus, TrialRecord, Vault
from unblind.platform.predose.agents import ProtocolParser

PROTOCOLS = DATA / "protocols"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("UNBLIND_OFFLINE", "1")   # rule-based path only; no Gemini calls in tests


class NoLLM:
    @staticmethod
    def available():
        return False


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer

    def available(self):
        return True

    def ask_json(self, *a, **k):
        return self.answer


def make_ctx(llm=NoLLM):
    tid = "TEST-" + uuid.uuid4().hex[:6]
    rec = TrialRecord(tid)
    bus = MessageBus(rec)
    return Ctx(rec=rec, bus=bus, approvals=ApprovalQueue(rec, bus), vault=Vault(tid), llm=llm, rng=random.Random(0))


def parse(name, llm=NoLLM):
    text = (PROTOCOLS / name).read_text()
    return ProtocolParser().run(text, make_ctx(llm)), text


# ---------------------------------------------------------------- Phase 1: parser
def test_parser_reads_both_examples():
    p, _ = parse("example_psilocybin_trd.md")
    assert (p["drug"], p["comparator"], p["rater_model"], p["prior_use_policy"]) == \
        ("psilocybin", "inert_placebo", "onsite", "ignore")
    assert p["primary_endpoint"] == {"scale": "MADRS", "week": 6}
    assert p["n_target"] == 60 and len(p["sites"]) == 3
    assert p["design_flags"]["raters_attend_sessions"] is True
    assert not p["has_blinding_questionnaire"] and not p["has_expectancy_measure"]
    assert len(p["eligibility"]["exclusion"]) == 4

    p, _ = parse("example_mdma_ptsd.md")
    assert (p["drug"], p["comparator"], p["rater_model"], p["prior_use_policy"]) == \
        ("mdma", "active_placebo", "central_remote", "stratify")
    assert p["primary_endpoint"] == {"scale": "CAPS-5", "week": 18}
    assert p["n_target"] == 80 and p["sites"] == ["Site A (London)", "Site C (Bristol)"]
    f = p["design_flags"]
    assert f["two_monitors"] and f["physician_15min"] and f["followup_12m"] and f["abuse_potential"]
    assert not f["factorial"] and not f["raters_attend_sessions"]
    assert p["has_blinding_questionnaire"] and not p["has_expectancy_measure"]


def test_parser_every_found_field_has_an_evidence_quote():
    for name in ("example_psilocybin_trd.md", "example_mdma_ptsd.md"):
        p, text = parse(name)
        found = ["drug", "indication", "comparator", "rater_model", "n_target", "primary_endpoint", "sites", "eligibility"]
        found += [k for k in ("has_blinding_questionnaire", "has_expectancy_measure") if p[k]]
        found += [f"design_flags.{k}" for k, v in p["design_flags"].items() if v]
        if p["prior_use_policy"] != "ignore":
            found.append("prior_use_policy")
        for k in found:
            assert k in p["evidence"], f"{name}: no evidence for {k}"
            assert p["evidence"][k] in text, f"{name}: evidence for {k} is not a quote from the text"


def test_parser_garbage_protocol_does_not_crash():
    ctx = make_ctx()
    p = ProtocolParser().run("!!! ???", ctx)
    assert (p["drug"], p["comparator"], p["rater_model"], p["prior_use_policy"]) == \
        ("unknown", "inert_placebo", "onsite", "ignore")
    assert p["primary_endpoint"] == {"scale": "MADRS", "week": 6} and p["n_target"] == 60
    assert p["evidence"] == {}
    assert ProtocolParser().run("", ctx)["drug"] == "unknown"
    assert any(e["agent"] == "protocol parser" and e["level"] == "decision" for e in ctx.rec["events"])


def test_parser_gemini_answer_is_validated():
    text = (PROTOCOLS / "example_psilocybin_trd.md").read_text()
    made_up = FakeLLM({"comparator": {"value": "active_placebo", "quote": "This sentence is not in the protocol."},
                       "rater_model": {"value": "teleported", "quote": "MADRS is administered by the site psychiatrist"}})
    p = ProtocolParser().run(text, make_ctx(made_up))
    assert p["comparator"] == "inert_placebo" and p["rater_model"] == "onsite"

    real_quote = "Participants receive a single oral dose of psilocybin 25 mg"
    good = FakeLLM({"comparator": {"value": "low_dose_same_drug", "quote": real_quote}})
    ctx = make_ctx(good)
    p = ProtocolParser().run(text, ctx)
    assert p["comparator"] == "low_dose_same_drug" and p["evidence"]["comparator"] == real_quote
    assert any("Gemini changed comparator" in e["text"] for e in ctx.rec["events"])


# ---------------------------------------------------------------- Phase 2: co-designer
from unblind.platform.master.orchestrator import Master  # noqa: E402


def master():
    m = Master("TEST-" + uuid.uuid4().hex[:6])
    m.setup()
    assert m.module_status["predose"] == "real"
    return m


def fix_approval(m, fid):
    return next(a for a in m.ctx.approvals.pending("predose") if a["action"] == {"type": "apply_fix", "fix": fid})


def check(m, cid):
    return next(c for c in m.rec["design_review"]["checklist"] if c["id"] == cid)


def test_checklist_psilocybin_is_missing_the_blinding_items():
    m = master()
    for cid in ("blinding_questionnaire", "expectancy_measure", "central_raters"):
        assert check(m, cid)["present"] is False
        assert check(m, cid)["note"]
    dr = m.rec["design_review"]
    assert dr["risk"]["band"] == "high" and dr["baseline_checklist_ok"] == 0
    assert "SYNTHETIC" in dr["risk"]["calibration"]
    assert set(dr["proposed_fixes"]) == {"central_raters", "blinding_questionnaire", "expectancy_measure",
                                         "alternative_control", "stratify_prior_use"}
    assert len(m.ctx.approvals.pending("predose")) == 5     # one approval per proposed fix
    assert m.rec["protocol_versions"][0]["version"] == 1


def test_fix_central_raters_creates_version_2_and_rechecks():
    m = master()
    m.decide(fix_approval(m, "central_raters")["id"], "Danny", "approved")
    assert len(m.rec["protocol_versions"]) == 2
    assert m.rec["protocol_versions"][1]["why"].startswith("fix approved by Danny")
    assert check(m, "central_raters")["present"] is True
    assert m.rec["protocol"]["design_flags"]["raters_attend_sessions"] is False
    assert any(x["kind"] == "protocol_amended" and x["from"] == "predose" for x in m.rec["messages"])
    pending = [a["action"]["fix"] for a in m.ctx.approvals.pending("predose")]
    assert sorted(pending) == sorted(set(pending)), "re-check must not duplicate pending approvals"
    assert "central_raters" not in pending


def test_fix_alternative_control_lowers_u_and_baseline_is_kept():
    m = master()
    u0 = m.rec["design_review"]["risk"]["u"]
    m.decide(fix_approval(m, "alternative_control")["id"], "Danny", "approved")
    dr = m.rec["design_review"]
    assert dr["risk"]["u"] < u0
    assert dr["baseline_risk"]["u"] == u0


def test_fix_rejected_changes_nothing():
    m = master()
    m.decide(fix_approval(m, "central_raters")["id"], "Danny", "rejected", "not now")
    assert len(m.rec["protocol_versions"]) == 1
    assert check(m, "central_raters")["present"] is False
