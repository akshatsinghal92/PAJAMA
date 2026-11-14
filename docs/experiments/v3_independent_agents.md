# v3: 80 independent agents, own random 10 examples each

Documented: 2026-11-13. Status: finished. A longer results write-up exists in
`substitutability/PROGRAM_ANALYSIS_V3.md`. This doc is the full experiment record.

## 1. Question and motivation
v2's programs were weak for identifiable reasons (see [v2](v2_single_agent_baseline.md)):
30 of 80 returned a fixed default score, and all 80 were written by one agent in one
conversation from the same skewed 10 examples (1 yes, 9 no). Reading the PAJAMA paper showed:
- programs come from independent API calls, not from one agent that remembers earlier programs;
- each prompt holds one rubric and 10 random validation examples (the authors' code samples
  once with seed 42, so all programs share the draw).

Question: do independent agents with their own random 10 validation examples produce better
or more varied programs than v2? The user asked for 80 independent agents, so that no agent
has memory of another, and for a random 10-example sample per agent from validation.

## 2. What changed (vs v2)

| Setting | v2 | v3 |
|---|---|---|
| Agents | 1, sequential, one conversation | 80, one per slot, no shared memory |
| Few-shot examples | same 10 for all (1 yes, 9 no) | own random 10 per slot from validation |
| Avoid list of existing approaches | yes | **no** |
| Rubrics / variants | 10 / 8 | 10 / 8 (same) |
| Similarity filter | code text 0.60 | code text 0.60 (same) |
| Validation cases, retry limits | same | same |
| Model | the session's own agent | Opus, effort medium |

Everything else is the same as `generate_programs.py` and the paper: same prompt template, same
validation cases, 5 attempts per slot, 300 global attempts.

## 3. How it was run
- **Harness:** `substitutability/synth_v3_tool.py`.
  - `init`: for each slot `rng = random.Random(42*1000 + pid)` and `shots = rng.sample(val_rows, 10)`.
    It writes `programs_synth_v3/_prompts/p{pid}.txt` with
    `build_prompt(heuristic, format_few_shot(shots), variant, None)`, plus
    `fewshot_per_slot.json` (the ids drawn) and an empty `manifest.json`.
  - `submit <pid> <file>`: runs `validate_code` outside a lock, then takes an `fcntl` lock and
    checks the attempt count, the 0.60 similarity against every accepted program, and updates
    the manifest. Max 5 attempts per slot, then a FAILED placeholder returning 0.0.
  - `status`.
- **Agents:** one Workflow run (`wf_1ab65f25-104`), 80 parallel agents, effort medium. Each
  agent was told to read only its own prompt file, not to read any other program, data or doc,
  and not to run its program on data. Workflow script:
  `~/.claude/projects/-Users-akshat-Documents/e4ab1802-4b4a-4900-9162-c9d20b9dce66/workflows/scripts/synthesize-programs-v3-wf_1ab65f25-104.js`.
- **Few-shot draws:** all 80 sets are different. Two slots share 0.27 examples on average. The
  draws cover 332 of the 380 validation rows. Each set has 2 to 9 yes examples (mean 5.1).
- **Baseline:** `run.py --judges programs_synth_v3 ...` into `outputs/paper_baseline_synth_v3/`.

## 4. Results

### Synthesis
78 slots accepted, 2 failed after 5 attempts (slots 25 and 27, both Nutritional Profile, both
failing the directional sanity check). 108 of 300 attempts used. The agents' transcripts show
**zero "TOO SIMILAR" rejections**. All rejected drafts failed the sanity check.

### Committee (PAJAMA)
All 80 programs passed the 50% filter (the two placeholders score about 53% on validation).
Top-k chose k = 11 with validation agreement 0.7211. Selected programs: 77, 16, 35, 9, 33, 58,
10, 34, 15, 62, 61 (Modifier x1, Preparation-State x4, Specificity x3, Processing x3).

| | Generated test (3,799) | Real (943) |
|---|---|---|
| Accuracy | **74.15%** | **81.55%** |
| Precision / recall | 0.719 / 0.738 | 0.836 / 0.921 |
| Majority class | 53.1% | 71.2% |

### Single programs (test)
Range 53.0% (program 50, the Food Category rubric) to 74.0% (program 16). Median about 66 to
68%. Only the two placeholders are flat (v2 had 30). Yes-rates range from 17% to 87%.

Mean accuracy by rubric: Preparation-State 70.7, Specificity 70.1, Preservation 68.2,
Processing 68.1, Modifier 68.0, Lexical 66.8, Core Identity 64.5, Culinary Role 64.2,
Nutritional 63.8, Food Category 58.1.

## 5. Comparison
vs v2: +1.4 points on test, **+7.0 on real**. The test gain is within noise of about 0.7.
The real gain is larger than its noise of about 1.3 points. See [README.md](README.md).

## 6. Error analysis
- **What is fixed:** no flat-default programs. Different-food pairs are rejected reliably (the
  share of programs saying yes on clearly different foods is 4% for B1, 16% for B2 and 18% for B3).
- **Programs became overlap matchers:** the median correlation of a program's score with
  shared-word overlap is 0.61 (v2: 0.34), against 0.33 with the label. 78 of 80 follow overlap
  more than the label. Plain word overlap correlates with the label at 0.425.
- **Share of programs wrong, by truth and word overlap:**

| Truth | Overlap under 0.2 | 0.2 to 0.5 | 0.5 to 0.8 | 0.8 or more |
|---|---|---|---|---|
| No | 0.09 | 0.26 | 0.58 | 0.90 |
| Yes | 0.84 | 0.57 | 0.31 | 0.10 |

  On 129 true matches whose names share no words, only 16% of programs say yes. On 376
  non-matches only 6% say yes.
- **Pair types:** G6 (synonym or renamed food) has 71% of programs wrong (v2: 52%), B8 56%,
  E2 48%, G7 48%.
- **Committee errors: 982** (515 false yes, 467 false no). Accuracy by tier: easy 0.893,
  medium 0.817, edge 0.737, hard 0.494. By type: G6 295 errors (accuracy 0.33), B8 147 (0.30),
  B9 54, B6 52, E2 51 (0.51), B3 49, G4 43, B5 41, B10 35 (0.57), G3 34.
- **Programs fail together:** mean pairwise agreement 0.74 (0.79 within the selected 11), mean
  Jaccard of error sets 0.45. In 240 of the 982 committee errors all 11 selected programs agree
  on the wrong answer, and in 541 at least 9 of 11 are wrong. This breaks the independence
  assumption behind Snorkel and is why top-k stops at 11.
- **442 test rows are wrong for at least 80% of programs** (373 true matches, 69 non-matches).
- **Code patterns:** 51 of 80 programs cut the ingredient at the first comma, 77 of 80 use
  hand-written word lists, 20 mention "sodium", 8 contain any synonym table, 5 are veto-style.
  Rows with a comma qualifier: average program accuracy 0.629 vs 0.661 elsewhere (164 rows).
- **Qualifier rows:** in 240 "no" rows where the USDA name adds a fat, salt or sugar qualifier,
  47% of programs still say yes (v2: 57%). 20 of 80 say no on at least 70% of them.
- **Examples, all 11 selected programs wrong:** synonyms such as "Japanese sea mustard" to
  "Seaweed, wakame, raw", "frankfurter" to "Hot dog, meat and poultry", "palmito, drained" to
  "Hearts of palm, canned". False yes such as "pear" to "Prickly pears, raw", "cooked eggplant,
  no added fat" to "Eggplant, cooked, fat added".

## 7. Validity and caveats
- **Label noise:** Haiku and generator labels disagree on 336 of the 3,799 test rows. 138 of
  the 982 committee errors fall on those rows, where the committee agrees with the generator
  label 41% of the time. Against generator labels the committee would score 72.57%. Some
  unanimous false-yes errors look like Haiku mistakes ("hearts of palm" to "Hearts of palm,
  raw" labelled no).
- Single run. The k sweep for v3 was started and then interrupted, so it was not run.
- The two placeholders pass the 50% filter and are counted in all-program figures.
- Code-pattern counts come from regular expressions and are approximate.

## 8. Conclusions and what it motivated
Independent agents fixed v2's flat-default failure but produced near-identical word-overlap
programs. Weak rubrics were Food Category and Nutritional Profile. The paper never justifies 10
rubrics, so the next questions were whether more rubrics and more examples per program add
variety. That motivated **v4**.

## 9. Files and reproduction
- Programs: `substitutability/programs_synth_v3/` (judge_1..80.py, manifest.json,
  attempts.json, fewshot_per_slot.json, `_prompts/`).
- Output: `outputs/paper_baseline_synth_v3/`.
- Scripts: `analysis_programs/deep_v3.py`, `deep2_v3.py`, `deep3_v3.py`, `deep4_v3.py`,
  `committee_v3.py`. Outputs in `analysis_programs/out_v3/`.
- Reproduce: `python synth_v3_tool.py init`, run 80 agents that each call
  `synth_v3_tool.py submit <pid> <file>`, then the baseline command in [../README.md](../README.md).
