import uuid
from unblind.platform.master.orchestrator import Master


def tid():
    return "TEST-" + uuid.uuid4().hex[:6]


def test_master_runs_to_close_with_stubs():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    assert m.rec["enrolled"], "stub predose should enrol people"
    m.run_to(95)
    assert m.rec["phase"] == "closed"
    assert m.rec.get("primary_lock_day") is not None


def test_vault_aggregates_only_and_suppresses_small_groups():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    one = [{"participant": m.rec["enrolled"][0]["id"], "guess": "drug", "g": "x"}]
    assert m.vault.blinding_stats(one, "g", "test")[0]["suppressed"] is True


def test_approval_decision_comes_back_as_message():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    a = m.ctx.approvals.request("tester", "dosing", "Test", "why", {"type": "x"})
    m.decide(a["id"], "Danny", "approved")
    assert any(x["kind"] == "approval_decided" and x["to"] == "dosing" for x in m.rec["messages"])


def test_record_never_contains_allocation():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    m.run_to(10)
    import json
    assert '"arm"' not in json.dumps(m.rec)


# ---------------------------------------------------------------- Phase 8.1 confirm: report sign-off status
def closing_events(m):
    return [e for e in m.rec["events"] if e["module"] == "master" and e["text"].startswith("trial closed")]


def signoff(m):
    return next(a for a in m.rec["approvals"] if (a.get("action") or {}).get("type") == "report_signoff")


def test_report_status_waits_then_signed_with_name_and_logs_once():
    m = Master(tid())
    m.setup()
    rs = m.state()["report_status"]
    assert set(rs) == {"status", "signed_by", "signed_day", "label"}
    assert rs["status"] in ("none", "collecting") and rs["signed_by"] is None
    short = next(a for a in m.ctx.approvals.pending("predose") if a["action"]["type"] == "shortlist")
    m.decide(short["id"], "Dr Clinician", "approved")
    m.run_to(90)
    assert m.rec["phase"] == "closed"
    rs = m.state()["report_status"]
    assert rs == {"status": "waiting_for_signoff", "signed_by": None, "signed_day": None,
                  "label": "FDA blinding report waiting for sign-off"}
    assert [e["text"] for e in closing_events(m)] == ["trial closed; FDA blinding report waiting for sign-off"]
    m.decide(signoff(m)["id"], "Dr Sign", "approved")
    rs = m.state()["report_status"]
    assert rs == {"status": "signed", "signed_by": "Dr Sign", "signed_day": 90,
                  "label": "FDA blinding report signed by Dr Sign"}
    later = [e for e in m.rec["events"] if e["module"] == "master" and e["text"] == "FDA blinding report signed by Dr Sign"]
    assert len(later) == 1 and later[0]["level"] == "decision"
    other = m.ctx.approvals.request("tester", "dosing", "Another decision", "why", {"type": "x"})
    m.decide(other["id"], "Danny", "approved")                    # settling again does not log it twice
    assert sum(e["text"] == "FDA blinding report signed by Dr Sign" for e in m.rec["events"]) == 1


def test_closing_event_says_signed_when_auto_approved():
    m = Master(tid(), auto_approve=True)
    m.setup()
    m.run_to(90)
    rs = m.state()["report_status"]
    assert rs["status"] == "signed" and rs["signed_by"] == "demo reviewer (auto-approve ON)"
    assert rs["label"] == "FDA blinding report signed by demo reviewer (auto-approve ON)"
    assert [e["text"] for e in closing_events(m)] == \
        ["trial closed; FDA blinding report signed by demo reviewer (auto-approve ON)"]
    assert not any("waiting for sign-off" in e["text"] for e in m.rec["events"] if e["module"] == "master")


def test_report_status_changes_requested_and_stub_draft():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    m.rec["report"] = {"status": "draft", "stub": True}
    assert m.report_status()["status"] == "waiting_for_signoff"
    m.rec["report"] = {"status": "changes_requested"}
    assert m.report_status() == {"status": "changes_requested", "signed_by": None, "signed_day": None,
                                 "label": "Sign-off refused; redraft needed"}
    m.rec["report"] = {"status": "final", "signed_by": "Dr X", "signed_day": 91}
    assert m.report_status()["label"] == "FDA blinding report signed by Dr X"
    m.rec["report"] = {}
    assert m.report_status()["label"] == "No report yet"
