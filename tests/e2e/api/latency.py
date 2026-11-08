"""Sequential latency of create, step and approve against a deployment (p50 / p95, in ms).

    PARALLAX_BYPASS_FILE=.vercel/bypass-token .venv/bin/python tests/e2e/api/latency.py --base-url <url> [--trials 8]

The bypass secret (for protected previews) is read from the file and never printed.
Trials are created with manual approvals so every pending approval can be timed; each trial
approves what is pending, then steps a week at a time until it is blocked or closed.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, round(q * (len(v) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--trials", type=int, default=8)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    bf = os.environ.get("PARALLAX_BYPASS_FILE")
    if bf:
        headers["x-vercel-protection-bypass"] = Path(bf).read_text().strip()

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=70) as r:
                code, data = r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            code, data = e.code, None
        return code, data, 1000 * (time.perf_counter() - t)

    lat = {"create": [], "step": [], "approve": [], "state": []}
    errors = {}
    examples = ["example_psilocybin_trd.md", "example_mdma_ptsd.md"]
    for i in range(a.trials):
        code, st, ms = call("POST", "/api/trials", {"example": examples[i % 2], "auto_approve": False})
        lat["create"].append(ms)
        if code != 200:
            errors[f"create {code}"] = errors.get(f"create {code}", 0) + 1
            continue
        tid = st["trial_id"]
        for _ in range(40):
            code, pend, ms = call("GET", f"/api/trials/{tid}/approvals")
            lat["state"].append(ms)
            for ap_ in (pend or [])[:3]:
                c, _, ms = call("POST", f"/api/trials/{tid}/approvals/{ap_['id']}",
                                {"reviewer": "Latency Bot", "decision": "approved"})
                lat["approve"].append(ms)
                if c != 200:
                    errors[f"approve {c}"] = errors.get(f"approve {c}", 0) + 1
            c, res, ms = call("POST", f"/api/trials/{tid}/step", {"days": 7})
            lat["step"].append(ms)
            if c != 200:
                errors[f"step {c}"] = errors.get(f"step {c}", 0) + 1
                break
            s = res["state"]
            if s.get("phase") in ("closed", "complete") or s.get("day", 0) >= s.get("close_day", 90):
                break
    out = {k: {"n": len(v), "p50": round(statistics.median(v)), "p95": round(pct(v, 0.95)), "max": round(max(v))}
           for k, v in lat.items() if v}
    out["errors"] = errors
    print(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
