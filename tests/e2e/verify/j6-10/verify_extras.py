"""Verifier extras for J6-J10 (does not modify the shared scripts in tests/e2e/browser/).

  .venv/bin/python tests/e2e/verify/j6-10/verify_extras.py --base-url http://127.0.0.1:5321 --env verify-j610-extras \
      --prefix verify --out tests/e2e/verify/j6-10/extras.json

J10v  J10 with a case-insensitive "accepted" check (the shared J10 compares against "Accepted", but the result
      label is rendered upper-case, so innerText is "ACCEPTED" and the shared check always fails).
J6x   API-1 / API-4: 12 portal applications in a row (none may say NOT SCREENED) and age "1e400" in the UI.
J7x   approvals as locked mutations: double-click Approve on one slip, then check one stamp, no error.
J8x   BP-2: one injected 404 on GET /api/trials/{id} must not drop the trial; an unknown stored id shows TrialLost.
"""
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "browser"))
from playwright.sync_api import sync_playwright  # noqa: E402

import j10_researcher_questions as j10  # noqa: E402
from harness import (JourneyAbort, create_trial, decide, fresh, on_start_page, parse_args,  # noqa: E402
                     run_journey, slips)


# ---------------------------------------------------------------- J10v
def j10_batch(j, when):
    p = j.page
    p.goto("/postdose")
    p.wait_for_timeout(1500)
    out = {}
    for label, q in j10.QUESTIONS.items():
        out[label] = j10.ask(j, label, q)
        j.note(f"[{when}] {label}: {out[label][:220]}")
    j.check(out["neutral"].lower().startswith("accepted"), f"[{when}] neutral not accepted: {out['neutral'][:160]}")
    for bad in ("leading", "unblinding", "identifying"):
        r = out[bad].lower()
        j.check(not r.startswith("accepted") or any(w in r for w in ("rewr", "block", "reject", "held")),
                f"[{when}] {bad} accepted unchanged: {out[bad][:160]}")
    return out


j10.batch = j10_batch
J10v = SimpleNamespace(ID="J10v", TITLE="J10 with case-insensitive accepted check", run=j10.run)


# ---------------------------------------------------------------- J6x
def j6x(j):
    p = j.page
    fresh(j)
    if not create_trial(j, "psilocybin"):
        raise JourneyAbort("trial was not created")
    p.get_by_role("link", name="Volunteer portal").first.click()
    p.get_by_role("heading", name="Apply to the study").wait_for()
    not_screened = 0
    for i in range(12):
        p.get_by_role("button", name="Reset form").click()
        with j.timed(f"apply:{i}"):
            p.get_by_role("button", name="Apply").click()
            p.wait_for_function("""() => { const r = document.querySelector('.portal__result');
                return r && !/Agents working/.test(r.innerText) && /PORTAL-|not screened|alert/i.test(r.innerText); }""",
                                timeout=15000)
        flat = " ".join(p.locator(".portal__result").inner_text().split())
        if "not screened" in flat.lower():
            not_screened += 1
            j.shot(f"not screened {i}")
        j.note(f"apply {i}: {flat[:120]}")
    j.check(not_screened == 0, f"{not_screened} of 12 applications showed NOT SCREENED (API-1)")
    # API-4
    p.get_by_role("button", name="Reset form").click()
    p.locator("#portal-age").fill("1e400")
    p.get_by_role("button", name="Apply").click()
    p.wait_for_timeout(2500)
    res = p.locator(".portal__result")
    flat = " ".join(res.inner_text().split()) if res.count() else ""
    err = p.locator("#portal-age-error")
    errt = err.inner_text() if err.count() else ""
    toasts = p.evaluate("window.__toasts.map(t => t.text)")[-3:]
    j.note(f"1e400: inline='{errt}' result='{flat[:200]}' toasts={toasts}")
    bad = "module action failed" in (flat + errt + " ".join(toasts)).lower()
    j.check(not bad, f"1e400 gives the generic 'module action failed': {flat[:200]} {toasts}")
    j.check(bool(re.search(r"whole number|number|age", (flat + errt + " ".join(toasts)), re.I)),
            f"1e400: no validation message shown: result='{flat[:200]}' inline='{errt}' toasts={toasts}")
    j.shot("1e400 outcome")


# ---------------------------------------------------------------- J7x
def j7x(j):
    p = j.page
    fresh(j)
    if not create_trial(j, "psilocybin"):
        raise JourneyAbort("trial was not created")
    s = slips(p, "confirm shortlist").first
    s.wait_for()
    s.locator("input[id$='-reviewer']").fill("QA Tester")
    btn = s.get_by_role("button", name="Approve")
    btn.dblclick()
    try:
        btn.click(timeout=500)
    except Exception:
        pass
    p.wait_for_timeout(3000)
    toasts = p.evaluate("window.__toasts.map(t => t.text)")
    approved = [t for t in toasts if t.startswith("APPROVED")]
    errs = p.locator(".slip__error").all_inner_texts()
    remaining = slips(p, "confirm shortlist").count()
    tid = p.evaluate("localStorage.getItem('unblind.trialId')")
    st = p.evaluate("(id) => fetch('/api/trials/' + id + '/state').then(r => r.json())", tid)
    txt = json.dumps(st)
    j.note(f"triple-click Approve: approved toasts={approved}, slip errors={errs}, open shortlist slips={remaining}")
    j.note(f"state mentions 'confirm shortlist' {len(re.findall('confirm shortlist', txt, re.I))} times")
    j.check(len(approved) <= 1, f"more than one APPROVED toast for one slip: {approved}")
    j.check(not errs, f"slip error after repeated Approve clicks: {errs}")
    j.check(not on_start_page(p), "app went back to Start a trial")


# ---------------------------------------------------------------- J8x
def j8x(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    hits = {"n": 0}
    pat = re.compile(r"/api/trials/[^/?]+/state$")

    def once(route):
        if hits["n"] == 0 and route.request.method == "GET" and pat.search(route.request.url.split("?")[0]):
            hits["n"] += 1
            route.fulfill(status=404, content_type="application/json", body='{"detail":"Trial not found (injected)"}')
        else:
            route.continue_()

    p.route("**/api/trials/**", once)
    p.reload()
    p.wait_for_timeout(5000)
    p.unroute("**/api/trials/**")
    j.note(f"injected 404s: {hits['n']}; start page: {on_start_page(p)}; lost: {p.locator('text=has expired').count()}")
    j.check(hits["n"] == 1, "the 404 was not injected")
    j.check(not on_start_page(p) and p.locator("text=has expired").count() == 0,
            "one transient 404 dropped the trial (BP-2)")
    j.check(p.evaluate("localStorage.getItem('unblind.trialId')") == tid, "stored trial id changed after one 404")
    # unknown id -> TrialLost
    p.evaluate("localStorage.setItem('unblind.trialId', 'T-000000-DEAD')")
    p.goto("/")
    t0 = time.time()
    try:
        p.locator("text=has expired").first.wait_for(timeout=15000)
        j.note(f"TrialLost shown after {time.time() - t0:.1f}s: "
               + " ".join(p.locator("main.page").first.inner_text().split())[:200])
    except Exception:
        j.check(False, "unknown trial id: TrialLost not shown within 15 s")
    j.shot("TrialLost for unknown id")
    toasts = p.evaluate("window.__toasts.map(t => t.text)")
    j.note(f"toasts: {toasts}")
    j.check(not any("not found" in t.lower() and "{" in t for t in toasts), f"raw server message in a toast: {toasts}")
    p.get_by_role("button", name="Start a new trial").click()
    p.wait_for_timeout(1000)
    j.check(on_start_page(p), "Start a new trial did not go to the start page")


MODS = [J10v,
        SimpleNamespace(ID="J6x", TITLE="API-1 repeat applications + API-4 1e400", run=j6x),
        SimpleNamespace(ID="J7x", TITLE="Approval double-submit (locked mutation)", run=j7x),
        SimpleNamespace(ID="J8x", TITLE="BP-2 transient 404 + TrialLost", run=j8x)]


def main():
    a = parse_args("verify")
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}
    mods = [m for m in MODS if not only or m.ID.upper() in only]
    out = Path(a.out or "tests/e2e/verify/j6-10/extras.json")
    results = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        for m in mods:
            results.append(run_journey(b, m, a.base_url, a.env, a.prefix))
            out.write_text(json.dumps({"base_url": a.base_url, "results": results}, indent=2))
        b.close()
    for r in results:
        print(f"{r['id']:5} {'PASS' if r['passed'] else 'FAIL'} {r['duration_s']:6.1f}s")
        for f in r["failures"]:
            print("   -", f["msg"][:200])


if __name__ == "__main__":
    main()
