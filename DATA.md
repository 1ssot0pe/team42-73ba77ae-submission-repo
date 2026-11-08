# Parallax: data statement

Every piece of data Parallax makes, reads or sends, with what it is, how it was produced, how it is
labelled and what evidence stands behind it. The format follows *Datasheets for Datasets*
(Gebru et al., Communications of the ACM, 2021): one card per dataset answering the same questions.

**In one paragraph.** Parallax uses no patient data of any kind. Everything about people (applicants,
participants, raters, guesses, scores, session notes) is **SYNTHETIC**, produced by a seeded simulator
and labelled on screen, in every chart title and in every stored row. The real data is published,
trial-level information only: a review paper, the FDA guidance, registry records and journal articles,
each cited with a link. Real facts extracted by agents stay marked "needs human check" until a named
person verifies them.

Last reviewed: 8 November 2026.

## Contents

1. [Summary table](#1-summary-table)
2. [Synthetic data](#2-synthetic-data): the trial simulator, the vault, the calibration set, assumptions
3. [Real data](#3-real-data): headline evidence, the candidate gold set, live lookups
4. [Invented test material](#4-invented-test-material)
5. [Evaluation outputs](#5-evaluation-outputs)
6. [Data the platform writes](#6-data-the-platform-writes)
7. [Checklist against the hackathon data rules](#7-checklist-against-the-hackathon-data-rules)
8. [Known gaps and next steps](#8-known-gaps-and-next-steps)
9. [References](#9-references)

## 1. Summary table

| Dataset | Real or synthetic | Where it lives | How it is labelled | Card |
|---|---|---|---|---|
| Simulated trial: applicants, participants, sites, raters, guesses, MADRS scores, session notes | Synthetic | `unblind/platform/world.py` (generated at run time) | "SYNTHETIC SPECIMEN" banner on every page, "SYNTHETIC" in chart titles, `synthetic: true` on every row | [2.1](#21-the-trial-simulator) |
| Treatment allocation | Synthetic | `unblind/platform/core.py` (`Vault`) | Never shown; agents see group totals only | [2.2](#22-the-vault-allocation) |
| Calibration set for the cross-trial correction | Synthetic | `data/calibration_synthetic.csv` | `provenance = SYNTHETIC` on every row; reports say "SYNTHETIC calibration" | [2.3](#23-the-synthetic-calibration-set) |
| Default assumptions | Team assumptions | `data/priors.json` | The file says "TEAM ASSUMPTIONS, NOT DATA" | [2.4](#24-team-assumptions) |
| Headline evidence on the problem cards | Real, published | `data/bottlenecks.json` | Citation and link on each card | [3.1](#31-headline-evidence) |
| Candidate gold set: 18 published trials | Real, published, unverified | `data/gold_candidates.csv` | Every row: "NO - needs human check" | [3.2](#32-the-candidate-gold-set) |
| Live registry and literature lookups | Real, public | ClinicalTrials.gov and Europe PMC APIs | Every extracted fact carries its quote and source | [3.3](#33-live-lookups) |
| Example protocols, test trials, bias-gate questions | Invented | `data/protocols/`, `tests/fixtures.py`, `unblind/platform/postdose/question_set.py` | "FICTIONAL EXAMPLE", "INVENTED", "FIXTURE" in the text | [4](#4-invented-test-material) |
| Evaluation results | Synthetic or fixture | `eval/`, `unblind/platform/dosing/eval_results/` | "SYNTHETIC" or "FIXTURE RUN" in each report title | [5](#5-evaluation-outputs) |

## 2. Synthetic data

### 2.1 The trial simulator

**What it is.** A stand-in for real people, sites and raters, so a whole 90-day trial can run in
minutes. Code: `unblind/platform/world.py` (class `World`, settings in `WorldConfig`).

**Why it exists.** Blinding failures cannot be studied on real patients in a prototype, and real
participant-level trial data is not public. A simulator with *planted* problems lets us check whether
the agents find them, because we know the right answer.

**How it is produced.** Python's `random.Random`, seeded per trial (default seed 42), so every run is
reproducible. Names are a first name from a fixed list of 24 plus an initial. Nothing is derived from
any real person or record.

| What is simulated | How | Basis |
|---|---|---|
| 500 applicants | Age uniform 16 to 79; 88% UK; prior psychedelic use never 55%, once 25%, several times 20%; 0 to 4 failed antidepressants; psychosis 4%, bipolar 5%, cardiovascular condition 6%, pregnant 2% | Assumption, chosen to give a realistic mix of eligible and excluded people |
| Hidden exclusions | 6% of applicants mention bipolar disorder, psychosis or high blood pressure only in free text | Planted test for the screening agent; the truth is stored under `_hidden_exclusion`, which agents may not read |
| Baseline depression score | MADRS drawn from a normal distribution, mean 32, SD 4 | Assumption: a typical baseline for treatment-resistant depression |
| Score over time | Everyone improves 6 points (placebo response), phased in over 21 days; noise SD 4; clipped to 0 to 60 | Assumption |
| True drug benefit | 4 MADRS points | In line with the Phase 3 psilocybin results: 3.6 points (COMP005) and 3.8 points (COMP006), see [3.1](#31-headline-evidence) |
| Expectancy bias | 3 extra points if the participant believes they got the drug; 2 if the rater does | Assumption; this is the bias Parallax tries to measure |
| Participant guesses | Guess "drug" with probability 0.88 if on drug, 0.25 if on control (adjusted by prior psychedelic use); "don't know" 8% of the time. Overall about 82% correct | Conservative relative to the review's finding of blinding failure above 90% for psilocybin, LSD and ayahuasca |
| Rater guesses | About 59% correct normally (0.60 drug, 0.42 control) | Assumption: raters can partly tell from outcomes and side effects |
| **Planted rater drift** | From day 28, raters at Site B (Manchester) guess about 89% correctly (0.90 and 0.12), as if sitting in on dosing sessions | Planted test for the drift agent. Consistent with the review's raters-and-participants failure rates |
| **Planted missing data** | Site C (Bristol) misses 18% of check-ins, other sites 5% | Planted test for the missing-data agent |
| Monitor session notes | Short text from fixed templates: strong effects on drug; mild relaxation or "asked whether they had received the active drug" on control; side effects 25% (drug) or 8% (control); "Outcome rater came into the room" 10% at every site | Assumption, written to exercise the debrief parser |
| Answers to researcher questions | One of five fixed answers | Placeholder |
| Effect of approved actions | Remote raters end the drift at that site; better reminders end the missing-data pattern | Lets the demo show whether a human-approved fix worked |

**Labelling.** Every stored row has `synthetic: true` (a test, `test_everything_synthetic`, enforces this
for the dosing sections). Every page shows the "SYNTHETIC SPECIMEN" banner and every chart is titled
"(SYNTHETIC)".

**Limits.** The numbers are assumptions, not fitted to individual-level data. The simulator has one
planted failure of each kind; real trials will fail in messier ways. Results on simulated trials say
the agents *can* find these patterns, not how often they would in a real trial.

**Note on phone numbers.** Applicant phone numbers are random digits in real formats (for example
`+44 7...`), so one could match a real number. If they are ever shown publicly, use the ranges set
aside for fiction instead (Ofcom's 07700 900000 to 07700 900999 in the UK, 555-0100 to 555-0199 in the US).

### 2.2 The vault (allocation)

**What it is.** The only holder of who got the drug. Code: `unblind/platform/core.py`, class `Vault`.

**How it is produced.** Stratified permuted-block randomisation, 1:1, blocks of 4, seeded.

**How agents interact with it.** Agents never see allocation. They send groups of guesses and get back
totals only (`blinding_stats`): accuracy, a 95% interval and a blinding index. Any group under 5 people
(`MIN_CELL = 5`) is suppressed, and the dosing monitor sends disjoint batches of at least 5 so its own
queries cannot be combined to single anyone out. Every query is written to an access log. Only the
simulator reads allocation, because it plays the role of reality (people on the drug really do feel it).
A test (`test_agents_never_touch_allocation_or_world_internals`) scans the agent code for any access.

### 2.3 The synthetic calibration set

**What it is.** 36 simulated trials used by the cross-trial correction (effect against unblinding)
until real trials are verified. File: `data/calibration_synthetic.csv`.

**How it is produced.** `unblind/synthetic.py`, `write_demo_calibration(seed=7)`: true effect at zero
unblinding g = 0.35; bias of 0.6 per unit of unblinding; on-site raters add 0.10; comparator mix 60%
inert placebo, 15% active placebo, 15% low dose, 10% other active; 40% of trials "report" blinding and
the rest are imputed from design.

**Labelling.** `provenance = SYNTHETIC`, `drug = synthetic-psychedelic`, IDs start `SYN-`. The model
labels its output "SYNTHETIC calibration set ... Not real-world performance" (`unblind/model.py`), and
the close-out report repeats this in its limitations.

### 2.4 Team assumptions

`data/priors.json` holds the expected unblinding for each comparator type (for example inert placebo
0.75, active placebo 0.50) and how feasible each design fix is. It is used only when fewer than 8 real
trials with blinding data are available, and the app shows the numbers whenever it uses them. The high
value for inert placebo is motivated by the 2026 review ([3.1](#31-headline-evidence)); the rest are
judgement calls with deliberately wide uncertainty.

## 3. Real data

### 3.1 Headline evidence

The cards that open every page (`data/bottlenecks.json`) cite primary sources. Checked on 8 November 2026.

| Claim on the page | Evidence | How it was checked |
|---|---|---|
| 29.5% (33 of 112) randomised psychedelic trials assessed blinding | Orsini DK et al. Blinding Integrity in Psychedelic Randomized Clinical Trials: A Systematic Review. *JAMA Psychiatry* 2026;83(7):755-769. doi:10.1001/jamapsychiatry.2026.0255. PMID 41984443 | Record confirmed through the Europe PMC API; figures from the abstract. The full text is not open access |
| Blinding failure above 90% for psilocybin, LSD and ayahuasca; above 85% for inert-placebo MDMA trials | Same review, abstract; also reported by the University of Toronto | As above |
| The FDA names functional unblinding as a threat to validity and recommends central blinded raters, blinding questionnaires and expectancy measures | FDA. *Psychedelic Drugs: Considerations for Clinical Investigations.* Final guidance, July 2026, docket FDA-2023-D-1987 | Downloaded the 16-page PDF from fda.gov and found each recommendation in the text; the Federal Register notice (2026-14158) confirms the docket and that it finalises the 2023 draft |
| Two monitors per session and an on-call physician within 15 minutes if the lead monitor is not a physician | Same guidance, safety monitoring section | Found in the text |
| Functional unblinding was raised in the FDA's review of MDMA-assisted therapy | FDA briefing document for midomafetamine (NDA 215455), 2024 | Public FDA document |
| COMP005: -3.6 MADRS points vs placebo (95% CI -5.7 to -1.5). COMP006: -3.8 points vs 1 mg (95% CI -5.8 to -1.8) | Compass Pathways press releases, 23 June 2025 and 17 February 2026. Registered as NCT05624268 (258 enrolled, completed) and NCT05711940 (572 enrolled) | Registry records confirmed through the ClinicalTrials.gov API; **no results are posted there yet**, so the effect sizes rest on company releases |
| Only 4 of 18 real trials reported clean per-arm guess data | The candidate gold set below | Our own extraction, unverified |

### 3.2 The candidate gold set

**What it is.** 333 facts about 18 published psychedelic trials (design, comparator, raters, effect
size, guess accuracy), one row per trial per field. File: `data/gold_candidates.csv`; full method in
[`data/gold_candidates_README.md`](data/gold_candidates_README.md).

**Why it exists.** It is the seed of the real calibration corpus that will replace the synthetic one,
and the source for the "non-comparable blinding data" finding.

**How it was produced.** Extracted on 7 November 2026 from journal pages and open repositories, each
fact with a short quote and a source link. Sources by number of rows: JAMA Network 106, Europe PMC 65,
MAPS bibliography 30, PubMed Central 19, Nature 17, Cambridge 15, others under 15 (company releases, an
SEC filing, HRA, university repositories). 278 rows have a value; the rest are blank because the fact
was not found. 14 values are **DERIVED** (calculated from quoted counts, with the arithmetic in `notes`).

**Labelling.** Every row says `verified = NO - needs human check`. Nothing enters the real calibration
corpus (`data/calibration_real.csv`) until a named person approves it.

**Licence.** Rows hold extracted facts and short quotes with links, not article text. Open-access status
is recorded per trial: 8 open access, 4 not, 6 unknown.

**Limits.** Quotes passed through a summarising fetch tool, so each must be checked against the source.
Effect signs are not harmonised across papers. The 2026 review's per-trial table was not available.

`data/psychedelic_trials.txt` lists 17 real ClinicalTrials.gov IDs from this set, used as input to
`python -m unblind build-corpus`.

### 3.3 Live lookups

The evidence engine and the weekly literature agent read public sources through one fetcher
(`unblind/net.py`). Only hosts on an allowlist can be reached:

| Source | Hosts | What is read | Terms |
|---|---|---|---|
| ClinicalTrials.gov API v2 | clinicaltrials.gov, cdn.clinicaltrials.gov | Registry records and posted protocol PDFs | US government registry; public domain as stated in `WRITEUP.md` |
| Europe PMC REST API | www.ebi.ac.uk, europepmc.org | Open-access full text and supplements | Licence differs per article and is recorded with each one |
| Gemini API (optional) | generativelanguage.googleapis.com | Sends fetched public text for extraction; only when `GEMINI_API_KEY` is set | No patient data is ever sent; without a key, deterministic rules are used |

Responses are cached locally (`.cache/`). Text found inside fetched documents is treated as data, never
as instructions, and links inside documents cannot send the fetcher to other hosts. Every extracted
fact must match its source word for word (the auditor agent) or it becomes "unknown".

## 4. Invented test material

| Material | File | Label |
|---|---|---|
| Two example draft protocols (psilocybin for depression, MDMA for PTSD) | `data/protocols/*.md` | "DRAFT protocol (FICTIONAL EXAMPLE)" and "It is not a real protocol" |
| Two test trials, NCT99999901 and NCT99999902 (the IDs do not exist) | `tests/fixtures.py`, `eval/results/fixture_gold.csv` | "INVENTED", "FIXTURE" in titles and URLs |
| Gold-set template rows | `data/gold_template.csv` | "EXAMPLE (invented fixture trial; delete this row ...)" |
| 15 researcher questions for testing the bias gate, labelled before the rules were tuned | `unblind/platform/postdose/question_set.py` | "These are invented questions, not real ones" |

## 5. Evaluation outputs

All evaluations run on synthetic trials or invented fixtures and say so in their titles. None of them
is evidence of real-world performance.

| Evaluation | Report | What it shows |
|---|---|---|
| Rater drift detection (dosing) | `unblind/platform/dosing/eval_results/drift_eval.md` | 20 simulated trials, 72 participants: the CUSUM agent caught the planted drift in 18 of 20, a median 13.5 days after onset, with 0.3 false alarms per trial; an end-of-trial check caught 14 of 20, 62 days after onset. Threshold set on separate seeds (100 to 129) |
| Effect recovery (post-dosing) | `eval/platform/results.md` | The reported effect overstates a planted 4-point benefit; the within-trial adjustment recovers it when its assumption holds and fails when improvement drives guessing |
| Cross-trial meta-regression | `eval/results/synthetic_recovery.md` | 300 simulated meta-analyses per scenario: a standard meta-analysis is biased by about 0.43 g; the Parallax estimate is close to the truth when its assumptions hold, and over-corrects under reverse causation |
| Extraction accuracy | `eval/results/extraction_eval_fixtures.md` | Runs only on the two invented fixtures, so it checks the scorer, not accuracy on real papers |
| Bias gate | `eval/platform/bias_gate_eval.py` | Scores the gate on the 15 invented questions |

## 6. Data the platform writes

| What | Where | Contents |
|---|---|---|
| Trial record | `data/trials/<trial id>.json` (not committed: git-ignored) | All of a trial's rows, every one `synthetic: true` |
| Vault file | `data/trials/<trial id>.vault.json` (not committed) | Allocation and the access log |
| Sign-offs | `data/signoffs.jsonl` (not committed) | Name, decision and time for each approved evidence report |
| Real calibration corpus | `data/calibration_real.csv` | Only trials a named person approved |
| Harmonised export | Generated on approval | Blinding rows in the standard instrument set, with salted-hash IDs and only participants who consented to data sharing |

## 7. Checklist against the hackathon data rules

| Rule | Status | How |
|---|---|---|
| Label synthetic data and say how you made it | Met | Banner, chart titles and `synthetic: true` on every row; this document and section [2](#2-synthetic-data) |
| Never present it as real-world performance | Met | Every evaluation report and every readout that comes from simulated trials says SYNTHETIC; the adjusted effect is labelled as using the SYNTHETIC calibration |
| No real patient data, ever | Met | Only published, trial-level data is used; no individual-level record from any source |
| Reference every dataset and check its licence | Mostly met | Every dataset is listed here with its source. Open items: 6 trials with unknown open-access status, and the gold set awaiting human checks (section [8](#8-known-gaps-and-next-steps)) |

## 8. Known gaps and next steps

1. **Verify the candidate gold set.** A person should check each quote against its source and mark
   the row verified. Start with the 4 trials that report per-arm guess data.
2. **Get the 2026 review's full text** through institutional access; its supplement should list per-trial
   blinding results for all 33 trials that measured it.
3. **Re-check the Compass effect sizes** once results are posted on ClinicalTrials.gov or published in a
   journal.
4. **Resolve open-access status** for the 6 trials marked unknown.
5. **Anchor more simulator settings in evidence.** Rater accuracy before drift (59%) and the expectancy
   sizes are assumptions; the review's per-trial data could set them.
6. **Consider Synthea** (synthetic patient generator, open source) for a more realistic mix of ages,
   sex and medical history among applicants.
7. **Use fiction-reserved phone numbers** for synthetic applicants (section [2.1](#21-the-trial-simulator)).

## 9. References

- Gebru T, Morgenstern J, Vecchione B, et al. Datasheets for Datasets. *Communications of the ACM*
  2021;64(12):86-92. https://doi.org/10.1145/3458723
- Orsini DK, Wong S, Di Luch S, et al. Blinding Integrity in Psychedelic Randomized Clinical Trials: A
  Systematic Review. *JAMA Psychiatry* 2026;83(7):755-769. https://doi.org/10.1001/jamapsychiatry.2026.0255
  (PMID 41984443)
- University of Toronto, Temerty Faculty of Medicine. Psychedelics promising, not prime time, say
  researchers. https://temertymedicine.utoronto.ca/news/psychedelics-promising-not-prime-time-say-researchers
- US Food and Drug Administration. Psychedelic Drugs: Considerations for Clinical Investigations.
  Guidance for Industry, July 2026. https://www.fda.gov/media/169694/download
- Federal Register notice of availability, document 2026-14158 (docket FDA-2023-D-1987).
  https://public-inspection.federalregister.gov/2026-14158.pdf
- US Food and Drug Administration. Briefing document, NDA 215455, midomafetamine.
  https://www.fda.gov/media/178984/download
- Compass Pathways. Second Phase 3 trial (COMP006) press release, 17 February 2026.
  https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Successfully-Achieves-Primary-Endpoint-in-Second-Phase-3-Trial-Evaluating-COMP360-Psilocybin-for-Treatment-Resistant-Depression/default.aspx
- Compass Pathways. First Phase 3 trial (COMP005) press release, 23 June 2025.
  https://www.biospace.com/press-releases/compass-pathways-successfully-achieves-primary-endpoint-in-first-phase-3-trial-evaluating-comp360-psilocybin-for-treatment-resistant-depression
- ClinicalTrials.gov records NCT05624268 and NCT05711940. https://clinicaltrials.gov/study/NCT05624268,
  https://clinicaltrials.gov/study/NCT05711940
- ClinicalTrials.gov API v2. https://clinicaltrials.gov/data-api/api
- Europe PMC RESTful web service. https://europepmc.org/RestfulWebService
- Synthea synthetic patient generator. https://synthetichealth.github.io/synthea/
