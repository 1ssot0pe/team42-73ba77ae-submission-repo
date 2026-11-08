"""Production browser journeys J1 to J15 (Tester BROWSER-PROD).

    .venv/bin/python tests/e2e/prod/journeys.py J1 J2 ...     # runs sequentially (shared public demo)

Each journey writes tests/e2e/prod/results/<J>.json (see harness.py) and screenshots at failure points.
Trials live in one Vercel function instance's memory, so they get lost. When the UI drops the trial
(start screen comes back), the journey records the loss (attempt, seconds after create, first 404 call)
and retries with a fresh trial, up to ATTEMPTS times, so later steps still get exercised.
"""
from __future__ import annotations

import re
import sys
import time
from typing import Callable, Optional

from harness import (PROD, REVIEWER, Run, api_get, approve_all, create_trial, dock_button, goto, headline,
                     on_start_screen, pending_slips, play_until_stop, state_text, toasts)

ATTEMPTS = 3
PAGES = ["/", "/predose", "/portal", "/dosing", "/postdose"]


class TrialLost(Exception):
    pass


def guard(r: Run, where: str) -> None:
    """Raise TrialLost if the UI has dropped the trial."""
    p = r.page
    if on_start_screen(p) or p.get_by_text("No trial yet").count() > 0:
        r.shot(f"trial lost at {where}")
        raise TrialLost(where)


def attempts(r: Run, body: Callable[[Run, int], Optional[str]], tries: int = ATTEMPTS) -> Optional[str]:
    """Run body(r, attempt) until it finishes without losing the trial. Logs every loss."""
    losses = r.timings.setdefault("losses", [])  # type: ignore[assignment]
    for k in range(1, tries + 1):
        n404 = len(r.trial_404)
        t0 = r.el()
        try:
            out = body(r, k)
            r.timings["attempts_used"] = k
            return out
        except TrialLost as e:
            new = r.trial_404[n404:]
            first = new[0] if new else None
            losses.append({"attempt": k, "where": str(e), "s_after_attempt_start": round(r.el() - t0, 1),
                           "first_404": first and {"call": first["call"], "page": first["page"], "t": first["t"]},
                           "n404": len(new)})
            r.note(f"attempt {k}: TRIAL LOST at {e}; first 404 {first and first['call']}")
            goto(r, "/")
    r.timings["attempts_used"] = tries
    r.check(f"journey completed within {tries} attempts", False, "trial lost every time")
    return None


def new_trial(r: Run, example: Optional[str] = "psilocybin", text: Optional[str] = None, auto: bool = False) -> str:
    p = r.page
    if not on_start_screen(p):
        goto(r, "/")
        if not on_start_screen(p):
            dock_button(p, "New trial").click()
    tid = create_trial(r, example, text, auto)
    if not tid:
        raise RuntimeError("create failed")
    p.wait_for_timeout(1500)
    guard(r, "right after create")
    return tid


def drive(r: Run, rounds: int = 25, approve: bool = True, stop_when: Optional[Callable[[], bool]] = None) -> str:
    """Approve what is pending (optional), Play until blocked or closed, repeat. Raises TrialLost."""
    p = r.page
    for i in range(rounds):
        guard(r, f"drive round {i}")
        if stop_when and stop_when():
            return headline(p)
        if approve and pending_slips(p).count():
            approve_all(r)
            guard(r, f"after signing in round {i}")
        if "closed" in state_text(p).lower() and pending_slips(p).count() == 0:
            return headline(p)
        if not dock_button(p, "Play").is_enabled():
            if pending_slips(p).count() == 0 or not approve:
                r.note(f"play disabled: {state_text(p)[:160]}")
                return headline(p)
            continue
        st = play_until_stop(r)
        r.note(f"play round {i}: {st} -> {headline(p)}")
    return headline(p)


def sign_report(r: Run) -> bool:
    """Sign the FDA blinding report through the post-dosing sign_off form."""
    p = r.page
    goto(r, "/postdose")
    guard(r, "postdose for sign-off")
    form = p.locator("form", has_text="Sign off the FDA blinding report")
    if form.count() == 0:
        r.note("no sign-off form on /postdose")
        return False
    form.get_by_label("Your name").fill(REVIEWER)
    with p.expect_response(lambda rs: "/actions/sign_off" in rs.url, timeout=60_000) as resp:
        form.get_by_role("button").last.click()
    r.note(f"sign_off -> {resp.value.status}")
    p.wait_for_timeout(1000)
    return resp.value.status == 200


def approvals_all(r: Run, tid: str):
    a = api_get(r, f"/api/trials/{tid}/approvals?status=all")
    return a["json"] if a["status"] == 200 else None


# ------------------------------------------------------------------ J1
def J1():
    with Run("J1") as r:
        r.timings["first_load_ms"] = goto(r, "/")

        def body(r: Run, k: int):
            p = r.page
            tid = new_trial(r, "psilocybin")
            fixes = approve_all(r, max_n=2, match="Protocol fix")
            r.check("signed 2 protocol fixes", len(fixes) == 2, str(fixes))
            guard(r, "after fixes")
            sl = approve_all(r, match="shortlist")
            r.check("approved the shortlist", len(sl) >= 1, str(sl))
            guard(r, "after shortlist")
            final = drive(r)
            r.check("reached close", "90" in final, final)
            r.check("FDA report signed", sign_report(r))
            rows = approvals_all(r, tid) or []
            r.note(f"approvals: {[(a['title'][:50], a['status']) for a in rows]}")
            return tid

        attempts(r, body)
        r.check("no trial 404s", not r.trial_404, f"{len(r.trial_404)} trial 404s")


# ------------------------------------------------------------------ J2
def J2():
    with Run("J2") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            new_trial(r, "psilocybin", auto=True)
            final = drive(r, approve=False)
            r.check("auto-approve reached close", "90" in final, final)
            r.shot("J2 end")

        attempts(r, body)
        r.check("no trial 404s", not r.trial_404, f"{len(r.trial_404)} trial 404s")


# ------------------------------------------------------------------ J3
def J3():
    with Run("J3") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            p = r.page
            tid = new_trial(r, "MDMA", auto=True)
            final = drive(r, approve=False)
            r.check("MDMA reached close", "90" in final, final)
            texts = {}
            for path in PAGES:
                goto(r, path)
                guard(r, f"MDMA page {path}")
                texts[path] = p.locator("main").inner_text()
            allt = " ".join(texts.values())
            r.check("CAPS-5 shown", "CAPS-5" in allt)
            r.check("no MADRS labels in an MDMA/PTSD trial", "MADRS" not in allt,
                    str([k for k, v in texts.items() if "MADRS" in v]))
            r.check("drift at Site C", bool(re.search(r"drift[^\n]{0,80}Site C|Site C[^\n]{0,80}drift", allt, re.I)))

        attempts(r, body)


# ------------------------------------------------------------------ J4
CUSTOM = """DRAFT protocol: Single-dose DMT for alcohol use disorder (custom test)
Drug: DMT 20 mg IV vs saline placebo
Comparator: inert saline placebo
Raters: site psychiatrists who also run the dosing sessions
Sites: Leeds Teaching Hospital, Bristol Royal Infirmary, Glasgow Royal Infirmary
Eligibility: adults 21 to 65 with alcohol use disorder; exclude psychosis, bipolar, pregnancy
Primary endpoint: percent heavy drinking days at week 12
Sample size: 90
"""


def J4():
    with Run("J4") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            p = r.page
            new_trial(r, text=CUSTOM, auto=True)
            final = drive(r, approve=False)
            r.note(f"custom final: {final}")
            texts = ""
            for path in PAGES:
                goto(r, path)
                guard(r, f"custom page {path}")
                texts += p.locator("main").inner_text()
            sites = {s: s.split()[0] in texts for s in ["Leeds", "Bristol", "Glasgow"]}
            r.check("custom site names used", all(sites.values()), str(sites))
            r.check("no default site letters leak", "Site A" not in texts and "Site C" not in texts)

        attempts(r, body)


# ------------------------------------------------------------------ J5
def J5():
    with Run("J5") as r:
        p = r.page
        goto(r, "/")
        p.get_by_role("heading", name="Start a trial").wait_for()
        p.locator("#mc-protocol").fill("!!! ???")
        with p.expect_response(lambda rs: rs.url.endswith("/api/trials") and rs.request.method == "POST", timeout=60_000) as resp:
            p.get_by_role("button", name="Create trial").click()
        st = resp.value.status
        body = resp.value.text()[:300]
        p.wait_for_timeout(2500)
        r.note(f"garbage create -> {st} {body[:160]}")
        r.shot("garbage protocol result")
        r.check("garbage protocol does not 5xx", st < 500, f"{st}")
        r.note(f"headline: {headline(p)}; toasts: {toasts(p)}; state: {state_text(p)[:200]}")


# ------------------------------------------------------------------ J6
PORTAL_CASES = [
    ("valid", {}),
    ("bipolar in free text", {"free": "I was diagnosed with bipolar disorder last year"}),
    ("age 17", {"age": "17"}),
    ("non-UK phone", {"phone": "+1 415 555 0100"}),
    ("lithium", {"medication": "lithium"}),
    ("psychedelic 3 months ago", {"prior": "once", "months": "3"}),
    ("non-numeric age", {"age": "thirty"}),
]


def J6():
    with Run("J6") as r:
        goto(r, "/")
        results = {}

        def body(r: Run, k: int):
            p = r.page
            new_trial(r, "psilocybin")
            goto(r, "/portal")
            for name, ch in PORTAL_CASES:
                if name in results:
                    continue
                guard(r, f"portal case {name}")
                p.get_by_role("button", name="Reset form").click()
                if "age" in ch:
                    p.locator("#portal-age").fill(ch["age"])
                if "phone" in ch:
                    p.get_by_label("Mobile").fill(ch["phone"])
                if "medication" in ch:
                    p.get_by_label("Current medication").fill(ch["medication"])
                if "prior" in ch:
                    p.get_by_label("Psychedelic use").select_option(ch["prior"])
                    p.locator("#portal-months").fill(ch["months"])
                if "free" in ch:
                    p.get_by_label("Anything else we should know?").fill(ch["free"])
                n = len(r.api)
                p.get_by_role("button", name="Apply").click()
                p.wait_for_timeout(2500)
                calls = [a for a in r.api[n:] if "/actions/apply" in a["path"]]
                res = p.locator(".portal__grid > :last-child").inner_text()[:300].replace("\n", " | ")
                err = p.locator(".portal__field-error").all_inner_texts()
                results[name] = {"status": calls[0]["status"] if calls else None, "result": res, "field_errors": err}
                r.note(f"portal {name}: {results[name]}")
                if calls and calls[0]["status"] == 404:
                    r.shot(f"portal 404 {name}")
                    raise TrialLost(f"portal apply ({name})")
            return None

        attempts(r, body)
        r.timings["portal"] = results  # type: ignore[assignment]
        exp = {"valid": "eligible", "bipolar in free text": "clinician|flag|review", "age 17": "exclu|18",
               "non-UK phone": "phone|UK|exclu|clinician", "lithium": "lithium|exclu|clinician",
               "psychedelic 3 months ago": "exclu|month|clinician"}
        for name, pat in exp.items():
            if name in results:
                r.check(f"portal {name}", bool(re.search(pat, results[name]["result"], re.I)), results[name]["result"][:160])
        if "non-numeric age" in results:
            rr = results["non-numeric age"]
            r.check("portal non-numeric age blocked client-side", bool(rr["field_errors"]) and rr["status"] is None, str(rr))


# ------------------------------------------------------------------ J7
def J7():
    with Run("J7") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            p = r.page
            tid = new_trial(r, "psilocybin")
            goto(r, "/predose")
            guard(r, "predose before enrolment")
            ed = p.locator("#protocol-editor-text")
            ed.wait_for()
            ed.fill(ed.input_value() + "\nAdded line before enrolment (E2E).")
            p.locator("#protocol-editor-name").fill(REVIEWER)
            n = len(r.api)
            p.get_by_role("button", name="Save version and re-check").click()
            p.wait_for_timeout(3000)
            calls = [a for a in r.api[n:] if "/actions/" in a["path"]]
            r.note(f"edit before enrolment: {[(c['path'].split('/')[-1], c['status']) for c in calls]}; toasts {toasts(p)}")
            r.check("edit before enrolment saved", any(c["status"] == 200 for c in calls))
            guard(r, "after edit 1")
            # enrol: approve everything and step until participants exist
            goto(r, "/")
            approve_all(r)
            guard(r, "after approvals")
            dock_button(p, "+1 week").click()
            p.wait_for_load_state("networkidle")
            guard(r, "after +1 week")
            goto(r, "/predose")
            guard(r, "predose after enrolment")
            for i, decision in enumerate(["Approve", "Reject"]):
                ed = p.locator("#protocol-editor-text")
                ed.fill(ed.input_value() + f"\nAmendment {i + 1} after enrolment (E2E).")
                p.locator("#protocol-editor-name").fill(REVIEWER)
                n = len(r.api)
                p.get_by_role("button", name="Save version and re-check").click()
                p.wait_for_timeout(3000)
                guard(r, f"after amendment {i + 1}")
                calls = [a for a in r.api[n:] if "/actions/" in a["path"]]
                r.note(f"amendment {i + 1}: {[(c['path'].split('/')[-1], c['status']) for c in calls]}")
                got = approve_all(r, decision=decision, max_n=1, match="amend|protocol")
                r.check(f"amendment {i + 1} went for approval and was {decision.lower()}d", bool(got), str(got))
            rows = approvals_all(r, tid) or []
            r.note(f"approvals: {[(a['title'][:50], a['status']) for a in rows]}")

        attempts(r, body)


# ------------------------------------------------------------------ J8
def J8():
    with Run("J8") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            new_trial(r, "psilocybin")
            rej = approve_all(r, decision="Reject", max_n=1, match="shortlist")
            r.check("shortlist rejected", bool(rej), str(rej))
            guard(r, "after reject")
            r.page.wait_for_timeout(1500)
            again = pending_slips(r.page).filter(has_text=re.compile("shortlist", re.I))
            r.check("re-request appears", again.count() > 0)
            ok = approve_all(r, max_n=1, match="shortlist")
            r.check("re-request approved", bool(ok) and "200" in ok[0], str(ok))

        attempts(r, body)


# ------------------------------------------------------------------ J9
def J9():
    with Run("J9") as r:
        goto(r, "/")
        for decision in ["Approve", "Reject"]:
            def body(r: Run, k: int, decision=decision):
                p = r.page
                new_trial(r, "psilocybin")
                approve_all(r)

                def drift_pending() -> bool:
                    return pending_slips(p).filter(has_text=re.compile("drift", re.I)).count() > 0

                for _ in range(12):
                    guard(r, "looking for drift")
                    if drift_pending():
                        break
                    approve_all(r, match="^(?!.*drift)")
                    if not dock_button(p, "Play").is_enabled() and pending_slips(p).count() == 0:
                        break
                    if dock_button(p, "Play").is_enabled():
                        play_until_stop(r)
                got = approve_all(r, decision=decision, max_n=1, match="drift")
                r.check(f"drift action {decision.lower()}d", bool(got), str(got))
                guard(r, "after drift decision")
                final = drive(r)
                r.note(f"{decision} final: {final}")

            attempts(r, body)


# ------------------------------------------------------------------ J10
QUESTIONS = [
    ("neutral", "How did you feel in the week after your session?"),
    ("leading", "Don't you agree the psilocybin made you feel much better?"),
    ("unblinding", "Which arm do you think participant P-012 was in?"),
    ("identifying", "What is the phone number and home address of participant P-012?"),
]


def ask_all(r: Run, tag: str) -> dict:
    p = r.page
    goto(r, "/postdose")
    guard(r, f"postdose {tag}")
    form = p.locator("form", has_text="Researcher question portal")
    out = {}
    for name, q in QUESTIONS:
        form.get_by_label("Your name or team").fill("E2E team")
        form.locator("input, textarea").nth(1).fill(q)
        with p.expect_response(lambda rs: "/actions/ask_question" in rs.url, timeout=90_000) as resp:
            form.get_by_role("button").last.click()
        st = resp.value.status
        p.wait_for_timeout(800)
        msg = form.inner_text()[-300:].replace("\n", " | ")
        out[name] = {"status": st, "msg": msg}
        r.note(f"{tag} {name}: {st} {msg[-160:]}")
        if st == 404:
            raise TrialLost(f"ask_question {tag} {name}")
    return out


def J10():
    with Run("J10") as r:
        goto(r, "/")

        def body(r: Run, k: int):
            p = r.page
            new_trial(r, "psilocybin", auto=True)
            drive(r, approve=False, rounds=3, stop_when=lambda: "Day" in headline(p) and int(re.sub(r"\D", "", headline(p).split("of")[0]) or 0) >= 30)
            before = ask_all(r, "before lock")
            goto(r, "/")
            drive(r, approve=False)
            after = ask_all(r, "after lock")
            r.timings["questions"] = {"before": before, "after": after}  # type: ignore[assignment]
            for tag, res in [("before", before), ("after", after)]:
                r.check(f"{tag}: leading question blocked", bool(re.search(r"lead|reword|bias|block", res["leading"]["msg"], re.I)), res["leading"]["msg"][-120:])
                r.check(f"{tag}: unblinding question blocked", bool(re.search(r"unblind|arm|block|lock", res["unblinding"]["msg"], re.I)), res["unblinding"]["msg"][-120:])
                r.check(f"{tag}: identifying question blocked", bool(re.search(r"identif|privacy|personal|block", res["identifying"]["msg"], re.I)), res["identifying"]["msg"][-120:])

        attempts(r, body)


# ------------------------------------------------------------------ J11
def J11():
    with Run("J11") as r:
        p = r.page
        # deep links with no trial (fresh context): each must render, not 404
        for path in ["/predose", "/portal", "/dosing", "/postdose"]:
            t = time.time()
            rs = p.goto(PROD + path, wait_until="networkidle")
            ok = rs.status == 200 and p.locator("h1").count() > 0
            r.check(f"deep link {path} (no trial) renders", ok, f"{rs.status} {round((time.time()-t)*1000)} ms h1={headline(p)}")
        goto(r, "/")

        def body(r: Run, k: int):
            tid = new_trial(r, "psilocybin", auto=True)
            dock_button(p, "+1 week").click()
            p.wait_for_load_state("networkidle")
            guard(r, "after +1 week")
            for path in PAGES:
                goto(r, path)
                p.reload(wait_until="networkidle")
                p.wait_for_timeout(1000)
                guard(r, f"refresh {path}")
                r.check(f"refresh keeps trial on {path}", tid in p.content())
            p2 = r.new_page()
            p2.goto(PROD + "/predose", wait_until="networkidle")
            p2.wait_for_timeout(1000)
            ok = tid in p2.content()
            r.check("second tab sees the trial", ok)
            if not ok:
                r.shot("second tab", page=p2)
            p2.close()
            # deep links with a trial id in localStorage
            for path in ["/predose", "/portal", "/dosing", "/postdose"]:
                p.goto(PROD + path, wait_until="networkidle")
                p.wait_for_timeout(800)
                guard(r, f"deep link {path} with trial")
                r.check(f"deep link {path} with trial", tid in p.content())

        attempts(r, body)


# ------------------------------------------------------------------ J12
def J12():
    for scheme in ["dark", "light"]:
        with Run(f"J12-{scheme}", viewport={"width": 390, "height": 844}, color_scheme=scheme) as r:
            p = r.page
            goto(r, "/")

            def body(r: Run, k: int):
                new_trial(r, "psilocybin", auto=True) if on_start_screen(p) else None
                for path in PAGES:
                    goto(r, path)
                    p.wait_for_timeout(700)
                    guard(r, f"390px {path}")
                    sw, cw = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                    over = p.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => {
                        const r = e.getBoundingClientRect(); return r.width > 0 && r.right > document.documentElement.clientWidth + 1
                    }).slice(0, 5).map(e => e.tagName + '.' + (e.className && e.className.baseVal === undefined ? e.className : '').toString().slice(0, 40))""")
                    ok = sw <= cw + 1
                    r.check(f"{scheme} 390px no horizontal scroll {path}", ok, f"scrollWidth {sw} vs {cw}; overflow {over}")
                    r.shot(f"{scheme} 390 {path}", full=True)

            attempts(r, body)


# ------------------------------------------------------------------ J13
def J13():
    with Run("J13") as r:
        p = r.page
        goto(r, "/")

        def body(r: Run, k: int):
            tid = new_trial(r, "psilocybin", auto=True)
            n = len(r.api)
            t = time.time()
            dock_button(p, "Play").click()
            stopped_at = None
            while time.time() - t < 120:
                p.wait_for_timeout(2000)
                if on_start_screen(p):
                    break
                if dock_button(p, "Play").count() and stopped_at is None:
                    stopped_at = round(time.time() - t, 1)
                    r.note(f"play stopped by itself after {stopped_at}s: {headline(p)}")
                    break
            if dock_button(p, "Pause").count():
                dock_button(p, "Pause").click()
            calls = r.api[n:]
            steps = [c for c in calls if c["path"].endswith("/step")]
            r.timings["play"] = {"s": round(time.time() - t, 1), "calls": len(calls), "steps": len(steps),  # type: ignore[assignment]
                                 "step_status": {s: sum(1 for c in steps if c["status"] == s) for s in {c["status"] for c in steps}},
                                 "step_ms_max": max((c["ms"] or 0 for c in steps), default=0),
                                 "trial_404": sum(1 for c in calls if c["status"] == 404), "stopped_at": stopped_at,
                                 "headline": headline(p)}
            r.note(f"play: {r.timings['play']}")
            guard(r, "after 2 minutes of play")
            # step 30 days at once via the API (the UI only offers 1 and 7)
            res = []
            for _ in range(3):
                t1 = time.time()
                rs = r.context.request.post(f"{PROD}/api/trials/{tid}/step", data={"days": 30}, timeout=90_000)
                res.append({"status": rs.status, "ms": round((time.time() - t1) * 1000),
                            "day": (rs.json().get("state", {}).get("day") if rs.ok else rs.text()[:120])})
            r.timings["step30"] = res  # type: ignore[assignment]
            r.note(f"step30: {res}")
            r.check("step 30 days under maxDuration 60 s", all(x["ms"] < 60_000 and x["status"] == 200 for x in res), str(res))

        attempts(r, body)


# ------------------------------------------------------------------ J14
def J14():
    with Run("J14") as r:
        p = r.page
        h = api_get(r, "/api/health")
        r.check("health reports gemini on", h["status"] == 200 and h["json"].get("gemini") is True, str(h)[:120])
        goto(r, "/")

        def body(r: Run, k: int):
            tid = new_trial(r, "psilocybin")
            pill = p.get_by_role("toolbar", name="Trial controls").get_by_text(re.compile(r"Gemini (on|off)"))
            r.check("dock shows Gemini on", "on" in pill.inner_text().lower(), pill.inner_text())
            ev = api_get(r, f"/api/trials/{tid}/events?limit=400")
            gem = [e for e in (ev["json"] if ev["status"] == 200 else []) if re.search("gemini|llm", str(e), re.I)]
            r.note(f"events mentioning gemini/llm: {len(gem)} e.g. {[str(g)[:160] for g in gem[:3]]}")
            goto(r, "/predose")
            guard(r, "predose gemini")
            txt = p.locator("main").inner_text()
            r.note(f"predose mentions gemini: {len(re.findall('gemini', txt, re.I))}")
            r.shot("predose with Gemini on", full=True)
            slow = sorted([a for a in r.api if a["ms"]], key=lambda a: -a["ms"])[:5]
            r.note(f"slowest calls: {[(a['method'], a['path'][:60], a['status'], a['ms']) for a in slow]}")

        attempts(r, body)


# ------------------------------------------------------------------ J15
def J15():
    with Run("J15") as r:
        p = r.page
        goto(r, "/")
        nav = p.get_by_role("navigation", name="Main")
        for label, path in [("Pre-dosing", "/predose"), ("Volunteer portal", "/portal"), ("Dosing", "/dosing"),
                            ("Post-dosing", "/postdose"), ("Mission control", "/")]:
            nav.get_by_role("link", name=label, exact=True).click()
            p.wait_for_load_state("networkidle")
            r.check(f"nav {label} -> {path}", p.url.rstrip("/") == (PROD + path).rstrip("/") and p.locator("h1").count() > 0, p.url)
        ev = nav.get_by_role("link", name=re.compile("Evidence engine"))
        href = ev.get_attribute("href")
        r.check("Evidence engine link is reachable from production", not re.search(r"localhost|127\.0\.0\.1", href or ""), f"href={href}")
        try:
            with p.context.expect_page(timeout=10_000) as pg:
                ev.click()
            np = pg.value
            try:
                np.wait_for_load_state("load", timeout=8000)
            except Exception:
                pass
            r.note(f"evidence engine tab url: {np.url}")
            r.shot("evidence engine tab", page=np)
        except Exception as e:
            r.note(f"evidence engine click: {e}")
        p.get_by_role("link", name=re.compile("Parallax, mission control")).click()
        r.check("wordmark goes home", p.url.rstrip("/") == PROD)
        # unknown route redirects home
        p.goto(PROD + "/nope", wait_until="networkidle")
        r.check("unknown route redirects to /", p.url.rstrip("/") == PROD, p.url)


JOURNEYS = {k: v for k, v in globals().items() if re.fullmatch(r"J\d+", k)}

if __name__ == "__main__":
    for name in sys.argv[1:] or sorted(JOURNEYS, key=lambda k: int(k[1:])):
        try:
            JOURNEYS[name]()
        except Exception as e:  # keep going: the next journey is independent
            print(f"[{name}] ERROR {type(e).__name__}: {e}", flush=True)
        time.sleep(2)
