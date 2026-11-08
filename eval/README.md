# Parallax evaluation

Three questions, three scripts. Each one says what it measures, what would count as success, and where it can mislead.

| Script | Question | Needs |
|---|---|---|
| `synthetic_recovery.py` | Does the meta-regression recover a known drug effect, and how does it fail when its assumptions break? | nothing (numpy, matplotlib) |
| `extraction_eval.py` | Do the agents read the right numbers out of real trial documents? | `data/gold.csv` (human-verified), network or a warm cache |
| `baseline_vs_pipeline.py` | Is the agent pipeline better than one Gemini prompt, and how much of Gemini's score is memory rather than reading? | `GEMINI_API_KEY`, `data/gold.csv` |

Run everything from the repo root. Python 3.10+.

```bash
python eval/synthetic_recovery.py                 # about 10 s; writes eval/results/synthetic_recovery.{md,png}
python eval/extraction_eval.py --fixtures         # offline end-to-end check on the two invented test trials
python eval/extraction_eval.py                    # real run; writes a template if data/gold.csv is missing
GEMINI_API_KEY=... python eval/baseline_vs_pipeline.py [--regulatory]
python eval/baseline_vs_pipeline.py --selftest    # offline plumbing test with a stub LLM (numbers meaningless)
```

## 1. Synthetic recovery (statistics only)

Simulates meta-analyses with a planted truth using `unblind.synthetic.make_trials`: three scenarios, k = 15, 30 and 60 trials, 300 replicates each, 35% of trials reporting blinding. It compares the Parallax intercept (primary fit on observed blinding, and the sensitivity fit with imputed blinding) against the **baseline a standard meta-analysis would report**: the DerSimonian-Laird random-effects pooled mean of the reported effects, ignoring blinding. Metrics: mean and median bias against the truth, RMSE, 95% CI coverage, CI width, share of fits that fail, each with Monte Carlo error.

| Scenario | What is planted | Success looks like |
|---|---|---|
| `expectancy` | bias = 0.6 x unblinding. The model's assumptions hold. | Parallax bias near 0 and coverage near 95%, naive clearly biased |
| `reverse_causation` | no expectancy bias. Patients who improve guess "drug" more often. | Nothing can succeed here for Parallax. The point is to measure how much it over-subtracts |
| `confounded` | better-blinded trials also had lower true effects | Same. Shows that cross-trial confounding is not fixed by the correction |

Two stress tests use small wrappers in the script (not edits to `make_trials`): `noisy_guess` measures unblinding from binomial guess counts instead of handing the model the true value, and `mixed` combines reverse causation with a real expectancy bias.

**What it does not show.** Synthetic results show the method works when its assumptions hold and how it fails when they do not. They are not real-world performance and must never be presented as such. The data generator encodes our own assumptions about effect sizes, unblinding by comparator and missingness (blinding reporting is missing completely at random here, which real trials will not be).

## 2. Extraction accuracy (agents)

Scores the pipeline field by field against `data/gold.csv`:

```
nct,field,gold_value,quote,source_url,verified_by
```

Fields: `effect_est`, `effect_lo`, `effect_hi` (as reported in the source, same units and sign), `comparator_type`, `rater_placement`, `guess_acc_participants`, `guess_acc_raters`, `prior_exposure` (proportions 0 to 1). Numbers match within ±0.02 for proportions and ±0.05 for effects. Categories must match exactly. Write `NR` when a careful reader finds the value genuinely not reported, so that abstaining is scored as correct and inventing a value is scored as the worst error.

Reported per field: accuracy with a Wilson 95% interval, coverage (answered rather than `unknown`), precision, recall, values given where gold is `NR`, how many `unknown`s were honest abstentions versus misses, and the quote-audit pass rate.

**Success**: high precision and near-zero "answered when NR" matter more than coverage. An `unknown` that sends a human to the paper is cheap. A confident wrong number in a meta-regression is not.

**The gold set must be human-verified.** Rows without `verified_by`, or marked `EXAMPLE`, are skipped. Build it by reading each paper and registry entry yourself, not by copying pipeline output, or the evaluation measures agreement with itself. Ideally two people verify each row independently and disagreements are logged.

`--fixtures` runs the whole evaluation offline on the two invented trials in `tests/fixtures.py` with a gold built from their known truth. It proves the harness works. It says nothing about accuracy on real papers.

## 3. Baseline vs pipeline (and memory leakage)

The baseline is a single Gemini prompt given exactly the source text the pipeline fetched (so it gets retrieval for free, and the comparison isolates extraction). It is asked for the same fields with verbatim quotes, plus a high, medium or low risk-of-expectancy-bias label. It runs three ways:

* **unmasked**: the text as fetched
* **masked**: drug names and aliases, sponsor, known psychedelic developers, trial acronyms, NCT IDs, DOIs and PubMed/PMC IDs replaced with placeholders. The same drug keeps the same placeholder, so a low-dose comparator stays recognisable
* **memory**: no document, only the NCT ID and title

**Memory leakage** is unmasked minus masked. Memory-only recall shows what the model "knows" without reading. A model that has read coverage of the Lykos MDMA programme can answer from memory, which inflates the unmasked score and says nothing about trials nobody has written about.

Both systems are scored with the same scorer as (2), plus **quote verifiability**: the share of claimed values whose quote appears verbatim (after `unblind.audit._norm`) in the text that system was given.

**Success**: the pipeline at least matches the masked baseline on accuracy, beats it on "answered when NR", and keeps quote verifiability near 100%. A baseline that only wins when unmasked is winning on memory.

`--regulatory` prints a label check for Lykos/MAPS and COMPASS trials. A regulatory decision is not ground truth for expectancy bias, "cleared for rolling review" is a procedural step rather than a verdict, and n is a handful of trials. It is a sanity check only. Add a source URL for each status in `REGULATORY` before showing it.

## Data and licences

* Synthetic data: generated by this repo, every row labelled `provenance=SYNTHETIC`.
* Fixture trials (`NCT999999xx`): invented, do not exist.
* ClinicalTrials.gov registry records: US National Library of Medicine, generally public domain (see clinicaltrials.gov terms). Protocol PDFs posted by sponsors may carry sponsor copyright.
* Europe PMC: full text is only fetched from the open-access subset. Check each article's licence (stored per source in the report) before redistributing text. CC BY allows reuse with attribution, CC BY-NC does not allow commercial reuse. Abstracts of closed papers are publisher copyright and are used only for extraction with citation.
* `eval/results/runs/` caches pipeline reports and fetched source text. It has its own `.gitignore`. Do not publish it.
* `data/gold.csv` quotes are short excerpts for verification, with their source URL.

## Known limitations of the evaluation itself

* The extraction gold set will be small. Report intervals, not just percentages.
* The synthetic study tests the statistics under assumptions we chose. A method that passes it can still fail on real data for reasons we did not simulate.
* Coverage above 95% for the Parallax intervals partly reflects a conservative Knapp-Hartung floor in `fit_metareg`. Under reverse causation, high coverage comes from wide intervals around a biased centre.
