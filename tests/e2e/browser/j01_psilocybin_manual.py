import time
"""J1: psilocybin example with manual approvals, from creation to a signed FDA blinding report."""
from harness import JourneyAbort, copy_checks, create_trial, day_number, decide, ensure_running, fresh, heading_text, \
    now_line, play, slips

ID = "J1"
TITLE = "Psilocybin, manual approvals: 2 fixes, shortlist, drift action, amendment, FDA report"


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    j.note(f"trial {tid}")
    j.check(slips(p).count() >= 6, f"expected 6 pending slips after creation, saw {slips(p).count()}")

    # Two fixes other than "central raters" (approving that one means the drift amendment is never proposed).
    for fix in ("guess questionnaire", "expectancy"):
        err = decide(j, f"^Protocol fix.*{fix}")
        j.check(err is None, f"sign protocol fix '{fix}': {err}")
        ensure_running(j, f"after protocol fix '{fix}'")
    err = decide(j, "confirm shortlist")
    j.check(err is None, f"approve clinician shortlist: {err}")
    ensure_running(j, "after the shortlist")
    # the header follows the next state refresh: ~0.1 s locally, up to ~1 s on Vercel
    t0 = time.time()
    while "Waiting" in now_line(p) and time.time() - t0 < 8:
        p.wait_for_timeout(250)
    j.check("Waiting" not in now_line(p), f"still blocked after the shortlist: {now_line(p)!r}")

    with j.timed("play_to_drift"):
        r = play(j, stop_when=lambda: slips(p, "raters to remote").count() > 0, timeout_s=180)
    ensure_running(j, "while playing to the drift alert")
    if not j.check(r == "condition", f"drift action slip never appeared while playing (play ended: {r}, day {day_number(p)})"):
        return
    j.note(f"drift action slip at day {day_number(p)}")
    err = decide(j, "raters to remote")
    j.check(err is None, f"approve drift action: {err}")

    with j.timed("play_to_amendment"):
        r = play(j, stop_when=lambda: slips(p, "permanent").count() > 0, timeout_s=120)
    ensure_running(j, "while playing to the amendment")
    if j.check(r == "condition", f"follow-up amendment slip never appeared (play ended: {r}, day {day_number(p)})"):
        err = decide(j, "permanent")
        j.check(err is None, f"approve follow-up amendment: {err}")

    with j.timed("play_to_close"):
        r = play(j, timeout_s=240)
    ensure_running(j, "while playing to close")
    h = heading_text(p)
    j.check("90" in h and day_number(p) == 90, f"play did not reach day 90 (heading {h!r}, play ended: {r})")
    t0 = time.time()
    while slips(p, "Sign off the FDA blinding report").count() == 0 and time.time() - t0 < 8:
        p.wait_for_timeout(250)
    j.check(slips(p, "Sign off the FDA blinding report").count() == 1, "no FDA report sign-off slip at close")
    err = decide(j, "Sign off the FDA blinding report")
    j.check(err is None, f"sign the FDA report: {err}")
    p.wait_for_timeout(1000)
    j.check("signed" in now_line(p).lower(), f"header does not say the report is signed: {now_line(p)!r}")
    j.check(p.locator(".seal").count() > 0, "no 'Report signed' seal after signing")
    copy_checks(j, "mission control at close")
    j.shot("closed and signed", full_page=False)
