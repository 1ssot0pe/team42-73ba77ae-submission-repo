"""J6: volunteer portal screening. Each case changes one field of the passing demo profile."""
from harness import JourneyAbort, create_trial, fresh

ID = "J6"
TITLE = "Volunteer portal: valid, bipolar free text, age 17, non-UK phone, lithium, recent use, non-numeric age"

CASES = [
    ("valid", {}, "eligible"),
    ("bipolar in free text", {"free": "I was diagnosed with bipolar disorder last year"}, "not_eligible"),
    ("age 17", {"age": "17"}, "excluded"),
    ("non-UK phone", {"phone": "+1 415 555 0100"}, "not_eligible"),
    ("lithium", {"medication": "lithium 800 mg"}, "excluded"),
    ("psychedelic use 3 months ago", {"prior": "once", "months": "3"}, "not_eligible"),
]


def fill(p, overrides):
    p.get_by_role("button", name="Reset form").click()
    form = p.locator("form.portal__form")
    if "age" in overrides:
        p.locator("#portal-age").fill(overrides["age"])
    if "phone" in overrides:
        form.get_by_label("Mobile").fill(overrides["phone"])
    if "medication" in overrides:
        form.get_by_label("Current medication").fill(overrides["medication"])
    if "prior" in overrides:
        form.get_by_label("Psychedelic use").select_option(overrides["prior"])
        p.locator("#portal-months").fill(overrides["months"])
    if "free" in overrides:
        form.get_by_label("Anything else we should know?").fill(overrides["free"])


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    p.get_by_role("link", name="Volunteer portal").first.click()
    p.get_by_role("heading", name="Apply to the study").wait_for()
    for name, ov, expect in CASES:
        fill(p, ov)
        with j.timed(f"apply:{name}"):
            p.get_by_role("button", name="Apply").click()
            try:
                p.wait_for_function("""() => { const r = document.querySelector('.portal__result');
                    return r && !/Agents working/.test(r.innerText) && (r.querySelector('.decision, .pill, [class*=decision]')
                    || r.querySelector('[role=alert]')); }""", timeout=15000)
            except Exception:
                pass
        res = p.locator(".portal__result").inner_text()
        flat = " ".join(res.split())
        j.note(f"{name}: {flat[:260]}")
        low = flat.lower()
        if expect == "eligible":
            j.check("eligible" in low and "not eligible" not in low and "excluded" not in low and "clinician" in low,
                    f"[{name}] expected an eligible decision: {flat[:200]}")
        elif expect == "excluded":
            j.check("excluded" in low, f"[{name}] expected Excluded: {flat[:200]}")
        else:
            j.check(("excluded" in low or "needs clinician" in low or "needs a clinician" in low) and "not screened" not in low,
                    f"[{name}] expected excluded or needs-clinician: {flat[:200]}")
        if name == "bipolar in free text":
            j.check("bipolar disorder last year" in flat, f"[{name}] the disclosure is not quoted back: {flat[:200]}")
    # non-numeric age: client-side validation, nothing sent
    fill(p, {"age": "thirty"})
    n_before = j.api_calls
    p.get_by_role("button", name="Apply").click()
    p.wait_for_timeout(800)
    err = p.locator("#portal-age-error")
    j.check(err.count() == 1 and "number" in err.inner_text().lower(), "no inline error for a non-numeric age")
    j.check(p.evaluate("document.activeElement && document.activeElement.id") == "portal-age",
            "focus did not move to the invalid age field")
    j.check(j.api_calls == n_before, "a request was sent although the age was not a number")
