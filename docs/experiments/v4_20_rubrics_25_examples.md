# v4: 20 rubrics and 25 random examples per independent agent

Documented: 2026-11-13. Status: finished.

## 1. Question and motivation
The [v3 analysis](v3_independent_agents.md) found that:
- almost every program was a word-overlap matcher, with errors concentrated on synonyms (G6,
  committee accuracy 33%) and look-alike variants (B8, 30%);
- the weakest rubrics were Food Category and Nutritional Profile;
- the paper never justifies using 10 rubrics (it calls them "starting guidance", and its
  appendix A.2 builds rubrics by brainstorming expressible dimensions and mining judge
  rationales on validation). Our 10 rubrics were hand-written by the project author.

Question: do 20 rubrics and 25 examples per program (instead of 10 and 10) give programs that
cover more of the error space and lift the committee? Requested by the user: 80 independent
agents, 20 rubrics, 25 random validation examples per agent (overlap between agents allowed),
everything else as in v3.

## 2. What changed (vs v3)

| Setting | v3 | v4 |
|---|---|---|
| Rubrics | 10 (`heuristics.py`) | **20** (`heuristics_20.py`: the same 10 plus 10 new) |
| Variants per rubric | 8 | **4** (prompt says "variant i/4") |
| Few-shot examples per program | 10 random | **25 random**, seed `42*1000+pid`, overlap between slots allowed |
| Agents, isolation, filter, retries, model | independent, 0.60 code filter, 5 attempts, Opus | same |

The 25-example draws have 7 to 18 yes examples per slot (mean 12.3) and cover all 380
validation rows between them.

### The 10 new rubrics (11 to 20)
Written by brainstorming string-expressible dimensions (the first step of paper A.2) with the v3
failure analysis in mind. Their examples are made up, not copied from data rows.

| # | Name | Targets |
|---|---|---|
| 11 | Synonym and Alias Resolution | same food under a regional, culinary or scientific name |
| 12 | Head Food Position | the ingredient's food appears only as a modifier ("almond" vs "Almond milk") |
| 13 | Unstated Added Qualifier | USDA entry adds low sodium, fat free, sweetened, enriched and similar |
| 14 | Polarity and Negation Conflict | opposite values: unsalted/salted, skinless/with skin |
| 15 | Brand and Commercial Product | brand tokens and branded variants |
| 16 | Single Ingredient vs Composite Dish | "with", "in sauce", "soup", "mix" |
| 17 | Cooking Method Agreement | raw, boiled, fried, roasted, toasted |
| 18 | Anatomical Part and Cut | leaves vs root, breast vs thigh, yolk vs white |
| 19 | Ingredient Detail Coverage | how much of the whole string (commas, parentheses) the USDA entry accounts for |
| 20 | Compound Food Name Integrity | "sweet potato" is not "potato", "coconut milk" is not "milk" |

## 3. How it was run
- **Harness:** `synth_v4_tool.py` (a copy of the v3 tool). It imports `HEURISTICS_20`, sets
  `PROGRAMS_PER_HEURISTIC = 4` and `NUM_FEW_SHOT = 25`, and writes to `programs_synth_v4/`. Prompts
  for all slots are in `programs_synth_v4/_prompts/`.
- **First workflow run `wf_7b24e92d-89c`:** 80 independent agents. It hit the user's 5-hour usage
  limit partway: 53 slots were final (52 accepted, slot 8 failed) and 27 agents errored out.
  Four of the unfinished slots (50, 52, 55, 56) had already used attempts.
- **Resume:** the attempt counters for slots 50, 52, 55 and 56 were reset in `attempts.json` so
  each new agent got 5 tries. A second workflow `wf_10655ed8-f2e` ran 27 fresh independent
  agents (slots 50, 52, 55, 56, 58 to 80) with the same prompts, rules and similarity check
  against the already accepted programs. Slot 61 failed. Slot 66 needed all 5 attempts.
- **Baseline:** `run.py --judges programs_synth_v4 ...` into `outputs/paper_baseline_synth_v4/`.
- **Final:** 78 accepted, 2 failed (slots 8, Core Food Identity variant 4, and 61, Single
  Ingredient vs Composite Dish), 105 of 300 attempts. The transcripts again show zero "TOO
  SIMILAR" rejections.

## 4. Results

### Committee
All 80 programs passed the 50% filter. Top-k chose k = 6 (validation agreement 0.75). Selected:
76 (Ingredient Detail Coverage), 17 (Specificity), 6 (Preparation-State), 52 (Unstated Added
Qualifier), 65 (Cooking Method), 29 (Processing and Additive).

| | Generated test (3,799) | Real (943) |
|---|---|---|
| Accuracy | **74.86%** | **82.40%** |
| Precision / recall | 0.739 / 0.717 | 0.830 / 0.946 |

### Committee size sweep (programs taken in validation order)

| k | Validation agreement | Test | Real |
|---|---|---|---|
| 1 | 72.9% | 72.5% | 78.1% |
| 3 | 74.2% | 75.3% | 82.3% |
| 4 | 74.0% | 75.6% | 82.5% |
| **6 (chosen)** | **75.0%** | 74.9% | 82.4% |
| 9 | 74.0% | 73.9% | 82.8% |
| 12 | 73.2% | 74.3% | 80.9% |
| 20 | 71.6% | 74.0% | 80.9% |
| 40 | 68.7% | 73.3% | 80.8% |
| 80 | 68.2% | 71.4% | 81.0% |

Any k from 3 to 25 gives 73 to 76% on test. Picking the 6 best programs by test accuracy
(unavailable to PAJAMA) gives 74.89%, the same as the chosen committee. A committee made of
the best program from each of the 20 rubrics gets 71.65% test and 81.2% real, worse than top-k.

### Single programs (test)
Minimum 53.1% (the placeholders), median 67.3% over all 80 programs (67.5% over the 78 working
ones, the figure used in the master comparison), maximum 74.7% (program 75). 23 programs are at
70% or more, 37 are at 65 to 70%, 16 at 60 to 65%, 4 below 60%. Validation and test accuracy
correlate 0.93. The programs ranked 1 to 26 are all within 67.6 to 72.9% on validation, so
their order is mostly noise (one validation row is 0.26 points).

Mean test accuracy by rubric: 19 Ingredient Detail Coverage 71.9, 5 Specificity 71.4, 17 Cooking
Method 70.7, 14 Polarity 70.6, 3 Preservation 69.9, 13 Unstated Qualifier 69.6, 8 Processing
69.2, 15 Brand 68.7, 20 Compound Name 67.3, 2 Preparation-State 67.1, 6 Lexical 66.6, 4
Nutritional 66.3, 10 Modifier 66.1, 12 Head Food 65.6, 11 Synonym 65.4, 1 Core Identity 65.2,
18 Anatomical 65.1, 16 Single vs Composite 62.5, 9 Culinary Role 62.4, 7 Food Category 61.1.

## 5. Comparison
vs v3: +0.7 on test (within noise), +0.85 on real. v4 is first by a small margin, effectively
tied with v3. See [README.md](README.md).

## 6. Error analysis
- **Committee errors 955** (450 false yes, 505 false no). Accuracy by tier: easy 0.886, medium
  0.813, edge 0.744, hard 0.530 (v3: 0.494).
- **By pair type:** G6 synonyms 0.29 (309 errors, worse than v3), **B8 variants 0.60 (85
  errors, v3: 0.30, 147)**, E2 0.59 (43), B10 0.59 (34). The qualifier-focused rubrics did what
  they were written for. Synonyms did not improve, and the Synonym rubric programs reach 65%
  on their own and none made the committee.
- **Still overlap matchers:** 78 of 80 programs follow word overlap more than the label (median
  correlation 0.61 with overlap, 0.34 with the label). True matches with under 0.2 overlap are
  still wrong for 84% of programs. 451 test rows are wrong for at least 80% of programs.
- **Agreement between programs (78 working programs, all pairs):**

| | Validation (380) | Test (3,799) |
|---|---|---|
| Same answer | 74.2% | 74.9% |
| Kappa | 0.47 | 0.49 |
| Error overlap (Jaccard) | 0.47 | 0.45 |
| When one is wrong, the other is too | 63% | 62% |
| Same rubric / different rubric (agreement) | 78.3% / 74.1% | 79.1% / 74.8% |
| The selected 6 | 81.1% | 80.5% |

  Pairwise agreement on validation correlates 0.94 with test, so validation shows the overlap
  accurately. Different rubrics add only about 4 points of diversity over the same rubric.
  On test, all 78 programs agree on 11.2% of rows, 355 rows are wrong for all 6 selected
  programs, and 71 rows are wrong for all 78.
- **Most similar programs:** Compound Name (78, 80), Lexical (21, 22) and Specificity (20). The
  most different mostly say yes far more often (57 to 70%) and are among the least accurate,
  except program 50 (Unstated Added Qualifier, 68.4%, 41% yes, agrees with others only 68%).
- **Programs 1 to 4 (Core Food Identity) and 45 to 47 (Head Food Position)** share 79 to 85% of
  their errors with code similarity of only 0.08 to 0.26.
- **Top-k isn't the bottleneck:** 17 of the 23 programs at 70% or more on test were dropped, but
  adding them does not help, because they all fail on the same rows.

## 7. Validity and caveats
- **Possible optimism on test:** the 10 new rubrics were written after the v3 analysis, which
  used test data. None of the examples are rows from the data, but foods from the rubric text
  appear in test rows (peanut butter in 16, almond milk in 9, scallion in 6, sweet potato in 6).
  The real set is not affected.
- **The code-similarity filter never fired.** Across all 3,003 pairs, code similarity averages
  0.06 (maximum 0.29). A `difflib` setting that treats common characters as junk on long strings
  deflates scores about fourfold. With it off the average is 0.25 and the maximum 0.47. No pair is
  near 0.60. Independent agents write code that looks different. Code similarity correlates only
  0.29 to 0.35 with error overlap.
- **Run interrupted:** the usage-limit stop and resume (section 3) means the 27 resumed slots
  were written later by new agents, with the same prompts.
- Single run. Placeholders 8 and 61 are in the all-program figures.
- The agreement figures exclude the two placeholders.

## 8. Conclusions and what it motivated
More rubrics fixed qualifier-variant pairs but not synonyms, and did not make programs more
varied. The finding that the code filter does nothing and that behaviour overlap on validation
predicts test overlap motivated **v5** (a hybrid filter). The question whether feedback helps
motivated **v6**.

## 9. Files and reproduction
- Programs: `substitutability/programs_synth_v4/`. Rubrics: `heuristics_20.py`. Harness:
  `synth_v4_tool.py`.
- Output: `outputs/paper_baseline_synth_v4/`.
- Scripts in `analysis_programs/`: `deep_v4.py` (per program), `summary_v4.py` (per rubric),
  `dropped_v4.py` (rank, k sweep, oracle, best per rubric), `agreement_v4.py` (agreement and
  error overlap on validation and test), `replay_filter_v4.py` (what a behaviour filter would
  have rejected), `committee_compare.py` (tier and pair type, all versions). Outputs in
  `analysis_programs/out_v4/`.
- Reproduce: `synth_v4_tool.py init`, run 80 agents calling `synth_v4_tool.py submit <pid> <file>`,
  then the baseline command in [../README.md](../README.md).
