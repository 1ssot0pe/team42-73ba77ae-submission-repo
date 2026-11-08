"""Run the Parallax browser journeys against one base URL and write a JSON report.

  .venv/bin/python tests/e2e/browser/run_all.py --base-url http://127.0.0.1:5173 --env local-proxy --prefix local
  .venv/bin/python tests/e2e/browser/run_all.py --base-url https://parallax-two-tau.vercel.app --env prod --prefix prod
  add --only J1,J6,F,G to pick journeys; --headed to watch.
"""
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402

from harness import RESULTS, parse_args, run_journey  # noqa: E402

MODULES = ["j01_psilocybin_manual", "j02_auto_approve", "j03_mdma", "j04_custom_protocol", "j05_garbage_protocol",
           "j06_portal", "j07_protocol_edit", "j08_shortlist_reject", "j09_drift_decisions", "j10_researcher_questions",
           "j11_refresh_tabs_deeplinks", "j12_dark_and_mobile", "j13_play_load", "j14_gemini", "j15_nav_links",
           "f_design_copy", "g_keyboard"]


def main():
    a = parse_args()
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}
    mods = [importlib.import_module(m) for m in MODULES if Path(__file__).with_name(m + ".py").exists()]
    mods = [m for m in mods if not only or m.ID.upper() in only]
    out = Path(a.out) if a.out else RESULTS / f"{a.env}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not a.headed)
        for m in mods:
            results.append(run_journey(browser, m, a.base_url, a.env, a.prefix))
            out.write_text(json.dumps({"base_url": a.base_url, "env": a.env, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                       "results": results}, indent=2))
        browser.close()
    print("\nSUMMARY", a.env, a.base_url)
    for r in results:
        print(f"  {r['id']:4} {'PASS' if r['passed'] else 'FAIL'} {r['duration_s']:6.1f}s  {r['title'][:60]}")
        for f in r["failures"][:5]:
            print(f"        - {f['msg'][:160]}")
    print("results:", out)


if __name__ == "__main__":
    main()
