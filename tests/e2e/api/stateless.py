"""Section C: statelessness through the round-robin proxy, and instance loss.

    # 1. a full journey through the proxy (two backends, alternating)
    .venv/bin/python tests/e2e/api/stateless.py journey --base http://127.0.0.1:8000
    # 2. create on A, kill A, continue on B (and through the proxy); then restart A yourself and run 'restart'
    .venv/bin/python tests/e2e/api/stateless.py kill --a http://127.0.0.1:8001 --b http://127.0.0.1:8002 \
        --proxy http://127.0.0.1:8000 --kill-port 8001
    .venv/bin/python tests/e2e/api/stateless.py restart --a http://127.0.0.1:8001 --trial <id> --trials-dir /tmp/parallax-e2e/8001

Every request is logged with the backend that served it (X-RR-Backend). Results go to tests/e2e/api/results/.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import signal
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import Client, dump  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
REVIEWER = "E2E Tester"


def summarise(c: Client, label: str):
    by = collections.defaultdict(lambda: collections.Counter())
    for row in c.log:
        by[row["backend"] or "direct"][row["status"]] += 1
    fails = [r for r in c.log if r["status"] >= 400]
    print(f"\n[{label}] {len(c.log)} requests, {len(fails)} failed")
    for b, cnt in sorted(by.items()):
        print(f"  {b}: {dict(cnt)}")
    for r in fails[:40]:
        print(f"  FAIL {r['method']} {r['path']} -> {r['status']} via {r['backend']}")
    return {"n": len(c.log), "failed": len(fails), "by_backend": {k: dict(v) for k, v in by.items()}, "log": c.log}


def journey(base: str):
    c = Client(base)
    r = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 42})
    created_on = r.headers.get("X-RR-Backend")
    tid = r.json()["trial_id"]
    print(f"created {tid} on {created_on}")
    T = f"/api/trials/{tid}"
    steps = []

    def do(label, method, path, **kw):
        rr = c.call(method, path, **kw)
        steps.append({"step": label, "status": rr.status_code, "backend": rr.headers.get("X-RR-Backend")})
        print(f"  {label:<40} {rr.status_code} via {rr.headers.get('X-RR-Backend')}")
        return rr

    do("state", "GET", f"{T}/state")
    do("state (again)", "GET", f"{T}/state")
    ap = do("approvals", "GET", f"{T}/approvals")
    ap2 = do("approvals (again)", "GET", f"{T}/approvals")
    pend = (ap.json() if ap.status_code == 200 else []) or (ap2.json() if ap2.status_code == 200 else [])
    for a in pend:
        do(f"approve {a['id']}", "POST", f"{T}/approvals/{a['id']}", json={"reviewer": REVIEWER, "decision": "approved"})
    for i in range(4):
        do(f"step 1 (#{i + 1})", "POST", f"{T}/step", json={"days": 1})
    do("view predose", "GET", f"{T}/modules/predose/view")
    do("view dosing", "GET", f"{T}/modules/dosing/view")
    do("action dosing/checkin", "POST", f"{T}/modules/dosing/actions/checkin",
       json={"payload": {"participant": "APP-0001", "guess": "drug", "confidence": 3, "expectancy": 3}})
    do("action predose/apply", "POST", f"{T}/modules/predose/actions/apply", json={"payload": {"name": "x", "age": 30}})
    do("action postdose/ask_question", "POST", f"{T}/modules/postdose/actions/ask_question",
       json={"payload": {"question": "How many check-ins are done?", "researcher": REVIEWER}})
    do("record", "GET", f"{T}/record")
    do("events", "GET", f"{T}/events")
    do("kpis", "GET", f"{T}/kpis")
    do("messages", "GET", f"{T}/messages")
    do("auto_approve on", "POST", f"{T}/auto_approve?on=true")
    do("step 30", "POST", f"{T}/step", json={"days": 30})
    do("state (final)", "GET", f"{T}/state")
    s = summarise(c, "journey via proxy")
    s.update(trial=tid, created_on=created_on, steps=steps)
    return s


def pid_on_port(port: int):
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]


def kill(a: str, b: str, proxy: str, kill_port: int):
    ca, cb, cp = Client(a), Client(b), Client(proxy)
    st = ca.post("/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 42, "auto_approve": True}).json()
    tid = st["trial_id"]
    ca.post(f"/api/trials/{tid}/step", json={"days": 5})
    print(f"created {tid} on {a}; stepped to day {ca.get(f'/api/trials/{tid}/state').json()['day']}")
    pids = pid_on_port(kill_port)
    for p in pids:
        os.kill(p, signal.SIGTERM)
    print(f"killed pid(s) {pids} on port {kill_port}")
    import time
    time.sleep(1.5)
    res = {}
    for label, c in (("B direct", cb), ("proxy", cp)):
        for p in ("state", "approvals", "events", "record?sections=enrolled"):
            r = c.get(f"/api/trials/{tid}/{p}")
            print(f"  {label:<9} GET {p:<26} {r.status_code} via {r.headers.get('X-RR-Backend') or label} {r.text[:80]!r}")
        r = c.post(f"/api/trials/{tid}/step", json={"days": 1})
        print(f"  {label:<9} POST step                    {r.status_code} via {r.headers.get('X-RR-Backend') or label} {r.text[:80]!r}")
    res["B_direct"] = summarise(cb, "B direct after A died")
    res["proxy"] = summarise(cp, "proxy after A died")
    res["trial"] = tid
    return res


def restart(a: str, tid: str, trials_dir: str):
    c = Client(a)
    f = os.path.join(trials_dir, f"{tid}.json")
    print(f"{f} exists on disk: {os.path.exists(f)} ({os.path.getsize(f) if os.path.exists(f) else 0} bytes)")
    r = c.get(f"/api/trials/{tid}/state")
    print(f"after restart, GET state on {a}: {r.status_code} {r.text[:120]!r}")
    return {"trial": tid, "file_exists": os.path.exists(f), "status": r.status_code, "body": r.text[:200]}


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    j = sp.add_parser("journey")
    j.add_argument("--base", default="http://127.0.0.1:8000")
    k = sp.add_parser("kill")
    k.add_argument("--a", default="http://127.0.0.1:8001")
    k.add_argument("--b", default="http://127.0.0.1:8002")
    k.add_argument("--proxy", default="http://127.0.0.1:8000")
    k.add_argument("--kill-port", type=int, default=8001)
    rs = sp.add_parser("restart")
    rs.add_argument("--a", default="http://127.0.0.1:8001")
    rs.add_argument("--trial", required=True)
    rs.add_argument("--trials-dir", default="/tmp/parallax-e2e/8001")
    x = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    if x.cmd == "journey":
        out = journey(x.base)
    elif x.cmd == "kill":
        out = kill(x.a, x.b, x.proxy, x.kill_port)
    else:
        out = restart(x.a, x.trial, x.trials_dir)
    dump(out, os.path.join(RESULTS, f"stateless_{x.cmd}.json"))


if __name__ == "__main__":
    main()
