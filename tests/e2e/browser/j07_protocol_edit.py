"""J7: protocol edit before enrolment (applies at once) and after enrolment (goes for approval: approve one, reject one)."""
from harness import REVIEWER, JourneyAbort, create_trial, decide, fresh, slips

ID = "J7"
TITLE = "Protocol edit before enrolment and after enrolment (approve one, reject one)"


def edit_and_save(j, line):
    p = j.page
    ta = p.locator("#protocol-editor-text")
    ta.wait_for()
    ta.fill(ta.input_value() + "\n" + line)
    p.locator("#protocol-editor-name").fill(REVIEWER)
    n = len(j.toasts())
    with j.timed(f"save:{line[:20]}"):
        p.get_by_role("button", name="Save version and re-check").click()
        p.wait_for_function(f"(window.__toasts||[]).length > {n}", timeout=20000)
    p.wait_for_timeout(800)
    return j.toasts()[n:]


def versions(p):
    return p.locator(".editor__chips .vchip").all_inner_texts()


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    p.goto("/predose")
    p.locator("#protocol-editor-text").wait_for()
    p.wait_for_timeout(1000)
    v0 = versions(p)
    t = edit_and_save(j, "Participants complete the expectancy questionnaire before randomisation.")
    j.note(f"before enrolment: toasts {t}; versions {v0} -> {versions(p)}")
    j.check(any("Saved protocol v" in x.title() or "SAVED PROTOCOL V" in x.upper() for x in t), f"no 'Saved protocol vN' toast: {t}")
    j.check(len(versions(p)) == len(v0) + 1, f"no new version chip ({len(v0)} -> {len(versions(p))})")

    # enrol: approve the shortlist (pre-dosing approvals live in the aside on this page)
    err = decide(j, "confirm shortlist")
    j.check(err is None, f"approve shortlist: {err}")
    p.wait_for_timeout(1500)
    j.check("enrolled" in p.locator(".pd-page header").inner_text().lower(), "header does not say participants are enrolled")
    v1 = versions(p)
    t = edit_and_save(j, "Amendment A: add a week 9 safety call.")
    j.note(f"after enrolment edit A: {t}")
    j.check(any("approval" in x.lower() for x in t), f"amendment A was not sent for approval: {t}")
    j.check(len(versions(p)) == len(v1), "amendment A applied without approval")
    ok = slips(p, "mendment").count() >= 1
    j.check(ok, "no amendment slip for amendment A on the pre-dosing page")
    t = edit_and_save(j, "Amendment B: add a week 10 safety call.")
    j.note(f"after enrolment edit B: {t}")
    p.wait_for_timeout(1000)
    n_slips = slips(p, "mendment").count()
    j.note(f"amendment slips pending: {n_slips}: {slips(p, 'mendment').locator('.slip__title').all_inner_texts()}")
    j.check(n_slips >= 2, f"expected 2 pending amendment slips, saw {n_slips}")
    if n_slips >= 1:
        err = decide(j, "mendment", "approved")
        j.check(err is None, f"approve amendment: {err}")
        p.wait_for_timeout(1200)
        j.check(len(versions(p)) == len(v1) + 1, f"approved amendment did not add a version ({len(v1)} -> {len(versions(p))})")
    if slips(p, "mendment").count() >= 1:
        v2 = versions(p)
        err = decide(j, "mendment", "rejected")
        j.check(err is None, f"reject amendment: {err}")
        p.wait_for_timeout(1200)
        j.check(len(versions(p)) == len(v2), "rejected amendment still added a version")
    text = p.locator("#protocol-editor-text").input_value()
    j.note(f"final versions: {versions(p)}; week 9 in text: {'week 9' in text}; week 10 in text: {'week 10' in text}")
