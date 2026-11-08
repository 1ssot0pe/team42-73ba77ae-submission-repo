"""Measure trial visibility across Vercel function instances (Tester BROWSER-PROD).

Creates one trial, then:
  * N sequential GET /state calls (gap G seconds): fraction that 404
  * B bursts of K parallel GETs (state, kpis, events, approvals: what Mission control fires on each tick)
  * /api/health samples: the distinct sets of trial ids each instance reports, a lower bound on live instances
Keeps load small: about 80 requests in total. Writes tests/e2e/prod/results/instance_probe-<ts>.json.

    .venv/bin/python tests/e2e/prod/instance_probe.py [--seq 30] [--gap 0.5] [--bursts 8]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import time
import urllib.request
from pathlib import Path

PROD = "https://parallax-two-tau.vercel.app"
OUT = Path(__file__).resolve().parent / "results"


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    rq = urllib.request.Request(PROD + path, data=data, method=method, headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(rq, timeout=90) as r:
            return r.status, json.loads(r.read() or b"null"), round((time.time() - t) * 1000), r.headers.get("x-vercel-id")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode(errors="replace"), round((time.time() - t) * 1000), e.headers.get("x-vercel-id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", type=int, default=30)
    ap.add_argument("--gap", type=float, default=0.5)
    ap.add_argument("--bursts", type=int, default=8)
    a = ap.parse_args()

    st, s, ms, _ = call("POST", "/api/trials", {"example": "example_psilocybin_trd.md"})
    tid = s["trial_id"]
    print(f"created {tid} in {ms} ms")
    res = {"trial": tid, "create_ms": ms, "seq": [], "bursts": [], "health": []}

    for i in range(a.seq):
        st, _, ms, vid = call("GET", f"/api/trials/{tid}/state")
        res["seq"].append({"i": i, "t": round(time.time(), 2), "status": st, "ms": ms, "vercel_id": vid})
        time.sleep(a.gap)
    seq404 = sum(1 for r in res["seq"] if r["status"] == 404)
    print(f"sequential: {seq404}/{a.seq} 404")

    paths = ["state", "kpis", "events?limit=40", "approvals"]
    with cf.ThreadPoolExecutor(4) as ex:
        for b in range(a.bursts):
            got = list(ex.map(lambda p: call("GET", f"/api/trials/{tid}/{p}"), paths))
            res["bursts"].append([{"path": p, "status": g[0], "ms": g[2]} for p, g in zip(paths, got)])
            time.sleep(1.0)
    b404 = sum(1 for burst in res["bursts"] for r in burst if r["status"] == 404)
    nb = sum(len(b) for b in res["bursts"])
    bursts_any = sum(1 for burst in res["bursts"] if any(r["status"] == 404 for r in burst))
    print(f"parallel bursts: {b404}/{nb} 404, {bursts_any}/{a.bursts} bursts had at least one 404")

    sets = {}
    for _ in range(10):
        st, h, ms, _ = call("GET", "/api/health")
        key = ",".join(sorted(h.get("trials", []))) if isinstance(h, dict) else str(h)
        sets[key] = sets.get(key, 0) + 1
        res["health"].append({"ms": ms, "has_trial": tid in key, "n_trials": len(h.get("trials", [])) if isinstance(h, dict) else None})
        time.sleep(0.3)
    print(f"health: {len(sets)} distinct trial sets in 10 sequential calls; "
          f"{sum(1 for x in res['health'] if x['has_trial'])}/10 list our trial")
    res["summary"] = {"seq_404": seq404, "seq_n": a.seq, "burst_404": b404, "burst_n": nb, "bursts_with_404": bursts_any,
                      "bursts": a.bursts, "health_distinct_sets": len(sets)}
    OUT.mkdir(exist_ok=True)
    (OUT / f"instance_probe-{time.strftime('%H%M%S')}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
