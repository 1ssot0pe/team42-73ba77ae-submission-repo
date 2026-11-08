# Verification: J1 to J5, local two-instance stack

Verifier: independent re-test (no product code changed). Date: 2026-11-08. Branch `danny-frontend-e2e` at `de78c84`. The working tree also had an uncommitted docstring-only edit to `backend/main.py`, which another session made and which does not change behaviour.

## Setup
- Two uvicorn backends on 8311 and 8312, each with its own `UNBLIND_TRIALS_DIR` and the same `UNBLIND_STORE_DIR=/tmp/parallax-verify-j15/store` (FileStore), as in production.
- Round-robin proxy `tests/e2e/rr_proxy.py` on 8310. Vite on 5311 with `VITE_API_TARGET=http://127.0.0.1:8310`.
- Journeys: `tests/e2e/browser/run_all.py --base-url http://127.0.0.1:5311 --env verify-j15-local --prefix verify --only J1,J2,J3,J4,J5 --out tests/e2e/verify/j1-5/results.json`. The shared scripts ran unmodified and worked.
- Extra resilience checks for API-1 and BP-2: `tests/e2e/verify/j1-5/resilience_extra.py`, a new verifier-only script.
  - R1: kill one backend in the middle of Play, then restart it.
  - R2: delete a trial from the store, then check that the UI shows TrialLost.

## Results per journey

| J | Result | Duration | API calls | Console errors | Failed requests | Why it failed |
|---|---|---|---|---|---|---|
| J1 Psilocybin, manual approvals | **FAIL** (flow passes; copy check fails) | 22.4 s | 339 | 0 | 0 | Only the BL-8 copy check (`UNBLIND-BLIND-1` in the UI) failed. Every step completed. |
| J2 Auto-approve, play to close | **FAIL** (flow passes; copy check fails) | 19.9 s | 298 | 0 | 0 | Only the BL-8 copy check failed. |
| J3 MDMA to close | **FAIL** (flow passes) | 29.4 s | 358 | 0 | 0 | BL-4 (MADRS labels, no CAPS-5), BL-3 and BL-8. |
| J4 Custom protocol sites | **FAIL** (flow passes) | 28.8 s | 369 | 0 | 0 | BL-5: London and Bristol are used; Leeds, Glasgow and Cardiff never appear. |
| J5 Garbage protocol | **FAIL** (flow passes) | 8.0 s | 45 | 0 | 0 | BL-6 (garbage accepted) and BL-8. |

Every J1 to J5 failure comes from a ledger item that is still open by design. No journey failed because a trial was lost, a request failed or the console logged an error.

Timings:
- J1: create 0.11 s; each sign about 0.06 s; play to drift 9.1 s (drift slip on day 47, Site B); play to the amendment 0.9 s; play to close 7.4 s; sign the FDA report 0.07 s.
- J2: create 0.06 s; play to close 16.6 s. The report was auto-signed on D+90.
- J3: create 0.11 s; play to drift 6.5 s (drift at **Site C**, day 33, as expected); play to close 10.5 s.
- J4: play to drift 7.8 s (Site B, day 39).
- J5: create 4.0 s.

J1 to J5 toasts: only success toasts (created, approved, closed). No error toast and no raw server message.

## 404 count on `/api/trials/{id}/...`
- **J1 to J5: 0.** The browser saw 0 failed requests. In the backend logs, all 1,418 `/api/` requests returned 200: 686 were served by 8311 and 689 by 8312, so the round-robin really did split the traffic.
- R1 (instance loss): **0 404s**. The only errors were 40 expected 502s from the proxy while 8311 was down ("Connection refused").
- R2 (a trial deleted on purpose): 2 404s on `GET state` for the deleted trial only. This is expected and is what drives TrialLost.

## Extra resilience checks
- **R1, instance loss mid-play: PASS** (22.8 s).
  - Steps: auto-approve trial, Play, `kill -9` backend 8311 on day 9. During the 6 s outage, half the requests got 502, including 5 `step` POSTs (`events` 13, `approvals` 9, `kpis` 9, `step` 5, `messages` 4).
  - While 8311 was down, the UI kept the trial and Play kept advancing (day 9 to 23) through 8312. It showed a "Reconnecting…" toast and then "The server had a problem (502). Try again in a moment."
  - After 8311 restarted, the trial reached day 90 and closed. The console logged 40 "Failed to load resource: 502" lines, one per failed request. That is browser noise, not app errors.
  - Screenshot: `docs/testing/screenshots/verify-J5-extra-R1-1.png`.
- **R2, real loss: PASS.**
  - After the trial's `.trial` file was deleted and the page reloaded, the app showed "Trial T-131238-215c has expired … Start a new trial". The stored trial id was kept; it did not fall back silently to "Start a trial", and no raw server toast appeared.
  - Screenshot: `docs/testing/screenshots/verify-J5-extra-R2-1.png`.
  - Note: with no reload, an idle page that waits on approvals does not poll. So a deleted trial goes unnoticed until the next user action, and Play is disabled in that state. This is acceptable and not a bug.

## Ledger verdicts

| ID | Verdict | Evidence |
|---|---|---|
| API-1 (trial loss) | **fixed** | 0 of 1,418 requests failed across two instances sharing the store (before the fix, 13 of 27 failed). The trial survives losing an instance (R1). |
| BP-2 (UI drops trial) | **fixed** | No silent fallback in J1 to J5. During the outage (R1) the UI retried, showed a reconnecting toast and kept the trial. A confirmed loss (R2) shows TrialLost, keeps the id, and the error copy is readable rather than a raw server message. |
| BL-3 | not fixed (observed) | J3 `/dosing`: "Primary endpoint locked: 0 of 73 participants have a week-6 MADRS." (`verify-J3-2.png`) |
| BL-4 | not fixed (observed) | J3: MADRS labels on `/`, `/dosing` and `/postdose`, and no CAPS-5 anywhere (`verify-J3-1..5.png`). The FDA report also says "MADRS points". |
| BL-5 | not fixed (observed) | J4: "Site C (Bristol)" and "Site A (London)" appear; none of Leeds, Glasgow or Cardiff appear (`verify-J4-1..2.png`). |
| BL-6 | not fixed (observed) | J5: `!!! ???` creates trial T-130734-6868 with "500 applicants screened" and "shortlist of 0 eligible", with no warning (`verify-J5-1..3.png`). |
| BL-8 | not fixed (observed) | `UNBLIND-BLIND-1` appears in J1, J2, J3 and J5 (slip titles, KPI label, FDA report). |

## Regressions or new issues
- No functional regression found in J1 to J5.
- Minor observation: after one backend comes back, the 502 toast ("The server had a problem (502). Try again in a moment.") can appear after "Reconnecting…" even though the play loop recovered on its own. That is noise, but harmless.
- Not in scope, for information: in J1, the follow-up amendment ("Make remote central raters permanent…") did appear after the drift fix was signed, which BL-7 said never happened. Re-check BL-7 under J9.

## Artifacts
- `tests/e2e/verify/j1-5/results.json`: full J1 to J5 report (network, console, toasts, timings).
- `tests/e2e/verify/j1-5/resilience_extra.py` and `resilience_results.json`. The JSON holds only the last R2 run; the R1 numbers above come from the first run.
- Screenshots `docs/testing/screenshots/verify-J1-1.png` (closed and signed), `verify-J3-1..5`, `verify-J4-1..2`, `verify-J5-1..3`, `verify-J5-extra-R1-1`, `verify-J5-extra-R2-1`.
