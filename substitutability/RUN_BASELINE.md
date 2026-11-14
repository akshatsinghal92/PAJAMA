# Running the PAJAMA baseline on data_synth_v2

This follows the paper's setup (§3.3, §4.1, App. C), adapted to pointwise yes/no labels:
synthesize 80 programs from 10 rubrics × 8 variants with 10 few-shot examples, tune a
per-program threshold on a labeled validation set, drop programs below 50% validation
accuracy, keep the top-k, aggregate with a Snorkel LabelModel, and report test accuracy with
abstentions filled at random.

## What is already set up

| Item | Where |
|---|---|
| Python env (numpy 2.2.6, snorkel 0.9.9, scikit-learn 1.7.2, anthropic 0.92.0, torch) | `PAJAMA/.venv` (git-ignored) |
| Splits with Haiku v3 labels as `label` (generator label kept as `label_intended`) | `data_synth_v2/pajama/` |
| Split builder | `prep_synth_v2.py` |
| Runner with several test sets and paper-style accuracy | `run.py` |
| Synthesis script with `--out-dir`, `--model`, and an overwrite guard | `generate_programs.py` |

### How the splits map to the paper

| File | Rows | Yes % | Role |
|---|---|---|---|
| `fewshot.jsonl` | 58 | 46.6 | Few-shot examples for program synthesis (10 drawn, balanced) |
| `fit.jsonl` | 1,456 | 46.9 | Validation set: threshold tuning, filtering, top-k, Snorkel |
| `router.jsonl` | 1,041 | 46.2 | Held out for the routing stage; not used by the baseline |
| `test.jsonl` | 1,624 | 47.5 | Synthetic test set |
| `real_external.jsonl` | 943 (595 distinct pairs) | 71.2 | Real labeled data (`data/val` + `data/test`), external test |
| `robustness.jsonl` | 163 | – | Perturbation variants, optional |

No food or ingredient line crosses synthetic splits, and no synthetic pair appears in the
real data.

## Steps

All commands run from `PAJAMA/substitutability/`.

```bash
cd /Users/akshat/Documents/PAJAMA/substitutability
PY=../.venv/bin/python

# 0. (Already done; rerun only if labels change.)
$PY prep_synth_v2.py
```

### Baseline A: existing 80 programs (no API cost)

These programs were synthesized earlier from real-data few-shot examples. The real `val`
split seeded them, so the real numbers below are slightly optimistic.

```bash
$PY run.py --judges programs \
  --val  data_synth_v2/pajama/fit.jsonl \
  --test data_synth_v2/pajama/test.jsonl \
  --extra-test real=data_synth_v2/pajama/real_external.jsonl \
  --output outputs/synth_v2_programsA
```

### Baseline B: paper-faithful, programs synthesized from the synthetic few-shot split

1. Synthesize 80 programs into a new folder. This calls the Anthropic API.

```bash
export ANTHROPIC_API_KEY=...        # set in your shell only, never in a file
$PY generate_programs.py \
  --val data_synth_v2/pajama/fewshot.jsonl \
  --out-dir programs_synth_v2 \
  --model claude-opus-4-6
```

   - `claude-opus-4-6` is the synthesizer the paper used. The paper reports about $7 for
     80 programs; expect a similar figure here (prompts are about 1k tokens, programs about
     1.5–2k tokens, roughly 80–120 calls with retries). A cheaper model works through
     `--model`, but the paper's ablation (Table 8) shows weaker synthesizers lose 6–8 points.
   - Check that the model id is still served before running.
   - The run resumes from `programs_synth_v2/manifest.json` if it stops part-way.

2. Fit and evaluate:

```bash
$PY run.py --judges programs_synth_v2 \
  --val  data_synth_v2/pajama/fit.jsonl \
  --test data_synth_v2/pajama/test.jsonl \
  --extra-test real=data_synth_v2/pajama/real_external.jsonl \
              robustness=data_synth_v2/pajama/robustness.jsonl \
  --output outputs/synth_v2_programsB
```

### Optional: tune on real data instead

To measure performance on real pairs with thresholds fitted to the real 71% yes-share
(see the prior-shift discussion in `DATA_AUDIT_REPORT.md`):

```bash
$PY run.py --judges programs_synth_v2 \
  --val data/val.jsonl --test data/test.jsonl \
  --output outputs/synth_v2_programsB_realfit
```

## Outputs

Each `--output` folder gets:

- `evaluation_metrics.json`: fit summary (surviving programs, best k, selected programs
  and thresholds), and per test set the covered metrics, `accuracy_full`, abstention count
  and majority baseline.
- `predictions_<name>.jsonl`: one row per pair with `label`, `pred`, `prob_substitutable`,
  plus `tier` and `relation_code` for slicing.

## Reading the numbers

- `accuracy_full` matches the paper's headline metric (random label where all programs
  abstain). `accuracy` is over covered rows only.
- Compare against `majority_baseline` for each set: about 52.5% on synthetic test and 71.2%
  on the real set.
- The validation set here is 1,456 rows against the paper's 500. The paper's Table 10 shows
  results are flat in validation size, so this is fine.
- Pointwise difference from the paper: programs score one pair, not two responses, so the
  per-program threshold is a decision point on the normalized score (grid 0.10–0.90),
  not an abstention band around zero. `--band` adds an abstention margin if wanted.
