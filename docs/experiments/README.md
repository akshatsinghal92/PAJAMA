# Experiments index and master comparison

Last updated: 2026-11-13. Add a row here and update the comparison tables whenever a new
experiment is documented. Shared setup and the doc template are in [../README.md](../README.md).

## Index

| Id | Doc | What it tested | Test acc | Real acc |
|---|---|---|---|---|
| v2 | [v2_single_agent_baseline.md](v2_single_agent_baseline.md) | One agent writes 80 programs from the same 10 examples (1 yes, 9 no) | 72.76% | 74.55% |
| v3 | [v3_independent_agents.md](v3_independent_agents.md) | 80 independent agents, own random 10 examples, 10 rubrics | 74.15% | 81.55% |
| v4 | [v4_20_rubrics_25_examples.md](v4_20_rubrics_25_examples.md) | 20 rubrics and 25 examples per agent | **74.86%** | **82.40%** |
| v5 | [v5_hybrid_redundancy_filter.md](v5_hybrid_redundancy_filter.md) | v4 plus a code and error-overlap redundancy filter, Sonnet agents | 71.73% | 80.81% |
| v6 | [v6_sequential_agent_error_analysis.md](v6_sequential_agent_error_analysis.md) | One Sonnet agent, sequential, error analysis on validation after every program | **77.34%** | **82.40%** |

Test accuracy is on the 3,799 generated test rows and real accuracy is on the 943 real rows,
both against the Haiku v3 labels, using the committee PAJAMA selected on validation.
Majority-class accuracy is 53.1% on test and 71.2% on real.

## Master comparison

### Setup

| | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|
| Who writes programs | 1 agent, one conversation | 80 independent agents | 80 independent agents | 80 independent agents | 1 agent, sequential, with memory |
| Synthesis model | the session's own agent | Opus | Opus | **Sonnet** | **Sonnet** |
| Rubrics | 10 | 10 | 20 | 20 | 20 |
| Variants per rubric | 8 | 8 | 4 | 4 | 4 |
| Few-shot examples per program | 10, same for all (1 yes, 9 no) | 10, random per program | 25, random per program | 25, random per program | 25, random per program |
| Sees other programs | yes (avoid list) | no | no | no | yes (own context and notes) |
| Sees validation errors | no | no | no | no | **yes, after every program** |
| Redundancy filter | code text 0.60 | code text 0.60 | code text 0.60 | code text plus validation error overlap | code text 0.60 |
| Attempts used (of 300) | not recorded here | 108 | 105 | 157 | 85 |
| Always-0 placeholders | not recorded here | 2 | 2 | 0 (3 forced redundant) | 0 |

### Headline results

| | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|
| Selected k | 3 | 11 | 6 | 3 | 5 |
| Validation agreement (PAJAMA) | n/a | 0.721 | 0.750 | 0.711 | 0.887 (inflated) |
| **Test accuracy** | 72.76% | 74.15% | 74.86% | 71.73% | **77.34%** |
| Test precision / recall | n/a | 0.719 / 0.738 | 0.739 / 0.717 | 0.725 / 0.640 | 0.793 / 0.700 |
| **Real accuracy** | 74.55% | 81.55% | 82.40% | 80.81% | 82.40% |
| Real precision / recall | n/a | 0.836 / 0.921 | 0.830 / 0.946 | 0.858 / 0.875 | 0.882 / 0.869 |

### Single programs (test accuracy, each with its tuned threshold)

| | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|
| Worst program | 47.4% | 53.0% (placeholder) | 53.1% (placeholder) | 58.9% | 64.7% |
| Median | 59% | about 67% | 67.5% | 66.4% | **74.1%** |
| Best | 72.3% | 74.0% | 74.7% | 74.3% | **77.8%** |
| Programs at 70% or more | n/a | n/a | 23 | 11 | **66 of 80** |
| Programs following word overlap more than the label | 59 of 80 | 78 of 80 | 78 of 80 | 80 of 80 | 80 of 80 |

### Agreement between programs (generated test set, all pairs)

| | v3 | v4 | v5 | v6 |
|---|---|---|---|---|
| Two programs give the same answer | 74% | 74.9% | 76.1% | **84.6%** |
| Share of errors in common (Jaccard) | 0.45 | 0.450 | 0.485 | **0.564** |
| When one is wrong, the other is wrong too | n/a | 62% | 65% | 72% |
| Selected committee agreement | 79% | 80.5% | 84.0% | 93.9% |
| Rows wrong for at least 80% of programs | 442 (11.6%) | 457 (12.0%) | 549 (14.5%) | 581 (15.3%) |

v3 figures are for all 78 working programs. v4 excludes the two placeholders. v5 and v6 include
all 80 programs.

### Committee error breakdown (generated test set)

| | v3 | v4 | v5 | v6 |
|---|---|---|---|---|
| Errors | 982 | 955 | 1,074 | **861** |
| False yes / false no | 515 / 467 | 450 / 505 | 433 / 641 | 326 / 535 |
| Easy tier (1,198 rows) | 89.3% | 88.6% | 87.5% | 89.7% |
| Medium (1,213) | 81.7% | 81.3% | 75.8% | 85.3% |
| Edge (289) | 73.7% | 74.4% | 71.6% | 75.4% |
| Hard (1,099) | 49.4% | 53.0% | 50.1% | **55.5%** |

By pair type, committee accuracy with number of errors in brackets:

| Pair type | Rows | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|
| G6 synonym or renamed food | 438 | 0.33 (295) | 0.29 (309) | 0.21 (344) | 0.33 (294) |
| B8 specific non-default variant | 210 | 0.30 (147) | 0.60 (85) | 0.49 (108) | **0.69 (66)** |
| B9 | 206 | 0.74 (54) | 0.71 (60) | 0.78 (45) | 0.72 (58) |
| B6 | 216 | 0.76 (52) | 0.77 (49) | 0.84 (35) | **0.89 (24)** |
| E2 | 104 | 0.51 (51) | 0.59 (43) | 0.46 (56) | 0.58 (44) |
| B3 | 195 | 0.75 (49) | 0.73 (53) | 0.74 (50) | 0.83 (33) |
| G4 | 222 | 0.81 (43) | 0.82 (41) | 0.77 (50) | 0.82 (39) |
| B5 | 194 | 0.79 (41) | 0.78 (42) | 0.62 (73) | **0.90 (20)** |
| B10 | 82 | 0.57 (35) | 0.59 (34) | 0.76 (20) | 0.60 (33) |
| G3 | 173 | 0.80 (34) | 0.78 (38) | 0.71 (51) | 0.82 (32) |

493 test rows are wrong for the committees of all four versions v3 to v6. 593 of v6's 861 errors
are also v4 errors. Source: `substitutability/analysis_programs/committee_compare.py`.

## What the experiments show together

1. **v2 to v3:** switching from one agent with a shared, skewed example set to 80 independent
   agents with their own random examples removed the "flat default" failure (30 of 80 programs
   gave one fixed score) and raised real accuracy by 7 points. See v3.
2. **v3 to v4:** more rubrics and more examples added a little on test (0.7 points, within
   noise) and fixed qualifier-variant pairs (B8 from 30% to 60%). Synonyms did not move.
3. **v4 to v5:** a behaviour-based redundancy filter did not make programs more different, and
   with Sonnet the committee got worse. The code-text filter had never fired in v3 or v4.
4. **v4 to v6:** a single agent with memory and validation error analysis made each program
   much better (median 67.5% to 74.1%) and raised the committee by 2.5 points on test, but
   programs became more alike, so the committee gained far less than the programs did. Real
   accuracy did not move.
5. **Across all versions:** synonym and renamed-food pairs (G6) stay at 29 to 33% committee
   accuracy, and about 15% of test rows are wrong for at least 80% of programs. Programs that
   only compare strings cannot know that palmito is hearts of palm.
6. **Never beaten:** the best single program is 74 to 78% in every set, and committee accuracy
   stays within 2 points of the best single program.

## Open questions

- Does selecting a committee for complementary errors (not top-k by accuracy) beat top-k? Not
  yet tested on the pooled programs of v3 to v6.
- How much of v6's gain survives if the agent only sees half the validation set? Not tested.
- Would an alias and synonym table, shared by all programs, fix the G6 pairs? Not tested.
- Routing the rows where programs agree and are wrong to the LLM judge. Earlier routing work is
  in `substitutability/ROUTING_AND_ABSTENTION.md`.
