# Why most synthesized judge programs perform poorly

Analysis of the 80 paper-faithful programs in `programs_synth_v2/`, scored against Haiku v3
labels on the generated test set (`data_synth_v2/pajama_paper/test.jsonl`, 3,799 rows), with
the real set (`data_synth_v2/pajama/real_external.jsonl`, 943 rows) shown for comparison.
Each program uses the threshold PAJAMA tuned for it on the 380 validation rows.

## Summary

Each program checks one narrow aspect of the pair (additives, form, category, qualifiers)
against a hand-written word list. When nothing on its list matches, it returns a fixed default
score, which the threshold turns into a yes or a no regardless of the pair. No program checks
whether the ingredient and the USDA entry are the same food. The useful signal that remains is
mostly shared-word overlap, so the programs fail on look-alike pairs that differ and on
synonyms that share no words.

Letting programs abstain when their rule is silent raised committee accuracy from 72.8% to
74.0% on generated test data and from 74.6% to 82.0% on real data, in one exploratory run.

## Baseline context

| | Generated test (3,799) | Real (943) |
|---|---|---|
| Vanilla PAJAMA committee (k = 3: programs 40, 37, 33) | 72.8% | 74.6% |
| Always guess the majority class | 53.1% | 71.2% |

- 78 of 80 programs passed the 50% validation filter. Top-k selection kept 3.
- Single-program test accuracy ranges from 47.4% to 72.3%, with a median of 59%.
- Validation and test accuracy agree closely across programs (correlation 0.91).

### Adding more programs does not help

The committee was re-run with more of the ranked programs:

| k | Generated test | Real |
|---|---|---|
| 1 | 71.4% | 77.1% |
| 3 (chosen) | 72.8% | 74.6% |
| 8 | 72.3% | 78.7% |
| 20 | 69.2% | 75.5% |
| all 78 | 63.2% | 75.2% |

### Worst and best programs

The worst programs are near-constant "yes" machines. The best are strict word-overlap
matchers.

| Group | Rubrics | Say "yes" on | Typical error |
|---|---|---|---|
| 10 worst (47 to 54%) | Preservation & Form 3, Processing & Additive 3, Modifier & Qualifier 2, Food Category 1, Culinary Role 1 | 77 to 99% of rows | 1,400 to 2,000 false yes each |
| 10 best (69 to 72%) | Specificity & Generality 5, Lexical & Token Overlap 4, Modifier & Qualifier 1 | 21 to 41% of rows | 670 to 1,080 false no each (miss about half of true matches) |

Sixteen programs say yes to 77% or more of rows. Preparation-State Equivalence has 5 of them,
Preservation & Form 4, and Processing & Additive 3.

Always-yes programs look acceptable on real data (about 71%), because real data is 71% yes.
That hides the problem unless generated data is checked too.

## Findings

### 1. When the rule is silent, the program guesses

- **How often:** 30 of 80 programs give one identical score to at least half of the test rows.
  Their rule only fires when a listed word appears.
- **Effect:** on those default rows accuracy is 45 to 58%, about a coin flip. On rows where the
  rule fires, the same programs reach 60 to 78%.
- **Example:** program 61 (Processing & Additive) starts at 10 and subtracts only for additive
  words such as "salted", "breaded" or "with sauce". "Green olives → Green beans, raw" contains
  none, so it scores 10 and the program says yes.
- **Extreme cases:** programs 74 and 76 return their default on 96 to 97% of rows. They are the
  two worst programs.
- **Different foods:** on pairs that are clearly different foods (type B2, e.g. "watermelon
  seeds → sunflower seed kernels"), 47% of programs say yes.

### 2. Most programs are weaker versions of word overlap

- **Accuracy follows overlap:** a program's accuracy is almost fully explained by how closely
  its score tracks shared-word overlap. The correlation across the 80 programs is 0.87.
- **Weaker than the baseline:** plain word overlap correlates with the label at 0.43, and the
  median program at 0.22. 59 of 80 programs follow overlap more than they follow the label.
- **Errors follow overlap:**

| Truth | Shared-word overlap | Rows | Share of programs wrong |
|---|---|---|---|
| No | under 0.2 | 709 | 34% |
| No | 0.5 to 0.8 | 268 | **67%** |
| Yes | under 0.2 | 298 | **57%** |
| Yes | 0.8 or more | 339 | 13% |

- **Pair types:** by share of programs wrong, the hardest types are B8 (specific non-default
  variant, 59%), B10 (56%), G6 (synonym, 52%) and E2 (51%). G1 (exact name match) is easiest at
  21%.

### 3. The word lists have gaps

- **Lists everywhere, few synonyms:** 70 of 80 programs rely on hand-written word lists. Only
  19 mention "sodium" anywhere, and only 4 contain a synonym or alias table.
- **Example gap:** program 74's qualifier groups cover whole, skim and nonfat but not "low
  sodium". It finds no conflict in "mozzarella cheese → Cheese, mozzarella, low sodium".
- **Qualifier rows:** in 240 "no" rows the USDA name adds a fat, salt or sugar qualifier the
  ingredient lacks. On these, 57% of programs still say yes, and only 18 of 80 say no on at
  least 70% of them.
- **Synonym rows:** in 129 true matches the two names share no words, e.g. "pilchards →
  sardines" or "palmito → hearts of palm". On these, only 43% of programs say yes.

### 4. Minor: text after the first comma is discarded

- 65 of 80 programs keep only the ingredient text before the first comma. This drops
  qualifiers such as "skinless", "unhulled" or "toasted".
- On the 164 rows with such a qualifier, average program accuracy is 57.2% against 60.4%
  elsewhere.

### Rows almost every program gets wrong

86 rows are wrong for at least 80% of programs. 63 are "no" pairs with high overlap.

| Truth | Ingredient → USDA entry | Programs wrong |
|---|---|---|
| no | plain Greek yogurt → Yogurt, Greek, plain, nonfat | 84% |
| no | ground turkey → Turkey, ground, fat free, raw | 84% |
| no | mozzarella cheese → Cheese, mozzarella, low sodium | 89% |
| no | hemp seeds, unhulled → Seeds, hemp seed, hulled | 85% |
| no | jalapeno pepper → Stuffed jalapeno pepper | 88% |
| no | barley flour → Barley malt flour | 86% |
| yes | pilchards, tinned → Fish, sardines, canned | 82% |
| yes | porridge oats cooked in water with butter → Oatmeal, … made with water, fat added | 88% |

## The few-shot examples

The programs were synthesized from 10 examples drawn from the validation set. Scored on
those same 10 rows, the committee gets 5 right (50%), and single programs average 44.6%.

- **Skew:** the draw had 1 yes and 9 no. That may push programs toward strictness, and gives
  them no synonym example. The one yes is a brand match.
- **Not the whole explanation:**
  - The worst programs lean toward yes, the opposite of what a no-heavy draw would cause.
  - The earlier program set, synthesized from real few-shot examples, also scored about 75%
    on real test data.

## Test: abstain when the rule is silent

PAJAMA allows a program to abstain instead of voting. In one exploratory run:

1. For each of the 56 programs whose most common score covered at least 30% of validation
   rows, that score was treated as an abstention.
2. Programs were re-ranked by validation accuracy on the rows where they did vote.
3. The usual top-k sweep and Snorkel fit were then applied.

| | k | Generated test | Real |
|---|---|---|---|
| Vanilla PAJAMA | 3 | 72.8% | 74.6% |
| Abstain on default | 11 (chosen on validation) | **74.0%** | **82.0%** |

With silent programs no longer voting, the committee could use 11 programs instead of 3. No
test row had every program abstain. `run.py` has not been changed. The real-data gain is
large, but the real set is small and noisy, so this needs a confirming run.

## Recommended changes

1. **Make abstaining the default.**
   - In the synthesis prompt, ask programs to return "no opinion" when their rule does not
     apply, instead of a full or empty score.
   - For the existing programs, add an abstain-on-default option to `run.py`.
2. **Check the core food first.** Require an identity check in every program, or add dedicated
   identity programs, so an additive or form rule cannot approve a different food.
3. **Fill the known gaps.** Provide a synonym or alias list and a fuller qualifier list (low or
   reduced sodium, fat free, nonfat, hulled, and similar) to the synthesis prompt.
4. **Keep the whole ingredient string** instead of the part before the first comma.
5. **Use a balanced few-shot draw.** About 5 yes and 5 no, including synonym and qualifier
   cases.

## Caveats

- Labels are Haiku v3 judgments, so accuracy means agreement with that judge. The data audit
  estimates about 1% clearly wrong labels and about 16% borderline pairs.
- "Word overlap" here is a simple shared-word measure after removing a few stopwords such as
  "raw", "fresh" and "and".
- The code patterns in Finding 3 (word lists, "sodium", synonyms) were counted with regular
  expressions. The counts are approximate.
- The abstention test and the k sweep were single runs. Differences under about 1 point are
  noise.

## Reproducing

Run these from `substitutability/` with `PYTHONPATH=. ../.venv/bin/python`. Outputs go to
`analysis_programs/out/`.

| Script | What it does |
|---|---|
| `analysis_programs/perprog.py` | Per-program accuracy, yes-rate and error counts |
| `analysis_programs/ksweep.py` | Committee accuracy for different k |
| `analysis_programs/fs.py` | Accuracy on the 10 few-shot rows |
| `analysis_programs/deep.py` | Score behaviour, overlap correlations, share of programs wrong per row. Run before `deep2`–`deep4` |
| `analysis_programs/deep2.py` | Flat-default programs and rows most programs get wrong |
| `analysis_programs/deep3.py` | Code-pattern counts, qualifier and synonym rows |
| `analysis_programs/deep4.py` | Effect of discarding text after the first comma |
| `analysis_programs/abst.py` | Abstain-on-default test |
