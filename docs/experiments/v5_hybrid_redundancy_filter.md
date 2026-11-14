# v5: hybrid redundancy filter (code text plus error overlap), Sonnet agents

Documented: 2026-11-13. Status: finished. Result: worse than v4.

## 1. Question and motivation
Two findings from [v4](v4_20_rubrics_25_examples.md):
- The paper's code-text similarity filter (0.60) never fired in v3 or v4. Independent agents
  write code that looks different even when it behaves the same: programs 1 to 4 share 79 to
  85% of their errors with code similarity of 0.08 to 0.26.
- Two programs' error overlap on the 380 validation rows correlates 0.93 with their error
  overlap on the 3,799 test rows, so validation can measure redundancy reliably.

Question (from the user): does a combined score of code similarity and behaviour (error
overlap with already accepted programs), used to reject and retry, produce programs different
enough to actually contribute? The user asked to use Sonnet agents and to keep everything else
as in v4: independent agents, 20 rubrics, 25 examples per agent.

## 2. What changed (vs v4)

| Setting | v4 | v5 |
|---|---|---|
| Synthesis model | Opus | **Sonnet** (workflow `model: 'sonnet'`, effort medium) |
| Redundancy filter | code text above 0.60 | **code text above 0.60 and a combined score** |
| Accuracy floor | none | **validation accuracy at least 0.55** |
| If all 5 attempts are redundant | placeholder | **least redundant attempt is accepted** (flagged `forced_redundant`) |
| Prompts, few-shot draws, rubrics | | identical (copied from v4, checked with `diff`) |

### The combined score
For a new program and each accepted program j:

```
redundancy_j = 0.3 * min(1, code_sim_j / 0.60) + 0.7 * err_jaccard_j
combined     = max over accepted j of redundancy_j
reject (REDUNDANT) if combined > TAU = 0.65
```

- `code_sim`: `difflib.SequenceMatcher` on code tokens (identifiers and punctuation,
  `autojunk=False`), not characters. This is fast on long code and more informative than the
  paper's character-level ratio.
- `err_jaccard`: overlap of the two programs' error sets on the 380 validation rows. Each program
  is scored with its own min-max normalisation and its own tuned threshold, as the PAJAMA
  pipeline would do. Abstentions (score exactly at the threshold) are not errors.
- The paper's character-level 0.60 rule is kept as a hard rule too.
- Only validation labels are used. Test data is not touched.
- Agents hear only a generic message: "REDUNDANT: this program behaves too much like programs
  already accepted for other slots (checked on a hidden check set). Write a substantively
  different approach, not just different code." No scores, no other programs.

### How TAU = 0.65 was chosen
`synth_v5_tool.py calibrate programs_synth_v4` replayed the 78 working v4 programs in slot order.

| TAU | v4 programs that would have been rejected |
|---|---|
| 0.50 | 71 of 78 |
| 0.55 | 57 |
| 0.60 | 31 |
| 0.62 | 28 |
| **0.65** | **20 (about 1 in 4)** |
| 0.70 | 11 (about 1 in 7) |

The replay flagged programs 2, 3, 4, 22, 23, 24, 46, 47 and similar near-copies. 0.65 was a
judgement call: strict enough to bite, loose enough that most slots pass. The replay overstates
real rejections, because a rejected program does not join the pool and its slot gets another try.

## 3. How it was run
- **Harness:** `synth_v5_tool.py` (commands `init`, `submit`, `status`, `calibrate`). `init`
  copies the v4 prompts and few-shot log. `submit` validates, then takes a file lock and compares
  the program with every accepted program. Each decision is logged to
  `programs_synth_v5/decisions.jsonl` and each accepted program's validation error vector to
  `val_errors.json`. Redundant drafts are kept in `_redundant/` as fallback candidates.
- **Smoke test:** three v4 programs were submitted for slots 1 to 3. The first was accepted and
  a near-copy was rejected as REDUNDANT (combined 0.84, error overlap 0.85). The test state was
  wiped before the real run.
- **Run:** workflow `wf_c64c6812-b88`, 80 independent Sonnet agents with the v4 isolation rules
  (read only your own prompt, no data, no testing). The retry message tells them to use a
  different algorithm, feature set and scoring formula for REDUNDANT or TOO SIMILAR.
- **Baseline:** `run.py --judges programs_synth_v5 ...` into `outputs/paper_baseline_synth_v5/`.

## 4. Results

### Synthesis
All 80 slots succeeded, using 157 of 300 attempts. Outcomes of the validated attempts: 77
accepted outright, 46 REDUNDANT, 30 failed the directional sanity check, 2 syntax errors, 1
constant output, 1 WEAK. Slots 23, 44 and 79 used the least-redundant fallback. Accepted
programs sit just under the cutoff (max combined: median 0.603, 90th percentile 0.645, maximum
0.678).

### Committee
Top-k chose k = 3 (validation agreement 0.7105): programs 49 (Unstated Added Qualifier), 5
(Preparation-State) and 16 (Nutritional Profile).

| | Generated test (3,799) | Real (943) |
|---|---|---|
| Accuracy | **71.73%** | **80.81%** |
| Precision / recall | 0.725 / 0.640 | 0.858 / 0.875 |

k sweep (test / real): k = 1 72.2 / 80.3, 3 71.7 / 80.8, 6 72.7 / 81.8, 8 73.2 / 81.6, 20 71.6 /
81.4, 40 71.5 / 78.6, 80 70.4 / 78.8. Best 6 by test accuracy: 72.76%. Best program from each
rubric (20): 70.91% test. Every k gives 70 to 73%.

### Single programs (test)
Minimum 58.9%, median 66.4%, maximum 74.3%. 11 programs are at 70% or more, 56 at 65% or more.
Mean accuracy by rubric: Unstated Qualifier 69.1, Preparation-State 69.0, Specificity 68.6,
Culinary 68.2, Brand 68.1, Lexical 68.0, Cooking Method 68.0, Detail Coverage 67.8, Modifier
67.3, Compound Name 66.5, Polarity 66.4, Core Identity 66.2, Nutritional 63.6, Head Food 63.8,
Anatomical 63.6, Food Category 61.8, Single vs Composite 64.9, Preservation 65.6, Processing
65.4, Synonym 65.2.

## 5. Comparison
vs v4: **-3.1 points on test, -1.6 on real.** The test difference is larger than the noise of
about 0.7. See [README.md](README.md).

## 6. Error analysis
- **The programs did not become more different.** Test set, all pairs:

| | v4 | v5 |
|---|---|---|
| Same answer | 74.9% | 76.1% |
| Kappa | 0.49 | 0.50 |
| Error overlap (Jaccard) | 0.450 | 0.485 |
| When one is wrong, the other is too | 62% | 65% |
| Selected committee agreement | 80.5% | 84.0% |
| Rows where at least 90% of programs agree | 38.5% | 45.1% |
| Rows wrong for at least 80% of programs | 457 | 549 |
| Rows wrong for all programs | 71 | 86 |
| Rows wrong for every selected program | 355 | 607 |

  80 of 80 programs follow word overlap more than the label (median correlation 0.655 with
  overlap, 0.33 with the label).
- **Why the filter did not help:** it caps how similar a program can be to its single nearest
  neighbour, so it only trims the tail. The typical pair stays far below the cutoff, and the
  typical pair is what carries the shared word-overlap bias.
- **Committee errors 1,074** (433 false yes, 641 false no). Accuracy by tier: easy 0.875, medium
  0.758, edge 0.716, hard 0.501. By type: G6 0.21 (344 errors), B8 0.49 (108), B5 0.62 (73),
  G8 0.63 (46), B7 0.70 (51). Fewer false yes than v4 but many more false no (641 vs 505).
- **Model effect versus filter effect.** The model changed along with the filter, so I
  checked first drafts (before any filter feedback): mean validation accuracy 0.650 against
  0.655 for the v4 programs. Sonnet's first drafts are about as good as Opus's. Programs rejected
  as REDUNDANT had validation accuracy 0.651 against 0.648 for accepted ones, so the filter did
  not throw out the good programs. In the 33 slots that retried after a validated attempt,
  validation accuracy went from 0.652 on the first attempt to 0.642 on the last, so retries did
  not produce better programs either.

## 7. Validity and caveats
- Model and filter changed together. The first-draft comparison suggests the model is not the
  main cause, but it cannot prove it. The 3-point gap could also include run-to-run variation,
  which a single run per setup cannot measure.
- Same rubric text as v4, so v5 carries the same possible test optimism (rubrics 11 to 20 were
  written after test-based analysis). That favours v5 as well, so it does not explain the
  worse result.
- Agreement figures in an early pass of the analysis wrongly excluded slots 8 and 61, which were
  v4 placeholders but real programs in v5. The numbers above include all 80 programs.
- The fallback means 3 slots hold programs the filter considered too redundant.
- The filter result depends on TAU and on the weights, which were chosen once.

## 8. Conclusions and what it motivated
A behaviour filter can keep near-copies apart, but a filter cannot create knowledge the programs
lack (for example that palmito is hearts of palm). Retries after "REDUNDANT" did not find a
different, accurate approach. This supports giving agents something new instead of only
rejecting them. That motivated **v6**: give the agent memory and feedback on its own errors.

## 9. Files and reproduction
- Programs: `substitutability/programs_synth_v5/` (also `decisions.jsonl`, `val_errors.json`,
  `redundant_candidates.json`, `_redundant/`, `_prompts/`). Harness: `synth_v5_tool.py`.
- Output: `outputs/paper_baseline_synth_v5/`.
- Scripts in `analysis_programs/`: `deep_v5.py`, `agreement_v5.py`, `dropped_v5.py`, and
  `replay_filter_v4.py` for the calibration. Outputs in `analysis_programs/out_v5/`.
- Reproduce: `synth_v5_tool.py init`, 80 Sonnet agents calling `synth_v5_tool.py submit <pid>
  <file>`, then the baseline command in [../README.md](../README.md).
