# Post-dosing module (owner: Izzy)

Turns everything the trial collected into evidence a regulator and a scientist can trust,
and makes that evidence comparable across trials. Follows `unblind/platform/MODULE_CONTRACT.md`.

| File | What it is |
|---|---|
| `module.py` | `class Module(BaseModule)`: `setup`, `on_day`, `on_message`, `kpis`, `view`, `handle` |
| `agents.py` | follow-up agent, bias gate, participant interview agent, harmoniser, close-out report agent |
| `effects.py` | reported, within-trial (guess-stratified) and cross-trial adjusted effects, from vault aggregates only |
| `question_set.py` | 15 labelled researcher questions (5 approve, 5 rewrite, 5 reject) |
| `eval/platform/` | `run_eval.py` writes `results.md`: 20-seed planted-truth evaluation, bias gate accuracy, end-to-end checks |
| `tests/platform/test_postdose.py` | 12 offline tests |

UI actions handled (`handle`): `ask_question {researcher, question}`, `sign_off {reviewer, decision, comment}`,
`draft_report {}`, `request_export {requested_by}`.

Human gates (ApprovalQueue): releasing each researcher question (ethics), releasing the UNBLIND-BLIND-1 export,
signing off the FDA report. The report cannot become `final` without a named reviewer.

## Step-by-step: put this on the `Cal_Work` branch so the team can see it

Run these from the repo root (`team42-73ba77ae-submission-repo`), in PowerShell or Git Bash.

**1. Check you are on the right branch.**
```
git status
git branch --show-current        # must print Cal_Work
```

**2. Do NOT run `git add .` or `git add -A`.** The repo contains a nested folder
`team42-73ba77ae-submission-repo/` that is a separate git clone (reference copy). Adding it would commit an
embedded repository. To hide it from `git status` on your machine only (this changes no tracked file):
```
echo team42-73ba77ae-submission-repo/ >> .git/info/exclude
```

**3. Install requirements and run the tests (no API key needed).**
```
pip install -r requirements.txt
$env:UNBLIND_OFFLINE = "1"          # PowerShell;  Git Bash: export UNBLIND_OFFLINE=1
python -m pytest tests -q            # expect all tests to pass
python eval/platform/run_eval.py     # rewrites eval/platform/results.md and effect_recovery.json
```

**4. Check no secret is about to be committed.** The code never contains a key: Gemini is read only from the
`GEMINI_API_KEY` environment variable by `unblind/llm.py`, and the export salt from `UNBLIND_EXPORT_SALT` or a
random file in the git-ignored `data/trials/`. If you want Gemini locally, set it for your terminal session only:
```
$env:GEMINI_API_KEY = "paste-your-key-here"     # PowerShell, this session only. Never put it in a file in the repo.
```
`.env` is already in `.gitignore`. Before every commit:
```
git diff --cached | Select-String "AIza"        # PowerShell; Git Bash: git diff --cached | grep AIza
```
This must print nothing.

**5. Stage only the post-dosing files, then commit and push.**
```
git add unblind/platform/postdose eval/platform tests/platform/test_postdose.py
git status                           # only those paths should be listed under "Changes to be committed"
git commit -m "Post-dosing module: follow-up, bias gate, harmonised export, FDA blinding report, evaluation"
git push origin Cal_Work
```

**6. Tell the team / open a pull request into `main`.** Nothing else needs changing: the master imports
`unblind.platform.postdose.module` automatically, and the labelled STUB disappears as soon as this file imports.
```
gh pr create --base main --head Cal_Work --title "Post-dosing module" --body "See unblind/platform/postdose/README.md and eval/platform/results.md"
```

**7. After Callum's dosing module is merged**, rerun `python -m pytest tests -q`. This module was also tested
against the dosing module on `origin/Issy-argon-4`: all tests pass and the report then shows real estimates.

## Draft for the write-up: what is new compared with Szigeti et al. 2026

Szigeti and colleagues' 2026 meta-analysis corrects psychedelic trial results for unequal unblinding after the
trials have ended, using whatever blinding data each trial happened to report. Parallax does not claim the idea
that blinding matters. What is new is running the measurement as a living, standard, agent-operated process inside
each trial, so that every trial collects the same guesses at the same timepoints and can report an
expectancy-adjusted effect with its limits at close-out.
(Check this against the paper itself before using it.)

## Known limits

* With fewer than about 120 participants the within-trial estimate is usually suppressed by the vault (cells under 5).
  The report says so and falls back to the cross-trial value, which over-corrects in our simulations.
* Week-12 follow-ups for participants dosed after day 6 fall after close-out on day 90; they are marked `after_close`.
* No baseline MADRS is recorded by the platform yet, so the effect uses the week-6 score (valid under randomisation).
  If pre-dosing adds a `baseline_madrs` to enrolled rows, or dosing records a week-0 outcome, the change score is used automatically.
* The FDA item "expectancy before randomisation" can only be met if pre-dosing's measurement plan includes it.
