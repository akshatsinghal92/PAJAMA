# Synthetic Data Generation Plan — USDA Ingredient Substitutability

A plan for generating a **balanced, de-duplicated, difficulty-stratified** dataset of
`(ingredient, usda_match) → substitutable` decisions with LLM calls. It is built from an
analysis of the current 943-row dataset and is designed to fix the specific problems that
analysis found. It extends, and partly supersedes, `../USDA_Substitutability_Data_Plan.docx`.

---

## 0. Why we need new data — what is wrong with the current set

All numbers below are measured on `data/val.jsonl` + `data/test.jsonl`. Programs strip gram
prefixes, so a pair is counted once after normalization.

| Problem | Evidence | Consequence |
|---|---|---|
| **Heavy duplication** | 943 rows but only **350 unique pairs**. Val is 222 rows / **70 pairs**. `salt → Salt, table` alone is **43 of 222 val rows**. The top-10 pairs are 60% of val. | Thresholds, top-k and Snorkel weights are fit to a handful of easy pairs. Val accuracy (0.955) is meaningless. |
| **Class imbalance** | 71% positive by row, 63% by pair. | The majority baseline is already 0.695, and the Snorkel prior is skewed. |
| **Lexical-overlap shortcut** | Token Jaccard *alone* gives AUC **0.779**, the same as the 80-program committee (0.787). Pairs with Jaccard ≥ 0.67 are **97% positive**. Pairs with Jaccard < 0.34 are 37% positive. | The programs learned "words overlap → substitutable". The data has almost no **high-overlap negatives** or **low-overlap positives**, so we cannot measure or train past the shortcut. |
| **Skewed toward easy cases** | Most positives are canonical (`honey → Honey`). Many negatives are retrieval junk (`frozen kale → Oil, teaseed`). | The hard middle, where one attribute decides the label, is thin, and that is where the committee fails. |
| **Too few errors for the router** | The val committee made **22 errors**. | The router cannot learn (see `PROGRAM_IMPROVEMENT_AND_ROUTING.md`). |
| **Label inconsistencies** | See §2.3. Near-identical cases receive opposite labels. | Some test "errors" are label noise. Policy needs to be written down. |

**Design goals:**
1. **Unique pairs.** Every row is a distinct decision, and quantity never creates copies.
2. **50/50 balance**, holding *within* every family and every difficulty tier.
3. **Decorrelate overlap from the label.** Include plenty of hard negatives with high overlap and hard positives with low overlap.
4. **Explicit difficulty tiers** that we can verify after generation.
5. **Robustness.** Linked surface perturbations, both label-preserving and label-flipping, for invariance tests.
6. **Realism.** USDA strings should come from the real FoodData Central database, so the data looks like production.
7. **Splits sized for every pipeline stage:** synthesis few-shot, committee fit, router training, and test.

---

## 1. How a data point is represented

### 1.1 The ingredient string (recipe side)

Observed grammar:

```
[QTY]g  [FORM/SOURCE] [PREP] [VARIETY] CORE_FOOD [, POST-PREP CLAUSE] [(NOTE)]
 200g    frozen        diced            onion     , thawed
 150g    canned        whole  cherry    tomatoes  , drained
 10g                                    garlic paste           (from tube)
 3g                                     Salt and pepper        (to taste)
```

| Slot | Observed values | Does it usually change the label? |
|---|---|---|
| Quantity | `3g` … `1000g`, always grams | Never. It is noise only. |
| Form/source | fresh, frozen, canned, jarred, dried, cooked, smoked, toasted, roasted, candied | **Often.** It must line up with the USDA state. |
| Prep (cut) | diced, chopped, shredded, minced, grated, sliced, shaved, florets, ground | Sometimes. It is trivial *except* vs. a different processed form (`diced → dehydrated`, `chopped almonds → almond butter`). |
| Variety | cherry, jasmine, arborio, kalamata, russet, sharp, Greek, Dijon, smoked | **Often.** A variety-specific ingredient vs. a generic or different-variety USDA entry. |
| Core food | 1–3 word food noun | It defines identity. |
| Post-prep clause | `, thawed`, `, drained`, `, soaked and cooked`, `, thawed and squeezed`, `, peeled` | It interacts with the USDA state (`frozen…, thawed → …, frozen` is OK). |
| Note | `(optional)`, `(to taste)`, `(from tube)` | Usually no. `(from tube)` signals a processed form. |
| Composite | `Salt and pepper`, `peas and carrots`, `mixed berries` | **Yes.** A single-component USDA entry is negative. |

### 1.2 The USDA match string (database side)

There are three real FoodData Central styles, all present today:

| Style | Example | Notes |
|---|---|---|
| SR Legacy (inverted, comma-separated) | `Spices, pepper, black`, `Beef, chuck for stew, separable lean and fat, choice, raw` | Head noun first, then modifiers, then state. |
| FNDDS (survey foods) | `Black beans, from canned, no added fat`, `Sweet potato, NFS`, `Potato, roasted, from fresh, peel eaten, made with oil` | `NFS`, `from …`, `no added fat`, dishes (`Lentil curry`). |
| Branded | `HOUSE FOODS Premium Firm Tofu`, `Margarine-like spread, SMART BEAT Smart Squeeze` | ALL-CAPS brand. Junk retrievals often come from here. |

A USDA string encodes **identity** (head), **variety/part**, **state** (raw, cooked, baked,
fried, dry, unprepared), **preservation** (frozen, canned, dried, dehydrated, pickled),
**composition** (unsweetened, low sodium, light, lowfat, with oats, syrup pack) and
**dish-ness** (`Soup, …`, `…sauce`, `Crisp, berry`, `Sushi roll`).

### 1.3 Label semantics

`substitutable = 1` **iff** both of the following hold:
1. the USDA food can replace the ingredient **without changing preparation**, and
2. a diner would **not notice a difference in taste, texture, or appearance**.

The target labels come from the production substitutability judge in
`usda-judge/backend/rerun_subjudge.py` (from line 35). The prompt below is quoted from the data
owner's email; the backend file itself is not in this repo:

```python
def substitutability_prompt(ingredient: str, usda_match: str) -> str:
    return (
        f'You are evaluating whether a USDA food database entry is an acceptable match '
        f'for a recipe ingredient.\n\n'
        f'Ingredient: "{ingredient}"\n'
        f'USDA match: "{usda_match}"\n\n'
        f'A match counts as "substitutable" if and only if BOTH conditions hold:\n'
        f'  1. It could be used in place of the ingredient without changing how the dish is prepared.\n'
        f'  2. A person eating the dish would not notice any difference in taste, texture, or appearance.\n\n'
        f'If the match would alter cooking method, change the dish\'s flavour, texture, or appearance, '
        f'or if a diner would notice they were eating something different, it is not substitutable.\n\n'
        f'Reason through whether both conditions are met. '
        f'Reply with JSON only, no markdown:\n'
        f'{{"reasoning": "<step-by-step analysis>", "substitutable": true_or_false}}'
    )
```

**What this means for generation:**
- **The judge sees only two strings.** It sees `ingredient` and `usda_match`, and never
  `other_candidates`. So `other_candidates` costs nothing to use as a source of *real* near-miss
  USDA entries (Stage C), and it is never a label leak.
- **The judge sees the raw ingredient, gram prefix included** (`"30g olive oil"`). Stage E1 must send
  the exact stored string, quantity and all, or the labels will drift from production.
- **The prompt contains no specificity rules.** Rules like "generic → default" and the strictness
  on unspecified variants (§2) emerge from "would not notice *any* difference". They are not
  instructions in the prompt. So the generator's intended label is only a guess, and
  **the judge label is the ground truth**.
- **Rows marked "Confirmed from API run (broq7p7y0)"** (the first six rows of the source CSV) were
  produced by an agent, not by this prompt. Re-label them with the prompt before using them as
  precedents or few-shot examples. Several of the same pairs appear in the 943-row set, e.g.
  `garlic paste (from tube) → Garlic sauce` ×18.
- **Human labels are secondary** (the data owner says they are "not too important"). That supports
  `judge_label` as the target. The human gold subset (§9) can be smaller, and it serves only as a
  sanity check.
- **The email does not state the model or temperature.** The repo docs assume `gpt-oss-120b` on Groq
  at temperature 0. Confirm both in `rerun_subjudge.py` before running E1.

The source CSV columns `judge_correct` through `_run` belong to a different judge (the reranker
judge). Ignore them.

---

## 2. Label policy — written rules with precedents

The generator needs explicit rules, and so does the reviewer. These are reverse-engineered from
the judge's actual decisions on the 350 unique pairs.

### 2.1 Positive patterns (label = 1)

| Code | Rule | Real precedents |
|---|---|---|
| P1 exact | Same food, same or neutral state | `honey → Honey`, `soy sauce → Soy sauce` |
| P2 reorder | USDA inverted word order | `black pepper → Spices, pepper, black`, `feta cheese → Cheese, feta` |
| P3 trivial prep | Cut, fresh, ripe or melted differences that a cook applies trivially | `fresh diced onion → Onions, raw`, `melted butter → Butter, without salt` |
| P4 matched preservation | Ingredient preservation + post-prep agrees with USDA state | `frozen mango chunks, thawed → Mango, frozen`, `canned mushrooms, drained → Mushrooms, canned, drained solids` |
| P5 generic → default | Unqualified ingredient maps to the regular/default variant | `milk → Milk, whole`, `sour cream → Sour cream, regular`, `olive oil → Oil, olive, salad or cooking` |
| P6 synonym / taxonomy | Different words, same food | `zucchini → Squash, summer, zucchini…`, `fresh mint → Spearmint, fresh`, `shredded purple cabbage → Cabbage, red, raw`, `mayo → Mayonnaise, regular` |
| P7 brand of generic | Branded entry of the same plain product | `firm tofu → HOUSE FOODS Premium Firm Tofu` |
| P8 irrelevant note | Optional/garnish notes ignored | `heavy cream (optional) → Cream, fluid, heavy whipping` |

### 2.2 Negative patterns (label = 0)

| Code | Rule | Real precedents |
|---|---|---|
| N1 unrelated | Retrieval junk, different food entirely | `frozen kale, thawed → Oil, teaseed`, `breadcrumbs → Popover` |
| N2 sibling food | Same category, different food | `chia seeds → Seeds, flaxseed`, `duck breast → Chicken breast…`, `cheddar → Cheese, parmesan` |
| N3 sibling blend | Different spice blend or seasoning | `garam masala → Spices, curry powder`, `Italian seasoning → Spices, poultry seasoning` |
| N4 dish / product containing it | USDA is a dish or derived product | `mixed berries → Crisp, berry`, `spaghetti → Spaghetti sauce`, `red lentils → Lentil curry`, `beet → Beet juice` |
| N5 lexical trap | A shared word with a different meaning | `ice → Italian Ice`, `cherry tomatoes → Maraschino cherries`, `baby potatoes → Babyfood, potatoes`, `diced potato → Bread, potato` |
| N6 cooking-state mismatch | Raw ingredient → cooked, baked, fried or grilled USDA | `penne pasta → Pasta, cooked`, `fresh salmon fillet → Fish, salmon, baked or broiled`, `fresh mushrooms → Fried mushrooms` |
| N7 physical-form mismatch | paste↔sauce, ground↔seed, flakes↔powder, fresh↔dried, whole↔chopped, fresh↔dehydrated | `garlic paste → Garlic sauce`, `cumin → Spices, cumin seed`, `chili flakes → Spices, chili powder`, `diced carrot → Carrot, dehydrated` |
| N8 preservation mismatch | jarred, frozen or canned ↔ raw/fresh, or a different processed form | `jarred minced garlic → Garlic, raw`, `frozen grated ginger → Ginger root, raw`, `zucchini → Zucchini, pickled` |
| N9 non-default variant | Generic ingredient → a *specific non-default* composition | `almond milk → Almond milk, unsweetened`, `cream cheese → Cream cheese, light`, `Greek yogurt → …plain, lowfat`, `fresh ground turkey → …fat free` |
| N10 flavor/process modifier | Smoked, toasted, sweetened, salted or oil-added differences | `smoked paprika → Spices, paprika`, `toasted almonds → Almonds, unroasted`, `canned jackfruit → …syrup pack` |
| N11 variety mismatch | A specific variety → a different or generic variety where it matters | `jasmine rice → Rice, white, cooked, glutinous`, `arborio → long grain`, `kalamata olives → Olives, black`, `Dijon mustard → Mustard`, `rice vinegar → Vinegar` |
| N12 partial composite | A composite ingredient → one component | `Salt and pepper → Salt, table`, `canned peas and carrots → Green peas, canned` |
| N13 liquid vs prepared | broth ↔ soup/bouillon, paste ↔ sauce-ready | `vegetable broth → Soup, vegetable broth, ready to serve`, `vegetable broth → Vegetable broth, bouillon` |

### 2.3 Known inconsistencies, to resolve before generation

The current judge is inconsistent on near-identical cases. Decide each rule explicitly and write it into the generator and reviewer prompts:

| Case | Observed labels | Decision needed |
|---|---|---|
| Cut words | `diced carrot → Carrots, raw` = **1**, but `shredded carrot → Carrots, raw` = **0** | Is a cut always trivial (P3)? |
| Generic herb | `thyme → Spices, thyme, dried` = 0 **and** `thyme → Thyme, fresh` = 0 | Does an unspecified fresh/dried herb map to anything? |
| Cut + nuts | `walnuts → Nuts, walnuts, english` = 1, but `chopped walnuts → …same` = 0 | Is a cut trivial for nuts? |
| Chicken part | `fresh chicken breast → …boneless, skinless, raw` = 1, but `fresh chicken thighs → …same pattern` = 0 | Does skin/bone matter? |
| Raw → cooked | `penne → Pasta, cooked` = 0, but `frozen corn kernels → Corn, frozen, cooked` = 1 | Is the raw-to-cooked rule strict? |
| Human disagreement | almond milk/unsweetened, tomato salsa/pico de gallo, vegetable broth/ready-to-serve soup | Is the target the strict judge or human intuition? |

**Recommendation:** keep three labels per row (§7). **`judge_label`** is the PAJAMA
distillation target. **`policy_label`** is the adjudicated label under your written rules.
**`human_label`** is filled on the gold subset. The inconsistent cases above become the
**T5 policy-boundary tier**, where they are measured, not hidden.

---

## 3. Coverage taxonomy

### 3.1 Food families (12) and quotas, for 2,000 unique pairs

| Family | Examples of core foods | Pairs |
|---|---|---|
| F1 Vegetables | onion, carrot, spinach, bell pepper, potato, mushroom, cabbage | 240 |
| F2 Fruits | apple, mango, berries, citrus, banana, avocado, coconut | 140 |
| F3 Herbs, spices, blends | thyme, cumin, paprika, garam masala, taco seasoning | 220 |
| F4 Oils & fats | olive/sesame/vegetable oil, butter, ghee, lard | 100 |
| F5 Dairy, eggs, plant milks | milk, cheeses, yogurt, cream, eggs, almond/oat milk | 200 |
| F6 Meat | beef cuts, pork, lamb, ham, bacon, sausage | 140 |
| F7 Poultry | chicken parts, turkey, duck, ground poultry | 110 |
| F8 Seafood | salmon, tuna, cod, shrimp, prawns, seaweed | 130 |
| F9 Grains, pasta, noodles, bread | rice types, pasta shapes, noodles, oats, flour, breadcrumbs | 200 |
| F10 Legumes, nuts, seeds, soy | lentils, chickpeas, beans, tofu, nuts, chia, tahini | 170 |
| F11 Condiments, sauces, pastes, dressings | soy sauce, miso, salsa, pesto, curry paste, mustard | 200 |
| F12 Broths, beverages, vinegars, sweeteners, baking | broth, wine, juice, vinegar, honey, sugar, baking powder | 150 |

Add cuisine diversity as a soft constraint, with at least 25% non-Western core foods
(gochujang, dashi, paneer, tamarind, nori, injera, harissa…). Production recipes are
diverse, and today's data underrepresents them.

### 3.2 Relation types × label

Use every P-code and N-code from §2 as a quota cell. Suggested split of the 1,000 positives and
1,000 negatives:

- **Positives:** P1 8%, P2 15%, P3 20%, P4 15%, P5 15%, P6 17%, P7 5%, P8 5%.
- **Negatives:** N1 6%, N2 12%, N3 5%, N4 10%, N5 7%, N6 12%, N7 12%, N8 8%, N9 9%, N10 7%, N11 7%, N12 3%, N13 2%.

N1 (junk) is kept deliberately small. It is easy and already over-represented today.

---

## 4. Difficulty tiers — defined, measurable, and balanced

| Tier | Share | Positive looks like | Negative looks like | Measurable criterion |
|---|---|---|---|---|
| **T1 trivial** | 10% | P1 exact (`honey → Honey`) | N1 unrelated (`kale → Oil, teaseed`) | Jaccard ≥ 0.8 for positives, = 0 for negatives |
| **T2 easy** | 20% | P2/P3 reorder, trivial cut | N2/N4 sibling or dish with low overlap | Overlap agrees with the label |
| **T3 medium** | 30% | P4/P5 preservation-matched, generic → default | N6/N7/N8 one state or form attribute differs | Exactly **one** attribute decides the label |
| **T4 hard** | 30% | P6/P7 **low-overlap** positives (synonyms, taxonomy, brand) | N9/N10/N11/N5 **high-overlap** negatives (`smoked paprika → Spices, paprika`) | Overlap is **anti-correlated** with the label |
| **T5 policy-boundary / adversarial** | 10% | Cases a strict judge accepts that look risky | Composites (N12), N13, and the §2.3 inconsistencies | Two LLM reviewers disagree, or the judge disagrees with the design intent |

**Balance:** each tier is 50/50 positive/negative, and each family × tier cell is within
±10 points of 50%. Then neither tier nor family can predict the label.

**Overlap decorrelation (the key fix).** Within each label, the distribution of token Jaccard
should be roughly matched. Concretely:
- The overlap-only baseline AUC on the full set should be **≤ 0.65**, compared with 0.779 today.
- Within T4 it should be **≤ 0.40**, because T4 is adversarial by construction.

**Post-hoc verification.** After generation, run the existing 80 programs and the committee.
Error rate should rise monotonically from T1 to T5. If a tier is not harder than the tier below
it, its quota cells are mislabeled, so re-tier or regenerate them.

---

## 5. Uniqueness and anti-duplication rules

1. **Canonical key.** Lowercase both strings, strip the quantity (`^\d+(\.\d+)?\s*g`), collapse
   whitespace and punctuation, and singularize simple plurals. **At most one row per canonical
   `(ingredient, usda_match)` key**, with no exceptions.
2. **Quantity is decoration.** Sample one realistic gram weight per row from a per-family
   distribution (spices 1–10g, liquids 100–1000g). Never emit the same pair at two quantities.
3. **Core-food contrast sets.** Each core food (e.g. `onion`) has **2–4 pairs**, ideally with at
   least one positive and at least one negative. The same ingredient then maps to a good and a
   bad USDA entry, so ingredient identity cannot predict the label. About 900 core foods × ~2.2
   pairs gives about 2,000.
4. **Caps.** Each core food gets ≤ 4 pairs. Each exact USDA string gets ≤ 3 uses. Each surface
   ingredient string appears in ≤ 4 pairs, and only within its own contrast set.
5. **Near-duplicate filter.** Use character-trigram Jaccard ≥ 0.85, or embedding cosine ≥ 0.95
   (BGE-m3 is already in the backend), between two ingredient strings of *different* core foods.
   Reject or merge.
6. **Surface diversity.** Within a family, no single template (e.g. `fresh X`) should exceed 20%
   of strings. Track the slot pattern from §1.1 per row.
7. **Group ID.** Every row carries `core_food_id`. All splits group by it (§9), which is stricter
   than today's per-pair grouping.

---

## 6. Robustness slice (linked variants, separate from the core set)

Generate about **600 variants** from **test-split core foods only**. Each variant points at its
parent via `variant_of`. Variants are **never** used for fitting. They measure invariance and
sensitivity.

**Label-preserving perturbations (expect the same label):**

| Type | Example |
|---|---|
| Case and punctuation | `Fresh Diced Onion`, `onion - diced` |
| Plural / singular | `garlic clove` ↔ `garlic cloves` |
| One-edit typo | `cinamon`, `parmesean` |
| Abbreviation / slang | `EVOO`, `AP flour`, `scallion` ↔ `green onion` |
| Other units | `2 tbsp`, `1 cup`, `1 large`, `a pinch of` |
| Filler words | `organic`, `good-quality`, `about`, `plus more for serving` |
| Parenthetical | `(divided)`, `(for garnish)`, `(about 2 cloves)` |
| Reordering | `onion, finely diced` |

**Label-flipping minimal pairs (expect the label to change):** add or remove exactly one decisive
attribute. Examples: `paprika → smoked paprika`, `almond milk → sweetened almond milk`,
`pasta → cooked pasta`, `garlic → garlic paste`, `salt → salt and pepper`.

**Metrics:** invariance rate (the same label on preserving variants) and flip rate (the correct
change on flipping variants), reported per perturbation type.

---

## 7. Generation pipeline (stages, LLM calls, prompts)

```
A. core-food inventory ─▶ B. surface strings ─▶ C. USDA candidates (retrieve real FDC)
        ─▶ D. pick pos/neg per relation code ─▶ E. label (prod judge + reviewer)
        ─▶ F. QA / dedup / re-tier ─▶ G. quota sampling ─▶ H. grouped splits ─▶ I. robustness
```

### Stage A — Core-food inventory (~50 calls)

Per family × cuisine cell, ask for about 40 distinct core foods. Each comes with its common
forms, varieties, and the processed or dish products it is confused with. Dedupe across calls
with the canonical key and embeddings. **Block-list** the core foods used in the 10 synthesis
few-shot examples, and in a reserved set of real-data cores (§9.3).

```text
You are building a taxonomy of recipe ingredients for family: {family}, cuisine focus: {cuisine}.
Return JSON: [{"core_food": "...", "varieties": [...], "forms": ["fresh","frozen","canned","dried",...],
"confusable_products": [...], "sibling_foods": [...]}]
Rules: 40 items; no item from this exclusion list: {already_seen}; prefer foods a home recipe would list.
```

### Stage B — Recipe-style surface strings (~60 calls)

Fill the §1.1 slots with a planned slot pattern per string (assigned in code, not chosen by the
LLM). This controls surface diversity. The LLM only makes each string natural.

```text
For each spec, write ONE natural recipe-ingredient line (no quantity; we add it).
Spec: {"core_food":"onion","form":"frozen","prep":"diced","post_prep":"thawed","note":null}
Return JSON list of strings, same order.
```

### Stage C — USDA candidates, grounded in real FDC (no LLM)

Download FoodData Central (SR Legacy + FNDDS + Foundation, plus a small branded sample). For
each ingredient, retrieve the **top-20 candidates** with the backend's retriever (BGE-m3 or
lexical). This mirrors production: the real CSV has an `other_candidates` column for exactly this
reason. Retrieval naturally surfaces realistic near-misses.

### Stage D — Pick positives and negatives per relation code (~1,100 calls)

Make one call per core-food contrast set. Give the model the ingredient, the 20 real candidates,
the policy table (§2) and the **requested relation codes** from the quota planner (e.g. "1×P4, 1×N7").
The model must **choose from the candidate list**. Only if no candidate fits may it write a
USDA-style string, flagged `synthetic_usda=true`, with a cap of ≤ 15% of rows.

```text
Policy: {rules P1-P8, N1-N13 with precedents}
Ingredient: "{ingredient}"
Candidates (real USDA): 1. ... 20. ...
Select candidates for these slots: {slots, e.g. [{"want":"P4"},{"want":"N7"}]}
Return JSON: [{"slot":"P4","candidate_index":k | null,"synthetic_usda":null|"...",
"intended_label":1,"decisive_attribute":"preservation","rationale":"<1 sentence>"}]
```

**Use at least two generator model families**, alternated by family, so one model's lexical
habits don't become a learnable artifact.

### Stage E — Labeling (two labelers + adjudication)

1. **`judge_label`.** Run `substitutability_prompt(ingredient, usda_match)` from §1.3 **verbatim**
   on every pair, with the full stored ingredient string including its gram prefix. Use the
   production model and temperature, to be confirmed in `rerun_subjudge.py`. Parse
   `{"reasoning", "substitutable"}`, store the reasoning as `judge_reasoning`, and re-ask on
   malformed JSON. This is the distillation target. Re-run on 10% to measure
   self-consistency, with a target of ≥ 97%.
2. **`review_label`.** An independent model from a different family, given the written policy
   and **not** told the intended label. It returns a label, a reason code and a confidence.
3. **Agreement logic:**
   - If `intended == judge == review`, accept.
   - If `judge ≠ intended`, keep the row, set `boundary_flag`, and send it to the adjudication
     queue. These seed T5.
   - If junk or schema-invalid, drop it.
4. **`policy_label`.** Set it by adjudication, either a third LLM pass or a human for all test
   rows that disagree.
5. **`human_label`.** Required on the **gold test subset** (§9). Use two annotators and report
   kappa.

**Balance on `judge_label`, not on the intended label.** Generate about 25% more than needed,
because some intended labels will flip.

### Stage F — Automated QA

- Schema validity: 100%.
- Canonical-key duplicates: 0.
- Caps from §5 are enforced.
- Near-duplicate filter applied.
- USDA string exists in FDC, unless flagged `synthetic_usda`.
- Ingredient contains its declared core food or a synonym.
- **Re-tier from measured overlap.** Compute Jaccard and assign the tier from the §4 criteria;
  where a cell disagrees with the planned tier, the measurement wins.
- **Leakage check.** No overlap with the few-shot core foods or the reserved real cores.

### Stage G — Quota sampling

Sample from the QA'd pool to hit the family × tier × label × relation quotas, with a tolerance of
±3 points on overall balance. Report any cell below its quota.

---

## 8. Output schema (JSONL)

`pipeline.py` only reads `ingredient`, `usda_match` and `label`. The extra fields are ignored by
it but used for slicing.

```json
{
  "id": "sub-000123",
  "ingredient": "200g frozen diced onion, thawed",
  "usda_match": "Onions, frozen, chopped, unprepared",
  "label": 1,
  "judge_label": 1, "review_label": 1, "intended_label": 1, "policy_label": 1, "human_label": null,
  "judge_reasoning": "...", "review_confidence": 0.9,
  "core_food": "onion", "core_food_id": "F1-onion", "family": "F1",
  "relation_code": "P4", "decisive_attribute": "preservation", "tier": "T3",
  "slot_pattern": "form+prep+core+post", "jaccard": 0.4,
  "synthetic_usda": false, "fdc_source": "SR_Legacy", "boundary_flag": false,
  "variant_of": null, "perturbation": null,
  "split": "fit", "generator_model": "...", "source_batch": "D-0042"
}
```

`label` = `judge_label`, so `run.py` and `pipeline.py` work unchanged.

---

## 9. Splits (grouped by `core_food_id`, stratified by family × tier × label)

### 9.1 Synthetic core set: 2,000 unique pairs

| Split | Pairs | Purpose |
|---|---|---|
| `fewshot` | 60 | The only pool used to sample program-synthesis examples. |
| `fit` | 700 | Thresholds, program selection and the Snorkel fit. That is 10× today's 70 effective pairs. |
| `router` | 500 | Disjoint training set for the router. At ~25% committee error that is about 125 errors, against 22 today. |
| `test` | 740 | Final reporting, including a **gold subset of 250** with human labels. |

### 9.2 Robustness set

About 600 variants of test-split pairs (§6), for evaluation only.

### 9.3 Real-data check (synthetic → production transfer)

Keep the existing **350 real unique pairs** as an external test. Before Stage A, reserve about
100 of their core foods (e.g. salt, olive oil, garlic) as a **block-list** so generation never
touches them. Report results on the real set split into seen-core and unseen-core subsets.
**Synthetic gains count only if they also appear on the real set.**

### 9.4 Evaluation convention

Report **pair-level** metrics (each unique pair counts once) and group-bootstrap CIs. Also report
results per tier, family, relation code and perturbation type.

---

## 10. Budget (tokens and calls)

| Stage | Calls | Input tokens | Output tokens |
|---|---|---|---|
| A inventory | ~50 | 50k | 150k |
| B surface strings | ~60 | 90k | 60k |
| D pick candidates (2,500 pairs incl. 25% oversample, ~1,100 contrast sets) | ~1,100 | 2.2M | 450k |
| E1 production judge (2,500 core + 600 variants + 10% re-runs) | ~3,400 | 1.1M | 1.0M |
| E2 reviewer (batched 10/call) | ~310 | 600k | 300k |
| E4 adjudication (~20% disagreements) | ~60 | 120k | 60k |
| I robustness variants | ~60 | 60k | 60k |
| **Total** | **~5,000** | **~4.2M** | **~2.1M** |

The production-judge pass on `gpt-oss-120b` comes to about **$1** at the Groq rates assumed in
`PROGRAM_IMPROVEMENT_AND_ROUTING.md`. Stages A–D and E2 depend on the models you choose: multiply
the token counts by current list prices. With 10 concurrent workers the API time is under an hour.
The real cost is human time on the 250-row gold subset plus test disagreements, about 4–6 hours
for two annotators.

---

## 11. Acceptance gates (is the dataset good?)

| Gate | Target |
|---|---|
| Unique canonical pairs | 100% (0 duplicates) |
| Overall label balance | 50% ± 3 |
| Balance per family and per tier | 50% ± 10 |
| Overlap-only baseline AUC | ≤ 0.65 overall, ≤ 0.40 on T4 (today 0.779) |
| Production-judge self-consistency | ≥ 97% |
| Judge ↔ reviewer agreement | Reported per tier. Expect high on T1–T2 and lower on T4–T5. |
| Human kappa (gold subset) | ≥ 0.7 |
| Committee error rate by tier | Monotonic T1 < T2 < T3 < T4 ≤ T5 |
| Rows with `synthetic_usda` | ≤ 15% |
| Every relation code | ≥ 20 pairs in `test` |

---

## 12. Pilot first

Run the full pipeline on **2 families × all tiers ≈ 150 pairs** before scaling.
- Check the gates.
- Read 50 rows by hand.
- Fix the prompts and policy wording.
- Then scale.

Most failures show up here: generator bias toward positives, synthetic-looking USDA strings, and
tiers that are not actually harder.

## 13. Decisions needed from you

1. **Target label.** Is it the strict production judge (`judge_label`, recommended as the PAJAMA
   target) or the adjudicated `policy_label`? This also settles the §2.3 inconsistencies.
2. ~~Recover the production prompt.~~ **Done.** It is in §1.3, from the data owner's email. Still
   open: confirm the judge **model and temperature** in `rerun_subjudge.py`, and obtain the backend
   zip if you want to reuse its retriever (decision 3).
3. **FDC retrieval.** Reuse the backend retriever and index (preferred), or build a lexical index here?
4. **Generator and reviewer models**, and whether at least two model families are available.
5. **Scale.** 2,000 core pairs is the plan. Go to 4,000 if the router or a learned aggregator
   needs more errors.
6. **Pairwise conversion** (from the docx) for upstream PAJAMA. It is still possible from the
   contrast sets (one positive and one negative per core food), but optional.
