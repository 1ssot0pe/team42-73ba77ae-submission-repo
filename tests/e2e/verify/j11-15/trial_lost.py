"""Trial-lost screen: (a) delete a trial's store files while Play runs mid-trial; (b) closed trial, delete, then navigate."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "browser"))
from playwright.sync_api import sync_playwright
from harness import create_trial, dock_button, parse_args, run_journey, day_number
STORE = Path("/tmp/parallax-verify-j1115/store")

def wait_lost(j, tid, label):
    p = j.page; t = time.time()
    try:
        p.get_by_text(f"Trial {tid} has expired").wait_for(timeout=30000)
    except Exception:
        j.check(False, f"[{label}] TrialLost not shown within 30 s"); return False
    j.timings[f"{label}_lost_after_s"] = round(time.time() - t, 1)
    j.shot(f"{label} TrialLost")
    p.get_by_role("button", name="Start a new trial").click(); p.wait_for_timeout(800)
    ok = p.get_by_role("heading", name="Start a trial").is_visible()
    j.check(ok, f"[{label}] Start a new trial did not reach the start page (url {p.url})")
    j.check(p.evaluate("localStorage.getItem('unblind.trialId')") is None, f"[{label}] stored id not cleared")
    return ok

class M:
    ID = "J13L"; TITLE = "Trial-lost screen"
    @staticmethod
    def run(j):
        p = j.page; p.goto("/"); p.evaluate("localStorage.clear()"); p.goto("/")
        tid = create_trial(j, "psilocybin", auto=True, settle_s=0.5)
        dock_button(p, "Play").click(); p.wait_for_timeout(3000)
        j.note(f"(a) {tid} playing at day {day_number(p)}; deleting files")
        for f in STORE.glob(f"{tid}*"): f.unlink()
        if wait_lost(j, tid, "a-playing"):
            j.check(create_trial(j, "psilocybin", auto=True, settle_s=1) is not None, "[a] could not create a new trial after TrialLost")
        # (b) closed trial: step to the end, delete, then click a nav link
        tid = p.evaluate("localStorage.getItem('unblind.trialId')")
        for n in (30, 30, 30, 30):
            p.request.post(f"{j.base_url}/api/trials/{tid}/step", data={"days": n})
        p.reload(); p.wait_for_timeout(1500)
        for f in STORE.glob(f"{tid}*"): f.unlink()
        p.wait_for_timeout(5000)
        j.note(f"(b) closed {tid}: 5 s after delete, lost shown without interaction: {p.get_by_text('has expired').count() > 0}")
        p.locator("nav").get_by_role("link", name="Dosing").first.click()
        wait_lost(j, tid, "b-closed-nav")

a = parse_args()
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); r = run_journey(b, M, a.base_url, a.env, a.prefix); b.close()
Path(a.out).write_text(json.dumps(r, indent=2))
print(json.dumps({k: r[k] for k in ("passed", "timings", "failures", "notes", "console_errors", "toasts")}, indent=1)[:4000])
