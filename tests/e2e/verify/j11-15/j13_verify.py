"""J13 verification (j11-15 verifier): Play 2 minutes through the round-robin proxy, kill backend 8331 at
~60 s (the trial must continue through 8332), 30-day API steps, then delete the trial's files from the
shared store mid-session and confirm the TrialLost screen and its "Start a new trial" button.

  .venv/bin/python tests/e2e/verify/j11-15/j13_verify.py --base-url http://127.0.0.1:5331 --prefix verify \
      --out tests/e2e/verify/j11-15/j13.json
Env: KILL_PORT (default 8331), STORE (default /tmp/parallax-verify-j1115/store).
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tests/e2e/browser"))
from playwright.sync_api import sync_playwright  # noqa: E402

from harness import JourneyAbort, create_trial, day_number, dock_button, parse_args, run_journey, running  # noqa: E402

KILL_PORT = os.environ.get("KILL_PORT", "8331")
STORE = Path(os.environ.get("STORE", "/tmp/parallax-verify-j1115/store"))


def kill_port(port: str) -> list:
    out = subprocess.run(["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
    for pid in out:
        os.kill(int(pid), signal.SIGKILL)
    return out


class J13:
    ID = "J13"
    TITLE = "Play 2 min via proxy, kill one backend mid-play, 30-day step, trial-lost screen"

    @staticmethod
    def run(j):
        p = j.page
        lat, statuses = [], {}

        def on_resp(r):
            if "/api/" in r.url:
                statuses.setdefault(r.status, 0)
                statuses[r.status] += 1

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
                if killed_at is None and time.time() - t0 > 60:
                    pids = kill_port(KILL_PORT)
                    killed_at = round(time.time() - t0, 1)
                    j.note(f"killed backend :{KILL_PORT} (pids {pids}) at t={killed_at}s, day {day_number(p)}")
                    j.shot("just after killing one backend", full_page=False)
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
            j.timings["step_max_ms"] = round(lat[-1])
        j.timings["stalls"] = stalls
        j.note(f"play: {trials} trials, {days} days, step calls {len(lat)}, stalls {stalls}, lost {lost_events}; "
               f"API statuses {statuses}")
        j.timings["api_status_counts"] = dict(statuses)

        # 30-day steps through the proxy (8331 is dead: half of these go to a dead backend at the proxy)
        if not running(p):
            create_trial(j, "psilocybin", auto=True, settle_s=0.5)
        tid = p.evaluate("localStorage.getItem('unblind.trialId')")
        for n in (30, 30, 31):
            t = time.time()
            r = p.request.post(f"{j.base_url}/api/trials/{tid}/step", data={"days": n})
            dt = time.time() - t
            body = r.json() if r.ok else r.text()[:200]
            day = body.get("state", {}).get("day") if isinstance(body, dict) else None
            j.note(f"API step {n} days: HTTP {r.status} via {r.headers.get('x-rr-backend')} in {dt:.2f}s, day now {day}")
            j.timings.setdefault("api_step_s", []).append(round(dt, 2))
        p.reload()
        p.wait_for_timeout(2000)
        j.check(running(p), "trial not shown after the 30-day steps and a reload (one backend dead)")

        # Trial-lost: delete this trial's files from the shared store
        if dock_button(p, "Play").count() and dock_button(p, "Play").is_enabled():
            dock_button(p, "Play").click()
        p.wait_for_timeout(800)
        files = sorted(STORE.glob(f"{tid}*"))
        for f in files:
            f.unlink()
        j.note(f"deleted {[f.name for f in files]} for {tid} at t={round(time.time() - t0)}s")
        t_del = time.time()
        alert = p.get_by_text(f"Trial {tid} has expired")
        try:
            alert.wait_for(timeout=40000)
            j.timings["trial_lost_screen_s"] = round(time.time() - t_del, 1)
            j.shot("trial lost screen")
        except Exception:
            j.check(False, "TrialLost screen did not appear within 40 s of deleting the trial files")
            return
        btn = p.get_by_role("button", name="Start a new trial")
        j.check(btn.is_visible(), "Start a new trial button missing on TrialLost")
        btn.click()
        p.wait_for_timeout(1000)
        ok = p.get_by_role("heading", name="Start a trial").is_visible()
        j.check(ok, f"Start a new trial did not open the start page (url {p.url})")
        j.check(p.evaluate("localStorage.getItem('unblind.trialId')") is None, "stored trial id not cleared")
        j.shot("after Start a new trial")
        if ok and create_trial(j, "psilocybin", auto=True, settle_s=1):
            j.note("new trial created after TrialLost")


if __name__ == "__main__":
    a = parse_args()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not a.headed)
        res = run_journey(b, J13, a.base_url, a.env, a.prefix)
        b.close()
    Path(a.out or "j13.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: res[k] for k in ("passed", "timings", "failures", "notes")}, indent=2)[:4000])
