# Verify J11 to J15 (protected Vercel preview)

Date: 2026-11-08. Preview `https://parallax-5daiofb6w-dannybudiada-7381s-projects.vercel.app` (`/api/health`: `gemini: true`, `store: postgres`, `store_ok: true`). Headless Chromium, Playwright. Every request to the preview origin carries the protection-bypass header, taken from `.vercel/bypass-token` through `PARALLAX_BYPASS_FILE`. The secret is not written to any result file; I grepped the results for it and found no match. Journeys ran one after another because the preview shares its database with production.

Raw results are in `tests/e2e/verify/j11-15-preview/`:
- `run_all.json` and `run_all.log`: the shared scripts for J11, J13, J14 and J15.
- `j11.json`, `j12.json` and `j13.json`: the verifier copies.
- `rerun.log`

## Summary

| Journey | Verdict | Notes |
|---|---|---|
| J11 refresh, second tab, deep links | **PASS** (verifier copy) | Reload of `/`, `/predose`, `/portal`, `/dosing` and `/postdose` at D+13 took 1.9 to 3.7 s each and reattached to the same trial (`T-133840-d26c`), on the same day. The second tab showed the same trial and stayed in sync after a step. Deep links worked with and without a trial, and an unknown path redirected to `/`. 135 API calls, 0 errors, 0 failed requests. The multi-instance check holds on Vercel with Postgres |
| J12 dark mode, 390 px | PASS (functional); known findings only | Menu, navigation and dock fit pass. Only known findings appeared: BL-8 "UNBLIND-BLIND-1" text, and F-1 dock "Play" at 3.95:1 in dark mode |
| J13 Play 2 min | **PASS** | 3 trials, 214 simulated days, 107 step calls, 0 stalls, 0 lost trials. API statuses: 200 x 686, and nothing else |
| J14 Gemini | **PASS** (Gemini ON) | `/api/health` with bypass returns `gemini: true`. The dock pill reads "GEMINI ON" |
| J15 nav links | FAIL (known BL-11 only) | Evidence engine `href=http://localhost:8501` opens `chrome-error://chromewebdata/` (`preview-J15-1.png`, `preview-J15-2.png`). All other links pass |

**404s on `/api/trials/{id}/...`: 0.** The harness records every response with status 400 or above. Across all runs, about 1,670 API calls returned no 4xx or 5xx from the app.

## J13 detail

These numbers come from the verifier copy `j13_preview.py`. The step latency is the browser's `requestStart` to `responseEnd` time for POST `/step` while Playing.

- Step latency: **p50 348 ms, p90 553 ms, p95 591 ms, max 863 ms** over 107 calls. The shared script's run measured p50 381 ms and max 1,519 ms over 92 calls. Locally the same step took about 13 ms. Per `/api/health`, about 140 ms of each mutation is store overhead (`last_store_overhead_ms` 141.57).
- 30-day API steps: HTTP 200 in 1.70 s (cold), 0.55 s and 0.40 s. Day 31 went to 61, then to 90, and the 31-day step was clamped at 90. After a reload the trial still showed.
- At t=77 s, Chromium reported `net::ERR_NETWORK_CHANGED` on one POST `/step` and one GET `/events`. This was a network change on the client machine, not the server. Play carried on, and no trial was lost or stalled. This is the retry path working (BP-2 and NEW-1).
- The backend-kill and store-deletion parts of the local `j13_verify.py` were left out, because they only apply to the local rig.

## Harness artifacts on the preview (not product bugs)

The shared scripts fail on the preview for reasons that are in the test code, not the product:

1. **`page.request` / `APIRequestContext` is not covered by `context.route`.** Direct API calls go out without the bypass header and get **HTTP 401** from Vercel protection. This hit the J13 30-day steps and J14's `/api/health` check. It also made J14 report "dock says GEMINI ON but health gemini=False": the health call failed, so the script fell back to False. The verifier J13 copy adds the header to `p.request` explicitly.
2. **J11 fresh context:** `browser.new_context()` for the no-trial deep links has no bypass route. Those requests land on `vercel.com/login`, which caused 5 of J11's failures. The copy adds the same route as `harness.py`.
3. **J11 day mismatch:** the script reads the day 1.5 s after the second "+1 week" click. On Vercel the step takes longer than that, so it read "D+6" while the server was at D+13. Every reload then showed D+13 on the same trial chip. The copy waits until the day has been stable for 3 s.
4. **J13 "play stopped early at day -1":** a race at the end of the 2-minute window. A new trial had just been created and was still in Setup (`preview-J13-1.png`). It is not a stall.

To make the shared harness work on protected previews, it would need a helper that adds the bypass header to `page.request` and to any `new_context`.

## Ledger verdicts on preview

| Item | Verdict |
|---|---|
| API-1 | **Fixed on preview**: 0 404s, refresh, second tab and deep links reattach, and 0 trials lost during Play |
| BP-2 / NEW-1 | Holds: a client network error during Play was retried without losing the trial |
| BL-11 | Open (J15) |
| BL-8 | Open (J12) |
| F-1 | Open (J12 dark "Play" 3.95:1) |
| G-1 | Not exercised here |

## New issues

No new product issues. Observation only: step latency on the preview is about 350 ms at p50 and about 600 ms at p95, against about 13 ms locally. Most of it is Postgres store overhead, which is about 140 ms per mutation according to `/api/health`. Play stays smooth with 0 stalls.

## Scripts written (the shared scripts were not edited)

All of these are in `tests/e2e/verify/j11-15-preview/`:
- `j11_preview.py`: J11 with the wait for a stable day, plus the bypass route on the fresh context.
- `j12_dark_and_mobile_fixed.py` and `run_j12.py`: copies of the fixed J12. It needed no change, because `run_journey` adds the bypass.
- `run_one.py`: a generic runner. `JMOD` selects the module.
- `j13_preview.py`: 2-minute Play, p50/p90/p95 latency, a count of 404s on `/api/trials/`, and 30-day steps with the bypass header.

Screenshots: `docs/testing/screenshots/preview-J11-*`, `preview-J12-*`, `preview-J13-*`, `preview-J13-play-1.png`, `preview-J14-*` and `preview-J15-*`.
