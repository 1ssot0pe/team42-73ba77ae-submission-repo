# Parallax end-to-end test report

## Environment
- **Branch:** `danny-frontend`. Worked locally as `danny-frontend-e2e`, branched from `origin/main` at `5df9b59`. Fixers worked on `fix/state`, `fix/frontend` and `fix/vercel` in separate worktrees (see `OWNERSHIP.md`).
- **Production:** https://parallax-two-tau.vercel.app. Danny merged PR #8 (`danny-frontend` → `main`) at 13:10 on 2026-11-08, so production now runs the state and frontend fixes, but without `DATABASE_URL` (see below).
- **Local:** two uvicorn instances behind `tests/e2e/rr_proxy.py`, a round-robin proxy that imitates Vercel's many function instances, plus vite.
- **Database:** Neon Postgres in `us-east-2`, pooled URL, present in Danny's local `.env.local`. It is **not yet set in Vercel's environment variables**.

## Test counts

| | Before | After |
|---|---|---|
| `pytest -q` | 141 passed | 163 passed, 1 skipped (opt-in browser test) |
| Store tests against real Neon (`TEST_DATABASE_URL`) | n/a | 15 of 15 passed |
| Frontend resilience (Playwright, `PARALLAX_E2E_FRONTEND=1`) | 1 of 4 passed on the old code | 5 of 5 passed |
| `npm run build --prefix frontend` | OK | OK |
| eslint | 0 errors | 0 errors |

## Bugs

The full ledger is in `BUGS.md`. Summary:

| Severity | Found | Fixed in this pass | Open (reason in the ledger) |
|---|---|---|---|
| Blocker | 1 (API-1: trials lost across instances) | 1 | 0 |
| Major | 7 (BP-2, BL-11, BL-2, BL-3, BL-4, BL-5, BL-6) | 1 (BP-2) | 6: three are teammates' code (TEAMMATE_PATCHES TP-1 to TP-3), BL-11 belongs to the redesign, BL-5 is too risky for this time box, BL-6 needs a product decision |
| Minor | 18, including 6 found in verification | 7 (API-2, API-3, API-4, API-5, API-7, API-8, NEW-1) | 11 |

Fixed bugs, with their regression tests and where each was verified:

| ID | Fix | Regression test | Local, two instances | Preview / prod |
|---|---|---|---|---|
| API-1 | Durable trial store: Postgres (row lock, version, zlib pickle, per-instance cache), with a file store when there is no database | `tests/platform/test_store.py`, `tests/platform/test_statelessness.py` | verified: 0 of about 3,400 trial calls failed; survives killing an instance | pending `DATABASE_URL` in Vercel |
| BP-2 | Request helper with timeouts, bounded backoff, a concurrency limit, a re-check before declaring a trial lost, and a TrialLost screen | `tests/e2e/frontend/test_resilience.py` | verified | pending |
| NEW-1 | Mutations retry up to 5 times on 502/503 (never on 504) | `test_four_502s_on_step_still_advance` | verified | pending |
| API-7 | `vercel.json` headers: immutable `/assets/*`, `no-store` on `/api/*` | `tests/platform/test_vercel_config.py` | n/a | pending a deploy |
| API-2, API-3, API-4, API-5, API-8 | Unknown module or action gives 404; events `limit` clamped; age overflow message; no stack traces in event data; trial ids no longer listed | `tests/platform/test_statelessness.py` (API edge cases) | verified (API-4 in J6) | pending |

## State option chosen: Postgres (Neon via Vercel), as Danny directed
Danny's next phase adds Postgres (projects, analyses, jobs), so trial state uses the same database. This replaces the options in the original brief: a Redis/KV snapshot store, deterministic replay, or a single always-on API host.

- **How it works:** each request loads the trial. Each change runs in one transaction: `SELECT ... FOR UPDATE`, unpickle, change, pickle and compress, `version + 1`, commit. The row lock serialises concurrent writers across instances, so updates are never lost. A per-instance cache skips the blob download when the version hasn't changed.
- **Snapshot size:** compressed, 47 KB at day 0, 68 KB at day 45 and 85 KB at day 90 (266, 407 and 512 KB raw).
- **Step latency, in process:** 1 day 21.7 → 8.1 ms; 7 days 87.5 → 12.0 ms; 30 days 303 → 22.9 ms; a full trial 1,938 → 57 ms. This is against local Postgres. The old code rewrote the whole record to disk once per simulated day, which was 97% of step time; that write is now opt-in.
- **Against the real Neon database, from a laptop in London:** about 1.3 s per change and 0.9 s per read, almost all of it a new TLS connection over a transatlantic round trip. Vercel's function runs in `iad1` (US East), close to Neon's `us-east-2`, so expect tens of milliseconds there. This still needs measuring on the preview.
- **Cold start on prod (before the fix):** 1.5 to 1.85 s for the first `/api/health`, and 3.27 s for the first trial creation.
- **Trade-offs:**
  - Pickles are tied to the class layout. A deploy that changes classes makes older trials read as "trial not found" (handled cleanly as a 404, with a test), not as a 500.
  - The server opens one connection per request; the Neon pooled URL absorbs this.
  - The allocation is inside the blob, so the table must stay server-side only.
- **Recommendation:** pin the function to `cle1` (Cleveland, the same region as Neon's `us-east-2`) once a preview confirms latency, or move Neon to London and pin `lhr1` so it sits near the users.

## Known open issues
- **Preview and prod verification of the state fix** is blocked until `DATABASE_URL` is set in Vercel (Preview and Production). This session's permission rules didn't allow adding it from here. Without it, production falls back to a per-instance `/tmp` file store, which still loses trials across instances. The UI now shows the TrialLost screen instead of silently resetting.
- **Browser runs on the preview** also need the protection-bypass token, which hasn't been saved yet.
- **Majors left open:**
  - BL-2, BL-3 and BL-4 are teammates' code (`TEAMMATE_PATCHES.md`).
  - BL-11 (the Evidence engine link points at localhost) is in a file the redesign owns. Suggested fix: hide the link unless `VITE_EVIDENCE_URL` is set.
  - BL-5 (site names in pasted protocols are ignored) is too risky for this pass.
  - BL-6 (garbage protocols are accepted) needs a decision: reject, or warn and continue.
- **Minor issues for the redesign:** contrast on glass (F-1), focus rings (G-1), lost-trial copy and navigation (NEW-3), the stale 502 toast (NEW-4), and "1 changed lines" (BL-9).

## Teammate patches pending
TP-1 to TP-5 in `TEAMMATE_PATCHES.md`, awaiting Danny's decision.

## Evidence
- **Ledgers:** `bugs/api.md`, `bugs/browser-local.md`, `bugs/browser-prod.md`.
- **Verification:** `verify/j1-5-local.md`, `verify/j6-10-local.md`, `verify/j11-15-local.md`.
- **Screenshots:** `docs/testing/screenshots/`. The repo holds one downscaled screenshot per journey; the full set stays local.
- **Scripts:** `tests/e2e/api/`, `tests/e2e/browser/`, `tests/e2e/prod/`, `tests/e2e/verify/` and `tests/e2e/frontend/`.
