# Tester API: bug ledger (sections B, C, E)

Branch `danny-frontend-e2e` at `5df9b59`. Local: uvicorn on 8001 and 8002 (`UNBLIND_TRIALS_DIR=/tmp/parallax-e2e/<port>`), round-robin proxy on 8000. Gemini was off locally and on in production. Prod: https://parallax-two-tau.vercel.app (deployment `dpl_Ez6UFiAATUjNQFPSSxH5SMC1Bqii`, function `api/index` 30.63 MB, region iad1).

Scripts (all runnable with `.venv/bin/python`; raw outputs in `tests/e2e/api/results/`):

| Script | What it does |
|---|---|
| `tests/e2e/api/contract.py --base http://127.0.0.1:8001` | B: every route, error codes, privacy walk, sizes, latency (104 checks) |
| `tests/e2e/api/stateless.py journey / kill / restart` | C: journey through the proxy, instance loss, restart from disk |
| `tests/e2e/api/snapshot_replay.py` | C: pickle and JSON sizes at day 0, 45 and 90, replay time, determinism diff |
| `tests/e2e/api/concurrency.py` | Parallel decides, steps and reads on one trial; RSS per trial |
| `tests/e2e/api/prod.py [--only cold\|burst\|reliability\|step30\|edges\|latency\|evidence]` | E: production checks |

## Bugs

### API-1: Trials live only in one process's memory, so most requests on Vercel return 404 and human sign-offs are lost
- **Severity:** blocker. **Environment:** both. **Area:** every trial-scoped route (all journeys)
- **Steps:** (a) local: `stateless.py journey` creates a trial through the round-robin proxy and runs a normal journey. (b) `stateless.py kill`: create the trial on 8001, kill 8001, continue on 8002. (c) Restart 8001 with the same trials directory, then `stateless.py restart`. (d) prod: `prod.py --only reliability --n 40`: create one trial, then send sequential follow-up requests.
- **Expected:** every follow-up request finds the trial, whichever instance serves it.
- **Actual:**
  - (a) 13 of 27 requests failed. Every request routed to 8001 got a 404 and every request routed to 8002 got a 200. 3 of the 6 approvals were lost (`approve 1832ac79 404 via 8001`, and the same for two others), so the trial stayed blocked. The step, the dosing check-in, the postdose question, the events request and the 30-day step were also lost (`results/stateless_journey.txt`).
  - (b) 8002 directly: 5 of 5 requests got 404 `no trial ... in this server session`. Through the proxy: 3 got 502 and 2 got 404 (`results/stateless_kill.txt`).
  - (c) `/tmp/parallax-e2e/8001/T-124433-79dd.json` is still on disk (735 KB), but the restarted server returns 404 for the trial (`results/stateless_restart.txt`).
  - (d) Three prod runs had 404 rates of 34 of 40 (85%), 7 of 40 (18%) and 54 of 60 (90%). That is **95 of 140 (68%)** overall. The health probe saw at least 3 instances, holding 4/5/6 and later 1/2/20/21 trials.
  - Vercel request logs (last 30 min, all clients): 314 of 462 trial-scoped requests got 404 (68%). `POST approvals/{aid}` got 404 on 26 of 28 calls, `POST step` on 7 of 11. The other tester's headless browser got 404 on 109 of 147. There were no 5xx.
- **Suspected root cause:** `backend/main.py:24` (`TRIALS: Dict[str, Master] = {}`) and `backend/main.py:32-35` (`_m` never falls back to disk). There is no way to rebuild a `Master` from a saved record. Per-instance `/tmp` also holds the vault (`unblind/platform/core.py:149`) and the export salt (`unblind/platform/postdose/agents.py:72-82`), so moving only the record would not be enough. `api/index.py:4` documents the problem.
- **Owner:** `backend/main.py`, `api/index.py`, `unblind/platform/master/orchestrator.py`, `unblind/platform/core.py`

### API-2: An unknown module or action returns 200 with an error body instead of 4xx
- **Severity:** minor. **Environment:** both. **Area:** `modules/{m}/view`, `modules/{m}/actions/{a}`
- **Steps:** `GET /api/trials/{tid}/modules/nosuch/view`, `POST .../modules/nosuch/actions/x`, and `POST .../modules/dosing/actions/nosuch` with `{"payload":{}}`.
- **Expected:** 404 (or 400), as the test plan requires.
- **Actual:** `200 {"error":"unknown module nosuch"}`. The action calls return `200 {"result":{"ok":false,"error":"dosing has no action 'nosuch'"},"state":...}`. The same happens for predose and postdose, and on prod (`results/prod_contract_spot.txt`). It is never a 500.
- **Suspected root cause:** `unblind/platform/master/orchestrator.py:259` and `:266` return error dicts, and `backend/main.py:205-216` passes them through as 200. The module fallbacks are at `dosing/module.py:130`, `postdose/module.py:139` and `core.py:311`.
- **Owner:** `backend/main.py`, `unblind/platform/master/orchestrator.py`

### API-3: `events?limit=0` returns every row, and a negative limit returns the wrong slice
- **Severity:** minor. **Environment:** both. **Area:** `GET /api/trials/{tid}/events`
- **Steps:** `GET .../events?limit=0` and `GET .../events?limit=-1`.
- **Expected:** `limit=0` returns no rows (or a 422), and a negative limit gets a 422.
- **Actual:** `limit=0` returned 27 of 27 rows locally and 13 of 13 on prod. `limit=-1` returned 26 of 27 rows, which is everything except the first row.
- **Suspected root cause:** `backend/main.py:165`. `rows[-limit:]` turns `-0` into the whole list. `limit` has no `Query(ge=1)` bound.
- **Owner:** `backend/main.py`

### API-4: A portal applicant with a huge number gives a generic "module action failed"
- **Severity:** minor. **Environment:** both. **Area:** predose `apply` (portal, J6)
- **Steps:** `POST .../modules/predose/actions/apply` with `{"payload":{"name":"x","age":"1e400"}}`.
- **Expected:** `{"ok":false,"error":"'age' must be a whole number"}`.
- **Actual:** `{"ok":false,"error":"module action failed; see timeline"}`, plus a warn event `predose raised OverflowError: cannot convert float infinity to integer`.
- **Suspected root cause:** `unblind/platform/predose/module.py:330-331`. `int(float("1e400"))` raises `OverflowError`, which the `except (TypeError, ValueError)` does not catch.
- **Owner:** `unblind/platform/predose/module.py`

### API-5: Server stack traces with absolute file paths are sent to the browser in event `data`
- **Severity:** minor. **Environment:** both. **Area:** `GET /api/trials/{tid}/events`
- **Steps:** Trigger any module exception (for example API-4), then `GET .../events?level=warn`.
- **Expected:** a short error message, with the traceback kept in server logs only.
- **Actual:** on prod, `data` contains `File "/var/task/unblind/platform/master/orchestrator.py", line 81, in _safe ... File "/var/task/unblind/platform/predose/module.py", line 330` (`results/prod_traceback_leak.txt`).
- **Suspected root cause:** `unblind/platform/master/orchestrator.py:83-84` stores `traceback.format_exc()` in the record, and `_strip_private` only drops `_` keys.
- **Owner:** `unblind/platform/master/orchestrator.py` (or filter in `backend/main.py` `events`)

### API-6: `GET record` exceeds 1 MB for large trials, and the Predose page refetches about 430 KB of applicants on every tick
- **Severity:** minor. **Environment:** both (gzip on prod softens the wire cost). **Area:** `GET /api/trials/{tid}/record`, Predose page
- **Steps:** Create with `n_applicants=2000, auto_approve=true`, run to day 90, then `GET .../record`.
- **Expected:** under 1 MB.
- **Actual:** 2,125,690 bytes locally and on prod. `applicants` alone is 1,578,860 bytes. With the default n=500, `GET record` is 545 KB at day 0, 772 KB at day 45 and 863 KB at day 90. The Predose page's own section list is 428 KB (applicants 394 KB), and it refetches on every `tick` (`frontend/src/pages/Predose.tsx:23,49`).
- **Suspected root cause:** `backend/main.py:146-151` returns whole applicant rows (each has screening evidence). There is no pagination or summary view.
- **Owner:** `backend/main.py`, `frontend/src/pages/Predose.tsx`

### API-7: Hashed `/assets/*` files are served with `max-age=0`
- **Severity:** minor. **Environment:** prod. **Area:** static hosting
- **Steps:** `curl -I https://parallax-two-tau.vercel.app/assets/index-CdtYRAEv.js`.
- **Expected:** `Cache-Control: public, max-age=31536000, immutable` for content-hashed files.
- **Actual:** `cache-control: public, max-age=0, must-revalidate`. The request logs show browsers revalidating with 304s on every navigation.
- **Suspected root cause:** `vercel.json` has no `headers` rule for `/assets/(.*)`.
- **Owner:** `vercel.json`

### API-8: Trials are never evicted, and every visitor can list, step and sign other people's trials
- **Severity:** minor. **Environment:** both. **Area:** `GET /api/trials`, `GET /api/health`, process memory
- **Steps:** `concurrency.py` creates 40 trials on 8002 and runs them to day 89. Separately, `GET /api/trials` on prod.
- **Expected:** a bounded number of trials per instance, and only your own trials visible.
- **Actual:**
  - RSS went from 78 MB to 119 MB after creating the 40 trials (about 1 MB each), and to 158 MB after running them (about 2 MB per run trial). Nothing is ever freed.
  - On prod, one instance listed 21 trials, and `GET /api/trials` returned the full state of 10 trials belonging to other people.
  - With a listed id, anyone can step a trial or approve its decisions under any reviewer name.
- **Suspected root cause:** `backend/main.py:24` has a global dict with no TTL. `backend/main.py:75` and `:118-123` list every trial.
- **Owner:** `backend/main.py`

## Measurements

### Serialised trial size (in-process, psilocybin example, n=500, auto-approve; `results/snapshot_replay_n500.json`)

| Day | Record JSON | Record JSON gzip | Record on disk (indent=1) | Pickle of Master (lock and llm dropped) | Pickle gzip | Vault JSON | World pickle |
|---|---|---|---|---|---|---|---|
| 0 | 611.8 KB | 34.5 KB | 701.8 KB | 266.4 KB | 46.0 KB | 1.1 KB | 12.9 KB |
| 45 | 882.0 KB | 53.5 KB | 1012.5 KB | 407.3 KB | 66.6 KB | 29.2 KB | 31.4 KB |
| 90 | 1057.4 KB | 72.6 KB | 1215.1 KB | 512.3 KB | 83.1 KB | 54.6 KB | 46.6 KB |

- **Pickling the Master untouched fails** with `TypeError: cannot pickle '_thread.RLock' object`. Two attributes block it:
  - `m.lock` (`threading.RLock`, `orchestrator.py:52`)
  - `m.ctx.llm` (the `unblind.llm` module, `orchestrator.py:62`), whose submodules (`json`, `os`, `JSONDecoder`/`_json.Scanner`) cannot be pickled
- After setting `lock=None` and `ctx.llm=None`, **everything else pickles**: the record, bus, approvals, vault (including the allocation), world with its RNG state, the three modules, and `ctx.rng`.
- Unpickling takes about 1 ms. The restored Master still shares one record object across `ctx`, `bus` and `approvals`, and it can `step()` once the lock and llm are re-attached.
- Caveats: the pickle contains `vault._alloc`, so it must stay server-side. A pickle is tied to the code version.

### Replay (same seed, auto-approve, creation to close, in-process)
- **1.94 to 1.97 s** per full trial (3 runs). Setup takes 0.02 to 0.03 s.
- **0.06 s** with `TrialRecord.save` disabled: about 97% of replay and step time is the record write.
- The record is written 31 times per 30-day step (`orchestrator.py:152` `_settle` runs once per simulated day, and `:238`), each time as indent=1 JSON of up to 1.2 MB.

### Determinism (two replays with the same seed compared field by field)
- Allocation is identical (`same_alloc: true`). Every event text is identical except one: the report sign-off text, which embeds a digest.
- **Approval and message ids** differ: `uuid.uuid4()` at `unblind/platform/core.py:84` (messages) and `:106` (approvals). Replaying human decisions by approval id therefore cannot work; decisions would have to be replayed by order.
- **Trial id:** `backend/main.py:109` `time.strftime('%H%M%S') + uuid4`.
- **Wall-clock fields:** `core.py:52` (`created`), `core.py:59` (`events[].t`), `core.py:162` (vault access-log time).
- **Export pseudonym salt:** random per trial directory, `secrets.token_hex(16)` at `unblind/platform/postdose/agents.py:81`. Pseudonyms (`exports.preview[].pid`) and the report digest change across replays and across Vercel instances. `UNBLIND_EXPORT_SALT` is not set on prod.
- **Gemini:** on prod, Gemini calls are non-deterministic. They happen in routing (`orchestrator.py:93`), debrief structuring (`dosing/agents.py:75`), check-ins (`dosing/agents.py:180`), protocol parsing and screening (`predose/agents.py:204`, `:671`) and postdose (`postdose/agents.py:318`, `:452`). A replay on prod would need cached LLM answers.
- **Decision order matters:** approving the shortlist before a pending fix expires that fix (seen in `concurrency.py`). A replay log must keep the exact order of decisions and step boundaries.

### Local latency (single instance 8001; `results/contract_local8001.json`)
- GET routes: p50 under 3.5 ms (`state` 0.6, `events` 3.4, `view dosing` 3.0). `record`: p50 25 ms, max 66 ms.
- POST `approvals/{aid}`: p50 6 ms, max 14 ms. Module actions: 6 to 15 ms. Create: 17 ms.
- Step: 1 day p50 16 ms (max 58). 7 days p50 73 ms (max 81). 30 days 227 to 388 ms (n=500) and up to 820 ms (n=2000). `days=1000` is clamped to 30 (352 ms).

### Response sizes (bytes, n=500, manual approvals)

| Day | state | record (all) | events (default) | approvals all | messages | view dosing | view postdose |
|---|---|---|---|---|---|---|---|
| 0 | 462 | 544,978 | 10,709 | 11,337 | 13,030 | 6,047 | 2,742 |
| 45 | 467 | 772,347 | 78,952 | 17,646 | 20,406 | 28,147 | 4,396 |
| 90 | 488 | 862,640 | 87,596 | 21,249 | 29,337 | 39,872 | 19,067 |
| 90 (n=2000) | 530 | **2,125,690** | 87,536 | 25,414 | 37,466 | 41,024 | 19,668 |

### Production
- **Cold start:**
  - On idle older production deployments (via `vercel curl`), the first `GET /api/health` took 1.85 s and 1.48 s, against 0.17 to 0.23 s warm.
  - The first `POST /api/trials` on an idle deployment took 3.27 s, against 0.70 s warm.
  - The live alias was never idle during testing, because another tester was active. Its first request took 313 ms.
  - Headers: `x-vercel-cache: MISS`, `x-vercel-id: lhr1::iad1::...`. The edge is in London and the function runs in iad1 (US East), which adds a transatlantic round trip to every API call.
  - A burst of 16 concurrent requests did not start a fresh instance (Fluid compute reuses instances).
- **404 rate for a just-created trial:** 95 of 140 sequential follow-ups (68%), from runs of 85%, 18% and 90% (API-1).
- **Step days=30:** 0.24 to 3.5 s (n=500) and up to 5.4 s (n=2000), against `maxDuration` 60 s. That is under 10% of the budget.
- **Latency (warm, successful responses only; `results/prod_latency.json`):**
  - p50 120 to 230 ms for GET routes. `health` p50 323 ms, and `protocols` max 1.3 s.
  - `record` p50 295 ms (max 364 ms), create p50 459 ms (max 491 ms).
  - In this run, 37 of 107 GETs were 404 instance misses and were retried.
- **`/api/evidence/run`:**
  - The psilocybin query returned 200 in 6.1 s (11 KB). `NCT03775200` returned 200 in 14.9 s.
  - Garbage and empty inputs returned 200 in under 0.7 s with `in_domain:false`.
  - A missing `input` gave 422.
- **Bundle and function:**
  - JS `index-CdtYRAEv.js` is 660,896 bytes, or 193,280 bytes with brotli. CSS is 58,300 bytes, or 11,985 with brotli.
  - The function bundle is 30.63 MB.
  - Env var names: `GEMINI_API_KEY` (Production, Preview) only.
- **Runtime logs:** `vercel logs` returned 0 runtime records in the 30-minute hobby retention window. The request logs had 0 responses with status 5xx.

## Passed checks
- **Protocols:** 404 for every traversal variant on `protocols/{name}`, locally and on prod: `..%2F..%2Fbackend%2Fmain.py`, `%2Fetc%2Fpasswd`, encoded `..`, backslashes, `%2E`, `..%2Fbottlenecks.json`, and `..%2F..%2Fapi%2Findex.py`. An unknown example in `POST /api/trials` gives 404.
- **Error codes:** an unknown trial gives 404 on all 11 trial routes. A bad or wrong-case decision gives 400. An empty or whitespace-only reviewer gives 400. A missing or null `reviewer` field gives 422, which is FastAPI body validation; the UI always sends the field. An unknown approval id gives 404, and so does an already-decided one.
- **Bad bodies get 422:** bad JSON, `n_applicants` 5 or 5000, `seed` set to "abc", `days` set to "abc", a missing step body, a non-dict `payload`, `on=abc`, and `limit=abc`.
- **Privacy:** a recursive walk of every response, including the full record, events, approvals, kpis, messages and the three views at day 90, found no `_` key at any depth and no participant-level arm. No arm-like key appears in any response. A client-supplied `id` and `_hidden_exclusion` on portal `apply` are ignored.
- **Trial lifecycle:** step clamps days to 1..30. A step while blocked returns `advanced:false` with a reason. The trial closes at exactly day 90. A step after close is a no-op. Creating a trial with no protocol and with the garbage protocol `!!! ???` both return 200.
- **Concurrency:** 60 parallel decides, steps, record reads and list calls on one trial gave no 5xx. Each approval was decided exactly once, and duplicates got 404.
- **Prod routing:** deep links (`/predose`, `/dosing`, `/postdose`, `/portal`, `/some/deep/link`) serve the SPA. `/assets/nope.js` gives a real 404, not the SPA. `/api/nope` gives a JSON 404. `/api/health/` gives a 307 to the https URL without the trailing slash.
- **Prod CORS:** only `http://localhost:5173` and `http://127.0.0.1:5173` are allowed. `https://evil.example` preflight gets 400. Same-origin calls need no CORS.

## Not run
- Cold start on the live alias after a true idle period: another tester kept it warm. Older idle production deployments were used instead.
- Per-request function duration from `vercel logs`: the hobby plan keeps no runtime records here, and request records carry no duration. Durations above are client-side.
