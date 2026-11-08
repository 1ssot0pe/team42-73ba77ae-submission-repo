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
    fixes = [a for a in m.ctx.approvals.pending("predose") if a["action"]["type"] == "apply_fix"]
    assert len(fixes) == 5     # one approval per proposed fix
    assert m.rec["protocol_versions"][0]["version"] == 1


def test_fix_central_raters_creates_version_2_and_rechecks():
    m = master()
    m.decide(fix_approval(m, "central_raters")["id"], "Danny", "approved")
    assert len(m.rec["protocol_versions"]) == 2
    assert m.rec["protocol_versions"][1]["why"].startswith("fix approved by Danny")
    assert check(m, "central_raters")["present"] is True
    assert m.rec["protocol"]["design_flags"]["raters_attend_sessions"] is False
    assert any(x["kind"] == "protocol_amended" and x["from"] == "predose" for x in m.rec["messages"])
    pending = [a["action"]["fix"] for a in m.ctx.approvals.pending("predose") if a["action"]["type"] == "apply_fix"]
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


# ---------------------------------------------------------------- Phase 2 follow-ups (decided by Danny)
def test_fix_rejected_is_not_asked_again_after_later_rechecks():
    m = master()
    m.decide(fix_approval(m, "central_raters")["id"], "Danny", "rejected")
    m.decide(fix_approval(m, "expectancy_measure")["id"], "Danny", "approved")    # triggers a re-check
    m.decide(fix_approval(m, "blinding_questionnaire")["id"], "Danny", "approved")  # and another
    asked = [a for a in m.rec["approvals"] if a["action"] == {"type": "apply_fix", "fix": "central_raters"}]
    assert len(asked) == 1 and asked[0]["status"] == "rejected"
    assert "central_raters" in m.rec["design_review"]["rejected_fixes"]


def test_fix_reparse_after_central_raters_keeps_the_item_present():
    m = master()
    m.decide(fix_approval(m, "central_raters")["id"], "Danny", "approved")
    text = m.rec["protocol"]["text"]
    assert "the rater is present during the dosing session" in text      # the old sentence is still there
    p = ProtocolParser().run(text, m.ctx)
    assert p["rater_model"] == "central_remote" and p["design_flags"]["raters_attend_sessions"] is False
    cl = {c["id"]: c["present"] for c in m.modules["predose"].codesigner.checklist(p)}
    assert cl["central_raters"] is True


# ---------------------------------------------------------------- Phase 3: recruitment, screening, enrolment
import json  # noqa: E402

from unblind.platform.predose.agents import CRITERIA, PreScreeningAgent, flesch  # noqa: E402


def shortlist(m):
    return next(a for a in m.ctx.approvals.pending("predose") if a["action"]["type"] == "shortlist")


def test_screening_nothing_enrolled_before_clinician_approval():
    m = master()
    assert m.rec["enrolled"] == []
    out = m.step(1)
    assert out["advanced"] is False and "Clinician: confirm shortlist" in out["blocked"]
    assert m.rec["day"] == -1
    sl = [a for a in m.rec["approvals"] if a["action"]["type"] == "shortlist"]
    assert len(sl) == 1, "the clinician shortlist is ONE approval"


def test_screening_every_hidden_exclusion_is_not_eligible():
    m = master()
    hidden = [a for a in m.rec["applicants"] if a.get("_hidden_exclusion")]
    assert hidden, "the synthetic world should plant some hidden exclusions"
    assert all(a["screening"]["decision"] != "eligible" for a in hidden)
    f = m.rec["recruitment"]["funnel"]
    assert f["applied"] == 500 and f["auto_eligible"] + f["auto_excluded"] + f["needs_clinician"] == 500


def test_screening_agent_never_reads_underscore_keys():
    ctx = make_ctx()
    clean = {"age": 30, "phone": "+447700900123", "self_reported_diagnosis": "treatment-resistant depression",
             "failed_antidepressants": 3, "current_medication": "none", "prior_psychedelic_use": "never",
             "can_attend_8_visits": True, "consents_to_chatbot_checkins": True, "free_text": "My GP suggested I look into trials."}
    proto = {"indication": "treatment-resistant depression"}
    a = PreScreeningAgent().screen_one(clean, proto, ctx)
    b = PreScreeningAgent().screen_one(dict(clean, _hidden_exclusion=True), proto, ctx)
    assert a == b and a["decision"] == "eligible"


def test_screening_portal_disclosure_needs_clinician_with_quote():
    ctx = make_ctx()
    out = PreScreeningAgent().screen_one({"age": 30, "phone": "+447700900123",
                                          "free_text": "I was diagnosed with bipolar disorder"},
                                         {"indication": "treatment-resistant depression"}, ctx)
    assert out["decision"] == "needs_clinician"
    assert {"criterion": "free_text", "quote": "I was diagnosed with bipolar disorder"} in out["evidence"]


def test_enrolment_after_approval_is_stratified_in_the_vault():
    m = master()
    m.decide(shortlist(m)["id"], "Dr Clinician", "approved")
    n = len(m.rec["enrolled"])
    assert n > 10
    assert sum(m.rec["recruitment"]["strata"].values()) == n == m.vault.enrolled()
    assert m.rec["recruitment"]["funnel"]["enrolled"] == n
    assert all(p["stratum"] == f"{p['site']}|{'naive' if p['prior_psychedelic_use'] == 'never' else 'experienced'}"
               for p in m.rec["enrolled"])
    eligible = {a["id"] for a in m.rec["applicants"] if a["screening"]["decision"] == "eligible"}
    assert {p["id"] for p in m.rec["enrolled"]} <= eligible          # flagged stay out without 'include flagged'
    assert any(x["kind"] == "enrolment_complete" and x["from"] == "predose" for x in m.rec["messages"])
    assert m.step(1)["advanced"] is True


def test_enrolment_include_flagged_adds_washout_only_never_disclosures():
    m = master()
    m.decide(shortlist(m)["id"], "Dr Clinician", "approved", "Include flagged after washout review")
    by_id = {a["id"]: a for a in m.rec["applicants"]}
    for p in m.rec["enrolled"]:
        s = by_id[p["id"]]["screening"]
        assert s["decision"] == "eligible" or s["criteria_hit"] == ["ssri_snri"]
        assert "free_text" not in s["criteria_hit"]


def test_enrolment_record_never_contains_an_arm():
    m = master()
    m.decide(shortlist(m)["id"], "Dr Clinician", "approved")
    dumped = json.dumps(m.rec)
    assert '"arm"' not in dumped and '"alloc"' not in dumped
    assert all(set(p) == {"id", "name", "site", "stratum", "prior_psychedelic_use", "dosing_day", "consents"}
               for p in m.rec["enrolled"])


def test_recruitment_ads_pass_checks_and_targeting_is_parked():
    m = master()
    r = m.rec["recruitment"]
    assert len(r["ads"]) == 3 and all(all(a["checks"].values()) for a in r["ads"])
    assert all(a["reading_ease"] > 50 for a in r["ads"])
    assert "UK GDPR" in r["parked"] and len(r["channels"]) == 4
    assert any("ethics approval" in e["text"] for e in m.rec["events"])
    assert flesch("") == 0.0 and len(CRITERIA) == 13
