"""J9: the drift action approved in one trial and rejected in another; each outcome must show in the UI."""
from harness import JourneyAbort, create_trial, day_number, decide, fresh, play, slips

ID = "J9"
TITLE = "Drift action approved vs rejected"


def one(j, decision):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort(f"trial was not created ({decision})")
    decide(j, "confirm shortlist")
    with j.timed(f"play_to_drift:{decision}"):
        r = play(j, stop_when=lambda: slips(p, "raters to remote").count() > 0, timeout_s=180)
    if not j.check(r == "condition", f"[{decision}] no drift slip (play ended {r}, day {day_number(p)})"):
        return
    d0 = day_number(p)
    err = decide(j, "raters to remote", decision, comment=f"QA {decision}")
    j.check(err is None, f"[{decision}] decide drift action: {err}")
    p.wait_for_timeout(1000)
    stamp = p.locator(".inbox__signed .stamp").all_inner_texts()
    want = "APPROVED" if decision == "approved" else "REJECTED"
    j.check(any(want in s.upper() for s in stamp), f"[{decision}] no {want} stamp in Recently signed: {stamp[:3]}")
    play(j, stop_when=lambda: (day_number(p) or 0) >= d0 + 20, timeout_s=120)
    p.goto("/dosing")
    p.locator(".log, [class*=agent-log], [class*=log]").first.wait_for(timeout=10000)
    p.wait_for_timeout(1500)
    txt = p.evaluate("document.body.innerText")
    if decision == "approved":
        j.check("Applied the action approved by" in txt or "moved to remote" in txt,
                "[approved] dosing page does not show the drift action being applied")
    else:
        j.check("rejected" in txt.lower() and "Monitoring continues" in txt,
                "[rejected] dosing page does not show the rejection and continued monitoring")
    j.note(f"[{decision}] drift decided at day {d0}; pending slips after +20 days: "
           f"{slips(p).locator('.slip__title').all_inner_texts()}")


def run(j):
    one(j, "approved")
    one(j, "rejected")
