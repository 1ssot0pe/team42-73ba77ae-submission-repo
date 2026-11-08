"""J3: MDMA for PTSD to close. Every outcome label must say CAPS-5 (never MADRS); drift is at Site C."""
import re

from harness import JourneyAbort, create_trial, day_number, decide, ensure_running, fresh, play, slips

ID = "J3"
TITLE = "MDMA example to close: CAPS-5 labels everywhere, drift at Site C"


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "MDMA")
    if not tid:
        raise JourneyAbort("trial was not created")
    j.note(f"trial {tid}")
    err = decide(j, "confirm shortlist")
    j.check(err is None, f"approve shortlist: {err}")
    with j.timed("play_to_drift"):
        r = play(j, stop_when=lambda: slips(p, "raters to remote").count() > 0, timeout_s=180)
    ensure_running(j, "while playing")
    if j.check(r == "condition", f"no drift slip while playing (ended: {r}, day {day_number(p)})"):
        title = slips(p, "raters to remote").first.locator(".slip__title").inner_text()
        j.note(f"drift slip at day {day_number(p)}: {title}")
        j.check("Site C" in title, f"drift is not at Site C: {title!r}")
        decide(j, "raters to remote")
    with j.timed("play_to_close"):
        play(j, timeout_s=240)
    ensure_running(j, "while playing to close")
    j.check(day_number(p) == 90, f"did not reach day 90 (day {day_number(p)})")

    for path in ("/", "/predose", "/dosing", "/postdose"):
        p.goto(path)
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1500)
        txt = p.evaluate("document.body.innerText")
        madrs = sorted({ln.strip()[:120] for ln in txt.split("\n") if re.search(r"MADRS", ln)})
        j.check(not madrs, f"[{path}] MADRS label in an MDMA/PTSD trial: {madrs[:4]}")
        if path in ("/dosing", "/postdose"):
            j.check("CAPS-5" in txt, f"[{path}] no CAPS-5 label anywhere on the page")
