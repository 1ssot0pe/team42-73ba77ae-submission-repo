"""J8: reject the clinician shortlist, then approve the re-request."""
from harness import JourneyAbort, create_trial, decide, fresh, now_line, slips, wait_slip

ID = "J8"
TITLE = "Reject the clinician shortlist, then approve the re-request"


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    err = decide(j, "confirm shortlist", "rejected", comment="Too many flagged; re-screen")
    j.check(err is None, f"reject shortlist: {err}")
    p.wait_for_timeout(1500)
    j.note(f"header after reject: {now_line(p)!r}; slips: {slips(p).locator('.slip__title').all_inner_texts()}")
    if not j.check(wait_slip(j, "shortlist", timeout=8000), "no re-requested shortlist slip after rejecting"):
        return
    err = decide(j, "shortlist", "approved")
    j.check(err is None, f"approve re-requested shortlist: {err}")
    p.wait_for_timeout(1500)
    j.check("Waiting" not in now_line(p), f"still blocked after approving the re-request: {now_line(p)!r}")
    p.goto("/predose")
    p.wait_for_timeout(1500)
    j.check("enrolled" in p.locator(".pd-page header").inner_text().lower(), "nobody enrolled after the re-request was approved")
