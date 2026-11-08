# team42-73ba77ae-submission-repo

## Parallax

*Parallax is the shift in what you see when you look from a different place. A rater sitting in the dosing room sees a different trial from one who never enters it, and a patient who has tripped sees a different trial from one who has not. Parallax measures that shift and corrects for it.*

**How much of a psychedelic trial's result is expectation?**

Patients in psychedelic trials usually know whether they got the drug. A 2026 systematic review of 112 randomised psychedelic trials found only 29.5% even assessed blinding, and psilocybin, LSD and ayahuasca studies frequently reported blinding failure above 90%. So every reported effect is drug plus expectation, and one trial cannot separate the two.

Many trials can. They were built differently (inert placebo or low active dose, on-site or central raters, experienced or naive participants), so their unblinding varies. Parallax fits effect against unblinding across trials, reads off the effect at zero unblinding, and ranks the design changes that would shrink the bias in the next trial.

The maths is a short meta-regression. The hard part is collecting about eight facts per trial from registries, papers, supplements and protocol PDFs, where they are scattered or missing. That is the agents' job.

> Built in 24 hours at Agentverse 2026 (Biotech track). Prototype. The bundled calibration set is **synthetic** until real trials are extracted and approved by a person.

## Quick start

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...            # optional: without it, deterministic rules extract every field
streamlit run app/app.py             # the demo
python -m unblind run NCT03866174    # command line, live agent trace
pytest -q                            # 14 offline tests
```

The project was first called UNBLIND, so the Python package is still `unblind` (as in `python -m unblind`), the environment variables still start with `UNBLIND_`, and the shared blinding instrument set keeps its ID `UNBLIND-BLIND-1`.

No internet? Press **Load fixture demo** in the app sidebar. It replays two INVENTED test trials (NCT99999901, NCT99999902) from cache.

The app accepts any handle: an NCT ID, a DOI, a PMID or PMCID, a pasted abstract, or a short description like "psilocybin alcohol use disorder".

## The agents

```
input ─► Resolver ─► Hunter ─┬─► Outcome extractor ──────┐
                             ├─► Design extractor ───────┤──► Evidence ledger ─► Auditor ─► Statistician ─► Design advisor ─► HUMAN SIGN-OFF
                             └─► Blinding hunter ────────┘      (fact + quote      (verbatim   (plain code,     (ranked fixes)
                                  paper → supplement → protocol   + source + licence) quote check)  not an LLM)
```

| Agent | Job | Where it decides its own next step |
|---|---|---|
| Resolver | Works out what the input is and finds the registered trial | DOI with no NCT ID, so it reads the paper for one. Free text, so it searches the registry and flags the match for a human to confirm |
| Hunter | Finds the publication | Reformulates the query on a miss (registry ID, then title + sponsor, then drug + condition). Falls back to the abstract if the paper is not open access |
| Outcome extractor | Picks the effect matching the **registered** primary endpoint | Loops back to the registry record, then rejects other timepoints, completers analyses and within-group numbers |
| Design extractor | Comparator, rater placement, prior psychedelic use | **Results-blind**: every sentence with effect statistics is redacted before it reads, so a dramatic result cannot sway how it reads the design |
| Blinding hunter | Guess-accuracy data | Paper, then supplements (only if open access), then protocol PDF. If the protocol planned a blinding check that was never reported, it flags possible selective reporting |
| Auditor | Checks every fact | Deterministic code, not another LLM. The quote must appear word for word in the cited source, and the numbers must appear in the quote. Failures become "unknown" |
| Statistician | Hedges' g from mean difference + CI + arm sizes, unblinding index, meta-regression | Plain numpy, so it cannot hallucinate |
| Design advisor | Counterfactuals: swap comparator, move raters central, enrol naive participants | Ranks by bias reduction x feasibility (feasibility weights are team assumptions in `data/priors.json`) |

Every fact has a status: **observed** (quoted and verified), **derived** (computed in code), **imputed** (estimated from design, labelled, with a wider interval) or **unknown**.

## The model

`g = a + b·u + c·central`, a random-effects meta-regression across trials.

- `g` is the standardised effect (positive means the drug did better).
- `u = 2 × guess accuracy − 1` is excess correct guessing (0 = coin flip, 1 = everyone knew).
- `central` = 1 when outcome raters were remote, blinded and absent from dosing.

The reference design is zero unblinding with central blinded raters (`a + c`). The primary fit uses only trials whose blinding was **observed**. Trials with imputed blinding enter a sensitivity fit, with their extra uncertainty propagated.

## Evaluation (see `eval/README.md`)

1. **Planted-truth simulation** (`eval/synthetic_recovery.py`, SYNTHETIC). The truth is 0.35 g, with 60 trials and 300 replicates per scenario.
   - **Expectancy bias only (assumptions hold):** a standard meta-analysis overstates the effect by +0.43 g and its interval contains the truth 0% of the time. Parallax's bias is −0.005 g, with 98% coverage, at the cost of intervals several times wider.
   - **Reverse causation (people guess "drug" because they improved):** Parallax over-subtracts by about 0.15 g. This is the method's key failure mode, and why every report calls the corrected value a conservative bound.
   - **Cross-trial confounding:** the correction is worse than doing nothing. We report it.
   - **With only 15 trials:** the primary fit fails about a third of the time.
2. **Extraction accuracy against a hand-verified gold set** (`eval/extraction_eval.py`). It reports field accuracy, coverage, honest abstention and audit pass rate. `data/gold_candidates.csv` holds 18 real trials with quotes and URLs, all marked **NOT VERIFIED**. A person must check each row before it becomes `data/gold.csv`.
3. **Baseline: single-shot Gemini vs the agent pipeline** (`eval/baseline_vs_pipeline.py`). The baseline runs on **masked** text (drug, sponsor and trial names replaced) and on unmasked text. The difference measures how much a model "knows" from news coverage rather than reads from the document.

## Data and licences

| Source | Use | Licence |
|---|---|---|
| ClinicalTrials.gov API v2 | registry records, posted results, protocol PDFs | US NLM; generally public domain. Sponsor documents cited, not redistributed |
| Europe PMC REST API | search, open-access full text, supplements | per-article licence, recorded on every source in the ledger (e.g. CC BY 4.0) |
| Abstracts (non-OA) | facts with citation | publisher copyright; quoted briefly for verification only |
| JulesCan/clinicaltrial-protocol-corpus (Hugging Face) | optional bulk protocol text | CC0-1.0, 49,002 protocols |
| `data/calibration_synthetic.csv` | demo calibration | generated by `unblind/synthetic.py`; labelled SYNTHETIC everywhere |

**No patient-level data, ever.** Fetched texts are cached locally (`.cache/`, git-ignored) and are not redistributed.

## Risks and safeguards

| Risk | Mitigation |
|---|---|
| A confidently wrong extraction gives a confidently wrong correction | Verbatim quote audit. Unsupported claims become unknown. Imputed values are labelled and widen the interval |
| An LLM reads a dramatic result and shades the design facts | Results firewall on the Design extractor |
| Prompt injection inside a fetched PDF or paper | Documents are passed as delimited data, the output must match a JSON schema, enums are checked in code, every claim is quote-checked, and injection phrasing is flagged in the report |
| An agent is steered to fetch arbitrary URLs | Host allowlist in `unblind/net.py` |
| Reverse causation and confounding | Stated on every report. The output is a bound with an interval, not a verdict. The synthetic evaluation shows the failure size |
| Garbage or out-of-domain input | Never crashes (tested). Out-of-domain trials get a loud warning |
| Bad rows poisoning the calibration | Only rows a named reviewer approves enter `data/calibration_real.csv`. Fixtures and out-of-domain trials are refused |
| Output treated as a regulatory answer | Every report is "AWAITING HUMAN SIGN-OFF" until a named person approves. Decisions are logged with a report fingerprint |

## Who it is for

A clinical development lead writing a Phase 2b or 3 psychedelic protocol, before the design is locked. Next step: run it on a sponsor's draft protocol, and produce a blinding section for an FDA meeting package aligned with the July 2026 guidance *Psychedelic Drugs: Considerations for Clinical Investigations*.

## Limitations

- **Reverse causation.** Improvement can cause correct guessing, so the correction can remove real effect.
- **Cross-trial confounding.** Drug, dose, population and era all differ between trials.
- **A low-dose comparator is also pharmacology.**
- **Few dots near zero unblinding.** Non-hallucinogenic compounds sit exactly where data are sparsest.
- **It estimates contamination, not efficacy.** It cannot predict what a trial will show.
- **Live APIs have not been exercised from the build sandbox,** whose network blocks them. All network branches are covered by offline fixtures. Run on a normal connection before the demo.

## Building the real corpus

```bash
python -m unblind build-corpus data/psychedelic_trials.txt   # 17 real trial IDs from the candidate gold set
streamlit run app/app.py   # sidebar: load each reports/NCT*.json, review, approve "add to calibration corpus"
```

Once at least 6 approved trials have observed blinding, the app switches from the synthetic calibration to the real one automatically.

## Repo map

```
unblind/   agents.py  audit.py  ledger.py  llm.py  model.py  net.py  pipeline.py  rules.py  signoff.py  sources.py  synthetic.py
app/       app.py (Streamlit demo)
eval/      synthetic_recovery.py  extraction_eval.py  baseline_vs_pipeline.py  results/
data/      priors.json (assumptions)  calibration_synthetic.csv  gold_candidates.csv (unverified)  psychedelic_trials.txt
tests/     offline fixtures (invented trials) and tests
```
