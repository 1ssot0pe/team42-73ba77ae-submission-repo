# Verify J6-J10, protected Vercel preview

Date 2026-11-08, branch `danny-frontend-e2e`. Target: `https://parallax-5daiofb6w-dannybudiada-7381s-projects.vercel.app` (store=postgres, Gemini on). Protection bypass: the harness reads `PARALLAX_BYPASS_FILE=.vercel/bypass-token` and adds the header only to the preview origin. The secret was not printed or logged. Browser: headless Chromium. All runs were sequential, because the preview shares its database with production.

**Runs and raw results** (all in `tests/e2e/verify/j6-10-preview/`):
- Shared scripts: `run_all.py --only J6,J7,J8,J9,J10 --prefix preview` → `results.json`
- Verifier extras: `verify_extras.py`, a copy of `../j6-10/verify_extras.py` → `extras.json` (J10v, J6x, J7x, J8x, JT plus the timing of every `/api/` request). Preview changes:
  - J8x's page-level route uses `route.fallback()` instead of `continue_()`, so the context route still adds the bypass header.
  - A `requestfinished` hook records browser-side request durations.
  - New probe JT: approve, then Play.
- `probe_play_after_approve.py` → `probe_play.json`: diagnoses the J9 failure.
- `j9_wait_enabled.py` → `j9_wait.json`: the shared J9 with one change. Before pressing Play, it waits up to 5 s for the button to be enabled.

## Per-journey results

| Journey | Result | Time | API calls | Console errors | Failed requests |
|---|---|---|---|---|---|
| J6 portal (6 cases + non-numeric age) | PASS | 8.2 s (each apply 0.33-0.55 s) | 22 | 0 | 0 |
| J7 protocol edit before and after enrolment, approve one, reject one | PASS | 14.6 s | 58 | 0 | 0 |
| J8 reject shortlist, approve re-request | PASS | 9.4 s | 37 | 0 | 0 |
| J9 drift action approved vs rejected (shared script) | FAIL, test race (see below) | 8.1 s | 34 | 0 | 0 |
| J9 rerun, waits for Play to be enabled | **PASS** | 85.2 s (play to drift 24.5 s and 27.3 s) | 492 | 0 | 0 |
| J10 researcher questions (shared script) | FAIL, test bug ("Accepted" vs "ACCEPTED") | 68.1 s | 290 | 0 | 0 |
| J10v (case-insensitive check) | **PASS** | 46.5 s | 290 | 0 | 0 |
| J6x 12 applications in a row + age `1e400` | PASS | 10.5 s | 27 | 0 | 0 |
| J7x Approve clicked 3 times on one slip | PASS | 8.0 s | 23 | 0 | 0 |
| J8x one injected 404, then an unknown trial id | PASS | 11.9 s | 26 | 3 (all expected 404s) | 3 (1 injected, 2 for `T-000000-DEAD`) |

**What matches the local run** (`j6-10-local.md`):
- **J6:** the same 6 outcomes.
- **J7:** v1, v2, then v3 (amended, approved). Week 9 is in the text and week 10 is not.
- **J8:** "Waiting for a human: 6 decisions to sign", and the re-requested shortlist approves.
- **J10/J10v:** the same labels before the lock (day -1) and after it (day 73).
- **J6x:** 0 "NOT SCREENED", and `1e400` gives an inline error.
- **J7x:** exactly one `APPROVED` toast, no `.slip__error`, and only **one** approve POST went out for the 3 clicks.
- **J8x:** the trial survives the injected 404. The unknown id shows "Trial T-000000-DEAD has expired" after 1.8 s, with no raw server text in toasts.

**J9 drift timing:** drift was decided at day 49 on the preview (day 47 locally) in both branches. 20 days later the pending slips were identical in both branches: "Add to reference data: MAPP1 (Mitchell 2021)" and "Site C: add SMS reminders and a coordinator call". The later day is probably because Play advances in larger steps per poll on a slower backend. The `stop_when` check runs every 250 ms. This is not judged a defect.

### J9 shared-script failure: a test race, not a product regression
- **What failed:** both branches report "no drift slip (play ended disabled, day -1)" with `play_to_drift` 0.0 s. The JT probe reproduces it: Play reads as disabled straight after the shortlist approve.
- **The probe (`probe_play.json`):** right after the approve, `GET /state` returns `blocked: null`, `phase: dosing`, and Play was enabled at the first sample (0.36 s). Play then advanced the trial to day 27 in 20 s.
- **The cause:** the shared `play()` checks `is_enabled()` once, immediately after `decide()`. The dock disables Play while `busy` or the post-approve state refresh is in flight (`ControlDock.tsx`: `disabled={!isPlaying && (closed || blocked || busy !== null)}`). Locally that refresh takes about 0.06 s; on the preview it takes about 0.3 s, so the test lost the race.
- **Fix for the test:** wait for Play to be enabled before clicking (see `j9_wait_enabled.py`). With that change J9 passes.

## 404 count on /api/trials/{id}/...

**There were 0 unintended 404s** across all runs: about 1,300 API calls, with no 5xx and no 401/403 from the protection layer. The only 404s were the 3 deliberate ones in J8x: 1 injected by Playwright, and 2 real "trial not found" responses for the made-up id `T-000000-DEAD`. That is the confirmed-twice rule, and the server replied `{"detail":"trial not found"}`. No trial was lost on the postgres store, including about 50 simulated days of Play per J9 branch.

## Approvals and steps (browser-side timings, preview)

Request durations come from Playwright `request.timing.responseEnd` (`extras.json`, `api_timings`). The UI-level timings come from the harness `timed()` blocks, measured from the click until the slip turns into a stamp.

| Call | n | median | p90 | max |
|---|---|---|---|---|
| POST `/trials/{id}/approvals/{slip}` (approve) | 3 | 335 ms | 382 ms | 382 ms |
| POST `/trials/{id}/step` | 37 | 302 ms | 478 ms | 511 ms |
| POST `/trials` (create) | 5 | 593 ms | 652 ms | 664 ms |
| POST `.../modules/predose/actions/apply` | 12 | 290 ms | 312 ms | 331 ms |
| POST `.../modules/postdose/actions/ask_question` | 8 | 299 ms | 316 ms | 342 ms |
| GET `/state`, `/events`, `/approvals`, `/kpis`, `/messages` | 288 | about 250 ms | about 300 ms | 1,025 ms (one `/events`) |

- **UI approve/reject, click to stamp:** 0.29-0.39 s for the shortlist and amendment slips, and 0.62 s for the drift-action slip in J9. Locally the same actions took 0.05-0.07 s.
- **Locked database writes:** all approvals and rejections (J7, J8, J9, J10, J7x, JT) succeeded, with no slip errors, no lost decisions and no double-apply. The 3 rapid Approve clicks in J7x produced a single POST and a single stamp.

## Ledger items

| Item | Preview verdict |
|---|---|
| BL-2 (rejected question shows "ACCEPTED Rejected: ...") | Still present: "ACCEPTED Rejected: leading cannot be fixed by rewording." and the same for personal, before and after the lock. |
| BL-7 (no follow-up amendment after the drift decision) | Still present: in both branches the slips pending 20 days later are identical, and no follow-up amendment appears. |
| BL-10 ("the study session or the study session capsule") | Still present, word for word, before and after the lock. |
| API-1 / BP-2 / API-4 | Behave the same as locally (J6x, J8x). |

## New observations

1. **The shared J9 test is flaky on any slower backend (test debt, not product).** `harness.play()` should wait for Play to be enabled, for example with `wait_for_function` up to about 5 s, instead of returning `"disabled"` from a single check right after `decide()`. Evidence: `probe_play.json`, `preview-J9-1.png`, `preview-J9-2.png`, `preview-J9probe-JP-1.png`.
2. **The shared J10 check is still case-sensitive** (already known; J10v covers it). Evidence: `preview-J10-1.png`, `preview-J10-2.png`.
3. **Latency, not errors:** every API call on the preview takes about 0.25-0.3 s, against about 0.05 s locally. Play is therefore about 3-4x slower in wall-clock time (about 25 s to reach drift, against about 9 s locally). No timeouts or retries were seen.

**No new product issues were found.**
