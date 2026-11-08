"""Quick smoke check of a deployment of the redesigned UI (J1, J5 and J12 in spirit).

    .venv/bin/python tests/e2e/smoke/prod_smoke.py --base-url https://parallax-two-tau.vercel.app
    (protected previews: PARALLAX_BYPASS_FILE=.vercel/bypass-token; the secret is never printed)

API part
  J1  psilocybin, manual approvals: approve everything pending, step to close, sign the FDA report.
  J5  garbage protocol "!!! ???": what happens (BL-6 is a known open item: it is accepted).
  burst: 12 parallel reads plus a step, 10 times, counting "trial not found" 404s (must be 0).
Browser part (J12)
  The J1 trial opened as a project in the workspace; every stage plus Home and Trials, in light and dark,
  at 1440 and 390 px: console errors, failed requests, horizontal scroll, screenshot per page.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHOTS = ROOT / "docs" / "testing" / "screenshots"
STAGES = ["draft", "design-review", "recruitment", "screening", "dosing", "follow-up", "report"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--prefix", default="smoke")
    ap.add_argument("--out", default=str(ROOT / "tests/e2e/smoke/results.json"))
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    bf = os.environ.get("PARALLAX_BYPASS_FILE")
    secret = Path(bf).read_text().strip() if bf else None
    if secret:
        headers["x-vercel-protection-bypass"] = secret
    out = {"base_url": base, "api": {}, "browser": {}, "problems": []}
    lat = {}
    n404 = [0]

    def call(method, path, body=None, name=None):
        req = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=70) as r:
                code, data = r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            code, data = e.code, None
        if name:
            lat.setdefault(name, []).append(1000 * (time.perf_counter() - t))
        if code == 404 and "/api/trials/" in path:
            n404[0] += 1
        return code, data

    # ---------------- J1 (API)
    code, st = call("POST", "/api/trials", {"example": "example_psilocybin_trd.md", "auto_approve": False}, "create")
    assert code == 200, f"create failed: {code}"
    tid = st["trial_id"]
    approvals = 0
    for _ in range(60):
        _, pend = call("GET", f"/api/trials/{tid}/approvals", name="read")
        for ap_ in pend or []:
            if "report_signoff" in (ap_.get("kind"), ap_.get("type")) or "FDA blinding report" in ap_.get("title", ""):
                continue                                  # signed below through the postdose action
            c, _ = call("POST", f"/api/trials/{tid}/approvals/{ap_['id']}",
                        {"reviewer": "Smoke Test", "decision": "approved"}, "approve")
            approvals += c == 200
        c, res = call("POST", f"/api/trials/{tid}/step", {"days": 7}, "step")
        if c != 200:
            out["problems"].append(f"J1 step returned {c}")
            break
        s = res["state"]
        if s.get("day", 0) >= s.get("close_day", 90) and not s.get("blocked"):
            break
        if s.get("blocked") and "report" not in str(s.get("blocked")).lower() and not pend:
            pass
    _, s = call("GET", f"/api/trials/{tid}/state")
    c, sign = call("POST", f"/api/trials/{tid}/modules/postdose/actions/sign_off",
                   {"payload": {"reviewer": "Smoke Test", "decision": "approved"}}, "approve")
    _, rep = call("GET", f"/api/trials/{tid}/record?sections=report")
    out["api"]["J1"] = {"trial": tid, "approvals_signed": approvals, "final_day": s["day"], "phase": s["phase"],
                        "report_signoff": (sign or {}).get("result"), "report_status": ((rep or {}).get("report") or {}).get("status")}
    if s["day"] < 90:
        out["problems"].append(f"J1 did not reach day 90 (day {s['day']}, blocked: {s.get('blocked')})")
    if ((rep or {}).get("report") or {}).get("status") not in ("approved", "signed", "final"):
        out["problems"].append(f"J1 report not signed: {out['api']['J1']['report_status']} / {out['api']['J1']['report_signoff']}")

    # ---------------- J5 (API)
    c, g = call("POST", "/api/trials", {"protocol_text": "!!! ???", "auto_approve": True}, "create")
    out["api"]["J5"] = {"status": c, "trial": (g or {}).get("trial_id"), "phase": (g or {}).get("phase"),
                        "note": "BL-6 (known open): garbage is accepted as a trial" if c == 200 else "rejected"}

    # ---------------- burst
    gets = ["state", "kpis", "messages", "events?limit=50", "approvals", "record?sections=protocol"]
    with ThreadPoolExecutor(8) as ex:
        for _ in range(10):
            list(ex.map(lambda g: call("GET", f"/api/trials/{tid}/{g}", name="burst_read"), gets * 2))
    out["api"]["trial_not_found_404s"] = n404[0]
    if n404[0]:
        out["problems"].append(f"{n404[0]} 'trial not found' 404s")
    out["api"]["latency_ms"] = {k: {"n": len(v), "p50": round(statistics.median(v)),
                                    "p95": round(sorted(v)[min(len(v) - 1, round(0.95 * (len(v) - 1)))])}
                                for k, v in lat.items()}

    # ---------------- J12 (browser)
    from playwright.sync_api import sync_playwright
    project = {"id": "smoke-" + tid.lower(), "name": "Smoke test (psilocybin)", "createdAt": "2026-11-08T00:00:00Z",
               "updatedAt": "2026-11-08T00:00:00Z", "template": "blank", "draft": "", "trialId": tid, "status": "running"}
    pages = ["/", "/trials"] + [f"/trials/{project['id']}/{st_}" for st_ in STAGES]
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for scheme in ("light", "dark"):
            for w, h in ((1440, 900), (390, 844)):
                ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
                if secret:
                    ctx.route(f"{base}/**", lambda r: r.continue_(headers={**r.request.headers,
                                                                          "x-vercel-protection-bypass": secret}))
                ctx.add_init_script(f"localStorage.setItem('parallax.projects.v1', {json.dumps(json.dumps([project]))});")
                pg = ctx.new_page()
                errs, fails = [], []
                pg.on("console", lambda m: errs.append(m.text[:200]) if m.type == "error" else None)
                pg.on("response", lambda r: fails.append(f"{r.status} {r.url.replace(base, '')}")
                      if r.status >= 400 and base in r.url else None)
                for path in pages:
                    key = f"{scheme}-{w}{path.replace('/', '_') or '_home'}"
                    t = time.perf_counter()
                    pg.goto(base + path, wait_until="networkidle")
                    pg.wait_for_timeout(600)
                    overflow = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    lost = pg.get_by_text("has expired").count()
                    shot = SHOTS / f"{a.prefix}-J12-{key.replace('_', '-')}.png"
                    pg.screenshot(path=str(shot))
                    out["browser"][key] = {"ms": round(1000 * (time.perf_counter() - t)), "h_overflow_px": overflow,
                                           "trial_lost_screen": bool(lost)}
                    if overflow > 0:
                        out["problems"].append(f"horizontal scroll {overflow}px on {path} ({scheme}, {w}px)")
                    if lost:
                        out["problems"].append(f"trial-lost screen on {path} ({scheme}, {w}px)")
                out["browser"][f"{scheme}-{w}-console_errors"] = errs
                out["browser"][f"{scheme}-{w}-failed_requests"] = fails
                if errs:
                    out["problems"].append(f"{len(errs)} console errors ({scheme}, {w}px): {errs[:2]}")
                if fails:
                    out["problems"].append(f"failed requests ({scheme}, {w}px): {fails[:3]}")
                ctx.close()
        b.close()
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({"api": out["api"], "problems": out["problems"]}, indent=1))


if __name__ == "__main__":
    main()
