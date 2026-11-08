# Browser-Local bug ledger (Tester BROWSER-LOCAL)

Environment: local. Two uvicorn instances (8101, 8102, `UNBLIND_TRIALS_DIR=/tmp/parallax-e2e/<port>`), the round-robin proxy `tests/e2e/rr_proxy.py` on 8100, and vite on 5173 (`VITE_API_TARGET=http://127.0.0.1:8100`). For the single-instance comparison, a second vite ran on 5174 with `VITE_API_TARGET=http://127.0.0.1:8101`. Gemini was off. Chromium (Python Playwright 1.64), reduced motion, 1440x900 unless stated.

Scripts: `tests/e2e/browser/` (`harness.py` holds the shared helpers, plus one file per journey and `run_all.py`). Raw results: `tests/e2e/browser/results/local-single.json` (J1 to J8), `local-single-b.json` (J9 onwards), `local-proxy.json`. Screenshots: `docs/testing/screenshots/local-<J>-<n>.png` (proxy) and `local-single-<J>-<n>.png` (single instance).

"Proxy-only" means the bug appears only behind the round-robin proxy. "Single-instance too" means it also reproduces against one backend.

---

## BL-1: Every trial breaks across instances. The app forgets the trial or shows 404 toasts
- **Severity:** blocker
- **Environment:** local, proxy-only (this is the Vercel multi-instance symptom)
- **Journey:** J1, J2 (proxy run), and every journey that needs a trial
- **Steps:** Open http://127.0.0.1:5173 (vite pointing at the proxy). Pick the psilocybin example and click Create trial.
- **Expected:** Mission control shows the running trial, with 6 approval slips.
- **Actual:** The result is random, depending on which instance serves each request:
  - J1 run 1: the trial was created (toast "Trial T-124532-bdb2 created"), but the approval inbox stayed empty and showed an error. `GET /approvals`, `/kpis`, `/messages` and `/events` all returned 404 from 127.0.0.1:8102.
  - J1 run 2: toast "Trial T-125416-6be6 created", then the page fell back to "Start a trial". The `/state` refresh got a 404 and `trial.tsx` cleared the stored trial.
  - J2: Play stopped at once with the toast "No trial T-125446-e707 in this server session; create one" (twice). The day never moved from -1.
- **Evidence:** `docs/testing/screenshots/local-J1-1.png`, `local-J1-2.png`, `local-J2-1.png`. Network log from `results/local-proxy.json`: `GET /api/trials/T-124532-bdb2/kpis -> 404 (X-RR-Backend 127.0.0.1:8102) {"detail":"no trial T-124532-bdb2 in this server session; create one"}`, and the same for `/approvals?status=all`, `/messages` and `/events?module=master&limit=40`.
- **Suspected root cause:**
  - Trials live only in process memory: `backend/main.py:24` (`TRIALS: Dict[str, Master] = {}`) and `_m()` at `backend/main.py:30-34`.
  - The frontend treats any 404 from `/state` as "server restarted" and drops the trial: `frontend/src/trial.tsx:84-88`.
- **Owner files:** `backend/main.py`, `api/index.py`, `unblind/platform/core.py` (persistence or replay), `frontend/src/trial.tsx`
- **Single instance:** J1, J2, J11 and J15 pass on a single instance. The ordinary UI flow works, so this is purely statelessness.

## BL-2: Researcher questions that the bias gate rejected are shown as "Accepted"
- **Severity:** major
- **Environment:** local, single-instance too
- **Journey:** J10
- **Steps:** Create the psilocybin trial, approve the shortlist and play to day 31. On Post-dosing, ask "Don't you agree that the treatment made you feel much better?" in the Researcher question portal form.
- **Expected:** The result is marked as rejected or not accepted.
- **Actual:** The result reads **"ACCEPTED Rejected: leading cannot be fixed by rewording."** The identifying question gives "ACCEPTED Rejected: personal cannot be fixed by rewording.", and the unblinding one gives "ACCEPTED Rewrite proposed: ...". It is the same before the lock (day 31) and after it (day 73). The toast uses the "good" tone.
- **Evidence:** `docs/testing/screenshots/local-single-J10-1.png`, `local-single-J10-2.png`, and the notes in `results/local-single-b.json`.
- **Suspected root cause:** `frontend/src/components/module/ViewForm.tsx:51-53` treats any result with `ok !== false` and no `error` as accepted. The postdose `ask_question` action returns `ok: true` with a rejection message (`unblind/platform/postdose/module.py:113`).
- **Owner files:** `frontend/src/components/module/ViewForm.tsx`. The result shape may also need a fix in postdose (patch note for Callum).

## BL-3: In the MDMA trial (primary endpoint at week 8) the primary lock finds 0 of 73 participants
- **Severity:** major
- **Environment:** local, single-instance too
- **Journey:** J3
- **Steps:** Create the MDMA example, approve the shortlist and play to close. Open Dosing.
- **Expected:** The primary endpoint locks with the week-8 CAPS-5 data.
- **Actual:** The agent log says "Primary endpoint locked: 0 of 73 participants have a week-6 MADRS. No more changes to the primary analysis data."
- **Evidence:** `docs/testing/screenshots/local-single-J3-2.png`
- **Suspected root cause:** The schedule uses the protocol's primary week (8 for MDMA): `unblind/platform/predose/agents.py:856,870`. `PrimaryLock` counts only `visit_week == 6`: `unblind/platform/dosing/agents.py:362`.
- **Owner files:** `unblind/platform/dosing/agents.py` (Izzy; patch goes in TEAMMATE_PATCHES.md). Possibly also `predose/agents.py`.

## BL-4: The MDMA/PTSD trial shows MADRS labels everywhere and never CAPS-5 on Dosing or Post-dosing
- **Severity:** major
- **Environment:** local, single-instance too
- **Journey:** J3
- **Steps:** Run the MDMA example to close. Read Mission control, Dosing and Post-dosing.
- **Expected:** CAPS-5 labels throughout. The protocol says "change in CAPS-5 total severity at week 8".
- **Actual:** MADRS shows on every page and CAPS-5 shows nowhere on Dosing or Post-dosing:
  - Mission control: "Collected 3 follow-up visits (MADRS, end-of-treatment guess and expectancy)".
  - Dosing: "Recorded 2 rater assessment(s): MADRS plus the rater's guess" and "week-6 MADRS".
  - Post-dosing FDA report: "COMP005: -3.6 MADRS points vs placebo".
  - The drift slip text also says "MADRS interviews".
- **Evidence:** `docs/testing/screenshots/local-single-J3-1.png` to `local-single-J3-5.png`
- **Suspected root cause:** Hard-coded "MADRS" strings, and a `madrs` field, in `dosing/agents.py:230,365-366`, `dosing/module.py:190`, `dosing/monitor.py:228`, and in `postdose/agents.py`, `postdose/module.py:7` and `postdose/effects.py`. Predose has a scale map (`predose/agents.py:34,820`) that the other modules do not use.
- **Owner files:** dosing (Izzy) and postdose (Callum), via TEAMMATE_PATCHES.md. Also `world.py`.

## BL-5: A pasted custom protocol's site names are ignored, and the example sites are used instead
- **Severity:** major
- **Environment:** local, single-instance too
- **Journey:** J4
- **Steps:** Paste a protocol with "Site A (Leeds), Site B (Glasgow) and Site C (Cardiff)", create it, approve the shortlist and play to close.
- **Expected:** Leeds, Glasgow and Cardiff appear in every site label.
- **Actual:** None of the pasted names appear anywhere. Every page shows "Site A (London)", "Site B (Manchester)" and "Site C (Bristol)", for example "participant unblinding at Site C (Bristol)".
- **Evidence:** `docs/testing/screenshots/local-single-J4-1.png`, `local-single-J4-2.png`
- **Suspected root cause:** Hard-coded `SITES` in `unblind/platform/world.py:25`, `unblind/platform/predose/agents.py:17` and `unblind/platform/master/stubs.py:70`.
- **Owner files:** `world.py`, `predose/agents.py`, `master/stubs.py`

## BL-6: The garbage protocol "!!! ???" is accepted as a full trial
- **Severity:** major
- **Environment:** local, single-instance too
- **Journey:** J5
- **Steps:** Start a trial, click Blank page, type `!!! ???` and click Create trial.
- **Expected:** A clear message that this is not a protocol, and no trial.
- **Actual:**
  - A trial is created (toast "Trial T-124830-6d89 created").
  - Pre-dosing reads "Protocol: !!! ???. 500 applicants screened."
  - The agents propose 5 protocol fixes, and the shortlist slip reads "confirm shortlist of 0 eligible applicants and review 215 flagged".
  - No warning is shown anywhere.
- **Evidence:** `docs/testing/screenshots/local-single-J5-1.png`, `local-single-J5-2.png`, `local-single-J5-3.png`
- **Suspected root cause:** There is no validation in `backend/main.py:create_trial` (around line 100) or in the predose protocol parser. Any non-empty text becomes a protocol.
- **Owner files:** `backend/main.py`, `unblind/platform/predose/agents.py`, `frontend/src/components/mission/StartTrial.tsx`

## BL-7: The drift agent proposes "move raters to remote" when the protocol already uses central remote raters
- **Severity:** minor (demo credibility)
- **Environment:** local, single-instance too
- **Journey:** J1, J3
- **Steps:** Either approve "Protocol fix: Move outcome raters to central, remote, blinded assessment" in the psilocybin trial, or use the MDMA example (its protocol already has "central blinded raters by videoconference"). Then play.
- **Expected:** No site rater drift, or at least no proposal to switch to remote raters.
- **Actual:** "Move Site B raters to remote (central) assessment" appears on day 47 (psilocybin). "Move Site C raters to remote (central) assessment" appears on day 33, and again on day 74 (MDMA). Approving the central-raters fix only suppresses the follow-up amendment. The drift itself still happens.
- **Evidence:** J1 and J3 notes in `results/local-single.json`, plus API probes on 8101.
- **Suspected root cause:** The simulated drift in `world.py` and `dosing/monitor.py:227` ignores `protocol.rater_model`.
- **Owner files:** `unblind/platform/world.py`, and `dosing/monitor.py` (Izzy)

## BL-8: "UNBLIND" still shows in the UI as "UNBLIND-BLIND-1"
- **Severity:** minor
- **Environment:** local, single-instance too
- **Journey:** J1, J2, J5, F
- **Actual:** The old name appears in four places:
  - Slip "Protocol fix: Add the UNBLIND-BLIND-1 guess questionnaire..."
  - Slip "Release the UNBLIND-BLIND-1 harmonised export"
  - Readout "BLINDING ROWS EXPORTED IN UNBLIND-BLIND-1"
  - The FDA report text "Standard: UNBLIND-BLIND-1"
- **Expected:** Parallax naming throughout.
- **Owner files:** `unblind/platform/predose/agents.py` (measurement standard), `postdose` (Callum), and the `frontend/src/styles/tokens.css:1` comment (not rendered)

## BL-9: Grammar "1 changed lines"
- **Severity:** minor
- **Environment:** local, single-instance too
- **Journey:** J7
- **Actual:** The toast says "SENT FOR APPROVAL · 1 CHANGED LINES". The slip title says "Protocol amendment: edit by QA Tester (1 changed lines)".
- **Owner files:** `frontend/src/components/predose/ProtocolEditor.tsx:110` and the predose `recheck` slip title

## BL-10: The bias gate rewrites an unblinding question into nonsense
- **Severity:** minor
- **Environment:** local, single-instance too
- **Journey:** J10
- **Actual:** "Do you think you received psilocybin or the placebo capsule?" is rewritten to "Do you think you received the study session or the study session capsule?"
- **Owner files:** `unblind/platform/postdose/` (Callum)

## BL-11: The Evidence engine nav link goes to http://localhost:8501 and fails to load
- **Severity:** minor (major on production, where it can never work)
- **Environment:** local, single-instance too
- **Journey:** J15
- **Steps:** Click "Evidence engine" in the nav.
- **Expected:** The evidence engine opens, or the link is hidden when the engine is not deployed.
- **Actual:** A new tab opens on `chrome-error://chromewebdata/`, because nothing is listening on 8501.
- **Evidence:** J15 in `results/local-single-b.json`; failure screenshots `local-single-J15-*.png`.
- **Suspected root cause:** the default `evidenceUrl = "http://localhost:8501"` in `frontend/src/components/shared/GlassNav.tsx:76`.
- **Owner files:** `frontend/src/components/shared/GlassNav.tsx`

---

## Passed checks (single instance, 5174 to 8101)
- **J1:** manual approvals pass end to end. 2 fixes, then the shortlist, then the drift slip on day 47 (approved), then the amendment "Make remote central raters permanent at every site" (approved), then play to day 90, then the FDA report signed. The header and seal say "signed". Total 24 s, with no console errors and no failed requests. Note: if the central-raters fix is one of the 2 fixes signed, the amendment never appears (see BL-7).
- **J2:** auto-approve reaches day 90 in 18 s. No slips are pending, the stamps read "Auto-approved (demo)", and the header says the report was signed by the demo reviewer. The only failure was BL-8.
- **J3:** the drift is at Site C on day 33, as expected.
- **J6:** all portal cases pass:
  - The valid profile is Eligible.
  - The bipolar free text gives Needs clinician, with the quote.
  - Age 17, a non-UK phone, lithium, and psychedelic use 3 months ago are each Excluded, with a reason.
  - A non-numeric age gives an inline error, focus moves to the field, and no request is sent.
- **J7:** an edit before enrolment becomes v2 at once. After enrolment, two edits go for approval as 2 slips. Approving one adds v3, and rejecting the other adds no version.
- **J8:** rejecting the shortlist brings a re-request, and approving it enrols participants.
- **J9:** an approved drift action shows "Applied the action approved by..." on Dosing. A rejected one shows "rejected... Monitoring continues". The stamps are correct.
- **J11:** reload on all 5 pages keeps the trial and the day. A second tab shows the same trial and day after a step. Deep links to /predose, /portal, /dosing and /postdose return 200 with and without a trial ("No trial yet" when there is none). An unknown path redirects to /.
- **J14:** `/api/health` reports gemini=false, and the dock pill reads "GEMINI OFF". Portal screening works without Gemini.
- **J13 (partial):** in 2 minutes, 7 trials ran 578 simulated days with 292 step calls. Step latency was p50 36 ms and max 98 ms. A 30-day API step took 0.39 s (day 31 to 61), and a 31-day step was clamped to 30 (0.44 s, reaching day 90). Not confirmed: in one cycle the Play loop stopped at day 31 with no toast, possibly a race in the script. Re-check before filing.
- **Timings (single instance):** create trial 0.07 to 0.11 s, decide 0.06 s, play to close 18 s. API steps took about 0.02 to 0.03 s per day.

## Not run or incomplete (time box)
- **J12:** aborted by a script error: the script clicked "+1 week" while the trial was blocked on approvals. The dark-mode 390 px screenshot is at `docs/testing/screenshots/local-single-J12-1.png`. Contrast and scroll were not concluded.
- **F (design and copy) and G (keyboard):** the scripts are written (`f_design_copy.py`, `g_keyboard.py`) but were not run before the time box ended. BL-8 (UNBLIND naming) came from the copy checks inside J1, J2 and J5. No em dash was found in any page those journeys checked.
- **Proxy run:** J1 to J6 completed and all fail with BL-1 symptoms:
  - J3: the trial vanished right after creation.
  - J4: approving the shortlist failed with "no trial ... in this server session".
  - J6: alternate portal applications came back "NOT SCREENED: no trial T-125531-572b in this server session" while the others screened normally.
- **Proxy run, not run:** J7 onwards were not run or not finished at hand-off.
