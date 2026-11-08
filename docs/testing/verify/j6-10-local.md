# Verify J6-J10, local two-instance setup

Date 2026-11-08, branch `danny-frontend-e2e` at `de78c84`. Fix diff checked: `git diff 22193b6..HEAD -- backend api unblind frontend/src vercel.json`.

**Stack.** There were two uvicorn backends (8321 and 8322). They shared one store, `UNBLIND_STORE_DIR=/tmp/parallax-verify-j610/store` (`/api/health` reported `store: file, store_ok: true`), and each had its own `UNBLIND_TRIALS_DIR`. The round-robin proxy `rr_proxy.py` ran on 8320 and Vite ran on 5321 (`VITE_API_TARGET=http://127.0.0.1:8320`). The browser was headless Chromium.

**Runs.**
- Shared scripts: `run_all.py --only J6,J7,J8,J9,J10 --prefix verify`. Raw results are in `tests/e2e/verify/j6-10/results.json`.
- Verifier extras: `tests/e2e/verify/j6-10/verify_extras.py` (new; the shared scripts were not edited). Results are in `extras.json` (J10v, J6x) and `extras2.json` (J7x, J8x, rerun after I fixed two URL mistakes in my own script).

## Per-journey results

| Journey | Result | Time | API calls | Console errors | Failed requests |
|---|---|---|---|---|---|
| J6 portal (6 cases + non-numeric age) | PASS | 3.9 s (each apply about 0.06 s) | 27 | 0 | 0 |
| J7 protocol edit before and after enrolment, approve one, reject one | PASS | 11.3 s | 68 | 0 | 0 |
| J8 reject shortlist, approve re-request | PASS | 7.1 s | 48 | 0 | 0 |
| J9 drift action approved vs rejected | PASS | 36.2 s (play to drift about 9.1 s per branch) | 502 | 0 | 0 |
| J10 researcher questions before and after lock | PASS (shared script reports FAIL; the script is at fault) | 23.5 s | 316 | 0 | 0 |
| J6x 12 applications in a row + age `1e400` | PASS | 6.3 s | | 0 | 0 |
| J7x Approve clicked 3 times on one slip | PASS | 6.1 s | | 0 | 0 |
| J8x one injected 404, then an unknown trial id | PASS | 9.8 s | | 3 (all expected 404s) | 3 (1 injected, 2 for `T-000000-DEAD`) |

**Notes per journey.**
- **J6:** The outcomes were:
  - valid applicant: ELIGIBLE
  - bipolar in free text: NEEDS CLINICIAN, with the disclosure quoted back
  - age 17: EXCLUDED
  - non-UK phone: EXCLUDED
  - lithium: EXCLUDED
  - psychedelic use 3 months ago: EXCLUDED

  Each case got a toast `SCREENED · PORTAL-000n · ...`. Non-numeric age gives an inline error, focus moves to the field and no request is sent.
- **J7:**
  - Before enrolment, the edit saves directly as v2.
  - After enrolment, two edits each go "SENT FOR APPROVAL". The 2 amendment slips are pending; A is approved and B rejected.
  - Final versions are v1, v2, v3 (amended, approved). Week 9 is in the text and week 10 is not, so the rejected edit was not applied.
- **J8:** After the shortlist is rejected, the header shows "Waiting for a human: 6 decisions to sign" and the re-requested shortlist slip is present. Approving it works.
- **J9:** Drift appears at day 47 in both branches, and both decisions save. 20 days later the pending slips are the same in both branches: "Add to reference data: MAPP1" and "Site C: add SMS reminders".
- **J10:** The shared check compares against `startsWith("Accepted")`, but the result label renders in upper case (innerText is "ACCEPTED"), so the neutral question always "fails". This is a bug in the test, not the product. Evidence: `verify-J10-1.png`, `verify-J10-2.png`. J10v (the same flow with a case-insensitive check) passes before the lock (day 31) and after it (day 73).

## 404 count on /api/trials/{id}/...

**The journeys produced 0.**
- Backend logs: 1380 `/api/trials/...` requests, split about evenly between 8321 and 8322 (464 and 462 during the J6-J10 run). There were no unintended 404s and no 5xx.
- The only 404s seen were deliberate:
  - one injected by Playwright in J8x
  - two from the TrialLost probe with id `T-000000-DEAD`
  - one from a wrong URL in the first version of my own script (`GET /api/trials/{id}`, which is not a route)

## Ledger verdicts

| Item | Verdict | Evidence |
|---|---|---|
| API-1 (trial loss across instances) | **Fixed** (locally) | Requests alternate between both backends and all 926 J6-J10 trial calls succeed. J6x sent 12 portal applications in a row: 0 showed "NOT SCREENED" (before the fix, every other one did). J9 played about 70 days through the proxy with no loss. |
| BP-2 (UI clears trial on one 404) | **Fixed** | J8x injected one 404 on `GET /api/trials/{id}/state` and reloaded. The trial stays, there is no "Start a trial", no TrialLost, and the stored id is unchanged. With an unknown stored id, after 2 confirmed 404s (about 1.3 s) the app shows "Trial T-000000-DEAD has expired" with a "Start a new trial" button (`verify-J8x-1.png`), and that button goes to the start page. No toast contained a raw server message. |
| API-4 (portal age `1e400`) | **Fixed** | UI: an inline "Enter your age as a number" error, and the request is never sent (`verify-J6x-1.png`). API: `POST .../modules/predose/actions/apply` with `{"payload":{"applicant":{"age":1e400}}}` (number or string) returns `{"ok":false,"error":"'age' must be a whole number"}`. "thirty" gets the same answer, and 30 is accepted. |
| BL-2 (rejected question shows "ACCEPTED Rejected: ...") | **Still present** (not expected fixed) | J10/J10v: "ACCEPTED Rejected: leading cannot be fixed by rewording." and "ACCEPTED Rejected: personal cannot be fixed by rewording.", before and after the lock. |
| BL-7 (drift proposes raters to remote; follow-up amendment missing) | **Still present** (not expected fixed) | J9 signs a drift slip matching "raters to remote" at day 47. In both branches, the slips pending 20 days later contain no follow-up amendment, and the approved and rejected branches look identical. |
| BL-10 ("the study session or the study session capsule") | **Still present** (not expected fixed) | J10 unblinding rewrite: "Do you think you received the study session or the study session capsule?" |

## Approvals as locked, saved mutations (J7, J8, J9, J7x)

All approve and reject actions finished in about 0.05-0.07 s through the proxy, with no slip errors and no lost decisions. J7x clicked Approve 3 times quickly (double-click plus one click) on the shortlist slip. The result was exactly one `APPROVED` toast, no `.slip__error`, and the slip was gone. There was no double-apply and no error. **No regressions were found.**

## New observations (not regressions)

1. **Envelope-less module action is silently accepted (minor, API).** `POST /api/trials/{id}/modules/predose/actions/apply` with body `{"applicant":{"age":1e400}}` (no `payload` wrapper) returns 200. It creates a blank portal applicant ("Age not stated", NEEDS CLINICIAN), because the `Action` model ignores unknown keys and defaults `payload` to `{}`. The UI always sends `payload`, so users are not affected, but direct API callers get no error. To reproduce, send that curl twice: the `applicants` count goes up each time.
2. **TrialLost wording (cosmetic).** A trial id that never existed is reported as "has expired". The TrialLost page also has no app nav (only the button).
3. **Test debt.** The shared `j10_researcher_questions.py` check is case-sensitive (see J10 above) and should use `.lower().startswith("accepted")`. The shared J6 `CASES` comment mentions non-numeric age, but it does not cover `1e400`. J6x covers it.
