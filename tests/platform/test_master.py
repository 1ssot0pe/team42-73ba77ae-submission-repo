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
