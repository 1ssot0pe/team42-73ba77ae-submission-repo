"""J5: a garbage protocol ('!!! ???'). Expect either a clear refusal or a trial that degrades gracefully, never a crash."""
from harness import copy_checks, fresh, now_line, on_start_page, running, trial_id

ID = "J5"
TITLE = "Garbage protocol (!!! ???)"


def run(j):
    p = j.page
    fresh(j)
    p.get_by_role("heading", name="Start a trial").wait_for()
    p.get_by_role("button", name="Blank page").click()
    p.locator("#mc-protocol").fill("!!! ???")
    with j.timed("create"):
        p.get_by_role("button", name="Create trial").click()
        p.wait_for_timeout(4000)
    toasts = j.toasts()
    j.note(f"toasts: {toasts}")
    if running(p):
        j.note(f"a trial was created from garbage: {trial_id(p)}; header: {now_line(p)!r}")
        h = p.locator("h1").first.inner_text()
        j.note(f"heading: {h!r}")
        p.goto("/predose")
        p.wait_for_timeout(2000)
        title = p.locator(".pd-page header p").first.inner_text() if p.locator(".pd-page header p").count() else ""
        j.note(f"pre-dosing header: {title[:200]!r}")
        j.shot("garbage protocol trial, pre-dosing", full_page=True)
        p.goto("/")
        p.wait_for_timeout(1000)
        j.shot("garbage protocol trial, mission control", full_page=False)
        # A garbage protocol should not silently become a full trial with 500 screened applicants.
        j.check("garbage" in " ".join(toasts).lower() or "could not" in " ".join(toasts).lower()
                or "not a protocol" in (now_line(p) + title).lower(),
                "garbage input '!!! ???' was accepted as a protocol with no warning to the user")
    else:
        j.check(on_start_page(p), "neither a trial nor the start page after a garbage protocol")
        j.check(any(t for t in toasts), "garbage protocol rejected without any message")
    j.check(not [c for c in j.console_errors if "pageerror" in c["text"]], "uncaught page error")
    copy_checks(j, "after garbage protocol")
