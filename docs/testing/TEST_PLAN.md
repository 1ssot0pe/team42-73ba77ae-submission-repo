# Parallax end-to-end test plan

Branch: `danny-frontend` (worked locally as `danny-frontend-e2e`, based on `origin/main` at `5df9b59`).
Production: https://parallax-two-tau.vercel.app (public). Preview deployments sit behind Vercel Authentication, so use `vercel curl` for API calls there. Browser runs on a preview need a protection-bypass token.

Baseline before any fix: `pytest -q` gives **141 passed**; `npm run build --prefix frontend` builds fine (JS bundle 660.8 kB, 191.5 kB gzip).

## Environments and ports

| Use | Ports |
|---|---|
| Tester API: two uvicorn instances plus the round-robin proxy | 8001, 8002, proxy on 8000 |
| Tester Browser-Local: two uvicorn instances, the proxy, and vite | 8101, 8102, proxy on 8100, vite on 5173 (`VITE_API_TARGET=http://127.0.0.1:8100`) |
| Production | https://parallax-two-tau.vercel.app |

The proxy is `tests/e2e/rr_proxy.py`. It is stdlib only and alternates requests between backends. Each response carries an `X-RR-Backend` header naming the backend that served it.

Start each uvicorn instance with `UNBLIND_TRIALS_DIR=/tmp/parallax-e2e/<port>`, so that instances cannot share state through disk the way they can't on Vercel.

## A. Regression
- Run `.venv/bin/python -m pytest -q`. All tests must pass before and after the fixes.

## B. API contract (every route in `backend/main.py`)
For each of `health`, `bottlenecks`, `protocols`, `protocols/{name}`, `POST trials`, `GET trials`, `state`, `step`, `auto_approve`, `record`, `events`, `approvals`, `POST approvals/{aid}`, `kpis`, `messages`, `modules/{m}/view`, `modules/{m}/actions/{a}` and `evidence/run`:
- Success shape and status code.
- Error codes: unknown trial gives 404; bad decision value or missing reviewer gives 400; an unknown or already-decided approval gives 404; a bad body gives 422; path traversal on `protocols/{name}` gives 404; an unknown module or action gives 4xx, never 500.
- Privacy: no key starting with `_`, and no allocation or arm assignment, at any depth of any response. Walk the JSON recursively.
- Size: flag any response over 1 MB, and record the size for a trial at day 0, 45 and 90.
- Latency: p50 and max per endpoint, and for `step` with 1, 7 and 30 days.

## C. Statelessness (the suspected root cause)
- Run two instances behind the round-robin proxy. Create a trial, step it, approve something, call module actions, and fetch record and events. Every request must succeed whichever instance serves it.
- Instance loss: create a trial on 8001, kill 8001, and continue on 8002.
- Measure, to inform the state-fix options: the size in KB of a serialised trial at day 0, 45 and 90 (pickle and JSON of the record), and the time to replay a full trial from scratch.

## D. Browser journeys (Python Playwright, Chromium)
Run each journey locally (vite against the round-robin proxy) and on production. Record console errors, failed network requests (status, URL, body), screenshots at failure points (`docs/testing/screenshots/`), and timings.

| # | Journey |
|---|---|
| J1 | Psilocybin example with manual approvals: create, sign 2 fixes, approve the shortlist, play to close, approve the drift action and the follow-up amendment, sign the FDA report |
| J2 | Auto-approve on, play to close |
| J3 | MDMA example to close: CAPS-5 labels everywhere, drift at Site C |
| J4 | Pasted custom protocol with other site names |
| J5 | Garbage protocol (`!!! ???`) |
| J6 | Volunteer portal: valid applicant, bipolar in free text, age 17, non-UK phone, lithium, psychedelic use 3 months ago, non-numeric age |
| J7 | Protocol edit before enrolment (applies directly) and after enrolment (goes for approval; approve one, reject one) |
| J8 | Reject the clinician shortlist, then approve the re-request |
| J9 | Drift action approved vs rejected |
| J10 | Post-dosing researcher question (neutral, leading, unblinding, identifying), before and after the primary lock |
| J11 | Refresh mid-trial on each page; open a second tab; deep-link to `/predose`, `/portal`, `/dosing`, `/postdose` |
| J12 | Dark mode and 390 px width on every page |
| J13 | Play continuously for 2 minutes (polling under load); step 30 days at once (duration limit) |
| J14 | Gemini off (local); Gemini on (production has `GEMINI_API_KEY`) |
| J15 | Every nav link, including Evidence engine (currently `localhost:8501`) |

## E. Production specifics
- Cold start time: the first request after idle, and `x-vercel-*` headers.
- Function duration per endpoint against `maxDuration` 60 (`vercel logs`, `vercel inspect`).
- Function bundle size, writes to `/tmp`, rewrites (`/api/*`, deep links, `/assets/*`), asset cache headers, CORS.
- Environment variables, by name only (`vercel env ls`). Never print values.

## F. Design and copy
- SYNTHETIC labels on all simulated data.
- No em dashes in UI text.
- Parallax naming throughout, with no stray "UNBLIND" in the UI.
- Text contrast on glass panels in both themes.
- No horizontal scroll at 390 px.

## G. Accessibility smoke test
- Keyboard through the nav, the dock, approvals and forms.
- Focus is always visible, and the tab order makes sense.

## Bug ledger
Each tester writes to `docs/testing/bugs/<tester>.md`. The orchestrator merges these into `docs/testing/BUGS.md`. Each bug records: id, severity (blocker / major / minor), environment (local / prod / both), journey, steps to reproduce, expected, actual, evidence, suspected root cause, and owner files.

**Ownership:** Danny owns `predose/`, `master/`, `core.py`, `world.py`, `backend/`, `api/`, `frontend/` and `vercel.json`. `dosing/` (Izzy) and `postdose/` (Callum) are not edited. Patches for bugs in their code go in `docs/testing/TEAMMATE_PATCHES.md`.
