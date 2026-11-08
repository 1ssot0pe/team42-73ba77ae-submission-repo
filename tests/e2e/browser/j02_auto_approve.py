"""J2: auto-approve on from the start, then Play to close with no human input."""
from harness import JourneyAbort, copy_checks, create_trial, day_number, ensure_running, fresh, heading_text, now_line, play, slips

ID = "J2"
TITLE = "Auto-approve on, play to close"


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin", auto=True)
    if not tid:
        raise JourneyAbort("trial was not created")
    j.note(f"trial {tid}")
    j.check(p.locator(".mc-dock").get_by_label("Auto-approve (demo)").is_checked(), "dock auto-approve switch is not on")
    j.check(slips(p).count() == 0, f"{slips(p).count()} slips still pending with auto-approve on")
    with j.timed("play_to_close"):
        r = play(j, timeout_s=240)
    ensure_running(j, "while playing")
    j.check(day_number(p) == 90 and "90" in heading_text(p), f"did not reach day 90 (play ended: {r}, day {day_number(p)})")
    p.wait_for_timeout(1000)
    j.check(slips(p).count() == 0, f"{slips(p).count()} slips pending at close with auto-approve on")
    stamps = p.locator(".stamp").all_inner_texts()
    j.check(any("AUTO-APPROVED" in s.upper() for s in stamps), f"no 'Auto-approved (demo)' stamps: {stamps[:4]}")
    j.note(f"header at close: {now_line(p)!r}")
    j.check("waiting for a human" not in now_line(p).lower(), f"closed trial still waiting: {now_line(p)!r}")
    copy_checks(j, "mission control (auto) at close")
