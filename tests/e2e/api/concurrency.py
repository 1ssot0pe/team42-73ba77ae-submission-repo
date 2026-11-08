"""Concurrency and memory on ONE instance: parallel steps / decides / reads on one trial, and RSS growth per trial.

    .venv/bin/python tests/e2e/api/concurrency.py --base http://127.0.0.1:8002 --port 8002 [--trials 40]
"""
from __future__ import annotations

import argparse
import collections
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from common import Client  # noqa: E402


def rss_kb(port):
    pid = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()[0]
    return int(subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True).stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8002")
    ap.add_argument("--port", type=int, default=8002)
    ap.add_argument("--trials", type=int, default=40)
    a = ap.parse_args()
    c = Client(a.base)
    tid = c.post("/api/trials", json={"example": "example_psilocybin_trd.md"}).json()["trial_id"]
    pend = c.get(f"/api/trials/{tid}/approvals").json()

    def job(i):
        cc = Client(a.base)
        if i < len(pend):   # each approval decided twice in parallel: exactly one 200 expected per id
            return ("decide", cc.post(f"/api/trials/{tid}/approvals/{pend[i % len(pend)]['id']}",
                                      json={"reviewer": f"r{i}", "decision": "approved"}).status_code)
        if i < 2 * len(pend):
            return ("decide-dup", cc.post(f"/api/trials/{tid}/approvals/{pend[i % len(pend)]['id']}",
                                          json={"reviewer": f"r{i}", "decision": "approved"}).status_code)
        if i % 3 == 0:
            return ("step", cc.post(f"/api/trials/{tid}/step", json={"days": 3}).status_code)
        if i % 3 == 1:
            return ("record", cc.get(f"/api/trials/{tid}/record").status_code)
        return ("trials", cc.get("/api/trials").status_code)

    with ThreadPoolExecutor(24) as ex:
        res = list(ex.map(job, range(60)))
    print("parallel results:", dict(collections.Counter(res)))
    allp = c.get(f"/api/trials/{tid}/approvals?status=all").json()
    decided = [x for x in allp if x["id"] in {p["id"] for p in pend}]
    print("each original approval decided once:", all(x["status"] == "approved" for x in decided),
          "events for 'approved:'", sum(1 for e in c.get(f"/api/trials/{tid}/events?limit=100000").json()
                                         if e["text"].startswith("approved: ")))

    before = rss_kb(a.port)
    ids = []
    for _ in range(a.trials):
        ids.append(c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "auto_approve": True}).json()["trial_id"])
    mid = rss_kb(a.port)
    for t in ids:
        c.post(f"/api/trials/{t}/step", json={"days": 30})
        c.post(f"/api/trials/{t}/step", json={"days": 30})
        c.post(f"/api/trials/{t}/step", json={"days": 31})
    after = rss_kb(a.port)
    n = len(c.get("/api/trials").json())
    lst = c.get("/api/trials")
    print(f"RSS before {before // 1024} MB; after creating {a.trials} trials {mid // 1024} MB; after running them to day 90 "
          f"{after // 1024} MB => ~{(after - before) / a.trials / 1024:.1f} MB per closed trial; trials held {n}; "
          f"GET /api/trials {len(lst.content)} bytes in {c.log[-1]['ms']} ms")


if __name__ == "__main__":
    main()
