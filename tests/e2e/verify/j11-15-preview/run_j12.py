"""Run the verifier's fixed J12 copy: .venv/bin/python tests/e2e/verify/j11-15-preview/run_j12.py --base-url ... --prefix verify --out ..."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "browser")); sys.path.insert(0, str(HERE))
from playwright.sync_api import sync_playwright
from harness import parse_args, run_journey
import j12_dark_and_mobile_fixed as m
a = parse_args()
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=not a.headed)
    r = run_journey(b, m, a.base_url, a.env, a.prefix)
    b.close()
Path(a.out or "j12.json").write_text(json.dumps(r, indent=2))
print(json.dumps({k: r[k] for k in ("passed", "failures", "notes", "console_errors", "network_failures")}, indent=1)[:5000])
