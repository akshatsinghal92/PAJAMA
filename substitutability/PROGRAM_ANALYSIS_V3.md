# Program set v3: how it was built and why it is still weak

This doc covers the 80 programs in `programs_synth_v3/`. Each was written by an independent
agent from its own random few-shot sample. All accuracies are against the Haiku v3 labels on
the generated test set (`data_synth_v2/pajama_paper/test.jsonl`, 3,799 rows) unless the doc
says otherwise. For the earlier program set (v2), see `PROGRAM_FAILURE_ANALYSIS.md`.

## Summary

- **What v3 fixed:** v2's main problem is gone. No program falls back to one fixed score when
  its rule doesn't fire, and programs now reject clearly different foods reliably.
- **What is still wrong:** almost every v3 program is a word-overlap matcher.
  - True matches that share few words are missed, such as synonyms and renamed foods.
  - Look-alike variants that share many words are accepted.
- **Why voting doesn't help:** the programs make the same mistakes, so the committee can't
  outvote them. In 24% of committee errors, all 11 selected programs are wrong together.
- **Headline result:** the committee reaches 74.2% on generated test data and 81.6% on real
  data. v2 reached 72.8% and 74.6%.

## How the v3 programs were created

### Setup

| Step | What was done |
|---|---|
| Slots | 10 rubrics from `heuristics.py` × 8 variants = 80 slots. Slot `pid` uses rubric `(pid-1) // 8`. |
| Agents | One independent subagent per slot, all in one workflow run (80 agents). Each agent read only its own prompt file (`programs_synth_v3/_prompts/p{pid}.txt`) and was told not to test its program on the data. |
| No shared memory | The prompt had no "already implemented approaches" list. No agent saw another agent's program. |
| Few-shot examples | Each slot got its own 10 examples, sampled at random from the 380 validation rows. The seed is `42*1000 + pid`, so every draw can be reproduced (`synth_v3_tool.py`, lines 74-75). |
| Prompt | The same template as `generate_programs.build_prompt`: role, definition of SUBSTITUTABLE, input shape, one rubric, diversity and failure-avoidance guidance, the 10 examples, 10 requirements, and the signature `judging_function(ingredient, usda_match)`. |
| Checks on submit | `validate_code` runs the fixed validation cases and a directional sanity check. The program is then compared with every program accepted so far and rejected if its code is more than 60% similar. A file lock keeps parallel agents from submitting at the same moment. |
| Retries | Each slot got up to 5 attempts, and the run had a cap of 300 attempts in total. A slot that failed all 5 got a placeholder that always returns 0. |

### What the few-shot draws looked like

- All 80 sets of examples are different. Two slots share 0.27 examples on average.
- The draws together cover 332 of the 380 validation rows.
- Each set holds between 2 and 9 "yes" examples, 5.1 on average.
- Each slot's draw is listed in `programs_synth_v3/fewshot_per_slot.json`.

### Outcome of synthesis

- 78 slots were accepted, using 108 of the 300 attempts.
- Slots 25 and 27 failed. Both are Nutritional Profile, and both failed the directional sanity
  check 5 times. They are now placeholders that always return 0.

### Differences from the paper

| | Paper | v3 |
|---|---|---|
| Few-shot examples | The same 10 for every program. The upstream code samples once with seed 42. | A different random 10 for each program. |
| Who writes the program | Separate API calls to Opus 4.6. | Claude Code subagents, no API calls. |
| Prompt, rubrics, validation, 0.60 similarity filter | as described | the same |

## Baseline result

PAJAMA was run exactly as in the paper, with the same threshold tuning, 50% validation filter,
top-k sweep and Snorkel aggregation. Output is in `outputs/paper_baseline_synth_v3/`.

| | Generated test (3,799) | Real (943) |
|---|---|---|
| v3 committee (k = 11) | **74.15%** (precision 0.719, recall 0.738) | **81.55%** (precision 0.836, recall 0.921) |
| v2 committee (k = 3) | 72.76% | 74.55% |
| Always guess the majority class | 53.1% | 71.2% |

- All 80 programs passed the 50% validation filter. The two placeholders scored about 53% on
  validation, so they passed too.
- The top-k sweep chose k = 11, with validation agreement 0.721.
- The 11 selected programs are 77, 16, 35, 9, 33, 58, 10, 34, 15, 62 and 61.

### What changed from v2

| | v2 | v3 |
|---|---|---|
| Programs that give one fixed score to most rows | 30 of 80 | 0, apart from the 2 placeholders |
| Share of programs saying yes to clearly different foods (types B1 / B2) | 30% / 47% | 4% / 16% |
| Median single-program accuracy | 59% | about 67% |
| Single-program range | 47.4% to 72.3% | 53.0% (program 50) to 74.0% (program 16) |
| Programs that track word overlap more than the label | 59 of 80 | 78 of 80 |
| Committee accuracy on hard rows | 49.4% | 49.4% |

## Findings

### 1. Almost every program is a word-overlap matcher

- **What scores follow:** the median program's score correlates with shared-word overlap at
  0.61 and with the true label at 0.33. For v2 the overlap figure was 0.34. Plain word overlap
  on its own correlates with the label at 0.43.
- **Errors follow overlap:**

| Truth | Shared-word overlap | Share of programs wrong |
|---|---|---|
| No | under 0.2 | 9% |
| No | 0.2 to 0.5 | 26% |
| No | 0.5 to 0.8 | 58% |
| No | 0.8 or more | **90%** |
| Yes | under 0.2 | **84%** |
| Yes | 0.2 to 0.5 | 57% |
| Yes | 0.5 to 0.8 | 31% |
| Yes | 0.8 or more | 10% |

- **Zero shared words:** on 129 true matches whose names share no words, only 16% of programs
  say yes. For v2 the figure was 43%.
- **First word missing:** when the USDA entry's first word doesn't appear in the ingredient,
  72% of programs get the true matches wrong.
- **The committee decides the same way.** Mean word overlap by committee outcome:

| Committee outcome | Mean word overlap |
|---|---|
| False no | 0.19 |
| Correct no | 0.19 |
| False yes | 0.40 |
| Correct yes | 0.58 |

- **Likely cause:** programs see only the two strings, and the prompt rules out heavy NLP
  libraries. Only 8 of 80 programs carry any synonym or alias table. 77 of 80 rely on
  hand-written word lists. Code that compares only the text has no way to know that maize is
  corn.

### 2. Two pair types account for 45% of committee errors

The committee makes 982 errors: 515 false yes and 467 false no.

| Pair type | Committee accuracy | Committee errors | Share of programs wrong |
|---|---|---|---|
| G6, synonym or renamed food | **33%** | 295 (30% of all errors) | 71% (v2: 52%) |
| B8, specific non-default variant | **30%** | 147 | 56% |
| E2 | 51% | 51 | 48% |
| B10 | 57% | 35 | |

Other types with many errors: B9 (54), B6 (52), B3 (49), G4 (43), B5 (41), G3 (34).

**Synonyms (G6):** all 11 programs say no to every pair below, though each is a true match.

- Japanese sea mustard → Seaweed, wakame, raw
- frankfurter → Hot dog, meat and poultry
- palmito, drained → Hearts of palm, canned
- Mexican hard white cheese → Queso cotija
- Chinese preserved bean curd → Tofu, salted and fermented (fuyu)
- African horned cucumber → Horned melon (Kiwano)

**Qualifier traps (B8 and similar):** in 240 "no" rows, the USDA entry adds a fat, salt or
sugar qualifier the ingredient lacks.

- 47% of programs still say yes on these rows (v2: 57%).
- 20 of 80 programs say no on at least 70% of them.
- Only 20 programs mention "sodium" anywhere in their code.

### 3. The programs fail together, so voting can't fix it

- **Agreement:** two programs give the same answer on 74% of rows on average, and two of the
  11 selected programs on 79%.
- **Shared mistakes:** the mean Jaccard overlap between two programs' error sets is 0.45.
- **Unanimous errors:** in 240 of the 982 committee errors (24%), all 11 programs are wrong.
  In 541 errors (55%), at least 9 of 11 are wrong.
- **Hard rows:** 442 test rows are wrong for at least 80% of all programs (373 are true
  matches). 919 rows are wrong for at least 60%.
- **Why this matters:** Snorkel treats the programs as independent voters. Correlated programs
  add confidence but no new information. This is also why the top-k sweep stops at 11: adding
  more programs adds more copies of the same mistakes.
- **Why the similarity filter misses it:** the filter compares code text. Programs can look
  different and still behave almost identically.

### 4. The committee covers only 4 of the 10 rubrics

| Rubric | Mean program accuracy | Programs in the committee |
|---|---|---|
| Preparation-State Equivalence | 70.7% | 4 |
| Specificity & Generality | 70.1% | 3 |
| Preservation & Form | 68.2% | 0 |
| Processing & Additive | 68.1% | 3 |
| Modifier & Qualifier | 68.0% | 1 |
| Lexical & Token Overlap | 66.8% | 0 |
| Core Food Identity | 64.5% | 0 |
| Culinary Role | 64.2% | 0 |
| Nutritional Profile | 63.8% (includes the 2 placeholders) | 0 |
| Food Category | **58.1%** | 0 |

- **Selection is by accuracy alone.** Top-k ranks programs only by their own validation
  accuracy, so programs that look at a pair from a different angle are never chosen.
- **Food Category (programs 49-56) is the weakest rubric.** Category keyword lists are too
  coarse: "dairy" matches "dairy" even when the foods differ. Program 50 says yes on 87% of
  rows.
- **Nutritional Profile is hard to code from a name.** A food's name says little about its
  nutrients, and both failed slots belong to this rubric.

### 5. Difficulty tiers: all of the gain is on easier rows

| Tier | Committee accuracy |
|---|---|
| Easy | 89.3% |
| Medium | 81.7% |
| Edge | 73.7% |
| Hard | **49.4%**, the same as v2 |

The hard tier is mostly synonyms, brand names and look-alike variants.

### 6. Smaller issues

- **Text after the first comma:** 51 of 80 programs keep only the ingredient text before the
  first comma (v2: 65). On the 164 rows where the dropped text matters, average program
  accuracy is 62.9%, against 66.1% elsewhere.
- **Label noise:** on 336 test rows, the Haiku label disagrees with the label the data
  generator intended (`label_intended`).
  - 138 of the 982 committee errors fall on these rows, and 25 of the 240 unanimous errors.
  - On these rows the committee agrees with the generator's label 41% of the time.
  - Some unanimous "false yes" errors look like labelling mistakes, for example "hearts of
    palm → Hearts of palm, raw", "canned hominy → Hominy, canned, yellow" and "buckwheat
    groats (kasha) → Buckwheat groats", which are all labelled no.
  - Scored against the generator's labels, the committee gets 72.6%. Label noise explains
    part of the residual error, not most of it.

## Suggested fixes

None of these have been tested yet. They are ordered by expected impact.

1. **Give programs knowledge they can't derive from the text.** Build a synonym and alias table
   once, for example with an LLM (maize ↔ corn, palmito ↔ hearts of palm, frankfurter ↔ hot
   dog, cilantro ↔ coriander). Put it in the prompt, or ship it as a shared lookup every
   program can import. This targets G6, about 30% of committee errors.
2. **Filter for different behaviour, not different code.** Reject a new program if its
   predictions on the validation rows agree with an existing program's on more than about 90%
   of rows.
3. **Choose a committee that covers more rubrics.** For example, take the best one or two
   programs from each rubric, or choose programs whose errors overlap least.
4. **Add an explicit qualifier-conflict rubric** with a full list of qualifiers: low or reduced
   sodium, fat free, nonfat, with salt, hulled, flavoured, and brand names. This targets B8.
5. **Use word overlap as a routing signal.** Errors cluster on low-overlap "yes" pairs and
   high-overlap "no" pairs, so the router can send those to the LLM judge.
6. **Derive rubrics from data, as in paper appendix A.2.** List dimensions that code can
   express, then add more by mining the LLM judge's explanations on validation rows. The
   current 10 rubrics were written by hand.
7. **Keep the full ingredient string** instead of the text before the first comma.
8. **Clean the labels** on the 336 rows where Haiku and the generator disagree, before trusting
   small accuracy differences.

## Caveats

- Labels are Haiku v3 judgments, so "accuracy" means agreement with that judge.
- "Word overlap" is a simple shared-word measure after removing a few stopwords such as "raw",
  "fresh" and "and".
- Code-pattern counts (word lists, "sodium", synonym tables, comma cutting) were found with
  regular expressions and are approximate.
- Each result comes from a single run. Differences under about 1 point are noise.
- The two placeholders are counted in the all-program figures.

## Reproducing

Run these from `substitutability/` with `PYTHONPATH=. ../.venv/bin/python`.

| Step | Command or file |
|---|---|
| Write per-slot prompts and few-shot draws | `synth_v3_tool.py init` |
| Submit a program for a slot (validation, similarity check, save) | `synth_v3_tool.py submit <pid> <file>` |
| Check synthesis progress | `synth_v3_tool.py status` |
| Programs, manifest, attempt counts, few-shot draws | `programs_synth_v3/` |
| Baseline outputs | `outputs/paper_baseline_synth_v3/` |
| Per-program behaviour, overlap correlations, share wrong per row | `analysis_programs/deep_v3.py` (run first) |
| Flat programs and rows most programs get wrong | `analysis_programs/deep2_v3.py` |
| Code patterns, qualifier and synonym rows | `analysis_programs/deep3_v3.py` |
| Effect of comma cutting | `analysis_programs/deep4_v3.py` |
| Committee errors, agreement, error overlap, rubric means, label noise | `analysis_programs/committee_v3.py` |

Analysis outputs are written to `analysis_programs/out_v3/`. The workflow script that ran the 80
agents is saved outside the repo, in the Claude session folder
(`.../workflows/scripts/synthesize-programs-v3-wf_1ab65f25-104.js`).
