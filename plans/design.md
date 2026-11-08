# UNBLIND Lab Glass: Style Reference
> A clinical research bench under liquid glass. Eggshell lab-notebook paper, black ink, instrument-grade mono readouts, and two sparks of colour reserved for the data itself.

**Theme:** light first ("Bench"), with a dark variant ("Darkroom").
**Built from:** the ElevenLabs style reference (warm editorial minimalism, whisper-weight headlines, pill buttons, hairlines), adapted for a laboratory instrument and given a liquid glass layer.
**Product:** UNBLIND, an agentic platform that runs a psychedelic clinical trial from protocol design to the FDA report. Users are clinical development leads, clinicians and research staff. Judges see it live.
**Stack this applies to:** React + Vite + TypeScript, plain CSS custom properties, recharts. No UI kit.

---

## 1. The idea in one paragraph

UNBLIND should feel like a precise instrument sitting on a calm bench. The canvas is warm eggshell paper with a faint graph-paper grid. Content lives on flat taupe sheets, like pages in a lab notebook. The controls that operate the trial (the navigation, the play dock, the approval slips, the phase track) are liquid glass panels floating above a soft, blurred "specimen field" of colour, like instrument covers over a culture. Headlines whisper at weight 300. Numbers speak loudly in a mono face, always with a unit, a source and a status. Violet and orange never decorate the interface: they belong to measurements, charts and the unblinding sphere. Every decision a human signs looks like a signed lab slip. Everything simulated carries a hatched SYNTHETIC SPECIMEN label.

## 2. Principles

1. **Paper bench, glass instruments.** Flat taupe for content you read. Liquid glass only for controls you operate and things that float. Never make every card glass.
2. **Whisper headlines, loud numbers.** Display type is light (300). Readouts are Geist Mono with tabular numerals, larger than their labels.
3. **Sparks belong to the data.** Violet `#0447ff` and Ember `#ff4704` appear only in charts, gauges, the unblinding sphere and the specimen field. Never on buttons, links, borders or text.
4. **Every number has a unit, a source and a status.** A readout without "before", "assumption" or "synthetic" context is unfinished.
5. **Humans sign.** Approvals are slips with a signature line. Signed slips get a stamp with the reviewer and the trial day.
6. **Synthetic is always labelled.** Hatched specimen band on every page, a SYNTHETIC tag on every chart.
7. **Calm under pressure.** Alerts use muted lab tints (amber, brick), never flashing red. The interface stays quiet so the one thing that needs attention is obvious.

---

## 3. Tokens: colour

### Bench (light)

| Name | Value | Token | Role |
|---|---|---|---|
| Eggshell | `#fdfcfc` | `--color-eggshell` | Page canvas, inputs, paper document surfaces |
| Warm Taupe | `#f5f3f1` | `--color-taupe` | Flat content sheets (readouts, tables, checklists), section bands |
| Stone | `#ebe8e4` | `--color-stone` | Hairlines, dividers, table header fill, icon plates |
| Ink | `#000000` | `--color-ink` | Primary text, filled pill buttons, active states |
| Graphite | `#44403b` | `--color-graphite` | Strong secondary text, labels, agent names |
| Smoke | `#777169` | `--color-smoke` | Body copy, descriptions, quotes |
| Ash | `#a59f97` | `--color-ash` | Footnotes, axis labels, tertiary text |
| Violet Spark | `#0447ff` | `--color-spark-violet` | DATA ONLY: primary measurement series, sphere core, specimen field |
| Ember Spark | `#ff4704` | `--color-spark-ember` | DATA ONLY: thresholds, drift onset markers, rater series, sphere rim |
| Grid | `rgba(0,0,0,0.035)` | `--color-grid` | Graph-paper grid on the canvas and chart gridlines |

### Lab status tints (state, not accent)
Status uses muted, ink-heavy tints so they read as instrument states, not marketing colour. Always pair the colour with a word (Present, Missing, Eligible) so colour is never the only signal.

| State | Text | Fill | Token pair | Used for |
|---|---|---|---|---|
| Assay (good) | `#25654a` | `#e6f1ea` | `--status-good-fg/bg` | Present, Eligible, Approved, Signed |
| Amber (watch) | `#8a5a00` | `#faf0da` | `--status-watch-fg/bg` | Needs clinician, Pending, Medium risk, Auto-approve on |
| Brick (alert) | `#a3352a` | `#fae8e4` | `--status-alert-fg/bg` | Missing, Excluded, High risk, Drift alert, Rejected |
| Neutral | `#44403b` | `#ebe8e4` | `--status-neutral-fg/bg` | Stub, Info, Not started |

### Darkroom (dark)

| Name | Value | Token |
|---|---|---|
| Canvas | `#0e0d0c` | `--color-eggshell` |
| Sheet | `#171614` | `--color-taupe` |
| Hairline | `#2a2724` | `--color-stone` |
| Ink | `#f5f3f1` | `--color-ink` |
| Graphite | `#d6d1cb` | `--color-graphite` |
| Smoke | `#a59f97` | `--color-smoke` |
| Ash | `#7a746c` | `--color-ash` |
| Violet Spark | `#4d7bff` | `--color-spark-violet` |
| Ember Spark | `#ff6a33` | `--color-spark-ember` |
| Grid | `rgba(255,255,255,0.04)` | `--color-grid` |
| Status good/watch/alert fg | `#7cc9a2` / `#e8b65a` / `#f08a7d` | |
| Status good/watch/alert bg | `#16261e` / `#2a2112` / `#2c1714` | |

In Darkroom, filled pill buttons invert: `--color-ink` fill (warm white) with `--color-eggshell` text (near black).

---

## 4. Tokens: liquid glass

Liquid glass is a translucent panel that blurs and slightly saturates what is behind it, with a bright inner rim, a hairline outer edge and a soft specular highlight across the top third. It only looks right when there is something soft and colourful behind it, so the page always has a **specimen field** (Section 6.1) under the content.

| Token | Bench | Darkroom | Notes |
|---|---|---|---|
| `--glass-fill` | `rgba(253,252,252,0.58)` | `rgba(23,22,20,0.55)` | Default panel tint |
| `--glass-fill-strong` | `rgba(253,252,252,0.82)` | `rgba(23,22,20,0.82)` | Panels holding body text or forms; also the fallback |
| `--glass-blur` | `22px` | `22px` | `backdrop-filter: blur()` |
| `--glass-saturate` | `165%` | `140%` | `backdrop-filter: saturate()` |
| `--glass-rim` | `inset 0 0 0 1px rgba(255,255,255,0.65)` | `inset 0 0 0 1px rgba(255,255,255,0.10)` | Bright inner edge |
| `--glass-edge` | `0 0 0 0.5px rgba(0,0,0,0.08)` | `0 0 0 0.5px rgba(0,0,0,0.6)` | Hairline outer edge |
| `--glass-depth` | `0 1px 1px rgba(0,0,0,0.04), 0 10px 30px rgba(68,64,59,0.10)` | `0 1px 1px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.45)` | Lift for floating glass only |
| `--glass-specular` | `linear-gradient(180deg, rgba(255,255,255,0.70) 0%, rgba(255,255,255,0.08) 38%, rgba(255,255,255,0) 60%)` | `linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 45%)` | Top highlight, drawn with `::before` |

**Glass recipe (copy exactly):**
```css
.glass {
  position: relative;
  background: var(--glass-fill);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  box-shadow: var(--glass-rim), var(--glass-edge);
  border-radius: var(--radius-glass);
  isolation: isolate;
}
.glass::before {               /* specular highlight */
  content: ""; position: absolute; inset: 0; border-radius: inherit;
  background: var(--glass-specular); pointer-events: none; z-index: -1;
}
.glass--float { box-shadow: var(--glass-rim), var(--glass-edge), var(--glass-depth); }
.glass--strong { background: var(--glass-fill-strong); }
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass { background: var(--glass-fill-strong); }
}
@media (prefers-reduced-transparency: reduce) {
  .glass { background: var(--color-eggshell); backdrop-filter: none; -webkit-backdrop-filter: none; }
}
```

**Glass rules**
- Glass levels: **L2** in-page glass (phase track, approval slips, portal result), **L3** floating glass (nav bar, control dock, toasts, dialogs) which adds `--glass-depth`.
- Body text and form fields on glass use `.glass--strong`. Text contrast must stay at or above 4.5:1 against the worst point of the specimen field behind it.
- Never stack glass on glass more than once.
- Glass radius: 24px for panels, 9999px for the nav bar, dock and pills.

---

## 5. Tokens: typography

Waldenburg is not available, so the display role uses **Inter 300** (the reference's own substitute). A lab instrument needs a stronger mono voice than ElevenLabs, so **Geist Mono** is promoted to the readout and label role.

Load from Google Fonts: `Inter:wght@300;400;500` and `Geist+Mono:wght@400;500`.

| Role | Family | Weight | Size / line height | Tracking | Token |
|---|---|---|---|---|---|
| display | Inter | 300 | 48px / 1.08 | -0.96px | `--text-display` |
| heading | Inter | 300 | 36px / 1.17 | -0.72px | `--text-heading` |
| heading-sm | Inter | 300 | 28px / 1.15 | -0.56px | `--text-heading-sm` |
| title | Inter | 500 | 18px / 1.4 | -0.1px | `--text-title` |
| body-lg | Inter | 400 | 18px / 1.6 | 0 | `--text-body-lg` |
| body | Inter | 400 | 15px / 1.6 | 0.15px | `--text-body` |
| body-sm | Inter | 400 | 13px / 1.5 | 0.13px | `--text-body-sm` |
| button | Inter | 500 | 14px / 1 | 0.14px | `--text-button` |
| readout-xl | Geist Mono | 400 | 40px / 1.05 | -0.8px, tabular-nums | `--text-readout-xl` |
| readout | Geist Mono | 400 | 24px / 1.1 | -0.3px, tabular-nums | `--text-readout` |
| mono-body | Geist Mono | 400 | 13px / 1.69 | 0 | `--text-mono` |
| label | Geist Mono | 500 | 11px / 1.4 | +0.08em, UPPERCASE | `--text-label` |
| caption | Inter | 400 | 11px / 1.5 | 0.1px | `--text-caption` |

**Type rules**
- Display and heading never go above weight 300.
- All numbers (readouts, table figures, day counters, IDs, timestamps) are Geist Mono with `font-variant-numeric: tabular-nums`.
- Eyebrows and specimen tags use the `label` style: mono, uppercase, +0.08em.
- `text-wrap: balance` on headings; running text at most 68 characters wide.

---

## 6. Surfaces, background and elevation

| Level | Name | Treatment | Used for |
|---|---|---|---|
| L0 | Bench canvas | `--color-eggshell` + graph-paper grid (`--color-grid`, 24px squares) | Page background |
| L0.5 | Specimen field | Fixed, blurred colour fields behind everything (6.1) | Gives glass something to refract |
| L1 | Notebook sheet | `--color-taupe`, radius 20px, no border, no shadow | Readouts, tables, checklists, logs |
| L1b | Paper document | `--color-eggshell`, hairline `--color-stone`, radius 20px | Protocol editor, drafted sections, reports |
| L2 | Glass panel | `.glass` | Phase track, approval slips, portal result |
| L3 | Floating glass | `.glass.glass--float` | Nav bar, control dock, toasts, dialogs |

### 6.1 Specimen field (the background that makes the glass work)
A fixed layer behind the app with three very large, heavily blurred radial colour fields at low opacity. Sitting behind the glass it reads as refracted culture colour; behind flat sheets it is barely visible.

```css
.specimen-field { position: fixed; inset: 0; z-index: -1; pointer-events: none; overflow: hidden; }
.specimen-field span { position: absolute; border-radius: 50%; filter: blur(80px); opacity: var(--field-opacity, 0.16); }
.specimen-field .v { width: 46vw; height: 46vw; left: -8vw; top: -10vw; background: radial-gradient(circle, var(--color-spark-violet), transparent 65%); }
.specimen-field .e { width: 40vw; height: 40vw; right: -10vw; top: 18vh; background: radial-gradient(circle, var(--color-spark-ember), transparent 65%); }
.specimen-field .p { width: 36vw; height: 36vw; left: 30vw; bottom: -14vw; background: radial-gradient(circle, #ff8fc7, transparent 65%); opacity: 0.10; }
@media (prefers-reduced-motion: no-preference) {
  .specimen-field span { animation: drift 48s ease-in-out infinite alternate; }
}
@keyframes drift { to { transform: translate3d(3vw, 2vh, 0) scale(1.06); } }
```
Darkroom: `--field-opacity: 0.22`.

### 6.2 Graph-paper canvas
```css
body {
  background-color: var(--color-eggshell);
  background-image:
    linear-gradient(var(--color-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-grid) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

---

## 7. Spacing, radius, layout

- **Base unit:** 4px. Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96.
- **Radius:** pills, tags, buttons, nav, dock `9999px` · notebook sheets `20px` · glass panels `24px` · inputs `10px` · small plates `6px`.
- **Page:** max width 1280px, side gutter 64px desktop, 24px tablet, 16px phone.
- **Section gap:** 64px inside the app (tighter than a marketing site), 96px between major page sections.
- **Card padding:** 24px (sheets), 20px (glass slips), 32px (paper documents).
- **Element gap:** 8 to 16px.
- **Breakpoints:** 1100px (two columns become one where needed), 720px (readout grid goes to 2 columns), 420px (1 column, dock wraps).

---

## 8. Components

### 8.1 Floating glass nav (L3)
Pill-shaped `.glass.glass--float`, 56px tall, sticky at `top: calc(env(safe-area-inset-top,0px) + 12px)`, centred, max-width 1280px.
- Left: wordmark `UNBLIND` in Inter 500, 15px, +0.12em tracking, ink.
- Centre: nav links as ghost pills (Inter 14/500, graphite; active link gets ink text and a 6px ink dot before it). Links: Mission control, Pre-dosing, Volunteer portal, Dosing, Post-dosing, Evidence engine.
- Right: trial chip in mono (`T-0012`), day counter `D+23 / 90` in mono, and a pending-decisions count as an amber pill (`3 to sign`). Hidden until a trial exists.

### 8.2 Synthetic specimen band
Full-width band directly under the nav. Hatched background: `repeating-linear-gradient(135deg, var(--color-taupe) 0 10px, var(--color-stone) 10px 11px)`. Content: label `SYNTHETIC SPECIMEN` (mono label style), then one sentence in body-sm smoke: "People, sites and raters are simulated so the whole trial can run in minutes. No real patient data." Never dismissible.

### 8.3 Phase track (L2 glass)
A segmented glass track showing design, recruitment, dosing, follow-up, close-out, closed.
- Each segment is a specimen tag (pill, label style). Done: graphite text + small check. Current: ink fill, eggshell text. Upcoming: ash text.
- Underneath, a day ruler from D0 to D90 with a hairline tick every day and a taller tick every 7 days, labelled W1 to W12 in mono 10px ash. The current day is a 2px ink needle. If the trial is blocked, the needle turns amber and the reason appears to its right in body-sm.

### 8.4 Control dock (L3 glass)
Floating pill fixed at the bottom centre (`bottom: calc(env(safe-area-inset-bottom,0px) + 20px)`), 64px tall.
Buttons, left to right: `Next day` (outline pill), `+1 week` (outline pill), `Play` / `Pause` (filled ink pill with a small play glyph), a divider hairline, an **Auto-approve** switch whose label reads "Auto-approve (demo)" and whose track turns amber when on. On phones the dock wraps to two rows.

### 8.5 Readout tile (L1 sheet)
The KPI unit. Taupe sheet, 20px radius, 20px padding, min-height 132px.
- Top: label style eyebrow (`APPLICANTS DECIDED AUTOMATICALLY`).
- Middle: readout-xl value with unit in readout size, smoke (`89 %`, `56 of 500`, `0.55 u`).
- Bottom row in mono 12px: `before 0.79 → now 0.55`, and a delta arrow coloured with the status tint (good if it moved the right way).
- Footnote chip when needed: `ASSUMPTION 20 min/screen` (neutral tint) or `EVAL vs SYNTHETIC TRUTH` (watch tint).
Grid: 4 columns desktop, 2 at 720px, 1 at 420px. All tiles same height in a row.

### 8.6 Unblinding sphere (signature visual)
The lab version of the ElevenLabs audio sphere. A 220px circle that visualises predicted or measured unblinding `u` (0 to 1).
- `u = 0`: a calm stone sphere (radial gradient from eggshell to stone), barely tinted.
- As `u` rises, violet blooms from the centre and ember spreads from the lower rim. At `u = 1` the sphere is fully saturated violet to ember.
- Implementation: `background: radial-gradient(circle at 38% 34%, rgba(255,255,255,0.9), transparent 34%), radial-gradient(circle at 50% 55%, color-mix(in oklab, var(--color-spark-violet) calc(var(--u)*100%), var(--color-stone)), transparent 70%), radial-gradient(circle at 60% 85%, color-mix(in oklab, var(--color-spark-ember) calc(var(--u)*90%), var(--color-stone)), transparent 60%), var(--color-stone);` with `--u` set inline.
- Beside it: the value in readout-xl mono (`u = 0.79`), a band pill (Low / Medium / High), and a 0 to 1 scale with labelled ends: `0 coin flip` and `1 everyone knows`.
- Caption in caption style: "Predicted from a SYNTHETIC calibration" when applicable.
- Use the sphere once per page at most: pre-dosing risk, and the dosing page's overall participant blinding.

### 8.7 FDA checklist (L1 sheet, ledger rows)
Rows divided by stone hairlines. Columns: mono item code (`FDA-01`), item text (body), status pill (`Present` good / `Missing` alert), evidence quote. Evidence uses the Evidence quote component. A summary readout sits above the list: `0 / 8 → 4 / 8`.

### 8.8 Approval slip (L2 glass, `.glass--strong`)
The signed-decision component, designed like a lab sign-off slip.
- Eyebrow: `PREDOSE · PROTOCOL CO-DESIGNER · D−1` (label style).
- Title: Inter 500 16px ink.
- Rationale: body-sm smoke.
- Evidence: a `<details>` disclosure, summary in mono 12px (`View evidence`), contents as Evidence quotes or a mono list.
- Signature line: an underlined input (no box, 1px ink bottom border) with the label `Reviewer` and the remembered name, plus an optional comment field.
- Actions: `Approve` (filled ink pill) and `Reject` (outline pill). No colour on either.
- Signed state: the slip collapses to one line with a stamp, mono label style, inside a dashed 1px graphite border rotated -2deg: `SIGNED · APPROVED · DANNY · D+3` (good tint text) or `REJECTED` (alert tint text). Auto-approved slips say `AUTO-APPROVED (DEMO)` in watch tint.
- The inbox heading shows a count readout: `3 waiting for a human`.

### 8.9 Agent log (L1 sheet)
The lab notebook of everything agents did.
- Row: mono day stamp column (`D+12`, 56px wide, ash), agent name (Inter 500 13px graphite), then the text (body-sm ink).
- Decision rows carry a small outline pill `DECISION` (label style). Human rows have a good-tint left hairline (2px). Warning rows have a watch-tint background.
- Filter tab pills above: All, Decisions, Human, Warnings. Newest first. Max height 480px with internal scroll and a fading bottom mask.

### 8.10 Agent network
SVG on a taupe sheet. Nodes are 52px discs styled as tiny glass (eggshell fill at 70%, rim, hairline). Master in the centre, predose, dosing, postdose and approvals around it. Edges are 1px ink hairlines at 35% opacity whose stroke width grows with log(count). Edge counts in mono 10px. Labels in mono 11px. Real modules show a solid outline; STUB modules a dashed outline with the label `STUB`.

### 8.11 Ledger table
Taupe sheet, header row on stone with label-style column headings, 13px body rows, stone hairlines between rows, numbers right-aligned in mono tabular. Sticky header inside its own scroll container (`overflow-x: auto`). Zebra striping is not used; hairlines do the work.

### 8.12 Evidence quote
Every extracted fact can show its source. 2px ink left rule at 20% opacity, quote in body-sm smoke italic, then a source tag pill in mono 11px (`ctgov:NCT03866174`, `protocol v2`). Never use a spark colour here.

### 8.13 Protocol editor (L1b paper)
A paper document on eggshell with a stone hairline, max 72 characters per line, Inter 15/1.7. A slim left gutter shows the diff after a re-check: added lines have a `+` in good tint, removed lines a `−` in alert tint, both with a 4% tint wash on the line. Above the editor: version chips (`v1 initial draft`, `v2 central raters`) as outline pills; the current one is filled ink. Primary button below: `Save version and re-check`.

### 8.14 Screening funnel
Five stages on one taupe sheet: Applied → Eligible (auto) → Excluded (auto) → Needs clinician → Enrolled. Each is a horizontal bar whose length is proportional to the count, bar fill stone with an ink 2px leading edge, count in readout mono at the right, stage label in label style above. The Needs clinician bar uses the watch tint, Excluded the alert tint, Enrolled ink.

### 8.15 Decision pill
Pill, label style, status tint fill and text: `ELIGIBLE` (good), `NEEDS CLINICIAN` (watch), `EXCLUDED` (alert). Always followed by the reasons as a plain list and any quoted disclosure as an Evidence quote.

### 8.16 Charts (recharts)
- Background: transparent on a taupe sheet.
- Grid: `stroke: var(--color-grid)` darker variant `rgba(0,0,0,0.06)`, dashed `2 4`.
- Axes: Geist Mono 11px, ash, no axis line, ticks 4px.
- Primary series: violet spark, 2px, no dots except an emphasised endpoint (5px dot with a 2px eggshell ring).
- Secondary series: ember spark 2px dashed. Threshold lines: ember 1px dashed with a mono label.
- Area under the primary series: violet at 8% opacity.
- Drift onset: a vertical ember 1px line with a small label `DRIFT ONSET D+28` in mono 10px.
- Legend: mono 11px, graphite, square swatches.
- A `SYNTHETIC` specimen tag sits in the top-right corner of every chart.
- Tooltip: `.glass.glass--strong` with mono values.

### 8.17 Buttons
| Variant | Fill | Text | Border | Use |
|---|---|---|---|---|
| Filled pill | ink | eggshell | none | The one primary action per region (Create trial, Approve, Play, Apply) |
| Outline pill | eggshell (or transparent on glass) | ink | 1px `#e5e5e5` (Darkroom `--color-stone`) | Secondary (Reject, Next day, +1 week) |
| Ghost pill | transparent | graphite | none, stone fill on hover | Nav links, inline actions |
Height 36px (40px in the dock), padding 0 16px, Inter 14/500, radius 9999px. Focus: 2px ink outline, 2px offset. Disabled: 40% opacity. Never a coloured button.

### 8.18 Inputs and forms
Eggshell fill, 1px stone border, radius 10px, 40px tall, Inter 15. Labels above in body-sm graphite 500. Help text in caption ash. Focus: border ink + 3px ring `rgba(0,0,0,0.08)`. Checkboxes and switches are custom: square 18px with 4px radius for checkboxes, 36×20 pill switches. The Volunteer portal form is a single 560px column on a paper document, with its result on a `.glass--strong` panel to the right (below on phones).

### 8.19 Bottleneck card (L1 sheet)
Opens every module page. Eyebrow `BOTTLENECK`, title (Inter 500 16px), the number in readout mono (`29.5% of 112 trials measured blinding`), source as an underlined smoke link, then "How we move it" in body-sm, and the metric in mono caption. Two or three side by side; one column on phones.

### 8.20 Toasts and dialogs (L3 glass)
Toasts: `.glass.glass--float`, pill radius, bottom-right above the dock, 4s, mono action label (`APPROVED · protocol v2 saved`). Dialogs: `.glass.glass--float.glass--strong`, 24px radius, max 520px. No other modals.

### 8.21 Empty and loading states
Empty: a small outline specimen icon, one sentence that says what will appear and how to start ("Create a trial to start the agents."), and the primary action. Loading: a 1px ink progress hairline under the nav plus the button label "Agents working…". No spinners on glass.

---

## 9. Page layouts

### Mission control
1. Nav, specimen band.
2. Header row: eyebrow `TRIAL T-0012 · SYNTHETIC`, display headline in whisper weight ("Day 23 of 90"), one smoke sentence on what is happening now (from the latest master summary).
3. Phase track (full width).
4. Readout grid: key readouts from every module (4 columns).
5. Two columns (5/12 and 7/12): Approval inbox (slips) | Agent log.
6. Agent network (full width, short).
7. Control dock floating at the bottom.
Before a trial exists: the header says "Start a trial", with a paper-document protocol editor (example selector as tab pills above it), an Auto-approve switch and a `Create trial` filled pill.

### Pre-dosing
Bottleneck cards → readout grid → two columns: Unblinding sphere card | FDA checklist → two columns: Protocol editor with diff | Drafted blinding section and version history → Screening funnel with flagged-applicant ledger and fairness table → Recruitment ads (paper sheets with reading ease and check pills, plus the parked-targeting note) → Measurement plan ledger → Agent log filtered to pre-dosing. Approval slips for pre-dosing appear in a sticky right column at ≥1100px.

### Volunteer portal
Centred, two columns: application form on paper (left) | Pre-screening agent result on strong glass (right). The result shows the decision pill, reasons, quoted disclosure, and the line "Final eligibility is always confirmed by a clinician."

### Dosing and Post-dosing (generic module page)
Rendered from each module's view model: STUB band if the module is a placeholder → bottleneck cards → readouts → cards (tone uses status tints) → charts → approval slips for this module → forms (as paper documents) → tables → agent log.

---

## 10. Motion

- Hover: 160ms ease-out on background and box-shadow. Buttons nudge 1px up on hover, back on press.
- Glass panels enter with opacity 0.0 → 1 and scale 0.985 → 1 over 220ms. Content is visible at rest; never wait on scroll.
- Play: the day counter rolls digits (translateY) per tick; the phase needle slides 180ms.
- Approvals: slip collapses 200ms to the stamp, stamp lands with a 120ms 1.06 → 1 scale.
- Specimen field drifts over 48s.
- `prefers-reduced-motion: reduce` turns off drift, digit rolls and scale; keep simple fades.

---

## 11. Voice and copy

- UK English. Plain verbs. No em dashes.
- Buttons say exactly what happens: `Approve`, `Reject`, `Save version and re-check`, `Create trial`, `Apply`.
- Labels are mono, uppercase, short: `REVIEWER`, `EVIDENCE`, `BEFORE`, `NOW`, `SYNTHETIC`.
- Numbers always carry units and context: `u 0.55 (medium)`, `56 of 500`, `D+28`.
- Errors say what went wrong and how to fix it: "Type your name first. Every decision is signed."

---

## 12. Accessibility

- Text contrast 4.5:1 minimum, including on glass over the brightest part of the specimen field. Use `.glass--strong` wherever body text sits on glass.
- Colour is never the only signal: every status pill has a word, every chart series has a legend and a pattern difference (solid vs dashed).
- Visible focus on every control (2px ink outline, 2px offset).
- Honour `prefers-reduced-motion` and `prefers-reduced-transparency`.
- Hit targets at least 40px in the dock and 36px elsewhere.

---

## 13. Do and don't

### Do
- Keep the canvas eggshell with the faint graph-paper grid, and put the specimen field behind everything.
- Use glass only for the nav, phase track, control dock, approval slips, portal result, toasts and dialogs.
- Set every number in Geist Mono with tabular numerals, with a unit and context.
- Keep display headlines at Inter 300 with -0.02em tracking.
- Use pills (9999px) for every button, tag, chip and the nav.
- Reserve violet and ember for data marks, the sphere and the specimen field.
- Show `SYNTHETIC` on every page and every chart.
- Show who signed what, and when, on every decided approval.

### Don't
- Don't make every card glass, and don't stack glass on glass.
- Don't put a spark colour on a button, link, border, icon or text.
- Don't bold the display type or use weights above 300 for headings.
- Don't use pure white `#ffffff` for surfaces, or pure grey neutrals.
- Don't use heavy drop shadows; only floating glass gets depth.
- Don't use red flashing alerts, emoji, or icons as the only signal.
- Don't use sharp corners under 6px on anything a user touches.
- Don't hide the reason a trial is blocked; always show it next to the day needle.

---

## 14. Quick start: CSS custom properties

```css
:root {
  /* Bench (light) */
  --color-eggshell: #fdfcfc; --color-taupe: #f5f3f1; --color-stone: #ebe8e4;
  --color-ink: #000000; --color-graphite: #44403b; --color-smoke: #777169; --color-ash: #a59f97;
  --color-spark-violet: #0447ff; --color-spark-ember: #ff4704; --color-grid: rgba(0,0,0,0.035);
  --status-good-fg: #25654a; --status-good-bg: #e6f1ea;
  --status-watch-fg: #8a5a00; --status-watch-bg: #faf0da;
  --status-alert-fg: #a3352a; --status-alert-bg: #fae8e4;
  --status-neutral-fg: #44403b; --status-neutral-bg: #ebe8e4;
  --button-border: #e5e5e5;

  --glass-fill: rgba(253,252,252,0.58); --glass-fill-strong: rgba(253,252,252,0.82);
  --glass-blur: 22px; --glass-saturate: 165%;
  --glass-rim: inset 0 0 0 1px rgba(255,255,255,0.65);
  --glass-edge: 0 0 0 0.5px rgba(0,0,0,0.08);
  --glass-depth: 0 1px 1px rgba(0,0,0,0.04), 0 10px 30px rgba(68,64,59,0.10);
  --glass-specular: linear-gradient(180deg, rgba(255,255,255,0.70) 0%, rgba(255,255,255,0.08) 38%, rgba(255,255,255,0) 60%);
  --field-opacity: 0.16;

  --font-display: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-body: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  --radius-pill: 9999px; --radius-sheet: 20px; --radius-glass: 24px; --radius-input: 10px; --radius-plate: 6px;
  --page-max: 1280px; --gutter: 64px; --section-gap: 64px;
  color-scheme: light;
}
@media (max-width: 1100px) { :root { --gutter: 24px; } }
@media (max-width: 420px)  { :root { --gutter: 16px; } }

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-eggshell: #0e0d0c; --color-taupe: #171614; --color-stone: #2a2724;
    --color-ink: #f5f3f1; --color-graphite: #d6d1cb; --color-smoke: #a59f97; --color-ash: #7a746c;
    --color-spark-violet: #4d7bff; --color-spark-ember: #ff6a33; --color-grid: rgba(255,255,255,0.04);
    --status-good-fg: #7cc9a2; --status-good-bg: #16261e;
    --status-watch-fg: #e8b65a; --status-watch-bg: #2a2112;
    --status-alert-fg: #f08a7d; --status-alert-bg: #2c1714;
    --status-neutral-fg: #d6d1cb; --status-neutral-bg: #2a2724;
    --button-border: #2a2724;
    --glass-fill: rgba(23,22,20,0.55); --glass-fill-strong: rgba(23,22,20,0.82); --glass-saturate: 140%;
    --glass-rim: inset 0 0 0 1px rgba(255,255,255,0.10); --glass-edge: 0 0 0 0.5px rgba(0,0,0,0.6);
    --glass-depth: 0 1px 1px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.45);
    --glass-specular: linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 45%);
    --field-opacity: 0.22;
    color-scheme: dark;
  }
}
/* Repeat the same dark values under :root[data-theme="dark"] so a manual toggle wins. */
```

---

## 15. Agent prompt guide (quick reference)

- **Canvas:** `#fdfcfc` with a 24px graph-paper grid, specimen field behind.
- **Text:** ink `#000`, body smoke `#777169`, footnote ash `#a59f97`.
- **Sheets:** taupe `#f5f3f1`, radius 20px, no shadow.
- **Glass:** fill `rgba(253,252,252,0.58)`, blur 22px, saturate 165%, white inner rim, hairline edge, specular top gradient.
- **Data sparks:** violet `#0447ff` (primary series), ember `#ff4704` (thresholds, drift, rater series). Never UI chrome.
- **Primary action:** black filled pill.
- **Type:** Inter 300 headlines (-0.02em), Inter 400/500 body, Geist Mono for every number and label.

**Example component prompts**
1. "Create a readout tile: taupe sheet, 20px radius, eyebrow `PREDICTED UNBLINDING` in Geist Mono 11px uppercase +0.08em, value `0.55` in Geist Mono 40px tabular with unit `u` in smoke, footer `before 0.79 → now 0.55` in mono 12px with a good-tint delta."
2. "Create an approval slip: strong glass panel, 24px radius, eyebrow `PREDOSE · PROTOCOL CO-DESIGNER · D−1`, title Inter 500 16px, rationale in smoke, underlined Reviewer input, Approve (black pill) and Reject (outline pill). Signed state: dashed stamp rotated -2deg `SIGNED · APPROVED · DANNY · D+3`."
3. "Create the floating glass nav: 56px pill, sticky 12px from the top, wordmark UNBLIND, ghost pill links, right side trial chip `T-0012` and `D+23 / 90` in mono and an amber `3 to sign` pill."
4. "Create the unblinding sphere for u = 0.79: 220px circle, violet blooming from the centre and ember from the lower rim, white specular highlight upper left, value and band pill beside it, 0 to 1 scale labelled `coin flip` and `everyone knows`."
5. "Create a line chart of rater guess accuracy by site: violet primary series, ember dashed series for Site B, ember dashed threshold at 0.75 labelled in mono, vertical `DRIFT ONSET D+28` marker, mono axes, SYNTHETIC tag top right, glass tooltip."
