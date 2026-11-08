# Parallax design v2

This overrides `plans/design.md` wherever the two differ. Anything not mentioned here keeps the v1 rule.

## The idea

Parallax is a calm workspace for running and checking psychedelic trials. It should read like a well set document, not an instrument panel. Hierarchy comes from type and whitespace, not from boxes, pills and colour.

## Type

- Open Sans everywhere, loaded from Google Fonts: 300 for display and headings, 400 for body, 600 for emphasis.
- Geist Mono only for trial IDs and applicant IDs (`.t-id`). Nothing else is mono.
- Every number uses `font-variant-numeric: tabular-nums`.
- Display 44px/1.1 weight 300; heading 32px/1.2 weight 300; title 18px/1.4 weight 600; body 16px/1.6; small 13px/1.5.
- Labels are sentence case, 13px, smoke colour. No uppercase letter-spaced eyebrows anywhere.

## Colour

| Token | Light | Dark |
|---|---|---|
| Canvas `--color-eggshell` | `#fdfcfc` | `#0e0d0c` |
| Ink | `#000000` | `#f5f3f1` |
| Graphite | `#44403b` | `#d6d1cb` |
| Smoke | `#777169` | `#a59f97` |
| Hairline `--color-stone` | `#ebe8e4` | `#2a2724` |

- The background is plain canvas. No graph-paper grid, no specimen field colour blobs.
- Violet `#0447ff` and orange `#ff4704` appear only inside charts.
- Status tints (good, watch, alert, neutral) stay from v1 but are used as a small coloured dot plus a word, not as filled pills.

## Surfaces

- Glass is used only for the top nav. Everything else is flat.
- Fewer cards. Prefer a hairline rule or whitespace between sections over a box.
- Details open in a right-hand drawer, not in stacked cards.
- At most one readout row per page.

## Controls

- Pills only for the one primary action on a page, and for a status that needs attention (for example "Needs sign-off").
- Secondary actions are quiet text buttons.

## Synthetic labelling

- One quiet line in the footer: "All trial data in Parallax is synthetic. No real patients."
- Charts carry a small "Synthetic" note. No hatched bands.

## Developer details

Trial ID, Gemini on or off, and real or stub module status live behind a "Developer" toggle in the nav overflow menu. They are hidden by default.

## Structure

- `/` Home: headline, one sentence, two doors (Evidence studio, Trials), recent work.
- `/studio` Evidence studio: check a published trial.
- `/trials` Trials: list of projects, empty state when there are none.
- `/trials/:projectId/:stage?` Project workspace. Stages: Draft, Design review, Recruitment, Screening, Dosing, Follow-up, Report.
- A vertical stepper sits on the right of the workspace (sticky): one 1px line, a dot per stage. Filled is done, ring is current, hollow is upcoming. Hover or focus shows the stage name, status and trial day. Below 900px it becomes a horizontal dot row under the nav. The old horizontal phase bar and day ruler are gone.

## Writing

- UK English. Sentence case. No em dashes.
- Plain words: "Launch trial", "Saved", "Rule-based mode".

## Build ownership map (redesign/platform-ui)

No two agents edit the same file. Off limits to all: `backend/`, `api/`, `unblind/`, `vercel.json`, `requirements*.txt`, `tests/`, `frontend/src/api.ts`, `frontend/src/trial.tsx`.

| Owner | Files |
|---|---|
| Orchestrator | `docs/design-v2.md`, `frontend/src/store/projects.ts`, `frontend/src/components/stepper/stages.ts` |
| Builder 1: shell and stepper | `frontend/index.html`, `src/main.tsx`, `src/App.tsx` (the only owner of routes), `src/dev.ts`, `src/styles/{tokens,base,glass,components,stepper,shell}.css`, `src/components/SpecimenField.tsx`, `src/components/shared/*`, `src/components/stepper/VerticalStepper.tsx`, `src/components/mission/PhaseTrack.tsx` |
| Builder 2: home, trials, editor | `src/pages/{Home,Trials,Workspace}.tsx`, `src/components/projects/*`, `src/styles/{home,workspace}.css` |
| Builder 3: evidence studio | `src/pages/Studio.tsx`, `src/store/analyses.ts`, `src/api-extra.ts`, `src/components/studio/*`, `src/styles/studio.css` |
| Builder 4: stage page restyle | `src/pages/{Predose,Portal,ModulePage,MissionControl}.tsx`, `src/components/{predose,module}/*`, `src/components/mission/*` except `PhaseTrack.tsx`, `src/styles/{predose,mission,module}.css` (presentation only, no data logic changes) |

## Storage

Projects and analyses live in localStorage for now (`src/store/`). The interfaces are kept small so they can be swapped for a Postgres API later.
