# v6: one sequential agent with memory and validation error analysis

Documented: 2026-11-13. Status: finished. Result: best test accuracy so far (77.34%), but
validation accuracy is inflated and the committee gains much less than the individual programs.

## 1. Question and motivation
- [v3](v3_independent_agents.md) to [v5](v5_hybrid_redundancy_filter.md) all used independent
  agents. The programs were near-copies of one word-overlap judge, and a behaviour filter (v5)
  could not make them different.
- v2 used one agent with memory, but it had no feedback on its mistakes and a skewed example set.

Question (from the user): if a single agent builds the programs one after another, remembers
what it built, runs each program on the validation set, and does the error analysis itself
before building the next one, do the programs get better, and does the committee improve?

User instruction: no independent agents; one agent produces the programs sequentially; after
each program, run the validation set on it, have the agent do the error analysis only (no
revision of the program), then move on. Keep the rest as in v4: 20 rubrics, 25 random examples
per program, similarity filter on code text only.

## 2. What changed (vs v4)

| Setting | v4 | v6 |
|---|---|---|
| Agents | 80 independent | **1 agent, sequential, with memory** |
| Model | Opus | **Sonnet** (the user's choice) |
| Feedback | none | **validation report after every accepted program** |
| Memory | none | agent's own context plus `notes.md` on disk, and it may reread its programs |
| Order | parallel | strictly slot 1 to 80, enforced by the harness |
| Rubrics, variants, 25-example draws, prompts | | identical to v4 (prompt files copied and checked with `diff`) |
| Similarity filter | code text 0.60 | code text 0.60 only (no hybrid filter) |
| Accepted programs | | frozen, never revised |

Decisions the user made when asked: the agent sees accuracy and the misclassified rows from the
full validation set (not a half), runs as one subagent with a notes file (not a chain, not the
main session), and uses Sonnet.

## 3. How it was run
- **Harness:** `substitutability/synth_v6_tool.py`.
  - `init`: copies the v4 prompts and few-shot log, creates `manifest.json` and `notes.md`.
  - `status`: prints the next action (build slot N, or write the note for slot N) and the notes path.
  - `submit <pid> <file>`: slots must come in order and the previous accepted slot must have its
    note. It runs `validate_code` and the 0.60 code-similarity check, with up to 5 attempts and a
    placeholder after that. On acceptance it runs the program on all 380 validation rows
    (own min-max normalisation, tuned threshold as in PAJAMA) and prints a report.
  - `note <pid> <file>`: appends the lesson to `notes.md`. Notes under 80 characters are refused.
- **The report:** accuracy, threshold, yes-rate, counts of false yes and false no, and a random
  sample of 15 mistakes of each kind (seeded `1000+pid`). The full list of every mistake is
  written to `programs_synth_v6/_reports/p{pid}_val.txt`. Only ingredient, USDA entry, label and
  score are shown, never tier or pair-type codes.
- **The agent:** one background `general-purpose` subagent on Sonnet, started once with
  instructions for the loop above. Rules: read only its own slot prompt, `notes.md`, its own
  programs and reports. Do not read other program folders, data, test data or docs. Do not run
  its program on data or self-test before submitting. Write general rules and do not hard-code or
  memorise specific validation rows. If its context is compacted, run `status` and reread the
  notes.
- **Smoke test before the run:** out-of-order submit refused, report format checked, the next
  submit refused until a note existed. The test state was wiped before the real run.
- **Run:** 169 tool calls, about 633k tokens, about 55 minutes. Final state: 80 of 80 slots
  accepted, 0 failed, 85 of 300 attempts used. Slots 22, 47, 48, 67 and 79 each needed a second
  attempt after a "TOO SIMILAR" rejection. These are the first TOO SIMILAR rejections of any run,
  because one agent with memory sometimes writes code close to its own earlier programs.
- **Baseline:** `run.py --judges programs_synth_v6 ...` into `outputs/paper_baseline_synth_v6/`.

## 4. Results

### Committee
Top-k chose k = 5 with validation agreement **0.8868**. Selected: 69, 72, 75, 68, 58.

| | Generated test (3,799) | Real (943) |
|---|---|---|
| Accuracy | **77.34%** | **82.40%** |
| Precision / recall | 0.793 / 0.700 | 0.882 / 0.869 |

### k sweep (validation order)

| k | Validation agreement | Test | Real |
|---|---|---|---|
| 1 | 87.4% | 75.9% | 83.5% |
| 3 | 87.9% | 76.8% | 82.9% |
| **5 (chosen)** | **88.7%** | 77.3% | 82.4% |
| 6 | 88.4% | 77.4% | 84.1% |
| 9 | 87.4% | 77.4% | 84.4% |
| 12 | 87.1% | 77.3% | 84.2% |
| 20 | 86.6% | 77.6% | 84.1% |
| 25 | 86.6% | 77.8% | 84.1% |
| 40 | 85.5% | 77.4% | 84.1% |
| 60 | 83.4% | 76.3% | 83.6% |
| 80 | 81.1% | 75.4% | 82.5% |

- Any k from 3 to 40 gives 76.8 to 77.8% on test, so the committee is flat.
- The 6 best programs picked by test accuracy (unavailable to PAJAMA) give 77.7%, essentially the
  chosen committee. The best program of each rubric (20 programs) gives 76.9% test and 83.6% real.
- Real accuracy is 82.7 to 84.4% for k from 1 to 40, mostly above the 82.4% PAJAMA chose. The real set is small
  (standard error about 1.3), so I do not treat that as a finding.

### Single programs (test)
Minimum 64.7%, median **74.1%**, maximum 77.8% (program 55). 66 of 80 programs are at 70% or
more and 28 at 75% or more. Top by test accuracy (validation accuracy in brackets): 55 77.8
(83.9), 68 77.5 (86.1), 50 77.5 (84.5), 51 77.3 (83.2), 58 77.3 (85.8), 67 77.2 (84.5), 63 76.9
(84.5), 56 76.8 (82.6). 61 of the 66 programs at 70% or more were not selected. The lowest
selected program is 75.9% and the highest dropped one is 77.8%.

### Validation versus test, by slot
The agent saw validation mistakes after every program, so its validation accuracy overstates
what it would score on unseen data, and more so later in the run.

| Slots | Programs | Validation | Test | Gap | Best test |
|---|---|---|---|---|---|
| 1 to 20 | 20 | 70.0% | 70.6% | -0.5 | 76.1% |
| 21 to 34 | 14 | 72.0% | 70.7% | +1.3 | 74.7% |
| 35 to 48 | 14 | 77.3% | 73.3% | +4.0 | 75.4% |
| 49 to 64 | 16 | 82.6% | 76.3% | +6.3 | 77.8% |
| 65 to 80 | 16 | 84.0% | 75.7% | +8.2 | 77.5% |
| All | 80 | 77.0% | 73.2% | +3.7 | |

Correlation between validation and test accuracy across programs is 0.88. Test accuracy still
rose from 70.6% in the first block to 76.3% in the middle of the run, so the programs learned
something real, not only the validation rows.

## 5. Comparison
vs v4: **+2.5 points on test** (about 3.5 standard errors, single run), **no change on real**
(82.40% in both). Median single program up from 67.5% to 74.1%. Best single program up from
74.7% to 77.8%. See [README.md](README.md).

## 6. Error analysis
- **Committee errors 861** (326 false yes, 535 false no), the fewest of any version. v4 had 955.
  The error mix moved toward false no.
- **Tier accuracy:** easy 0.897, medium 0.853, edge 0.754, hard **0.555** (v4: 0.530).
- **The gain is on variant and qualifier pairs, not synonyms:**

| Pair type | v4 | v6 |
|---|---|---|
| B8 specific non-default variant (210 rows) | 0.60 (85 errors) | **0.69 (66)** |
| B5 (194) | 0.78 (42) | **0.90 (20)** |
| B6 (216) | 0.77 (49) | **0.89 (24)** |
| B3 (195) | 0.73 (53) | 0.83 (33) |
| G6 synonyms and renamed foods (438) | 0.29 (309) | 0.33 (294) |

  Synonyms stay at about a third. Most of the remaining test errors are G6.
- **Programs became more alike, which limits the committee.** Test set, all 80 programs:

| | v4 | v6 |
|---|---|---|
| Same answer | 74.9% | **84.6%** |
| Kappa | 0.49 | 0.67 |
| Error overlap (Jaccard) | 0.450 | **0.564** |
| When one is wrong, the other is too | 62% | 72% |
| Same rubric / different rubric (agreement) | 79.1% / 74.8% | 89.3% / 84.4% |
| Selected committee agreement | 80.5% | 93.9% (Jaccard 0.77, shared mistakes 87%) |
| Rows where all programs agree | 11.2% | 31.2% (1,186 rows) |
| Rows where at least 90% agree | 38.5% | 66.1% |
| Rows wrong for at least 80% of programs | 457 | 581 (15.3%) |
| Rows wrong for every program | 71 | 205 |

  On validation the figures are similar (agreement 82.2%, error overlap 0.454, selected 94.6%).
  The agent drew the same lessons for each program, so programs improved together and the
  committee has little to gain over its best member (77.3% against 77.8% for the best program).
- **Still overlap-driven:** 80 of 80 programs track word overlap more than the label, but
  correlation with the label rose to a median of 0.41 (0.33 in v3) and overlap fell to 0.595.
- **What the agent reported learning (its final summary):**
  - Identity and category are not the discriminating signal. The hard negatives are mostly the
    same food in a different state, a different part or cut, an unstated qualifier (low sodium,
    lowfat, "with oats"), or a brand or dish form.
  - The big gains came from asymmetric penalty tables for qualifiers the USDA entry adds,
    symmetric method and state compatibility tables, and stripping ALL-CAPS brand tokens (but
    not NFS or NS) and cut or part words out of the identity core.
  - Combiners mattered as much as features. Geometric, harmonic and soft-min combinations of
    aspect "experts" beat plain additive sums, because one strong objection should veto.
    Positive bonuses such as "intact compound", "same category" or "same role" backfired.
  - Bugs it hit repeatedly: "butter" or "sugar" excluded from the identity core by a flavour or
    stem list, asymmetric lookup keys in the method-cost table (slot 65), phrase merging that
    broke comma-reversed USDA names, parenthetical alias rescue applied to non-head words, and
    ties from multiplicative or discrete-tier designs.
  - Validation accuracy rose from about 0.62 to 0.70 in the first dozen slots to 0.82 to 0.87
    from slot 49 on. Best: slots 69 and 72 at 0.874, slot 68 at 0.861, slot 58 at 0.858. The
    weakest late slots (73, 76, 77, 80, 0.79 to 0.82) were the pure summed-cost, token-overlap and
    F-measure designs.
- **Rows nearly every strong program gets wrong** (the agent suspects label noise or idioms):
  stew meat vs "Stew, beef", frozen sirloin tip vs tri-tip, bison vs "Buffalo ... (Shoshone
  Bannock)", "half and half" vs a pork shank "half", sage vs "Sage Valley ... Cookies".

## 7. Validity and caveats
- **The agent fitted validation.** It said that from slot 35 onward some alias and idiom rules
  were prompted by validation error reports (shungiku, sufu, jamun, the stew-meat idiom, the lean
  ground turkey and variety-conflict rules), despite the instruction to write general rules. It
  also added broader general knowledge later (regional names, cultivar to base, part and cut
  taxonomy). Its own view is that late validation accuracies of 0.84 to 0.87 are somewhat
  optimistic. The table in section 4 shows the gap growing to 8 points.
- **Consequence:** PAJAMA's validation agreement (0.887), per-program thresholds and top-k choice
  are less reliable for v6 than for earlier versions. Test and real are the honest numbers.
- **Test data was never touched by the agent.** Validation and test are split by core food, so
  specific aliases learned from validation rows do not appear in test rows.
- **Not a like-for-like replication of the paper.** v6 learns from the labels of most of the
  380 validation rows through error analysis, where the paper uses 10 examples per program. The
  gain comes from extra supervision, not only from sequential memory.
- **Confounded with the model.** v4 used Opus and v6 uses Sonnet. v5 suggests Sonnet's first
  drafts are about as good as Opus's, but v6 is not an isolated test of memory or of feedback.
- **Real accuracy did not improve.** The test gain may partly reflect patterns specific to the
  synthetic generator, such as qualifier phrasing. This is not tested.
- Single run. Label noise (336 rows where Haiku and the generator disagree) applies as in
  earlier versions.
- Error analysis by tier and pair type was added after the run (`committee_compare.py`).

## 8. Conclusions and what it motivated
- Sequential memory plus validation feedback makes each program much better (median +6.6 points)
  but also makes them alike, so the committee improves by only 2.5 points. In v3 to v5 the
  opposite held: variety without quality, then neither.
- The synonym pairs (G6) are not fixed by feedback, since string-only programs cannot know that
  palmito is hearts of palm.
- Next experiments suggested by the results, none run yet: complementary committee selection on
  the pooled programs of v3 to v6; a repeat with half of validation hidden from the agent to get
  an honest validation score; a shared alias table for the G6 pairs; routing the rows where the
  programs agree and are wrong to the LLM judge.

## 9. Files and reproduction
- Programs: `substitutability/programs_synth_v6/` (`judge_1..80.py`, `manifest.json`,
  `attempts.json`, `notes.md` with the agent's 80 lessons, `_reports/` with every validation
  report, `_prompts/`). Harness: `synth_v6_tool.py`.
- Output: `outputs/paper_baseline_synth_v6/`.
- Scripts in `analysis_programs/`: `deep_v6.py`, `agreement_v6.py`, `dropped_v6.py`,
  `committee_compare.py`. Outputs in `analysis_programs/out_v6/`.
- Reproduce: `synth_v6_tool.py init`, start one Sonnet subagent with the instructions in section
  3 (the loop, the read and write rules, the report and note commands), wait for `status` to
  print "ALL 80 SLOTS ARE FINAL", then run the baseline command in [../README.md](../README.md).
  The agent's own output will differ between runs.
