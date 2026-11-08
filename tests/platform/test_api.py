"""Phase 5: FastAPI backend (thin glue over the Master)."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _new_trial(**kw):
    body = {"example": "example_psilocybin_trd.md", "seed": 42, "n_applicants": 60}
    body.update(kw)
    r = client.post("/api/trials", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _shortlist(tid):
    rows = client.get(f"/api/trials/{tid}/approvals", params={"status": "pending"}).json()
    sl = [a for a in rows if (a.get("action") or {}).get("type") == "shortlist"]
    assert sl, f"no pending shortlist approval: {rows}"
    return sl[0]


def test_health_and_protocols():
    h = client.get("/api/health").json()
    assert h["ok"] is True and "gemini" in h and isinstance(h["trials"], list)
    names = [p["name"] for p in client.get("/api/protocols").json()]
    assert "example_psilocybin_trd.md" in names
    p = client.get("/api/protocols/example_psilocybin_trd.md").json()
    assert p["text"].strip()


def test_new_trial_is_blocked_until_shortlist_approved_then_steps():
    st = _new_trial()
    tid = st["trial_id"]
    st = client.get(f"/api/trials/{tid}/state").json()
    assert st["blocked"], "trial should be blocked before the clinician approves the shortlist"
    out = client.post(f"/api/trials/{tid}/step", json={"days": 1}).json()
    assert out["advanced"] is False and out["blocked"]

    a = _shortlist(tid)
    r = client.post(f"/api/trials/{tid}/approvals/{a['id']}",
                    json={"reviewer": "Dr Test", "decision": "approved", "comment": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["approval"]["status"] == "approved"
    assert r.json()["state"]["blocked"] is None

    out = client.post(f"/api/trials/{tid}/step", json={"days": 2}).json()
    assert out["advanced"] is True and out["day"] >= 1
    assert out["state"]["day"] == out["day"]


def test_empty_reviewer_gives_400():
    tid = _new_trial()["trial_id"]
    a = _shortlist(tid)
    r = client.post(f"/api/trials/{tid}/approvals/{a['id']}",
                    json={"reviewer": "", "decision": "approved", "comment": ""})
    assert r.status_code == 400


def test_record_strips_hidden_keys():
    tid = _new_trial()["trial_id"]
    r = client.get(f"/api/trials/{tid}/record", params={"sections": "applicants"})
    assert r.status_code == 200
    assert r.json()["applicants"], "expected applicants in the record"
    assert "_hidden_exclusion" not in r.text
    assert '"_' not in r.text
    # a section outside the allow-list is ignored
    r = client.get(f"/api/trials/{tid}/record", params={"sections": "config,applicants"})
    assert "config" not in r.json()


@pytest.mark.parametrize("path", [
    "/api/protocols/../../etc/passwd",
    "/api/protocols/..%2F..%2Fetc%2Fpasswd",
    "/api/protocols/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd",
    "/api/protocols/..%2Fplans%2Fplan.md",
    "/api/protocols/nope.md",
])
def test_protocol_path_traversal_blocked(path):
    r = client.get(path)
    assert r.status_code == 404
    assert "root:" not in r.text


@pytest.mark.parametrize("name", ["../../etc/passwd", "../plans/plan.md", "/etc/passwd", "..", "nope.md"])
def test_protocol_guard_itself(name):
    """The HTTP router already rejects most traversal paths; check the guard in get_protocol directly too."""
    from fastapi import HTTPException
    from backend.main import get_protocol
    with pytest.raises(HTTPException) as e:
        get_protocol(name)
    assert e.value.status_code == 404


def test_unknown_trial_404():
    assert client.get("/api/trials/NOPE/state").status_code == 404


def test_predose_apply_action():
    tid = _new_trial()["trial_id"]
    applicant = {"name": "Judge J.", "age": 41, "site": "London",
                 "free_text": "I have had depression for years and tried two antidepressants."}
    r = client.post(f"/api/trials/{tid}/modules/predose/actions/apply", json={"payload": {"applicant": applicant}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "result" in body and "state" in body
    res = body["result"]
    assert res.get("ok") is True, res
    assert res.get("applicant") and res["applicant"].get("screening", {}).get("decision") in (
        "eligible", "excluded", "needs_clinician")
    assert "_hidden_exclusion" not in r.text


def test_dosing_view_returns_view_model():
    tid = _new_trial()["trial_id"]
    r = client.get(f"/api/trials/{tid}/modules/dosing/view")
    assert r.status_code == 200
    v = r.json()
    assert v.get("module") and v.get("title")
    assert "status" in v


def test_kpis_messages_events():
    tid = _new_trial()["trial_id"]
    k = client.get(f"/api/trials/{tid}/kpis").json()
    assert set(k) >= {"predose", "dosing", "postdose"}
    m = client.get(f"/api/trials/{tid}/messages").json()
    assert "edges" in m and "recent" in m
    ev = client.get(f"/api/trials/{tid}/events", params={"module": "predose"}).json()
    assert ev and all("idx" in e and e["module"] == "predose" for e in ev)


@pytest.mark.parametrize("n,code", [(9, 422), (2001, 422), (-5, 422), (10, 200)])
def test_n_applicants_is_clamped(n, code):
    r = client.post("/api/trials", json={"example": "example_psilocybin_trd.md", "n_applicants": n})
    assert r.status_code == code, r.text


def test_unknown_approval_id_is_404_but_empty_reviewer_stays_400():
    tid = _new_trial()["trial_id"]
    r = client.post(f"/api/trials/{tid}/approvals/NOPE-1", json={"reviewer": "Dr Test", "decision": "approved"})
    assert r.status_code == 404
    r = client.post(f"/api/trials/{tid}/approvals/NOPE-1", json={"reviewer": "  ", "decision": "approved"})
    assert r.status_code == 400


def test_list_protocols_survives_empty_file(tmp_path, monkeypatch):
    import backend.main as bm
    (tmp_path / "empty.md").write_text("")
    (tmp_path / "titled.md").write_text("\n# A title\nbody\n")
    monkeypatch.setattr(bm, "PROTOCOLS", tmp_path)
    rows = {p["name"]: p["title"] for p in client.get("/api/protocols").json()}
    assert rows == {"empty.md": "empty.md", "titled.md": "A title"}


def test_reads_during_a_long_step_do_not_crash():
    """React polls while a 30-day step runs in another threadpool worker; reads must hold the lock."""
    import threading
    tid = _new_trial(auto_approve=True)["trial_id"]
    errors = []

    def poll():
        try:
            for _ in range(15):
                for path in ("state", "events", "kpis", "messages", "record?sections=schedule,checkins"):
                    r = client.get(f"/api/trials/{tid}/{path}")
                    assert r.status_code == 200, (path, r.status_code)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=poll)
    t.start()
    out = client.post(f"/api/trials/{tid}/step", json={"days": 30}).json()
    t.join(timeout=60)
    assert not errors, errors
    assert out["advanced"] is True
