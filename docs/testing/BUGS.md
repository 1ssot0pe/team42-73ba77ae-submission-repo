# Bug ledger (merged)

Sources: `bugs/api.md` (API-*), `bugs/browser-local.md` (BL-*), `bugs/browser-prod.md` (BP-*). Duplicates are merged under the first id. Full steps, evidence and screenshots are in the source ledgers.

Status: **fixing** = a fixer is on it on the named branch; **fixed** = merged with a regression test; **open** = documented, not fixed in this pass, with the reason.

| ID | Sev | Env | Summary | Root cause | Owner / where | Status |
|---|---|---|---|---|---|---|
| API-1 (= BL-1, BP-1) | blocker | both | Trials vanish: 68% of prod follow-up calls got 404, and 79% in real browser use (concurrent GETs fan out across instances). Locally 13 of 27 through the round-robin proxy failed; instance loss gave 5 of 5 failures | Trials live in one process's memory (`backend/main.py:24` `TRIALS`, `_m()`). The vault and export salt sit in each instance's `/tmp` | Danny: `backend/`, `core.py`, `master/`, new `store.py` | **fixed** (`fix/state`). Tests: `tests/platform/test_store.py`, `test_statelessness.py`. Verified locally on two instances: 0 of about 3,400 trial calls failed, and the trial survives instance loss. Store tests pass against the real Neon database. Preview and prod wait on `DATABASE_URL` in Vercel |
| BP-2 (+ part of BL-1) | major | both | On one 404 the UI silently clears the trial and goes back to "Start a trial", with a raw server message in a toast; stale data mixes with inline errors; one Approve took 23 tries | `trial.tsx:72-88` clears the trial on any 404; no retry or backoff | Danny: `frontend/src/api.ts`, `trial.tsx` | **fixed** (`fix/frontend`). Test: `tests/e2e/frontend/test_resilience.py`. Verified: retries during an outage, and a "Trial ... has expired" screen after a confirmed loss |
| API-7 (= BP-5) | minor | prod | Hashed `/assets/*` served with `max-age=0, must-revalidate` | No `headers` rule in `vercel.json` | Danny: `vercel.json` | **fixed** (`fix/vercel`, test `tests/platform/test_vercel_config.py`). Prod check pending a deploy |
| API-8 (= BP-4) | minor | both | `/api/health` and `GET /api/trials` list every visitor's trial ids, so anyone can drive or sign another trial | Listing endpoints expose ids | Danny: `backend/main.py` | **fixed** (`fix/state`, regression tests in `tests/platform/test_statelessness.py`) |
| API-3 | minor | both | `events?limit=0` returns every row; `limit=-1` drops the first | `rows[-limit:]` with no bounds (`main.py:165`) | Danny: `backend/main.py` | **fixed** (`fix/state`, regression tests in `tests/platform/test_statelessness.py`) |
| API-2 | minor | both | Unknown module or action returns 200 with an error body, not 4xx | `orchestrator.py:259,266`, passed through by `main.py:205-216` | Danny | **fixed** (`fix/state`, regression tests in `tests/platform/test_statelessness.py`) |
| API-4 | minor | both | Portal age `1e400` gives a generic "module action failed" | Overflow not caught (`predose/module.py:330-331`) | Danny | **fixed** (`fix/state`, regression tests in `tests/platform/test_statelessness.py`) |
| API-5 | minor | both | Server stack traces (with `/var/task/...` paths on prod) are sent to the browser in event data | `orchestrator.py:83-84` | Danny | **fixed** (`fix/state`, regression tests in `tests/platform/test_statelessness.py`) |
| BP-7 | minor | prod | The function runs in iad1 (US East) while visitors and the edge are in London, so every API call crosses the Atlantic (about 120 to 240 ms per GET) | Default region | Danny: `vercel.json` `regions` | open: the region should match the Neon database region, so it waits on that choice |
| API-6 | minor | both | `GET record` is 2.1 MB at 2000 applicants and day 90; the Predose page re-downloads about 430 KB of applicants every tick | The page requests all sections | Danny: frontend pages | open: needs page changes, and pages belong to the redesign (`redesign/platform-ui`) |
| BL-11 (= BP-3) | major | prod | Evidence engine nav link points at `http://localhost:8501`, so production opens a connection error | `GlassNav.tsx:56,76` default | Danny: `GlassNav.tsx` | open: the file belongs to the redesign. Fix: hide the link unless `VITE_EVIDENCE_URL` is set |
| BL-2 | major | both | A rejected researcher question shows "ACCEPTED Rejected: ..." | postdose returns `ok: true` for a rejection; `ViewForm.tsx:51` reads `ok` as accepted | Callum: postdose (or the redesign: ViewForm) | open: TEAMMATE_PATCHES TP-3 |
| BL-3 | major | both | MDMA trial: "0 of 73 participants have a week-6 MADRS" at lock (primary week is 8) | `dosing/agents.py:362` counts week 6 only | Izzy: dosing | open: TEAMMATE_PATCHES TP-1 (re-confirmed in verification) |
| BL-4 | major | both | MDMA/PTSD trial shows MADRS labels; CAPS-5 never appears on Dosing or Post-dosing | Scale hard-coded in dosing and postdose strings | Izzy, Callum | open: TEAMMATE_PATCHES TP-2 |
| BL-5 | major | both | A pasted protocol's site names (Leeds, Glasgow, Cardiff) are ignored; London, Manchester and Bristol are used | Sites hard-coded in `world.py:25`, `predose/agents.py:17`, `master/stubs.py:70` | Danny | open: a behaviour change across the world model and three modules. Too risky for this time box |
| BL-6 (= BP-8) | major | both | Garbage protocol `!!! ???` accepted as a full trial (500 screened, 5 or 6 fixes, shortlist of 0), no warning | Parser falls back to defaults silently | Danny: predose parser | open: needs a product decision (reject, or warn and continue) |
| BL-7 | minor | both | Drift agent proposes "move raters to remote" when raters are already central and remote; after that fix is signed, the follow-up amendment never appears | Monitor ignores the current rater model | Izzy: `dosing/monitor.py` | open: teammate code |
| BL-8 (= BP-6) | minor | both | "UNBLIND-BLIND-1" appears in the UI | Data-standard id shared across modules | All three | open: TEAMMATE_PATCHES TP-5 (contract change) |
| BL-9 | minor | both | Copy reads "1 changed lines" | No pluralisation | Frontend (ProtocolEditor) | open: redesign branch |
| BL-10 | minor | both | Bias-gate rewrite gives "the study session or the study session capsule" | Word-by-word replacement | Callum: postdose | open: TEAMMATE_PATCHES TP-4 |

## Found during verification

| ID | Sev | Env | Summary | Status |
|---|---|---|---|---|
| NEW-1 | minor | local (round-robin) | Play stopped when one step hit a dead backend 3 times in a row (502) | **fixed**: POSTs retry up to 5 times on 502/503 (the function never ran, so a retry cannot apply a step twice). Not on 504. Test `test_four_502s_on_step_still_advance` failed before the fix and passes after |
| NEW-2 | minor | both | A module action sent without the `payload` wrapper returns 200 and adds a blank applicant ("Age not stated"). The UI always sends the wrapper | open: input validation in `backend/main.py` `Action` model. Low risk, but not done in this time box |
| NEW-3 | minor | both | A trial id that never existed is described as "has expired", and the lost-trial screen has no app navigation | open: copy and layout belong to the redesign |
| NEW-4 | minor | both | After an outage, a "server had a problem (502)" toast can still show although Play recovered | open: ControlDock belongs to the redesign |
| F-1 | minor | both | Contrast below 4.5:1 on glass: nav "↗" glyph 2.57:1, Portal result line 2.56:1, W12/D90 labels 4.43:1, dark dock Play 3.95:1 | open: redesign |
| G-1 | minor | both | No visible focus ring on the start-page protocol textarea or on the approval slips' reviewer and comment inputs | open: redesign |
| BL-7 note | | | In verification J1, the follow-up amendment did appear after the drift fix was signed. The "proposes remote raters when already remote" part still reproduces (J9) | open |
| Script | | | J10's check is case-sensitive ("Accepted" vs "ACCEPTED"); J12 clicks "+1 week" while it is disabled. Fixed copies: `tests/e2e/verify/j6-10/`, `tests/e2e/verify/j11-15/` | test scripts only |

## Not run in the first round
- F (design and copy) and G (keyboard) scripts are written (`tests/e2e/browser/f_design_copy.py`, `g_keyboard.py`) but were not run before the time box. No em dashes were seen on the pages checked in J1 to J5.
- J12 (dark mode, 390 px): the script stopped on a test-script error, so there is no conclusion.
- On prod, everything after trial creation in J1 to J14 was blocked by API-1, so those steps get verified on the preview after the fix.
- Prod cold start after a real idle period, and per-request function duration (the hobby plan keeps no runtime logs).
