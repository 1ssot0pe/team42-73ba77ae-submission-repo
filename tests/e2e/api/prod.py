"""Section E: production checks against the public deployment. Read-mostly: it creates a few trials.

    .venv/bin/python tests/e2e/api/prod.py [--base https://parallax-two-tau.vercel.app] [--n 40] [--evidence]
    .venv/bin/python tests/e2e/api/prod.py --only cold        # one timed request + x-vercel-* headers

Measures: first-request (cold) time and x-vercel-* headers; per-endpoint latency; how often a freshly created
trial is found by follow-up requests (404 rate over --n sequential requests); step days=30 against maxDuration 60;
rewrites (/api/*, deep links, /assets/* cache headers); CORS; static bundle size; /api/evidence/run (time-boxed).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import Client, dump, privacy_scan  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
VH = lambda r: {k: v for k, v in r.headers.items() if k.lower().startswith(("x-vercel", "age", "cache-control", "server", "x-matched"))}  # noqa: E731


def cold(base):
    t = time.perf_counter()
    r = requests.get(base + "/api/health", timeout=90)
    dt = time.perf_counter() - t
    body = r.json() if r.ok else r.text[:200]
    out = {"ms": round(dt * 1000), "status": r.status_code, "headers": VH(r),
           "instance_trials": len(body.get("trials", [])) if isinstance(body, dict) else None,
           "gemini": body.get("gemini") if isinstance(body, dict) else None, "at": time.strftime("%H:%M:%S")}
    print("cold/first request:", json.dumps(out))
    return out


def burst(base, n=16):
    """n concurrent first requests: Vercel must start new instances; a fresh one reports 0 trials and is slow."""
    from concurrent.futures import ThreadPoolExecutor

    def one(_):
        t = time.perf_counter()
        r = requests.get(base + "/api/health", timeout=90)
        return {"ms": round((time.perf_counter() - t) * 1000), "status": r.status_code,
                "instance_trials": len(r.json().get("trials", [])) if r.ok else None,
                "vercel_id": r.headers.get("x-vercel-id")}
    with ThreadPoolExecutor(n) as ex:
        rows = list(ex.map(one, range(n)))
    fresh = [r["ms"] for r in rows if r["instance_trials"] == 0]
    warm = [r["ms"] for r in rows if r["instance_trials"]]
    out = {"rows": rows, "fresh_instance_ms": sorted(fresh), "warm_instance_ms": sorted(warm)}
    print("burst:", json.dumps({k: v for k, v in out.items() if k != "rows"}))
    return out


def reliability(c: Client, base: str, n: int):
    """Create a trial, then n sequential follow-ups. Each follow-up also reports how many trials its instance holds."""
    r = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "auto_approve": True}, key="POST trials")
    st = r.json()
    tid = st["trial_id"]
    print(f"created {tid} in {c.log[-1]['ms']} ms ({r.headers.get('x-vercel-id')})")
    rows = []
    for i in range(n):
        path = [f"/api/trials/{tid}/state", f"/api/trials/{tid}/approvals", f"/api/trials/{tid}/kpis",
                f"/api/trials/{tid}/events?limit=20"][i % 4]
        rr = c.get(path)
        h = c.get("/api/health", key="GET /api/health (probe)")
        hb = h.json() if h.ok else {}
        rows.append({"i": i, "path": path.split(tid)[1], "status": rr.status_code, "ms": c.log[-2]["ms"],
                     "vercel_id": rr.headers.get("x-vercel-id"), "probe_has_trial": tid in hb.get("trials", []),
                     "probe_instance_trials": len(hb.get("trials", []))})
    cnt = collections.Counter(r["status"] for r in rows)
    print(f"{n} follow-ups: {dict(cnt)}  404 rate {cnt.get(404, 0) / n:.0%}")
    sigs = collections.Counter(r["probe_instance_trials"] for r in rows)
    print("health probe 'trials on this instance' counts seen:", dict(sigs))
    return {"trial": tid, "statuses": dict(cnt), "rate_404": round(cnt.get(404, 0) / n, 3), "rows": rows}


def step30(c: Client, tries: int = 25):
    """Step a trial to close in 30-day jumps, retrying 404s (instance miss). Records each successful step time."""
    st = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "auto_approve": True}).json()
    tid = st["trial_id"]
    times, misses, other = [], 0, []
    for _ in range(tries):
        r = c.post(f"/api/trials/{tid}/step", json={"days": 30}, key="POST step days=30 (prod)", timeout=90)
        ms = c.log[-1]["ms"]
        if r.status_code == 404:
            misses += 1
            continue
        if r.status_code != 200:
            other.append({"status": r.status_code, "ms": ms, "body": r.text[:200]})
            continue
        b = r.json()
        times.append({"ms": ms, "day": b.get("day"), "phase": b.get("phase"), "advanced": b.get("advanced")})
        if b.get("phase") == "closed" or b.get("day", 0) >= 90:
            break
    print(f"step30: successes {times} misses {misses} other {other}")
    return {"trial": tid, "ok": times, "misses_404": misses, "other": other}


def latency(c: Client, reps: int):
    name = "example_psilocybin_trd.md"
    for _ in range(reps):
        c.get("/api/health")
        c.get("/api/bottlenecks")
        c.get("/api/protocols")
        c.get(f"/api/protocols/{name}")
        c.get("/api/trials")
    for _ in range(max(2, reps // 3)):
        st = c.post("/api/trials", json={"example": name}).json()
        tid = st.get("trial_id")
        for p in ("state", "approvals", "record", "events", "kpis", "messages", "modules/predose/view",
                  "modules/dosing/view", "modules/postdose/view"):
            for _ in range(15):          # retry instance misses so every endpoint gets 200 samples
                if c.get(f"/api/trials/{tid}/{p}").status_code != 404:
                    break


def edges(base: str):
    out = {}
    s = requests.Session()
    idx = s.get(base + "/", timeout=30)
    assets = sorted(set(re.findall(r'(/assets/[^"\']+)', idx.text)))
    out["index"] = {"status": idx.status_code, "bytes": len(idx.content), "headers": VH(idx), "assets": assets}
    tot = {}
    for a in assets:
        r = s.get(base + a, headers={"Accept-Encoding": "gzip, br"}, timeout=30, stream=True)
        raw = r.raw.read()
        tot[a] = {"status": r.status_code, "wire_bytes": len(raw), "encoding": r.headers.get("content-encoding"),
                  "cache-control": r.headers.get("cache-control"), "content-type": r.headers.get("content-type"),
                  "x-vercel-cache": r.headers.get("x-vercel-cache")}
        r2 = s.get(base + a, timeout=30)
        tot[a]["decoded_bytes"] = len(r2.content)
    out["assets"] = tot
    for p in ["/predose", "/dosing", "/postdose", "/portal", "/mission", "/some/deep/link?x=1", "/assets/nope.js",
              "/api/nope", "/api", "/api/", "/api/health/", "/API/health", "/favicon.ico", "/index.html"]:
        r = s.get(base + p, timeout=30, allow_redirects=False)
        out[p] = {"status": r.status_code, "ctype": r.headers.get("content-type"), "bytes": len(r.content),
                  "is_spa_html": "<div id=\"root\"" in r.text, "head": r.text[:100], "headers": VH(r)}
    cors = {}
    for origin in ["https://evil.example", "http://localhost:5173", "https://parallax-two-tau.vercel.app"]:
        r = s.options(base + "/api/trials", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "content-type"}, timeout=30)
        g = s.get(base + "/api/health", headers={"Origin": origin}, timeout=30)
        cors[origin] = {"preflight_status": r.status_code, "preflight_acao": r.headers.get("access-control-allow-origin"),
                        "preflight_body": r.text[:80], "get_acao": g.headers.get("access-control-allow-origin")}
    out["cors"] = cors
    return out


def errors_and_privacy(c: Client):
    out = {}
    for p in ["/api/trials/T-NOPE/state", "/api/protocols/..%2F..%2Fbackend%2Fmain.py", "/api/protocols/%2Fetc%2Fpasswd",
              "/api/protocols/..%2F..%2Fapi%2Findex.py", "/api/protocols/nope.md"]:
        r = c.get(p, key="errors")
        out[p] = {"status": r.status_code, "body": r.text[:120]}
    r = c.post("/api/trials", json={"n_applicants": 5}, key="errors")
    out["create n_applicants=5"] = r.status_code
    lst = c.get("/api/trials").json()
    out["GET /api/trials count on this instance"] = len(lst)
    out["privacy GET /api/trials"] = privacy_scan(lst)[:5]
    return out


def evidence(base: str, budget: int):
    t = time.perf_counter()
    try:
        r = requests.post(base + "/api/evidence/run", json={"input": "psilocybin for treatment-resistant depression"},
                          timeout=budget)
        return {"status": r.status_code, "s": round(time.perf_counter() - t, 1), "bytes": len(r.content),
                "head": r.text[:300], "headers": VH(r)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "s": round(time.perf_counter() - t, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://parallax-two-tau.vercel.app")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--only", choices=["cold", "burst", "reliability", "step30", "edges", "latency", "evidence"])
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    c = Client(a.base, timeout=90)
    res = {"base": a.base, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if a.only in (None, "cold"):
        res["cold"] = cold(a.base)
    if a.only == "burst":
        res["burst"] = burst(a.base)
    if a.only in (None, "reliability"):
        res["reliability"] = reliability(c, a.base, a.n)
    if a.only in (None, "step30"):
        res["step30"] = step30(c)
    if a.only in (None, "latency"):
        latency(c, a.reps)
    if a.only is None:
        res["errors"] = errors_and_privacy(c)
    if a.only in (None, "edges"):
        res["edges"] = edges(a.base)
        print(json.dumps(res["edges"], indent=1)[:6000])
    if a.only == "evidence" or a.evidence:
        res["evidence"] = evidence(a.base, 75)
        print("evidence:", res["evidence"])
    res["latency"] = c.latency_table()
    res["latency_ok_only"] = c.latency_table(ok_only=True)
    res["status_counts"] = dict(collections.Counter(f"{r['method']} {r['status']}" for r in c.log))
    for row in res["latency_ok_only"]:
        print(f"{row['endpoint']:<50} n={row['n']:<3} p50={row['p50_ms']:>8} ms  max={row['max_ms']:>8} ms")
    print("status counts:", res["status_counts"])
    dump(res, os.path.join(RESULTS, f"prod_{a.only or 'all'}{a.label}.json"))


if __name__ == "__main__":
    main()
