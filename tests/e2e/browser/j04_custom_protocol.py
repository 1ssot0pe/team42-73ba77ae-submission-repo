"""J4: a pasted custom protocol with other site names. The app must use the pasted sites, not the example's."""
import re

from harness import JourneyAbort, create_trial, day_number, decide, fresh, play, slips

ID = "J4"
TITLE = "Pasted custom protocol with other site names"

PROTOCOL = """# DRAFT protocol: Psilocybin for anorexia nervosa (QA custom)

## Design
A randomised, double-blind trial in 40 adults at three sites: Site A (Leeds), Site B (Glasgow) and Site C (Cardiff).
Participants receive psilocybin 25 mg or an identical-appearing inert placebo capsule.

## Outcomes
The primary outcome is change from baseline in MADRS total score at week 6.
MADRS is administered by the site psychiatrist, who is present during the dosing session.

## Population
Inclusion criteria:
- Adults aged 18 to 65
- Major depressive episode with at least two failed antidepressant treatments
Exclusion criteria:
- Personal history of psychosis or bipolar disorder
- Pregnancy or breastfeeding
"""
OLD = ("London", "Manchester", "Bristol")
NEW = ("Leeds", "Glasgow", "Cardiff")


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, example=None, text=PROTOCOL)
    if not tid:
        raise JourneyAbort("trial was not created from pasted text")
    j.note(f"trial {tid}")
    err = decide(j, "confirm shortlist")
    j.check(err is None, f"approve shortlist: {err}")
    with j.timed("play_to_drift_or_close"):
        play(j, stop_when=lambda: slips(p, "raters to remote").count() > 0, timeout_s=180)
    if slips(p, "raters to remote").count():
        t = slips(p, "raters to remote").first.locator(".slip__title").inner_text()
        j.note(f"drift slip day {day_number(p)}: {t}")
        decide(j, "raters to remote")
        play(j, timeout_s=240)
    seen_old, seen_new = set(), set()
    for path in ("/", "/predose", "/dosing", "/postdose"):
        p.goto(path)
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1200)
        txt = p.evaluate("document.body.innerText")
        for o in OLD:
            if o in txt:
                seen_old.add(f"{o}@{path}: " + next(ln.strip()[:100] for ln in txt.split("\n") if o in ln))
        seen_new |= {n for n in NEW if n in txt}
    j.check(not seen_old, f"example site names leak into a custom-protocol trial: {sorted(seen_old)[:5]}")
    j.check(bool(seen_new), "none of the pasted site names (Leeds, Glasgow, Cardiff) appear anywhere")
    j.note(f"pasted site names seen: {sorted(seen_new)}")
    p.goto("/predose")
    p.wait_for_timeout(1500)
    title = p.locator(".pd-page header p").first.inner_text()
    j.check("anorexia" in title.lower(), f"pre-dosing header does not show the pasted title: {title[:120]!r}")
