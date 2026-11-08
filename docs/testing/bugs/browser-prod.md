# Bug ledger: Tester BROWSER-PROD

Environment: production, https://parallax-two-tau.vercel.app (deployment `dpl_Ez6UFiAATUjNQFPSSxH5SMC1Bqii`, created 12:31 GMT on 2026-11-08, function `api/index` 30.63 MB in iad1, edge lhr1, Gemini on).
Tested 2026-11-08, 12:40 to 13:00 GMT, headless Chromium (Python Playwright), journeys run one after another.
Scripts: `tests/e2e/prod/harness.py`, `tests/e2e/prod/journeys.py` (J1 to J15), `tests/e2e/prod/instance_probe.py`. Raw per-journey logs (every API call with status, ms, x-vercel-id and error body): `tests/e2e/prod/results/<J>.json`, `tests/e2e/prod/results/run-normal.log`.
`SERIAL=1 SERIAL_GAP_MS=250` runs the same journeys with a test-only init script that queues the page's `/api/` fetches, one at a time with a 250 ms gap. It changes no product code. Those results end in `-serial`.

---

## BP-1 (blocker): the trial is lost about 2 seconds after creation in every browser journey
- **Environment:** prod
- **Journeys:** all trial journeys (J1 to J14). The losses are logged per attempt in `results/<J>.json` under `timings.losses`.
- **Steps:** open `/`, keep the psilocybin example, and click **Create trial**.
- **Expected:** Mission control shows the trial, and every later call works.
- **Actual:** `POST /api/trials` returns 200 (0.5 to 1.9 s). Mission control then renders "Setup before day 1 of 90, 6 decisions to sign". Its first refresh fires about 6 GETs at once: `state`, `kpis`, `messages`, `events?module=master`, `approvals`, and `events`. Most of these return **404** `{"detail":"no trial T-… in this server session; create one"}`. When the 404 lands on `GET state`, `trial.tsx` clears the stored id, and the page returns to **Start a trial** with two toasts: "Trial T-… created" and "No trial T-… in this server session; create one" (screenshot `prod-J1-3.png`). In 42 of 45 browser creates the UI dropped the trial within 2.1 to 4.4 s. In the other 3 creates the run still hit 404s at the next action, such as `POST step`, `POST approvals/{id}` or a later GET. **0 of 45 trials survived long enough to reach day 1.**
- **Evidence:** `docs/testing/screenshots/prod-J1-1.png` (trial shown, 6 to sign), `prod-J1-3.png` (back on Start a trial with the error toast). In an earlier serialised run (screenshot overwritten by the re-run; the calls are logged in `results/J1-serial.json` history and `run-normal.log`) the approval slip shows the raw error "no trial … in this server session; create one" in red, and the agent log shows the same error above stale entries. Example 404 response: `GET /api/trials/T-124204-5263/kpis` → 404, `x-vercel-id lhr1::iad1::x67p7-1794141724907-324680d3dbfa`.
- **Root cause (reproduced with curl):** the trials live in the memory of one function instance (`backend/main.py:23` `TRIALS: Dict[str, Master] = {}`, looked up in `_m()` at `backend/main.py:31-35`). Vercel sends sequential requests to the one warm instance and sends **concurrent requests to other instances**, which do not hold the trial:
  - 10 sequential curl GETs on a trial: 10 × 200. 6 sequential GETs over one keep-alive connection: 6 × 200.
  - 8 parallel GETs on the same trial: 4 × 404. 4 HTTP/2-multiplexed GETs: 2 × 404.
  - `instance_probe.py`: 30/30 sequential GETs returned 200, then 31/32 GETs in parallel bursts of 4 returned 404, and 8/8 bursts had at least one 404. After the bursts the trial was gone from every instance (`/api/health` no longer listed it).
  - 20 sequential `/api/health` calls all reached one instance, which held 19 of my trials. So creates do land there, and the browser loses the trial only because the page fans out its requests.
  - The UI fans out on every tick: `MissionControl.tsx:63` (`Promise.all` of kpis, messages and events), `ApprovalInbox`, `AgentLog.tsx:48`, `trial.tsx:72` (state). The other pages do the same, for example `Predose.tsx:678`.
- **Mitigation evidence:** the page itself running `/api/` calls one at a time with no gap still gave 13/33 trial 404s. With a 250 ms gap it gave **0/32** 404s on J1 setup (see `results/J1-serial.json`). This is only a workaround: any other visitor's concurrent traffic, or an instance being recycled, would still lose the trial. The real fix is to keep trial state outside the instance (an external store, or state carried by the client) as plan.md Section C proposes.
- **Owner files:** `backend/main.py`, `api/index.py`, and possibly `frontend/src/trial.tsx`.

## BP-2 (major): when the trial is lost, the UI silently discards it and shows server jargon
- **Environment:** prod (caused by BP-1, but this is how the UI behaves on any 404)
- **Journeys:** J1, J2 and all others
- **Steps:** as in BP-1.
- **Expected:** a clear message that the trial is no longer on the server, with a way to recover or restart. A 404 on one secondary call (`kpis`) should not count as a lost trial.
- **Actual:**
  1. On a 404 from `/state`, `trial.tsx:72-79` calls `setTrialId(null)`, and the user is silently returned to **Start a trial**. The only explanation is a toast in raw lowercase backend text ("no trial T-… in this server session; create one").
  2. When the `state` call happens to succeed but other calls 404, the page stays in a mixed state. It shows the trial header and stale slips, with an inline red "no trial … in this server session; create one" in the Approval inbox (`Approvals.tsx`), the Agent log, and each slip after Approve. One click on **Approve** returned 404 twenty-three times before one attempt reached the right instance (`J1-serial.json`, first run).
  3. After the drop the Start screen briefly showed only the "Blank page" tab with an empty editor, because the protocols list was still reloading (`prod-J1-3.png`).
- **Evidence:** `prod-J1-1.png`, `prod-J1-3.png`, and `prod-J5-*` (the J5 toasts read "Trial … created" followed by two "No trial … in this server session").
- **Owner files:** `frontend/src/trial.tsx:72-79`, `frontend/src/api.ts:36-48` (errorText passes the server detail through), `frontend/src/pages/MissionControl.tsx:71`, `frontend/src/components/shared/Approvals.tsx`, `frontend/src/components/shared/AgentLog.tsx:50`.

## BP-3 (major): the Evidence engine nav link points at localhost:8501
- **Environment:** prod
- **Journey:** J15
- **Steps:** open any page and click **Evidence engine ↗** in the nav or in the mobile menu.
- **Expected:** a working page, or the link is hidden in production.
- **Actual:** `href="http://localhost:8501"`. The new tab ends at `chrome-error://chromewebdata/` (connection refused). For a visitor who happens to run something on port 8501, it opens their own local service.
- **Evidence:** `results/J15.json`, `docs/testing/screenshots/prod-J15-*.png`.
- **Root cause:** the default value `evidenceUrl = "http://localhost:8501"` in `frontend/src/components/shared/GlassNav.tsx:56`. It is not configurable through an env var such as `VITE_EVIDENCE_URL`.
- **Owner files:** `frontend/src/components/shared/GlassNav.tsx`.

## BP-4 (minor): `/api/health` lists every live trial id to anyone
- **Environment:** prod
- **Journey:** E / J14
- **Steps:** `curl https://parallax-two-tau.vercel.app/api/health`
- **Expected:** `{ok, gemini}` with no list of other users' trials.
- **Actual:** `"trials": [...]` lists every trial id on that instance (19 at one point). Any visitor can then call `state`, `approvals/{aid}` (sign as any reviewer), `step` and so on for another visitor's trial. The data is synthetic, but on a shared public demo one visitor can drive or sign another visitor's trial.
- **Root cause:** `backend/main.py:76` `"trials": list(TRIALS)`. `GET /api/trials` (`backend/main.py:117-122`) also returns the full state of every trial.
- **Owner files:** `backend/main.py`.

## BP-5 (minor): hashed static assets are served with `max-age=0, must-revalidate`
- **Environment:** prod
- **Journey:** E
- **Steps:** `curl -sD- -o/dev/null https://parallax-two-tau.vercel.app/assets/index-CdtYRAEv.js`
- **Expected:** `cache-control: public, max-age=31536000, immutable` for the content-hashed `/assets/*`.
- **Actual:** `cache-control: public, max-age=0, must-revalidate` (and `x-vercel-cache: MISS`) for both the JS (660 kB raw) and the CSS, so every visit revalidates them.
- **Root cause:** `vercel.json` has no `headers` rule for `/assets/(.*)`.
- **Owner files:** `vercel.json`.

## BP-6 (minor): the stray "UNBLIND" name is visible in the UI
- **Environment:** prod (and local)
- **Journey:** J1 (Mission control approval slip)
- **Actual:** the slip title reads "Protocol fix: Add the **UNBLIND-BLIND-1** guess questionnaire for participants and raters" (visible in the inbox in `prod-J1-1.png` after scrolling; the title is in `results/J1.json` notes). Test plan F requires no stray "UNBLIND" in the UI.
- **Root cause:** `unblind/platform/predose/agents.py:257`, `unblind/platform/predose/agents.py:400`, and `STANDARD = "UNBLIND-BLIND-1"` at `unblind/platform/postdose/agents.py:32`, which is used in postdose form and table titles. The postdose file belongs to Callum, so a patch belongs in TEAMMATE_PATCHES.md.
- **Owner files:** `unblind/platform/predose/agents.py`, `unblind/platform/postdose/agents.py`.

## BP-7 (minor): the API function runs in iad1, but visitors (and the edge) are in lhr1
- **Environment:** prod
- **Actual:** every `x-vercel-id` is `lhr1::iad1::…`. Each API call crosses the Atlantic: the median trial GET is 130 to 240 ms, and `POST /api/trials` is 0.5 to 1.9 s. This is not a functional bug, but the many requests per tick each pay the transatlantic latency.
- **Owner files:** `vercel.json` (`regions`).

## BP-8 (minor): the garbage protocol `!!! ???` is accepted as a normal trial
- **Environment:** prod
- **Journey:** J5
- **Steps:** on Start a trial, replace the text with `!!! ???` and click **Create trial**.
- **Expected:** a validation message, or a trial that says the protocol could not be read.
- **Actual:** `POST /api/trials` → 200, and the UI shows "Setup before day 1 of 90 · Waiting for a human: 6 decisions to sign", the same as the psilocybin example. No warning says the text was not a protocol. The trial was then lost (BP-1), so I could not inspect what protocol was used in its place.
- **Evidence:** `results/J5.json`, `prod-J5-1.png`.
- **Owner files:** `backend/main.py:104-114`, `unblind/platform/predose/`.

---

## Measurements

### Trial-loss / 404 rate per journey (normal browser, no workaround)
"Creates" counts trials created (up to 3 attempts per journey, 6 for J9). "Lost" counts the times the UI dropped back to Start a trial.

| Journey | Trial 404s / trial calls | Creates | UI dropped trial | First 404 call(s) | Seconds from attempt start to drop |
|---|---|---|---|---|---|
| J1 | 15 / 18 | 3 | 3 | approvals, kpis, messages | 2.5, 2.3, 2.4 |
| J2 | 13 / 18 | 3 | 3 | events, events, approvals | 2.5, 2.4, 2.3 |
| J3 | 13 / 18 | 3 | 3 | approvals ×3 | 2.3, 2.4, 2.3 |
| J4 | 15 / 18 | 3 | 3 | kpis, messages, kpis | 2.2, 2.1, 2.2 |
| J5 | 7 / 11 | 1 | 0 (still 404 toasts) | kpis | n/a |
| J6 | 21 / 24 | 3 | 3 | kpis, events, messages | 3.1, 3.5, 2.7 |
| J7 | 13 / 18 | 3 | 3 | events, messages, messages | 3.2, 3.2, 2.8 |
| J8 | 19 / 23 | 3 | 2 (3rd: actions 404) | state, kpis | 3.6, 2.3 |
| J9 | 30 / 36 | 6 | 6 | mixed | 2.2 to 3.1 |
| J10 | 14 / 18 | 3 | 3 | events, events, messages | 2.3, 2.2, 2.2 |
| J11 | 15 / 18 | 3 | 3 | approvals, events, kpis | 2.4, 2.3, 2.2 |
| J12 dark 390 px | 23 / 30 | 3 | 3 | kpis, events, events | 4.1, 2.4, 4.1 |
| J12 light 390 px | 19 / 24 | 3 | 3 | state, state, approvals | 2.3, 2.3, 4.4 |
| J13 | 21 / 24 | 3 | 2 (3rd: `step` 404) | messages, events | 2.4, 2.3 |
| J14 | 28 / 39 | 3 | 2 (3rd: later 404s) | kpis, messages | 2.3, 3.1 |
| **Total** | **266 / 337 = 79 %** | **46** | **42** | | median about 2.4 s |

Every one of the 46 trials created in the browser hit at least one 404 within its first refresh. None reached day 1.

With the test-only serialised fetch: no gap gave 13/33 trial 404s (39 %), with the trial lost twice in 3 attempts. A 250 ms gap: in J1-serial (trial T-125327-9bb6, `results/J1-serial.json`) the trial **survived to Day 90**, with **20 / 359 trial calls 404 (5.6 %)**. The 404s were all `POST step` and `POST approvals/{aid}`. Each `step` 404 stopped Play with an error toast, and the approval "Add to reference data: MAPP1" needed 7 clicks before one landed. So serialising the calls cuts the loss rate a lot, but it does not remove it.

API probe (`instance_probe.py`, one trial): 0/30 sequential 404s, 31/32 404s in parallel bursts, and the trial was gone from every instance afterwards.

### Cold start
Not measured cleanly. Other testers and the 12:31 redeploy kept the function warm for my whole window, and I had no idle period before the time box. The first API call of my session was `GET /api/health` in 337 ms. That was warm, after an earlier visitor's trials T-123410/T-123419 had already been created. The first page load (networkidle) of `/` took 1.4 s. Deep links with no trial (networkidle): `/predose` 1450 ms, `/portal` 995 ms, `/dosing` 1783 ms, `/postdose` 841 ms.

### Function duration against maxDuration 60
`vercel logs` shows no runtime lines (the app logs nothing), and request records don't expose duration ("CDN request dimension "duration" is not publicly queryable"). The client-measured times to first byte were:
- `POST /api/trials`: 0.50 to 1.94 s (46 samples).
- Trial GETs: median about 130 to 240 ms, max 628 ms.
- `POST step` with days=2 (the Play loop, J1-serial, 53 calls, day 0 to 90): p50 232 ms, max 900 ms. That is far under the 60 s maxDuration.
- In normal mode every J13 attempt (2-minute Play, and `step` days=30 ×3) returned **404 in 114 to 217 ms** before any simulation ran. **J13's 2-minute Play and its 30-day step are NOT RUN** (blocked by BP-1). No 5xx or 504 appeared in any journey.

### Headers, rewrites, CORS
- `/` and the deep links `/predose`, `/portal`, `/dosing`, `/postdose` and `/nonexistent` all return 200 `text/html` (the SPA rewrite works). `/nope` redirects to `/` in the client.
- `/assets/does-not-exist.js` returns 404 `text/plain` (correct: no SPA fallback for assets).
- `/api/nope` returns 404 JSON. A CORS preflight from a foreign origin returns 400 with no `access-control-allow-origin` (same-origin only, which is fine).
- Asset `cache-control`: see BP-5. HTML: `public, max-age=0, must-revalidate`, `x-vercel-cache: HIT`.

---

## Passed checks
- J1-serial (with the test-only fetch queue): created a trial, signed 2 protocol fixes and the shortlist, played to **Day 90 of 90 (phase closed)**, and signed the drift-related approvals ("Site C: add SMS reminders and a coordinator call", "Move Site B raters to remote (central) assessment") and the export. The FDA report sign-off form was not found by my selector on `/postdose` after close (`prod-J1-serial-1.png`). This is unverified: it may be my selector or the report status, and is not logged as a bug.
- J15: every in-app nav link (Mission control, Pre-dosing, Volunteer portal, Dosing, Post-dosing) routes correctly. The wordmark goes home, and an unknown route redirects to `/`.
- J11 (no-trial part): deep links `/predose`, `/portal`, `/dosing` and `/postdose` load directly with 200 and render their "No trial yet" empty states.
- J14: `/api/health` reports `gemini: true`, and the dock shows a "Gemini on" pill. The Gemini output itself was not observable: no trial lived long enough, and the setup events carried no Gemini or LLM text.
- J5: the garbage protocol does not cause a 5xx (but see BP-8).
- No uncaught page errors (`pageerror`) in any journey. Every console error was the browser's "Failed to load resource: 404" for the BP-1 calls.
- No 5xx responses observed on any endpoint.

## Not run (blocked by BP-1: no trial survived)
J1 in normal mode (it passed only with the test-only fetch queue; FDA sign-off unverified), J2 play to close, J3 (CAPS-5 labels, drift at Site C), J4 custom site names, J6 portal screening cases, J7 protocol edit and amendments, J8 shortlist reject and re-request, J9 drift approve versus reject, J10 researcher questions before and after the lock, J11 refresh / second tab / deep links with a trial, J12 dark mode and 390 px on populated pages, J13 2-minute Play and the 30-day step duration, and J14 Gemini output in the agents' text. Each of these needs the state fix first, or a local run behind the round-robin proxy (Tester Browser-Local).
