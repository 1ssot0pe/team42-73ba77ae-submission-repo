# File ownership for the end-to-end fix pass

No two agents edit the same file. The integration branch is `danny-frontend-e2e` (pushed as `danny-frontend`; the brief calls it `fix/vercel-e2e`). Each fixer works in its own worktree and branch, cut from the integration branch.

Merge order: each branch is merged only after its own tests pass. After each merge the full suite runs (`pytest -q` and `npm run build --prefix frontend`). If anything regresses, the merge is reverted with a new revert commit (never a reset or force-push) and the branch goes back to its fixer.

| Agent | Branch / worktree | Files it may edit |
|---|---|---|
| Fixer State | `fix/state`, `.claude/worktrees/fix-state` | `backend/main.py`, `api/index.py`, `unblind/platform/store.py` (new), `unblind/platform/core.py`, `unblind/platform/world.py`, `unblind/platform/master/orchestrator.py`, `unblind/platform/master/stubs.py`, `unblind/platform/predose/*.py`, `requirements.txt`, `requirements-dev.txt`, `tests/platform/test_store.py` (new), `tests/platform/test_statelessness.py` (new) |
| Fixer Frontend | `fix/frontend`, `.claude/worktrees/fix-frontend` | `frontend/src/api.ts`, `frontend/src/trial.tsx`, `frontend/src/components/shared/TrialLost.tsx` (new, minimal error-state UI only), `tests/e2e/frontend/` (new) |
| Fixer Vercel (launched after triage) | `fix/vercel`, `.claude/worktrees/fix-vercel` | `vercel.json`, `.vercelignore` |
| Tester API | integration worktree | `tests/e2e/api/`, `docs/testing/bugs/api.md` |
| Tester Browser-Local | integration worktree | `tests/e2e/browser/`, `docs/testing/bugs/browser-local.md`, `docs/testing/screenshots/local-*` |
| Tester Browser-Prod | integration worktree | `tests/e2e/prod/`, `docs/testing/bugs/browser-prod.md`, `docs/testing/screenshots/prod-*` |
| Verifiers (one per journey group J1-J5, J6-J10, J11-J15 per environment) | integration worktree, read-only on product code | `docs/testing/verify/<group>-<env>.md` |
| Orchestrator | integration worktree | `docs/testing/BUGS.md`, `OWNERSHIP.md`, `TEST_REPORT.md`, `TEAMMATE_PATCHES.md`, `TEST_PLAN.md`, `tests/e2e/rr_proxy.py`, merges |

## Off limits for every agent
- `unblind/platform/dosing/` (Izzy) and `unblind/platform/postdose/` (Callum). Write patches for their bugs in `TEAMMATE_PATCHES.md` only.
- Frontend layout and styles: everything in `frontend/src/` apart from the files listed above. Another agent is redesigning the UI on `redesign/platform-ui`. UI bugs outside these files go into `BUGS.md` for that work.
- Production deploys, force-pushes, and rewriting history.

## Testing split
The first round of testers was split by environment, because it had started before this map existed: API/state, browser-local and browser-prod. Verification is split by journey group and environment: J1-J5, J6-J10 and J11-J15, each run on local two-instance and on the Vercel preview.
