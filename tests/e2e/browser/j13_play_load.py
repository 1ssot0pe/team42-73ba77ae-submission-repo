"""J13: Play continuously for 2 minutes (new trials as each closes), then a 30-day step at once."""
import time

from harness import JourneyAbort, create_trial, day_number, dock_button, running

ID = "J13"
TITLE = "Play for 2 minutes under polling load; step 30 days at once"


def run(j):
    p = j.page
    lat = []

    def on_done(req):
        if "/step" in req.url:
            t = req.timing
            lat.append(t["responseEnd"] - t["requestStart"] if t["responseEnd"] > 0 else None)
    p.on("requestfinished", on_done)
    p.goto("/")
    p.evaluate("localStorage.clear()")
    p.goto("/")
    t_end = time.time() + 120
    trials, days = 0, 0
    while time.time() < t_end:
        if not running(p):
            if not create_trial(j, "psilocybin", auto=True, settle_s=0.5):
                raise JourneyAbort("could not create a trial")
            trials += 1
        start = day_number(p) or -1
        dock_button(p, "Play").click()
        while time.time() < t_end:
            p.wait_for_timeout(500)
            if not running(p):
                j.check(False, f"trial lost during play at {day_number(p)}")
                break
            if dock_button(p, "Play").count():
                break
        days += (day_number(p) or 0) - start
        if dock_button(p, "Pause").count():
            dock_button(p, "Pause").click()
            p.wait_for_timeout(600)
        if running(p) and day_number(p) == 90:
            p.locator(".mc-dock").get_by_role("button", name="New trial").click()
            p.wait_for_timeout(500)
        elif running(p):
            j.check(False, f"play stopped early at day {day_number(p)}: toasts {j.toasts()[-3:]}")
            break
    ok = [x for x in lat if x is not None]
    ok.sort()
    j.note(f"2 minutes: {trials} trials, {days} simulated days, {len(lat)} step calls, step latency ms "
           f"p50={ok[len(ok) // 2]:.0f} max={ok[-1]:.0f}" if ok else "no step timings")
    j.timings["play_2min_step_calls"] = len(lat)
    if ok:
        j.timings["step_p50_ms"] = round(ok[len(ok) // 2])
        j.timings["step_max_ms"] = round(ok[-1])

    # 30 days at once (the server clamps 1..30); the UI only offers +1 week, so call the API the app uses
    if not running(p):
        create_trial(j, "psilocybin", auto=True, settle_s=0.5)
    tid = p.evaluate("localStorage.getItem('unblind.trialId')")
    for n in (30, 31):
        t = time.time()
        r = p.request.post(f"{j.base_url}/api/trials/{tid}/step", data={"days": n})
        dt = time.time() - t
        body = r.json() if r.ok else r.text()[:200]
        day = body.get("state", {}).get("day") if isinstance(body, dict) else None
        j.note(f"step {n} days: HTTP {r.status} in {dt:.2f}s, day now {day}")
        j.timings[f"api_step_{n}_s"] = round(dt, 2)
        j.check(r.ok, f"step {n} days failed: HTTP {r.status} {body}")
    p.reload()
    p.wait_for_timeout(1500)
    j.check(running(p), "trial not shown after the 30-day steps and a reload")
