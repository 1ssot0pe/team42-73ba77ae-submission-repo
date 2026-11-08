"""Two API processes, one trial store: the way Vercel runs the backend (many instances, shared database).

Each process gets its own UNBLIND_TRIALS_DIR (scratch files are NOT shared, as on separate Vercel instances) and
the same trial store. Requests alternate between the processes, parallel bursts hit both at once, then one
process is killed and the trial carries on in the other. Every call must succeed and no update may be lost.

FileStore always runs; Postgres runs too when TEST_DATABASE_URL is set."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
PG_URL = os.environ.get("TEST_DATABASE_URL")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(port: int, env: dict) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
                             "--port", str(port), "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _wait(url: str, proc: subprocess.Popen) -> None:
    for _ in range(150):
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read().decode()[-2000:])
        try:
            if httpx.get(url + "/api/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"{url} did not start")


@pytest.fixture(params=["file"] + (["postgres"] if PG_URL else []))
def two_instances(request, tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "POSTGRES_URL", "GEMINI_API_KEY", "UNBLIND_EXPORT_SALT", "UNBLIND_DEBUG")}
    env["PYTHONPATH"] = str(ROOT)
    if request.param == "file":
        env["UNBLIND_STORE_DIR"] = str(tmp_path / "shared-store")
    else:
        env["DATABASE_URL"] = PG_URL
    procs, urls = [], []
    for i in range(2):
        port = _free_port()
        e = dict(env, UNBLIND_TRIALS_DIR=str(tmp_path / f"instance-{i}"))   # private scratch per instance
        p = _start(port, e)
        procs.append(p)
        urls.append(f"http://127.0.0.1:{port}")
    try:
        for u, p in zip(urls, procs):
            _wait(u, p)
        yield request.param, urls, procs
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()


def test_trial_works_across_instances_and_survives_losing_one(two_instances):
    kind, (a, b), procs = two_instances
    c = httpx.Client(timeout=60)
    calls = []

    def call(method, url, **kw):
        r = c.request(method, url, **kw)
        calls.append((method, url, r.status_code))
        assert r.status_code == 200, (method, url, r.status_code, r.text[:300])
        return r.json()

    h = call("GET", f"{a}/api/health")
    assert h["store"] == kind and h["store_ok"] is True
    assert "trials" not in h or h["trials"] == []

    # ---- alternate every request between the two instances
    st = call("POST", f"{a}/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 42, "n_applicants": 60})
    tid = st["trial_id"]
    T = f"/api/trials/{tid}"
    assert call("GET", f"{b}{T}/state")["trial_id"] == tid
    pend = call("GET", f"{a}{T}/approvals", params={"status": "pending"})
    shortlist = next(x for x in pend if (x.get("action") or {}).get("type") == "shortlist")
    out = call("POST", f"{b}{T}/approvals/{shortlist['id']}", json={"reviewer": "Dr Test", "decision": "approved"})
    assert out["approval"]["status"] == "approved"
    # the decision is visible to the other instance, and deciding it again there is a clean 404
    r = c.post(f"{a}{T}/approvals/{shortlist['id']}", json={"reviewer": "Dr Test", "decision": "approved"})
    assert r.status_code == 404
    out = call("POST", f"{a}{T}/step", json={"days": 3})
    assert out["advanced"] is True and out["day"] == 2
    assert call("GET", f"{b}{T}/state")["day"] == 2
    res = call("POST", f"{b}{T}/modules/predose/actions/recheck", json={"payload": {}})
    assert "result" in res
    assert call("GET", f"{a}{T}/record", params={"sections": "enrolled,schedule"})["enrolled"]
    ev = call("GET", f"{b}{T}/events")
    assert any("approved" in e["text"] for e in ev)
    call("GET", f"{a}{T}/kpis")
    call("GET", f"{b}{T}/messages")
    call("GET", f"{a}{T}/modules/dosing/view")
    call("POST", f"{b}{T}/auto_approve", params={"on": "true"})
    assert call("GET", f"{a}{T}/state")["auto_approve"] is True

    # ---- parallel bursts: the page fires ~6 GETs per refresh, fanned out over instances, while a step runs
    gets = ["state", "kpis", "messages", "events", "approvals", "record?sections=schedule", "modules/predose/view",
            "state"]
    before = call("GET", f"{a}{T}/state")["day"]
    with ThreadPoolExecutor(16) as pool:
        futs = [pool.submit(c.get, f"{(a, b)[i % 2]}{T}/{g}") for i, g in enumerate(gets * 2)]
        futs += [pool.submit(c.post, f"{(a, b)[i % 2]}{T}/step", json={"days": 1}) for i in range(6)]
        futs += [pool.submit(c.post, f"{(a, b)[i % 2]}{T}/modules/postdose/actions/ask_question",
                             json={"payload": {"question": f"How was sleep in week {i}?", "researcher": "Dr Q"}})
                 for i in range(2)]
        rs = [f.result() for f in futs]
    bad = [(r.request.method, str(r.request.url), r.status_code) for r in rs if r.status_code != 200]
    assert not bad, bad
    after = call("GET", f"{b}{T}/state")["day"]
    assert after == before + 6, (before, after)            # six concurrent steps, none lost

    # ---- to past the primary lock, then an export requested on one instance, approved on the other
    call("POST", f"{b}{T}/auto_approve", params={"on": "false"})     # humans decide from here
    for i in range(3):
        call("POST", f"{(a, b)[i % 2]}{T}/step", json={"days": 30})
    st = call("GET", f"{a}{T}/state")
    assert st["primary_lock_day"] is not None
    ex = call("GET", f"{b}{T}/record", params={"sections": "exports"})["exports"]
    if ex.get("status") != "awaiting_approval":
        req = call("POST", f"{a}{T}/modules/postdose/actions/request_export", json={"payload": {"requested_by": "Dr X"}})
        ex = call("GET", f"{b}{T}/record", params={"sections": "exports"})["exports"]
        assert req["result"].get("ok") is True, req
    assert ex.get("status") == "awaiting_approval", ex.get("status")
    call("POST", f"{b}{T}/approvals/{ex['approval_id']}", json={"reviewer": "Dr Y", "decision": "approved"})
    ex2 = call("GET", f"{a}{T}/record", params={"sections": "exports"})["exports"]
    assert ex2["status"] == "exported" and ex2["n_rows"] > 0   # (salt round-trip itself: test_store.py)

    # ---- lose instance A; the trial carries on in B
    procs[0].send_signal(signal.SIGKILL)
    procs[0].wait(10)
    s = call("GET", f"{b}{T}/state")
    assert s["trial_id"] == tid
    call("POST", f"{b}{T}/step", json={"days": 1})
    call("GET", f"{b}{T}/events", params={"since": 0, "limit": 50})
    call("GET", f"{b}{T}/record")
    assert c.get(f"{b}/api/trials/T-000000-nope/state").status_code == 404
    assert c.get(f"{b}/api/trials/T-000000-nope/state").json()["detail"] == "trial not found"
    assert len(calls) >= 20


# ---------------------------------------------------------------------------
# API edge cases found by the end-to-end testers (in-process client on the store-backed API)
# ---------------------------------------------------------------------------
@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from unblind.platform import store
    monkeypatch.delenv("UNBLIND_DEBUG", raising=False)
    store.set_store(store.FileStore(tmp_path / "store"))
    try:
        c = TestClient(app)
        tid = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 42, "n_applicants": 60,
                                          "auto_approve": True}).json()["trial_id"]
        yield c, tid
    finally:
        store.set_store(None)


def test_health_counts_trials_without_listing_ids(api, monkeypatch):
    c, tid = api
    h = c.get("/api/health").json()
    assert h["trial_count"] == 1 and h["store"] == "file" and h["store_ok"] is True
    assert tid not in str(h)
    assert c.get("/api/trials").json() == []                 # no enumeration of other people's trials
    monkeypatch.setenv("UNBLIND_DEBUG", "1")
    assert [t["trial_id"] for t in c.get("/api/trials").json()] == [tid]


def test_unknown_trial_is_404_trial_not_found(api):
    c, _ = api
    for method, path in (("GET", "state"), ("GET", "events"), ("POST", "step"), ("POST", "auto_approve")):
        r = c.request(method, f"/api/trials/T-nope/{path}", json={"days": 1} if path == "step" else None)
        assert r.status_code == 404 and r.json()["detail"] == "trial not found", (path, r.text)
    assert c.get("/api/trials/..%2F..%2Fetc/state").status_code == 404


def test_events_limit_is_clamped(api):
    c, tid = api
    c.post(f"/api/trials/{tid}/step", json={"days": 5})
    n_all = len(c.get(f"/api/trials/{tid}/events", params={"limit": 1000}).json())
    assert n_all > 1
    assert len(c.get(f"/api/trials/{tid}/events", params={"limit": 0}).json()) == 1
    assert len(c.get(f"/api/trials/{tid}/events", params={"limit": -5}).json()) == 1
    assert len(c.get(f"/api/trials/{tid}/events", params={"limit": 10 ** 6}).json()) == min(n_all, 1000)


def test_unknown_module_or_action_is_404_and_saves_nothing(api):
    from unblind.platform.store import get_store
    c, tid = api
    v = get_store().version(tid)
    assert c.get(f"/api/trials/{tid}/modules/nope/view").status_code == 404
    assert c.post(f"/api/trials/{tid}/modules/nope/actions/x", json={"payload": {}}).status_code == 404
    for mod in ("predose", "dosing", "postdose"):
        r = c.post(f"/api/trials/{tid}/modules/{mod}/actions/no_such_action", json={"payload": {}})
        assert r.status_code == 404, (mod, r.text)
    assert get_store().version(tid) == v


def test_portal_overflowing_age_is_a_validation_message(api):
    c, tid = api
    r = c.post(f"/api/trials/{tid}/modules/predose/actions/apply", json={"payload": {"applicant": {"age": "1e400"}}})
    assert r.status_code == 200
    assert r.json()["result"] == {"ok": False, "error": "'age' must be a whole number"}


def test_module_errors_keep_stack_traces_out_of_the_timeline(api, monkeypatch):
    from unblind.platform.store import get_store
    c, tid = api

    def boom(m):
        def bad_kpis(rec):
            raise RuntimeError("kaboom")
        m.modules["dosing"].kpis = bad_kpis
        m.kpis()
        del m.modules["dosing"].kpis
    get_store().mutate(tid, boom)
    ev = [e for e in c.get(f"/api/trials/{tid}/events", params={"limit": 1000}).json() if "kaboom" in e["text"]]
    assert ev and all(not e.get("data") for e in ev)
    assert "Traceback" not in c.get(f"/api/trials/{tid}/events", params={"limit": 1000}).text
