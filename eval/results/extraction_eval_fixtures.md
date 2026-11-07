# Extraction accuracy: agent pipeline vs hand-verified gold

**FIXTURE RUN. Both trials are INVENTED test fixtures (tests/fixtures.py). This checks that the evaluation runs end to end and that the scorer behaves; it says nothing about accuracy on real papers.** Offline mode, no Gemini, so these are the deterministic rule extractors.

Gold file: `eval/results/fixture_gold.csv`, 16 verified cells over 2 trial(s).
Numeric fields match within ±0.02 (proportions) or ±0.05 (effects, in the units reported by the source);
categorical fields must match exactly. `NR` in the gold means not reported, so the right answer is to abstain.

| field | n | accuracy (95% Wilson) | coverage | precision | recall | wrong | answered when NR | unknowns | of which gold had a value (miss) | audit pass (n audited) |
|---|---|---|---|---|---|---|---|---|---|---|
| effect_est | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| effect_lo | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| effect_hi | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| comparator_type | 2 | 100% (34% to 100%) | 100% | 100% | 100% | 0 | 0 | 0 | n/a | 100% (2) |
| rater_placement | 2 | 100% (34% to 100%) | 100% | 100% | 100% | 0 | 0 | 0 | n/a | 100% (2) |
| guess_acc_participants | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| guess_acc_raters | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| prior_exposure | 2 | 100% (34% to 100%) | 50% | 100% | 100% | 0 | 0 | 1 | 0% | 100% (1) |
| **ALL FIELDS** | 16 | 100% (81% to 100%) | 62% | 100% | 100% | 0 | 0 | 6 | 0% | 100% (10) |

How to read it
* **accuracy** counts a correct value or a correct abstention. The Wilson interval is wide because n is small.
* **coverage** is the share of cells where the agent gave a value instead of `unknown`.
* **answered when NR** is the dangerous error: a value where a careful human found none.
* **of which gold had a value (miss)**: of the agent's `unknown` answers, the share that were misses rather than
  honest abstentions.
* **audit pass** is the share of quote-audited facts that passed the verbatim check (audit.py). Facts derived in
  code without a quote are not audited.

## Cell by cell

| nct | field | gold | agent | outcome | audit |
|---|---|---|---|---|---|
| NCT99999901 | effect_est | -6.2 | -6.2 | correct | pass |
| NCT99999901 | effect_lo | -9.4 | -9.4 | correct | pass |
| NCT99999901 | effect_hi | -3.0 | -3.0 | correct | pass |
| NCT99999901 | comparator_type | low_dose_same_drug | low_dose_same_drug | correct | pass |
| NCT99999901 | rater_placement | central_remote | central_remote | correct | pass |
| NCT99999901 | guess_acc_participants | 0.78 | 0.78 | correct | pass |
| NCT99999901 | guess_acc_raters | 0.55 | 0.55 | correct | pass |
| NCT99999901 | prior_exposure | 0.34 | 0.34 | correct | pass |
| NCT99999902 | effect_est | NR | unknown | correct_abstain |  |
| NCT99999902 | effect_lo | NR | unknown | correct_abstain |  |
| NCT99999902 | effect_hi | NR | unknown | correct_abstain |  |
| NCT99999902 | comparator_type | inert_placebo | inert_placebo | correct | pass |
| NCT99999902 | rater_placement | blinded_unspecified | blinded_unspecified | correct | pass |
| NCT99999902 | guess_acc_participants | NR | unknown | correct_abstain |  |
| NCT99999902 | guess_acc_raters | NR | unknown | correct_abstain |  |
| NCT99999902 | prior_exposure | NR | unknown | correct_abstain |  |

