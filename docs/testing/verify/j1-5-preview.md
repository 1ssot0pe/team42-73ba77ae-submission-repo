# Verification: J1 to J5, protected Vercel preview

Verifier: independent re-test (no product code changed). Date: 2026-11-08. Branch `danny-frontend-e2e`.

## Setup
- Preview: `https://parallax-5daiofb6w-dannybudiada-7381s-projects.vercel.app` (store=postgres, Gemini on; the dock shows "GEMINI ON" and all three modules "REAL").
- Protection bypass through `PARALLAX_BYPASS_FILE=.vercel/bypass-token` (the secret was not printed or copied).
- Command: `run_all.py --base-url <preview> --env preview-j1-5 --prefix preview --only J1,J2,J3,J4,J5`. Journeys ran sequentially.
- Results: `tests/e2e/browser/results/preview-j1-5.json`. Screenshots: `docs/testing/screenshots/preview-J1-*`, `preview-J3-*`, `preview-J4-1`, `preview-J5-1`, plus the follow-up checks `preview-J1-recheck-1` and `preview-J5-recheck-1`.
- Follow-up checks (verifier-only script, outside the repo): reload the stuck J1 trial, rerun J5 by hand with a longer wait, and read `state` and `approvals` for the J1 and J3 trials through the API.

## Results per journey

| J | Result | Duration | API calls | Console errors | Failed requests | Known open items | New / different from local |
|---|---|---|---|---|---|---|---|
| J1 Psilocybin, manual approvals | **FAIL** | 6.4 s | 31 | 0 | 0 | (BL-8 not reached) | **Yes**: blocked after the shortlist; Play disabled at D-1 (see N-1) |
| J2 Auto-approve, play to close | **FAIL** (flow passes, closed and signed on D+90) | 58.2 s | 291 | 0 | 0 | BL-8 | Slower only: play to close 53.3 s (local 16.6 s) |
| J3 MDMA to close | **FAIL** | 20.1 s | 49 | 0 | 0 | BL-4 (MADRS on `/` and `/postdose`, no CAPS-5 on `/dosing` and `/postdose`). BL-3 not reached | **Yes**: never left D-1 (no drift, no day 90). Same stale-state pattern as J1 (N-1) |
| J4 Custom protocol sites | **FAIL** | 19.6 s | 55 | 0 | 0 | BL-5 (Leeds, Glasgow, Cardiff never appear) | `play_to_drift_or_close` took 0.0 s, so play most likely did not run either (N-1 suspected, not confirmed) |
| J5 Garbage protocol | **FAIL** | 4.5 s | 2 | 0 | 0 | BL-6 when rerun by hand (see below) | **Yes**: no trial and no POST in the scripted run (see N-2) |

## 404 count on `/api/trials/{id}/...`
**0.** All five journeys recorded 0 failed requests (no status >= 400, no aborted request), and so did the follow-up checks. No trial was lost: both stuck trials (J1 `T-133451-01fa` and J3 `T-133557-c3c0`) are still in the Postgres store and return 200 from `state` and `approvals`.

## Timings (browser side)

| Step | J1 | J2 | J3 | J4 | J5 | Local (for comparison) |
|---|---|---|---|---|---|---|
| Create trial | 0.82 s | 0.81 s | 0.83 s | 0.83 s | 4.03 s (no POST was sent, N-2) | 0.06 to 0.11 s |
| Sign protocol fix (guess questionnaire) | 0.34 s | | | | | about 0.06 s |
| Sign protocol fix (expectancy) | 0.50 s | | | | | about 0.06 s |
| Confirm shortlist | 0.95 s | | 0.46 s | 0.39 s | | about 0.06 s |
| Play to close | | 53.3 s | not reached | not reached | | 16.6 s (J2) |

- Each step and approve is about 5 to 15 times slower than local. This fits the cross-Atlantic function region (BP-7, iad1) plus Postgres round trips. Gemini was on, but no Gemini error, timeout or error toast showed up. Manual create of the garbage protocol took 0.68 s for the POST.
- J2's 53 s Play still finished with no errors and no 502 or 504.

## New issues

### N-1 (major on the preview): Mission control keeps showing "Waiting for a human" after the last approval, and Play stays disabled
- J1: the script signed two protocol fixes and then the clinician shortlist. Signing the shortlist enrolled 49 participants and expired the three unsigned fixes ("EXPIRED AT ENROLMENT"). After that:
  - The inbox said "Approval inbox 0".
  - The header still said "Waiting for a human: 4 decisions to sign", and the nav pill said "4 TO SIGN".
  - The "Decisions waiting" KPI showed 4, the phase still read RECRUITMENT, and Play was disabled at D-1.
  - The blocked list still named the already-signed shortlist and the three expired fixes. Screenshots: `preview-J1-1.png` and `preview-J1-2.png`.
- The server disagrees with that UI. `GET state` for `T-133451-01fa` returns `phase: dosing`, `blocked: null`, `pending_approvals: 0`, and `enrolled: 49`. `GET approvals` returns `[]`.
- After a page reload the UI is correct: DOSING, "0 to sign", and Play enabled (`preview-J1-recheck-1.png`). The approvals view refreshed, but the trial state used by the header and dock did not, so the client is holding stale data.
- J3 shows the same pattern. The shortlist shows SIGNED, but the header still lists it and says "2 decisions to sign", and Play is disabled at D-1 (`preview-J3-1.png`). The server now reports `phase: dosing`, `enrolled: 73`, `blocked: null` and 0 pending.
- Locally, the same scripts with the same 800 ms settle passed. Possible causes:
  - The state refetch after an approve is slower than 800 ms on the preview and never repeats, because an idle page that is waiting on approvals does not poll (noted in `j1-5-local.md` R2).
  - The `state` GET ran in parallel with the approve POST and read the old row.
  - I did not separate these two causes within the time box. Either way, a user who signs the last decision on the preview sees a stuck trial until they reload.

### N-2 (minor): the start page's example load can overwrite the user's choice on a slow first load
- In the scripted J5 run, the script clicked "Blank page" and typed `!!! ???`, then clicked Create trial.
- 4 s later the page still showed "Start a trial", with the **psilocybin example selected and its text in the textarea** (`preview-J5-1.png`). The page made only 2 API calls (the protocols list and the example), and no `POST /api/trials`.
- The likeliest cause is that the default example finished loading after the user's choice and replaced the text, so the user's input was lost. With cold-start latency on the preview this race is easier to hit.
- Rerun by hand on a warm page: the garbage protocol created trial `T-133755-95c2` in 0.96 s, with no warning. That is BL-6, the same as local (`preview-J5-recheck-1.png`).

## Known open items seen again
- BL-4 (J3): "MADRS points" on `/` and `/postdose`, and no CAPS-5 label on `/dosing` or `/postdose`.
- BL-5 (J4): none of Leeds, Glasgow or Cardiff appear.
- BL-6 (J5, manual rerun): `!!! ???` is accepted as a trial with no warning.
- BL-8 (J2): `UNBLIND-BLIND-1` appears in the KPI label, slip title and export event.
- BL-3: not reached, because J3 never got to the primary lock (N-1).

## Verdict
- The trial-store fix holds on the preview: 0 "trial not found" 404s, 0 failed requests, 0 console errors, and trials persist in Postgres.
- The preview does **not** behave the same as local.
  - J1 and J3 (and probably J4) stop at D-1 because Mission control keeps stale blocked state after the last approval (N-1). The server is unblocked, and a reload fixes the page.
  - J5's scripted run lost the typed protocol to a late example load (N-2).
  - J2 completes end to end, but it is about 3 times slower than local.
- Before calling the preview equivalent to local, N-1 should be confirmed (watch the `state` GETs after the approve POST) and fixed, and then J1, J3 and J4 should be rerun.
