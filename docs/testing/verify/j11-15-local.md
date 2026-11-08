# Verify J11 to J15, F, G (local, two instances, shared store)

Date: 2026-11-08. Branch `danny-frontend-e2e` at de78c84. Fixes under test: `git diff 22193b6..HEAD` (FileStore in `unblind/platform/store.py`, `api.ts` retries, `trial.tsx` re-check and TrialLost).

Setup: two uvicorn backends, 8331 and 8332, sharing `UNBLIND_STORE_DIR=/tmp/parallax-verify-j1115/store` (each with its own `UNBLIND_TRIALS_DIR`). The round-robin proxy `tests/e2e/rr_proxy.py` runs on 8330 and Vite on 5331. Headless Chromium, Playwright.

Raw results: `tests/e2e/verify/j11-15/run1.json` (J11, J12 original, J14, J15, F, G), `j12.json` (fixed J12), `j13.json`, `trial_lost.json`.

## Summary

| Journey | Result | Notes |
|---|---|---|
| J11 refresh, second tab, deep links | PASS | Reload of `/`, `/predose`, `/portal`, `/dosing` and `/postdose` mid-trial (D+13) took about 1.35 s each and reattached to the same trial. Second tab and deep links also reattached. 0 console errors, 0 failed requests |
| J12 dark mode, 390 px | PASS (functional); copy and contrast findings | The shared script still dies on "+1 week", which is disabled while approvals are pending (verify-J12-1 from run1). The fixed copy passes the menu, navigation and dock-fit checks. Findings: BL-8 "UNBLIND-BLIND-1" text, and dock "Play" contrast 3.95:1 in dark mode |
| J13 Play 2 min, 30-day step, backend kill | PASS on trial continuity and API-1; one minor new finding | 4 trials, 313 simulated days, 161 step calls, 0 stalls, 0 lost trials, 0 unintended 404s. Play stopped once after 8331 was killed (see NEW-1) |
| Trial-lost screen | PASS | It appeared 1.8 s after the files were deleted mid-play. "Start a new trial" works. See the note on closed trials |
| J14 Gemini off | PASS | `/api/health` gemini=false, and the dock pill reads "GEMINI OFF" |
| J15 nav links | FAIL (known BL-11) | Evidence engine `href=http://localhost:8501` opens `chrome-error://chromewebdata/` (verify-J15-1, verify-J15-2). All other links pass |
| F design and copy | FAIL (minor, redesign) | 27 findings, listed below |
| G keyboard | FAIL (minor, redesign) | 4 findings, listed below |

## J13 detail

- Step latency while Playing through the proxy: p50 13 ms, p90 19 ms, max 34 ms over 161 calls.
- API 30-day step: 0.03 s (HTTP 200 via 8332). Before the fix it took 0.39 s. A 31-day step returned 200 in 0.03 s and was clamped; the trial reached day 90. One 30-day step routed to the dead 8331 returned 502 in 0.00 s; this was a direct request with no retry.
- 404 count: **0** during Play and normal use. Across all runs the proxy log has 10 responses with status 404, and all of them were for the three trials whose files I deleted on purpose. Before the fix, 13 of 27 requests failed.
- Backend kill: I killed 8331 with SIGKILL at t=60 s (day 31). The trial stayed attached and continued through 8332. API status totals for the run were 200 x 1031 and 502 x 22. All 502s came from the proxy for the dead 8331; GETs retried and succeeded. The frontend showed "RECONNECTING…" and never lost the trial or the stored id (verify-J13-1).
- **NEW-1 (minor): Play stops after one unlucky step during a backend outage.** In the proxy log (lines 1634 to 1642), the 3 POST `/step` attempts all landed on dead 8331, because polling GETs fired in between kept the round-robin parity. `api.ts` allows only 3 attempts for POSTs, so Play stopped at day 39 with the toast "THE SERVER HAD A PROBLEM (502). TRY AGAIN IN A MOMENT." (verify-J13-2). The trial was intact, and pressing Play continues it. This is partly a test-rig artifact: strict round-robin keeps sending traffic to a dead backend, and Vercel would not route to a dead instance. It may still happen on prod with real 502/503 platform errors. Possible fixes: give step more attempts, or have the Play loop retry once before it stops.
  Steps to reproduce: run the stack above, Play an auto-approve trial, kill 8331, and wait until Play stops with the 502 toast.
- **Trial-lost screen** (`tests/e2e/verify/j11-15/trial_lost.py`):
  - (a) Mid-trial with Play running at day 17, I deleted `T-…​.trial` and `.lock` from the store. "Trial T-131038-88c7 has expired" showed 1.8 s later (verify-J13-4). "Start a new trial" went to the start page, cleared `unblind.trialId`, and a new trial was created.
  - (b) A closed trial (D+90) whose files were deleted shows nothing until the person interacts: nothing polls a closed trial. After a nav click the screen showed in 1.3 s (verify-J13-5). My first attempt in `j13.json` deleted the files of a closed trial and waited without interacting, so it "failed" (verify-J13-3). This is expected behaviour, not a bug.
  - The browser console shows "Failed to load resource: 404" for the deleted trial's requests. These are expected.

## F findings (minor, for the redesign branch)

- BL-8 still open: "UNBLIND-BLIND-1" appears on every page, both modes, 1440 and 390 px. It shows in KPI labels, slips, the agent log and the blocked reason.
- Contrast on glass: the Evidence engine "↗" glyph in the nav is 2.57:1 in light and 4.05:1 in dark. The `.mc-track` "W12" and "D90" labels are 4.43:1. The Portal result line "PORTAL-000N · D+34" is 2.56:1 light and 3.97:1 dark. The dock "Play" label is 3.95:1 in dark at 390 px (J12).
- I checked for em dashes and for horizontal scroll at 390 px; neither raised a failure.

## G findings (minor, for the redesign branch)

- No visible focus ring on the start page `#mc-protocol` textarea or on the slip reviewer and comment inputs on Mission control.
- "Tab does not reach both the nav and Create trial": the start page's tab order cycles back to the nav after the textarea and the auto-approve checkbox. Create trial is disabled until a protocol is chosen, so this is likely a test artifact; it needs a manual check.
- "Tab never reaches the dock (Next day)": the order goes through the inbox and log, then to "INPUT:on" (auto-approve) and "New trial", but not Next day, +1 week or Play. Those are probably disabled while approvals are pending. Re-check with the approvals cleared.
- Approve buttons show a solid 2 px focus ring.

## Ledger verdicts

| Item | Verdict | Evidence |
|---|---|---|
| API-1 | **Fixed** (local, shared FileStore) | 0 unintended 404s over about 1050 API calls through the round-robin proxy (before: 13 of 27 failed). The trial survives losing one backend: kill of 8331 at t=60 s, and Play continued on 8332. 30-day step 0.03 s (before 0.39 s) |
| BP-2 | **Fixed** | No silent reset to "Start a trial". 502s give "RECONNECTING…" and retries. A real loss gives the TrialLost screen after a second check, with a working "Start a new trial". Residual: NEW-1, where Play stops on 3 consecutive 502s (trial kept) |
| BL-11 | **Not fixed** (open, as expected) | `GlassNav.tsx:58` default `http://localhost:8501`; J15 tab lands on `chrome-error://chromewebdata/` |
| BL-8 | Not fixed (observed) | F and J12 |

## Regressions

No regression found in J11 to J15. New minor finding: NEW-1, described above.

## Scripts written (the shared scripts were not edited)

- `tests/e2e/verify/j11-15/j12_dark_and_mobile_fixed.py` and `run_j12.py`: a copy of J12 that clicks "+1 week" only when it is enabled.
- `tests/e2e/verify/j11-15/j13_verify.py`: 2-minute Play with a mid-play kill of 8331, 30-day steps and a trial-lost check.
- `tests/e2e/verify/j11-15/trial_lost.py`: trial-lost mid-play, and on a closed trial after navigation.
