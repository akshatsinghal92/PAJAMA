# Docs

Documentation for the PAJAMA substitutability work (ingredient to USDA entry, judged by
synthesized programmatic judges).

- [experiments/README.md](experiments/README.md): index of every experiment and the master
  comparison table. Start here.
- One file per experiment in [experiments/](experiments/), named `<id>_<short_name>.md`.

## Standing rule

Every experiment is written up here as part of finishing it, in the same session as the
results. Nothing is left only in a chat transcript. Each write-up uses the template below, and
the index and master comparison in `experiments/README.md` are updated at the same time.

## Template for an experiment doc

```
# <id>: <short name>

Documented: <date>. Status: <finished / in progress>.

## 1. Question and motivation
What we wanted to find out and why. Link the earlier analysis or result that motivated it.

## 2. What changed
Table of every setting, with the previous version's value next to it. State what stayed the same.

## 3. How it was run
Commands, harness, seeds, models, workflow or run ids, interruptions and how they were handled,
and anything done by hand. Enough that someone else could repeat it.

## 4. Results
Headline accuracy (generated test and real), the committee PAJAMA selected, single-program
accuracy distribution, k sweep, synthesis outcomes (accepted, failed, attempts).

## 5. Comparison with earlier versions
Side-by-side table against the previous experiments, plus how large a difference counts as real.

## 6. Error analysis
By difficulty tier and pair type, false yes vs false no, agreement and error overlap between
programs, what the committee gets wrong and why.

## 7. Validity and caveats
Leakage, optimism, confounded changes, label noise, single-run noise, anything not measured.

## 8. Conclusions and what it motivated
What we learned, and which next experiment this points to.

## 9. Files and reproduction
Programs, outputs, scripts, logs, and the exact commands to reproduce.
```

## Shared setup (used by every experiment unless the doc says otherwise)

### Data
All under `substitutability/data_synth_v2/`.

| Item | Path | Size | Notes |
|---|---|---|---|
| Validation | `pajama_paper/val.jsonl` | 380 rows | 9.09% of the pool, the paper's proportion (500 of 5,500) |
| Generated test | `pajama_paper/test.jsonl` | 3,799 rows | 46.9% substitutable. Majority-class accuracy 53.1% |
| Real set | `pajama/real_external.jsonl` | 943 rows | 71.2% substitutable. Majority-class accuracy 71.2% |
| Few-shot pool (v2 only) | `pajama_paper/fewshot.jsonl` | 10 rows | seed 42, 1 yes and 9 no |

- Rows are ingredient text to USDA description pairs with a label. Built by `prep_synth_v2.py`
  and `prep_paper_split.py`, which groups rows by core food so contrast pairs never sit on both
  sides of the split.
- `label` is the Haiku v3 judgment that every accuracy is measured against. `label_intended` is
  the data generator's intended label. They disagree on 336 of the 3,799 test rows.
- Test rows also carry `tier` (easy, medium, edge, hard) and `relation_code` (pair type, for
  example G6 synonym or renamed food, B8 specific non-default variant). These are used only
  for analysis, never shown to program writers.

### PAJAMA pipeline (`pipeline.py`, run with `run.py`)
1. Score every row with every program.
2. Normalise each program's scores to [0, 1] (robust min-max on the 1st and 99th percentile of
   the validation scores).
3. Tune a per-program decision threshold on validation (grid 0.10 to 0.90, step 0.05).
4. Drop programs under 50% validation accuracy.
5. Rank the rest by validation accuracy and sweep top-k. Fit a Snorkel LabelModel for each k
   and keep the k with the best validation agreement.
6. Aggregate the selected programs with the Snorkel LabelModel. Report accuracy, precision and
   recall on the generated test set and the real set.

Command used for every baseline run, from `substitutability/`:

```
PYTHONPATH=. ../.venv/bin/python run.py \
  --judges programs_synth_vN \
  --val data_synth_v2/pajama_paper/val.jsonl \
  --test data_synth_v2/pajama_paper/test.jsonl \
  --extra-test real=data_synth_v2/pajama/real_external.jsonl \
  --output outputs/paper_baseline_synth_vN
```

### Program synthesis (`generate_programs.py` and the per-version harnesses)
- **Prompt:** `build_prompt(heuristic, few_shot_text, variant_index, existing_approaches)`.
  Food-informatics role, definition of SUBSTITUTABLE, input shape, one rubric to focus on,
  diversity and failure-avoidance blocks, labelled examples, ten requirements, signature
  `judging_function(ingredient, usda_match)`. No heavy NLP libraries.
- **Validation of a submitted program (`validate_code`):** it must define the function, return
  numbers, not be constant, and score a clear match above a clear non-match on fixed cases
  (olive oil vs olive oil and vs guava paste, ginger, garlic paste vs garlic sauce, red bell
  pepper). Programs that fail this ("directional sanity") are the most common rejection.
- **Code similarity filter (`too_similar`):** `difflib.SequenceMatcher` ratio on the code with
  comments removed, rejected above 0.60. This is the paper's rule, adapted from ROUGE-L.
- **Retry limits:** 5 attempts per slot, then an always-0 placeholder. 300 attempts overall.
- **Rubrics:** `heuristics.py` holds the original 10, which are "the pointwise-binary analog of
  PAJAMA's 10 pairwise rubrics". `heuristics_20.py` adds 10 more (see v4).

### Paper facts that matter here
- Programs come from independent API calls to Opus 4.6. Each prompt has one rubric and the
  same 10 random validation examples (upstream code samples once with seed 42).
- A text-similarity filter of 0.60 removes near-duplicates.
- Paper committees use 8 to 21 of 80 programs, on average 14.8.
- The paper never justifies the choice of 10 rubrics. They are "starting guidance".

### Conventions for reading results
- Test set is 3,799 rows, so one standard error is about 0.7 points. The real set is 943 rows,
  about 1.3 points. Differences under about 1 point on test are noise.
- Every number comes from a single run unless stated.
- "Selected" means chosen by PAJAMA's top-k sweep on validation.
