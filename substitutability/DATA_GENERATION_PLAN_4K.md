# Data Generation Plan (Simple Version, 4,000 rows)

A shorter version of `DATA_GENERATION_PLAN.md`. Same core ideas, fewer moving parts.

## The goal

Build **4,000 rows** of `(ingredient, USDA match) → substitutable (yes/no)` such that:

1. **No duplicates.** Every row is a different pair. (Today: 943 rows but only 350 unique pairs, and one pair is 43 of the 222 validation rows.)
2. **Balanced.** 50% yes, 50% no. This holds overall and inside every difficulty level.
3. **Covers easy to hard.** Including hard cases where word overlap points the *wrong* way.
4. **Labeled by the real judge**, so the programs learn to copy the production behaviour.

## Why the old data wasn't enough

| Problem | Evidence |
|---|---|
| Heavy duplication | 943 rows = 350 unique pairs. Val is 222 rows = 70 pairs. |
| Mostly yes | 71% positive by row. |
| Word overlap gives it away | Token overlap alone scores AUC 0.78, about the same as the 80-program committee. Pairs with high overlap are 97% yes. |
| Almost no hard cases | Few "looks similar but is wrong" pairs (`smoked paprika → Spices, paprika`) and few "looks different but is right" pairs (`zucchini → Squash, summer, zucchini`). |
| Too few errors to train a router | The validation set gave only 22 committee errors. |

## The 5 steps

```
1. Food list  →  2. Write pairs  →  3. Snap to real USDA  →  4. Judge labels  →  5. Check, balance, split
   (LLM)           (LLM)               (local, free)            (production judge)    (local code)
```

### Step 1 — Make a food list (LLM)

Ask for about **1,800 distinct core foods** (onion, cumin, tofu, gochujang…), in 12 groups:

vegetables · fruits · herbs/spices/blends · oils/fats · dairy/eggs/plant milks · meat · poultry · seafood · grains/pasta/bread · legumes/nuts/seeds/soy · sauces/pastes/dressings · broths/drinks/vinegars/sweeteners/baking

Aim for roughly equal groups, and **at least 25% non-Western foods** (dashi, paneer, tamarind, nori, harissa…). Remove duplicates.

**Why:** this is what fixes the duplication. Thousands of different foods instead of a few repeated ones.

### Step 2 — Write the ingredient/USDA pairs (LLM, 6 foods per call)

For each food, the LLM writes about **2–3 pairs**, **including at least one good and one bad match**.

Example for `onion`:

| Ingredient | USDA match | Intended |
|---|---|---|
| fresh diced onion | Onions, raw | good |
| frozen diced onion, thawed | Onions, frozen, chopped, unprepared | good |
| onion | Onion powder | bad |

Rules for this step:
- **Each call handles 6 foods** (about 380 calls in total). The long rule text is paid for once per 6 foods.
- Give each call the target mix, e.g. "for onion: one *preservation-match* good, one *wrong-form* bad". The mix comes from the tables below.
- **Quantities** like `30g` are decoration. Pick one random weight per row. Never write the same pair twice at different weights.
- **Each food appears in at most 4 pairs.** Each exact USDA string is used at most 3 times.
- Mix easy and hard cases on purpose (see the difficulty levels).

Output format, one JSON per pair:
```json
{"food": "onion", "ingredient": "30g frozen diced onion, thawed",
 "usda_match": "Onions, frozen, chopped, unprepared",
 "intended": 1, "type": "G4"}
```
Keep the output short: no long rationale text. It's a guess anyway. The judge in step 4 decides.

### Step 3 — Snap to real USDA names (local, free) — recommended

The LLM invents the USDA strings. Match each one to the nearest real entry in USDA's free **FoodData Central** download (a local lookup, no API cost).
- Programs and routers get tested on real USDA strings, so training on invented ones would teach the LLM's style, not USDA's.
- Drop pairs where no real entry is close enough.
- If you skip this step, mark all USDA strings as synthetic and don't expect gains to transfer.

### Step 4 — Label every pair with the production judge

Run the exact `substitutability_prompt(ingredient, usda_match)` from the email (see `DATA_GENERATION_PLAN.md` §1.3) on every pair.
- Send the **full stored ingredient string, gram prefix included**. The judge sees `"30g olive oil"`, not `"olive oil"`.
- Parse `{"reasoning", "substitutable"}`. Re-ask on bad JSON.
- **This label is the truth.** If it disagrees with the intended label, keep the judge's.
- Re-run 10% of the pairs to check the judge agrees with itself (target ≥ 97%).

### Step 5 — Check, balance and split (local code)

1. **Dedupe.** Lowercase, strip the gram prefix, collapse punctuation. At most one row per (ingredient, USDA) key.
2. **Balance on the judge's labels** to 50/50, overall and within each difficulty level. This is why step 2 generates about 25% extra: some labels flip, and some pairs get dropped in the snap.
3. **Check word overlap.** Overlap alone should *not* predict the label (see the checks below).
4. **Split by food, not by pair**, so the same food never lands in two splits:

| Split | Rows | Used for |
|---|---|---|
| `fewshot` | 40 | The only pool the program writer sees |
| `fit` | 1,400 | Thresholds, program selection, aggregator fit |
| `router` | 1,000 | Router training. At ~25% error this gives ~250 errors (vs 22 today). |
| `test` | 1,560 | Final results. Includes a **150-row** subset to hand-label as a sanity check. |

## What to put in the data

### Good matches (label should be yes)

| Code | Type | Example |
|---|---|---|
| G1 | Exact | `honey → Honey` |
| G2 | Same words, different order | `black pepper → Spices, pepper, black` |
| G3 | Trivial prep (diced, fresh, melted) | `fresh diced onion → Onions, raw` |
| G4 | Preservation matches | `frozen mango chunks, thawed → Mango, frozen` |
| G5 | Plain ingredient → default version | `milk → Milk, whole` |
| G6 | Synonym / taxonomy | `zucchini → Squash, summer, zucchini` |
| G7 | Brand of the plain product | `firm tofu → HOUSE FOODS Premium Firm Tofu` |

### Bad matches (label should be no)

| Code | Type | Example |
|---|---|---|
| B1 | Unrelated | `breadcrumbs → Popover` |
| B2 | Sibling food | `chia seeds → Seeds, flaxseed` |
| B3 | A dish or product containing it | `spaghetti → Spaghetti sauce` |
| B4 | Shared-word trap | `ice → Italian Ice` |
| B5 | Raw → cooked | `fresh mushrooms → Fried mushrooms` |
| B6 | Wrong form | `garlic paste → Garlic sauce`, `chili flakes → Spices, chili powder` |
| B7 | Wrong preservation | `jarred minced garlic → Garlic, raw` |
| B8 | Specific non-default version | `almond milk → Almond milk, unsweetened` |
| B9 | Flavour/process difference | `smoked paprika → Spices, paprika` |
| B10 | Wrong variety | `jasmine rice → Rice, white, cooked, glutinous` |
| B11 | Partial composite | `Salt and pepper → Salt, table` |

The rule of thumb behind these types comes from the judge's wording: a match is good only if a diner "would not notice **any** difference".

### Difficulty levels (about equal yes/no in each)

| Level | Share | Looks like | Notes |
|---|---|---|---|
| **Easy** | 30% | G1–G3 and B1–B3 | Overlap agrees with the label |
| **Medium** | 30% | G4–G5 and B5–B7 | Exactly one detail (form, state, preservation) decides it |
| **Hard** | 30% | G6–G7 and B4, B8–B10 | **Overlap points the wrong way**: similar-looking bad pairs, different-looking good pairs |
| **Edge** | 10% | B11 plus cases where the judge is inconsistent | Policy boundary cases |

Known judge inconsistencies go in Edge, not hidden. For example, `diced carrot → Carrots, raw` is yes but `shredded carrot → Carrots, raw` is no, and `fresh chicken breast` and `fresh chicken thighs` get opposite labels for the same pattern.

## Extra: robustness variants (evaluation only)

Take about **200 test pairs** and make variants:
- **Same label expected:** typos, `EVOO`, different case, other units, filler words.
- **Label should flip:** add or remove one decisive word (`paprika → smoked paprika`, `salt → salt and pepper`).

Never use these for fitting. They measure how robust the programs are.

## Final check on real data

Keep the existing **350 real unique pairs** as an external test, and block about 100 of their foods (salt, olive oil, garlic…) from generation. If results don't hold up on the real set, the synthetic data isn't doing its job.

## Is the data good? (checks)

| Check | Target |
|---|---|
| Duplicate pairs | 0 |
| Overall balance | 50% ± 3 |
| Balance within each difficulty level | 50% ± 10 |
| Word overlap alone, AUC | ≤ 0.65 overall (today 0.78) |
| Judge agrees with itself | ≥ 97% |
| Committee error rate | Rises Easy < Medium < Hard ≤ Edge |
| Pairs of each bad/good type in the test split | ≥ 15 |
| Share of USDA strings not found in FoodData Central | ≤ 15% |

## Cost (estimate, 4k rows, Haiku 5.5)

Assumes Haiku 5.5 ($0.10 / $0.50 per million tokens) for steps 1–2 and the optional reviewer, and the production judge on Groq (`gpt-oss-120b`, ~$0.15 / $0.75, the repo's assumption).

| Step | Cost |
|---|---|
| 1. Food list | ~$0.10 |
| 2. Write pairs (~380 calls, 6 foods each) | ~$1.2 |
| 3. Snap to real USDA | $0 |
| 4. Judge labels (~5,800 calls incl. 10% re-runs and variants) | ~$1.6 |
| 5. Check, balance, split | $0 |
| *Optional: second-LLM reviewer + adjudication on disputed rows* | *~$0.5* |
| *Pilot and iteration (+10%)* | *~$0.4* |
| **Total** | **~$4 (about $3 with the Batch API)** |

Using Sonnet 5.5 just for the Hard and Edge rows in step 2 would add about $2. Whichever model you pick, run the 150-row pilot first and replace these numbers with real token counts.

## Do first: a 150-row pilot

1. Generate 150 pairs across a few food groups and all four levels.
2. Run steps 3–5.
3. **Read 50 rows by hand.** Are the "hard" ones really hard? Is it balanced? Does the judge label look right?
4. Fix the step-2 prompt, then scale to 4,000.

## Still open

1. **The judge's model and temperature.** Confirm them in `rerun_subjudge.py` (the email didn't say).
2. **A FoodData Central index** for step 3. You can download it free from USDA, or reuse the one in the backend zip.
3. **The six "Confirmed from API run" rows** in the source CSV weren't made by this prompt. Re-label them before using them as examples.
4. **Whether the target is the judge's label or a human-corrected one.** The plan uses the judge's label, which matches the "reproduce the judge" goal.
