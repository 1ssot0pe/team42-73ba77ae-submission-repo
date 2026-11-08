"""J10: post-dosing researcher questions through the bias gate, before and after the primary lock."""
from harness import JourneyAbort, create_trial, day_number, decide, fresh, play

ID = "J10"
TITLE = "Researcher questions (neutral, leading, unblinding, identifying) before and after the primary lock"

QUESTIONS = {
    "neutral": "How many hours did you sleep in the week after your session?",
    "leading": "Don't you agree that the treatment made you feel much better?",
    "unblinding": "Do you think you received psilocybin or the placebo capsule?",
    "identifying": "What is your full name, home address and date of birth?",
}


def ask(j, label, q):
    p = j.page
    form = p.locator("form.mform", has_text="Researcher question")
    form.wait_for(timeout=15000)
    form.locator("input").nth(0).fill("QA team")
    form.locator("input").nth(1).fill(q)
    with j.timed(f"ask:{label}"):
        form.locator("button[type=submit]").click()
        p.wait_for_function("(f) => !f.querySelector('button[type=submit]').getAttribute('aria-busy')",
                            arg=form.element_handle(), timeout=15000)
    p.wait_for_timeout(300)
    res = form.locator(".mform__result")
    return " ".join(res.inner_text().split()) if res.count() else "<no result shown>"


def batch(j, when):
    p = j.page
    p.goto("/postdose")
    p.wait_for_timeout(1500)
    out = {}
    for label, q in QUESTIONS.items():
        out[label] = ask(j, label, q)
        j.note(f"[{when}] {label}: {out[label][:220]}")
    j.check(out["neutral"].startswith("Accepted"), f"[{when}] neutral question not accepted: {out['neutral'][:160]}")
    for bad in ("leading", "unblinding", "identifying"):
        r = out[bad].lower()
        j.check(not r.startswith("accepted") or any(w in r for w in ("rewr", "block", "reject", "held")),
                f"[{when}] {bad} question accepted unchanged: {out[bad][:160]}")
    return out


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    decide(j, "confirm shortlist")
    play(j, stop_when=lambda: (day_number(p) or 0) >= 30, timeout_s=120)
    j.note(f"before lock at day {day_number(p)}")
    batch(j, "before lock")
    p.goto("/")
    p.locator(".mc-dock").wait_for()
    play(j, stop_when=lambda: (day_number(p) or 0) >= 72, timeout_s=120)
    j.note(f"after lock at day {day_number(p)}")
    batch(j, "after lock")
