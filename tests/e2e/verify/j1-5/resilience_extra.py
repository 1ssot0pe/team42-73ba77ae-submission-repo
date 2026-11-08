"""Extra verifier checks for API-1 / BP-2 on the local two-instance stack (not part of the shared journeys).

  R1 instance loss mid-play: auto-approve trial, Play, kill backend B1 for ~6 s (proxy gives 502 on its turns),
     restart it, and the trial must reach day 90 without the UI dropping it.
  R2 real loss: delete the trial's file from the shared store; the UI must show TrialLost (with the id),
     not silently fall back to "Start a trial".

  .venv/bin/python tests/e2e/verify/j1-5/resilience_extra.py --base-url http://127.0.0.1:5311 \
      --store /tmp/parallax-verify-j15/store --kill-port 8311 --restart-cmd "<shell to restart 8311>"
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "browser"))
from playwright.sync_api import sync_playwright  # noqa: E402

import harness as H  # noqa: E402


def pids_on(port):
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--kill-port", type=int, default=8311)
    ap.add_argument("--restart-cmd", required=True)
    a = ap.parse_args()
    out = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        class M:
            ID, TITLE, CONTEXT = "R1", "instance loss mid-play", {}

            @staticmethod
            def run(j):
                p = j.page
                H.fresh(j)
                tid = H.create_trial(j, "psilocybin", auto=True)
                if not tid:
                    raise H.JourneyAbort("not created")
                j.note(f"trial {tid}")
                H.dock_button(p, "Play").click()  # start playing
                p.wait_for_timeout(1500)
                for pid in pids_on(a.kill_port):
                    os.kill(pid, signal.SIGKILL)
                j.note(f"killed :{a.kill_port} at day {H.day_number(p)}")
                p.wait_for_timeout(6000)
                j.check(H.running(p), "UI dropped the trial while one backend was down")
                j.note(f"day while backend down: {H.day_number(p)}; lost-banner={p.locator('text=has expired').count()}")
                subprocess.Popen(a.restart_cmd, shell=True)
                t = time.time()
                while time.time() - t < 30 and not pids_on(a.kill_port):
                    time.sleep(0.5)
                j.note(f"restarted :{a.kill_port} after {round(time.time()-t,1)}s")
                t = time.time()
                while time.time() - t < 120 and (H.day_number(p) or 0) < 90:
                    if H.dock_button(p, "Play").count() and not H.dock_button(p, "Pause").count():
                        H.dock_button(p, "Play").click()  # play loop may have paused on errors; resume
                    p.wait_for_timeout(1000)
                j.check(H.running(p), "trial not running after restart")
                j.check(H.day_number(p) == 90, f"did not reach day 90 after instance loss (day {H.day_number(p)})")
                j.shot("after instance loss")

        class L:
            ID, TITLE, CONTEXT = "R2", "real trial loss shows TrialLost", {}

            @staticmethod
            def run(j):
                p = j.page
                H.fresh(j)
                tid = H.create_trial(j, "psilocybin")
                j.note(f"trial {tid}")
                for ext in (".trial", ".lock"):
                    f = Path(a.store) / f"{tid}{ext}"
                    if f.exists():
                        f.unlink()
                p.wait_for_timeout(500)
                p.wait_for_timeout(3000)  # idle page does not poll (seen in run 1), so press Play to hit the API
                p.reload()  # Play is disabled while approvals wait; a reload is the user action that hits the API
                try:
                    p.get_by_text("has expired").first.wait_for(timeout=15000)
                    j.note("TrialLost shown: " + p.locator("main.page").first.inner_text()[:200].replace("\n", " | "))
                except Exception:
                    j.check(False, "TrialLost not shown after the trial was deleted from the store")
                j.check(not H.on_start_page(p), "UI silently went back to 'Start a trial'")
                j.note(f"stored id kept: {H.trial_id(p)}")
                j.check(H.trial_id(p) == tid, "stored trial id was cleared without user action")
                j.shot("trial lost state")

        for mod in ([L] if os.environ.get('ONLY_R2') else [M, L]):
            out[mod.ID] = H.run_journey(b, mod, a.base_url, "verify-j15-local", "verify-J5-extra" + os.environ.get("SHOT_SUFFIX", ""))
        b.close()
    (HERE / "resilience_results.json").write_text(json.dumps(out, indent=2))
    for k, r in out.items():
        fails = [n for n in r["network_failures"] if "/api/trials/" in n["url"]]
        print(k, "PASS" if r["passed"] else "FAIL", r["duration_s"], [f["msg"] for f in r["failures"]])
        print("  notes", r["notes"])
        print("  api failures", [(n["status"], n["url"][-60:], (n.get("body") or "")[:80]) for n in fails][:15],
              "count", len(fails), "404s", sum(1 for n in fails if n["status"] == 404))
        print("  console", r["console_error_count"], [c["text"][:120] for c in r["console_errors"][:5]])


if __name__ == "__main__":
    main()
