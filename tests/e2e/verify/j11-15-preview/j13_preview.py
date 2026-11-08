"""Preview J13 (verifier): 2-minute Play against the protected preview, step latency p50/p90/p95 from the
browser, count of 404s on /api/trials/, then 30-day API steps. No backend kill, no store deletion.
  PARALLAX_BYPASS_FILE=.vercel/bypass-token .venv/bin/python tests/e2e/verify/j11-15-preview/j13_preview.py \
      --base-url $PREVIEW --env preview-j11-15 --prefix preview --out tests/e2e/verify/j11-15-preview/j13.json
Screenshots are written as <prefix>-J13-play-<n>.png.
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tests/e2e/browser"))
from playwright.sync_api import sync_playwright  # noqa: E402

from harness import JourneyAbort, create_trial, day_number, dock_button, parse_args, run_journey, running  # noqa: E402


class J13:
    ID = "J13-play"
    TITLE = "Preview: Play 2 min (no backend kill), 30-day API steps, 404 count"

    @staticmethod
    def run(j):
        p = j.page
        lat, statuses, trial404 = [], {}, []

        def on_resp(r):
            if "/api/" in r.url:
                statuses.setdefault(r.status, 0)
                statuses[r.status] += 1
                if r.status == 404 and "/api/trials/" in r.url:
                    trial404.append(r.url)

        def on_done(req):
            if "/step" in req.url:
                t = req.timing
                if t["responseEnd"] > 0:
                    lat.append(t["responseEnd"] - t["requestStart"])
        p.on("response", on_resp)
        p.on("requestfinished", on_done)
        p.goto("/")
        p.evaluate("localStorage.clear()")
        p.goto("/")
        t0 = time.time()
        t_end = t0 + 120
        killed_at = None
        trials, days, lost_events, stalls = 0, 0, 0, 0
        last_day, last_change = None, time.time()
        while time.time() < t_end:
            if not running(p):
                if not create_trial(j, "psilocybin", auto=True, settle_s=0.5):
                    raise JourneyAbort("could not create a trial")
                trials += 1
            start = day_number(p) or -1
            if dock_button(p, "Play").count():
                dock_button(p, "Play").click()
            while time.time() < t_end:
                p.wait_for_timeout(500)
                if not running(p):
                    lost_events += 1
                    j.check(False, f"trial lost during play at day {day_number(p)}; toasts {j.toasts()[-3:]}")
                    break
                d = day_number(p)
                if d != last_day:
                    last_day, last_change = d, time.time()
                elif dock_button(p, "Pause").count() and time.time() - last_change > 8:
                    stalls += 1
                    j.note(f"stall: day {d} unchanged for 8 s while playing (t={round(time.time() - t0)}s)")
                    last_change = time.time()
                if dock_button(p, "Play").count():
                    break
            days += (day_number(p) or 0) - start
            if dock_button(p, "Pause").count():
                dock_button(p, "Pause").click()
                p.wait_for_timeout(600)
            if running(p) and day_number(p) == 90:
                p.locator(".mc-dock").get_by_role("button", name="New trial").click()
                p.wait_for_timeout(500)
            elif running(p) and time.time() < t_end:
                j.check(False, f"play stopped early at day {day_number(p)}: toasts {j.toasts()[-3:]}")
                break
        lat.sort()
        j.timings["play_trials"] = trials
        j.timings["play_days"] = days
        j.timings["step_calls"] = len(lat)
        if lat:
            j.timings["step_p50_ms"] = round(lat[len(lat) // 2])
            j.timings["step_p90_ms"] = round(lat[int(len(lat) * 0.9)])
            j.timings["step_p95_ms"] = round(lat[min(len(lat) - 1, int(len(lat) * 0.95))])
            j.timings["step_max_ms"] = round(lat[-1])
        j.timings["stalls"] = stalls
        j.note(f"play: {trials} trials, {days} days, step calls {len(lat)}, stalls {stalls}, lost {lost_events}; "
               f"API statuses {statuses}")
        j.timings["api_status_counts"] = dict(statuses)

        j.timings["trial_404s"] = len(trial404)
        j.check(not trial404, f"404s on /api/trials/: {trial404[:5]}")
        # 30-day API steps (bypass header added explicitly: page.request is not routed)
        hdr = {}
        bf = os.environ.get("PARALLAX_BYPASS_FILE")
        if bf:
            hdr["x-vercel-protection-bypass"] = Path(bf).read_text().strip()
        if not running(p):
            create_trial(j, "psilocybin", auto=True, settle_s=0.5)
        tid = p.evaluate("localStorage.getItem('unblind.trialId')")
        for n in (30, 30, 31):
            t = time.time()
            r = p.request.post(f"{j.base_url}/api/trials/{tid}/step", data={"days": n}, headers=hdr)
            dt = time.time() - t
            body = r.json() if r.ok else r.text()[:200]
            day = body.get("state", {}).get("day") if isinstance(body, dict) else None
            j.note(f"API step {n} days: HTTP {r.status} in {dt:.2f}s, day now {day}")
            j.timings.setdefault("api_step_s", []).append(round(dt, 2))
        p.reload()
        p.wait_for_timeout(2500)
        j.check(running(p), "trial not shown after the 30-day steps and a reload")
        j.shot("after 30-day steps and reload", full_page=False)


if __name__ == "__main__":
    a = parse_args()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not a.headed)
        res = run_journey(b, J13, a.base_url, a.env, a.prefix)
        b.close()
    Path(a.out or "j13.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: res[k] for k in ("passed", "timings", "failures", "notes")}, indent=2)[:4000])
