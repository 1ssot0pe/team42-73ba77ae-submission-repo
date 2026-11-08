# UNBLIND platform: module contract

Three modules, one owner each, never import each other. They share only:

* `TrialRecord` (a JSON dict, `unblind/platform/core.py`)
* `MessageBus` (agent-to-agent messages, routed by the master)
* `ApprovalQueue` (anything that changes the trial needs a named human)
* `Vault` (the only holder of allocation; agents get aggregates only)
* `World` (SYNTHETIC people, sites and raters; modules may call only its public methods,
  and must never read keys that start with `_`)

## Files each module owns

```
unblind/platform/<module>/agents.py   # the agents (classes or functions)
unblind/platform/<module>/module.py   # class Module(BaseModule): setup / on_day / on_message / kpis
(no UI code)                          # the React app renders your module from view(rec); see VIEW MODEL below
tests/platform/test_<module>.py       # offline tests
```

## Timeline (simulated days)

| Day | Who | What |
|---|---|---|
| setup (day -1) | predose | design review, recruitment ads, pre-screening, enrolment, stratified randomisation via `ctx.vault.randomise`, measurement plan, schedule |
| 1 to 20 | dosing | staggered dosing sessions (each participant has a `dosing_day`) |
| dosing_day to dosing_day + 42 | dosing | post-session check-ins, monitor debriefs, rater assessments at weeks 1, 3, 6 (MADRS + rater guess), daily blinding metrics, drift alerts, missing-data chasing, weekly literature scan |
| primary endpoint lock = last participant's week 6 + 1 | dosing -> master | dosing posts `{"kind": "primary_locked"}` to `master` |
| after lock to day 90 | postdose | follow-ups at weeks 8 and 12, researcher question portal (bias gate), harmonised export |
| 90 | postdose | FDA blinding report, close-out |

The master sets `rec["day"]` and `rec["phase"]`, delivers messages, then calls `on_day` on every module.

## Shared record sections (write only your own)

| Section | Owner | Shape |
|---|---|---|
| `protocol` | predose | `{title, drug, indication, comparator, rater_model, sites[], n_target, primary_endpoint{scale, week}, eligibility{inclusion[], exclusion[]}, text}` |
| `protocol_versions` | predose | list of `{version, day, digest, changes[], risk}` |
| `design_review` | predose | `{risk{u, u_sd, expected_bias_g, band}, fixes[], blinding_section_md, checklist[]}` |
| `recruitment` | predose | `{ads[], funnel{applied, auto_eligible, auto_excluded, needs_clinician, enrolled}}` |
| `applicants` | predose | applicant dicts + `screening{decision: eligible / excluded / needs_clinician, reasons[], evidence[]}` |
| `enrolled` | predose | `{id, name, site, stratum, prior_psychedelic_use, dosing_day, consents{...}}` |
| `measurement_plan` | predose | `{standard: "UNBLIND-BLIND-1", primary_week, instruments[{id, who, questions[], timepoints[], timepoints_days[], purpose}]}` (see the note below) |
| `schedule` | predose creates; dosing and postdose update `status` | `{id, participant, site, day, kind, owner, instrument, status}` where kind is one of `dosing_session, monitor_debrief, participant_checkin, rater_assessment, followup, research_question` |
| `sessions`, `checkins`, `debriefs`, `outcomes`, `blinding_metrics`, `alerts`, `actions`, `missing_data`, `literature` | dosing | see dosing/module.py docstring |
| `followups`, `research_questions`, `exports`, `report` | postdose | see postdose/module.py docstring |

**Measurement plan timepoints.** `timepoints_days` is a list of **integers**: days relative to each participant's
`dosing_day` (`-1` = before randomisation or baseline, `0` = dosing day, `1` = the day after, `7` = week 1,
`21` = week 3, `7 * primary_week` = the primary endpoint visit, `56` = week 8, `84` = week 12). `timepoints` is
the parallel list of human labels ("before randomisation", "baseline", "dosing day", "dosing +1", "week 1", ...),
one label per day, in the same order. The primary week comes from `protocol.primary_endpoint.week`, not a fixed 6.
So a participant's absolute day for a timepoint is `dosing_day + timepoints_days[k]`.

`outcomes` rows: `{participant, site, day, visit_week, madrs, rater_id, rater_guess, patient_guess}`.
`checkins` rows: `{participant, site, day, who: participant|rater|monitor, rater_id, guess: drug|control|dont_know, confidence, expectancy, channel: text|voice}`.
`blinding_metrics` rows: `{day, who, by: overall|site|rater, group, n, accuracy, accuracy_lo, accuracy_hi, u, bang_drug, suppressed}`.
`alerts` rows: `{id, day, module, severity: info|warn|critical, title, explanation, evidence, approval_id}`.

## Rules every agent follows

1. **Vault only.** Never compute anything from allocation. Use `ctx.vault.blinding_stats(...)` (aggregates, min cell 5).
2. **Human gate.** Any action that changes the trial goes through `ctx.approvals.request(...)`. Check the decision on later days with `ctx.approvals.get(id)`.
3. **Explain yourself.** Every decision writes `rec.event(agent, text, level, module)`, where `level` is `info | decision | warn | human`.
4. **Gemini optional.** Use `ctx.llm.available()` and `ctx.llm.ask_json(...)`. Always have a deterministic fallback, so the demo runs with no key.
5. **Bottleneck first.** Your module page opens with its bottleneck(s) from `data/bottlenecks.json`, and `kpis()` returns quantified impact as `[{label, value, baseline, unit, note, bottleneck_id}]`.
6. **Synthetic is labelled.** Anything from `World` is SYNTHETIC and must say so in the UI.
7. UK English, no em dashes in UI copy, plain language.

## Approvals come back as messages

When a human decides, the module that asked receives
`{"kind": "approval_decided", "from": "approvals", "payload": <the approval dict>}` in `on_message`.
Check `payload["status"]` (`approved` / `rejected`), `payload["action"]` (what you asked for) and `payload["reviewer"]`.

## VIEW MODEL (how your module appears in the React app)

Implement `view(self, rec) -> dict` returning only these keys (all optional except module/title):

```python
{
  "module": "dosing", "title": "Dosing: live blinding monitor",
  "kpis":   [{"label": "...", "value": 12, "unit": "days", "baseline": 62, "note": "...", "bottleneck_id": "blinding_failure"}],
  "cards":  [{"title": "Drift at Site B", "body": "Raters guessed right 88% ...", "tone": "warn"}],   # tone: info|warn|good|bad
  "charts": [{"title": "Rater guess accuracy by site", "x": "day",
              "series": [{"key": "Site A", "label": "Site A"}, {"key": "Site B", "label": "Site B"}],
              "data": [{"day": 10, "Site A": 0.52, "Site B": 0.55}, {"day": 11, "Site A": 0.5, "Site B": 0.61}]}],
  "tables": [{"title": "Alerts", "columns": ["Day", "Site", "What"], "rows": [[29, "Site B", "..."]]}],
  "forms":  [{"id": "play_patient", "title": "Play a patient", "action": "checkin",
              "fields": [{"name": "participant", "label": "Participant ID", "type": "text"},
                         {"name": "guess", "label": "Which group?", "type": "select", "options": ["drug", "control", "dont_know"]}]}]
}
```

A form submit calls `handle(self, rec, action, payload, ctx)` with the form values as `payload`.
Return a JSON-able dict, e.g. `{"ok": True, "message": "..."}`.

## Stubs

If your `module.py` cannot be imported, the master uses a labelled STUB (`master/stubs.py`) so the platform still
runs. As soon as your module imports cleanly it replaces the stub automatically.
