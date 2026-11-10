# Substitutability Set Audit: data_synth_v2

Audit date: 10 Nov 2026. Scope: 4,179 synthetic ingredient → USDA pairs (plus 163 robustness variants). A random sample of 1,500 rows was checked in depth. EDA covers the full set.

Saved files (in `data_synth_v2/audit_1500/`): `sample_1500_labels.csv` (every sampled row with planned, Haiku and blind labels plus verdict) and `metrics.json` (every number below).
Published version of this report: https://claude.ai/artifact/7NTjKe7KShzL9xPDJpCkk7

## 1. Verdict

The data is structurally clean and the Haiku labels are good enough to train on, but it should not be used as is.

1. **The `label` column still holds the generator's plan, and about 9% of those labels are wrong.** The Haiku v3 labels must be merged in first (still pending).
2. **Haiku is slightly too strict.** Of 17 confirmed Haiku mistakes in the sample, 15 say "no" to an acceptable pair. Most come from misreading standard USDA wording such as `trimmed to 0" fat` or `bone removed`.
3. **The set does not yet look like the real data.** Real pairs are 71.2% yes; this set is 46.9% yes. Ingredient lines and USDA names are longer than real ones, and the word "frozen" points toward yes here but toward no in the real data.

The hard tier does its job: a word-overlap rule gets it wrong more often than right (AUC 0.38). The easy tier is too easy and too negative.

### Headline numbers

| Measure | Value |
|---|---|
| Haiku v3 labels right after review (n = 1,500) | 97.1% (95% CI 96.1–97.8) |
| Haiku wrong | 17 rows, 1.1% (CI 0.7–1.8) |
| Haiku ambiguous (defensible either way) | 27 rows, 1.8% |
| Raw agreement Haiku vs blind review | 95.6% (CI 94.4–96.5), κ 0.912 |
| Generator's planned labels flagged by Haiku | 135 rows, 9.0% |
| Planned labels confirmed wrong by Haiku and blind review | 101 rows, 6.7% |
| Plan checks | 10 pass, 5 miss, 2 partial of 17 |
| Borderline pairs in the sample | 243, 16.2% |

## 2. Method

- **Sample:** 1,500 rows drawn at random from `all.jsonl` (seed 1500). Tier, split, source and cuisine shares are within 1.7 points of the full set.
- **Label check:** I labelled all 1,500 pairs from the two strings only, without seeing any existing label, using the production prompt's two conditions (usable without changing preparation; a diner would not notice a difference). I marked 243 as borderline. I compared with the Haiku v3 labels and read Haiku's reasoning for each of the 66 disagreements to decide who was right: HW (Haiku wrong), HR (Haiku right, my blind label wrong), AMB (defensible either way).
- **Two readings of "check the labels by Haiku":** (a) are the Haiku judge labels right; (b) are the generator's planned labels right, using Haiku as the checker. Both are reported.
- **No new spend.** No API calls were made. PAJAMA was not run; committee figures use the stored `committee_p` values.

**Limits**

- One reviewer, and it is a model (me), not a human. Rows where Haiku and I agree (1,434) were not re-examined, so shared mistakes would not show up.
- My blind labels were uneven on dried fruit against "dehydrated" entries, sweetened soy milk, industrial oils and toasted breads. On 167 rows labelled in earlier passes my labels matched 163 times (97.6%).
- Cause labels for generator errors are assigned by rule from pair type and wording, so single rows can be miscategorised.
- The committee error uses a 0.5 cut-off that I chose.

## 3. Plan checks

Labels are Haiku v3 unless stated.

| Check | Target | Sample (1,500) | Full set (4,179) | Result |
|---|---|---|---|---|
| Exact duplicate pairs | 0 | 0 | 0 | Pass |
| Foods shared between splits | 0 | – | 0 of 1,588 | Pass |
| Overall yes-share | 50% ± 3 | see EDA | 46.9% (planned 45.9%) | Miss (3.1 off) |
| Yes-share per tier | 50% ± 10 | – | easy 39.5 / medium 53.1 / hard 47.9 / edge 48.8 | Miss (easy by 0.5) |
| Word-overlap AUC | ≤ 0.65 | – | 0.732 (easy 0.923, medium 0.836, hard 0.383, edge 0.619) | Miss |
| Judge gives same answer twice | ≥ 97% | 70 of 74 | 197 of 208 (94.7%) | Miss |
| Committee error rises easy < medium < hard ≤ edge | ordered | – | 21.6 / 22.6 / 55.9 / 42.6 | Partial (edge below hard) |
| Pairs of each type in test | ≥ 15 | – | 21 of 22 types; G9 has 13 | Miss |
| USDA strings not found in FDC | ≤ 15% | – | 0.5% | Pass |
| Pairs per food | ≤ 4 | – | 47 of 1,588 foods over (max 12, "turkey") | Miss |
| Uses per USDA string | ≤ 3 | – | 78 of 2,935 over (max 11, "Oil, olive, salad or cooking") | Miss |
| Non-Western foods | ≥ 25% | – | 27.2% | Pass |
| Tier mix easy / medium / hard / edge | 30/30/30/10 | – | 31.7 / 31.5 / 29.0 / 7.8 | Pass |
| Split sizes (few-shot / fit / router / test) | 40/1,400/1,000/1,560 | – | 58 / 1,456 / 1,041 / 1,624 | Pass |
| Overlap with real evaluation pairs | no shared foods | – | 0 blocked foods, 0 shared pairs | Pass |
| Robustness variants | about 200 | – | 163 | Partial |
| Rows set aside for hand labelling | 150 | – | 151 | Pass |

Note: 60 ingredient lines (1.4%) also occur in the real files, and 6.4% of USDA strings appear in real data, though no pair does.

## 4. Full-set EDA (4,179 rows)

4,179 pairs from 1,588 foods and 2,935 distinct USDA entries, all written by one generator model.

- **Tiers:** easy 31.7%, medium 31.5%, hard 29.0%, edge 7.8%. The mix is the same in every split. No food, group or ingredient line crosses splits.
- **Yes-share by tier (Haiku vs planned):** easy 39.5%; medium 53.1%; hard 47.9%; edge 48.8% (edge was planned at about 37% yes).
- **Families:** the five `topup_*` families were added late to fill gaps. Haiku overturns 12–25% of their planned labels (topup_mod2 25.4%, topup_mod 21.9%, topup_syn 21.8%, topup_variant 21.7%) against 4–9% for main families.
- **USDA source:** synthetic SR Legacy 58.1%, FNDDS 34.5%, Foundation 7.4%. Real data is 49% / 34% / 15%, so Foundation is under-used. Overturn rate: SR Legacy 10.3%, FNDDS 6.5%, Foundation 6.1%.
- **Cuisine:** non-Western foods are 27.2% of all rows.
- **Length:** ingredient lines average 2.88 words here, 2.23 in real data. USDA entries 4.80 vs 3.11. One-word ingredient lines are about 7% here vs 22% real.
- **Word overlap and label:** above Jaccard 0.7, nearly every pair is yes (510 of 528).
- **Reuse:** 47 foods exceed 4 pairs, 78 USDA entries exceed 3 uses, largest group 50 rows.
- **Robustness variants:** 163 variants. When a typo, unit or filler word was added, Haiku kept its label on 82 of 84 (97.6%). When the generator edited a pair to flip the label, Haiku flipped on only 55 of 79 (69.6%). The 24 that did not flip are a mix of weak edits and judge misses.
- **Planned vs Haiku labels:** agree on 3,816 of 4,179 (91.3%), κ 0.825; 203 planned-no became yes, 160 planned-yes became no. Overturn rate by tier: easy 1.7%, medium 10.1%, hard 12.4%, edge 17.6%.
- **Overturn hot spots by pair type:** E2 40%, B8 23.7%, G8 23.5%, B7 21.8%, G7 14.1%, G6 12.7%, B10 12.2%, G9 12.2%, B6 9.7%; B1 and B4 0%.
- **Other label sources:** gpt-oss vs Haiku 309/344 (89.8%, κ 0.794); generation-time reviewer vs Haiku 3,370/3,546 (95.0%).
- **Committee error vs Haiku label, by tier:** easy 21.6%, medium 22.6%, hard 55.9%, edge 42.6%. The committee's AUC on hard pairs is 0.42, below chance.

## 5. Checks beyond the plan

### 5.1 Surface-feature shortcuts

AUC of logistic regression models that never compare the two foods, 5-fold grouped by food:

| Features | This set (Haiku labels) | Real data |
|---|---|---|
| Ingredient text only | 0.604 | 0.681 |
| USDA text only | 0.640 | 0.566 |
| Quantity only | 0.524 | 0.429 |
| Word overlap only | 0.732 | 0.762 |
| Length + overlap stats | 0.736 | 0.762 |
| All lexical | 0.826 | 0.837 |

Quantity carries no signal, which is right. Overlap statistics lead to 0.73 and all lexical features to 0.83. Real data has the same weakness at about the same level, so the set is no easier than reality, but the 0.65 target is missed. Inside the hard tier, high overlap means "no" (AUC 0.38): a model could learn that reversal as a new shortcut.

### 5.2 Words that tilt the label

Shift in yes-share relative to the 46.9% base, for words in at least 40 rows:

- Ingredient words: "cooked" +24.6, "(optional)" +21.4, "frozen" +12.5, "toasted" +11.5, "thawed" +11.4, "smoked" −16.4, "dried" −10.6.
- USDA words: "reduced" −35.7 (11.2% yes), "includes" +29.8, "ready" +20.1, "raw" +11.2, "low" −11.0.
- **Reversed direction vs real data:** in real data, "frozen" −30.2, "canned" −21.2, "thawed" −18.8, "fresh" +16.8. Here "frozen" is +12.5 and "fresh" is −0.1.

### 5.3 Resemblance to real data

| Property | This set | Real data |
|---|---|---|
| Rows / distinct pairs | 4,179 / 4,179 | 943 / 350 |
| Share labelled yes | 46.9% | 71.2% |
| Ingredient words per line | 2.88 | 2.23 |
| USDA words per entry | 4.80 | 3.11 |
| Ingredient lines with a comma | 21.8% | 9.0% |
| Ingredient lines with parentheses | 3.9% | 2.3% |
| Grams p10 / p50 / p90 | 10 / 110 / 400 | 5 / 50 / 400 |
| Quantities that are multiples of 5 g | 94.8% | 94.9% |
| Real ingredient tokens covered by this set's vocabulary | 93.3% (types 87.1%) | – |
| Real USDA word types covered | 92.3% | – |
| Domain classifier AUC (0.5 = identical) | 0.773 on pair text, 0.728 on ingredient | – |

Transfer proxy: a lexical model trained on this set (Haiku labels) ranks real pairs at AUC 0.800 (planned labels 0.786); a model trained on real data scores 0.824 in cross-validation. At a fixed 0.5 cut-off the synthetic-trained model scores 66.9%, below the 71.2% from always answering yes, because the two sets have different yes-shares. Any threshold fitted here needs recalibrating on real pairs.

### 5.4 Near-duplicates, contrast structure, diversity

- Exact duplicates: none. Near-duplicates (pair-text Jaccard ≥ 0.8) touch 15.1% of rows; at ≥ 0.9, 4.8%. Most are deliberate contrast pairs with opposite labels (e.g. `chestnuts → Flour, chestnut` beside `chestnut flour → Chestnuts`).
- 3.3% of test rows have a near-duplicate in the training splits.
- Contrast: 717 of 851 multi-row groups contain both a yes and a no (84.7% of rows). 498 of 849 reused USDA entries appear with both labels; 986 of 1,184 multi-pair foods have both labels. This is the strongest property of the set.
- Diversity: 86.2% of ingredient strings and 70.2% of USDA strings are unique. The top-10 first words cover 25% of rows ("fresh" 5.6%, "dried" 3.9%). Frequent parenthetical tags: optional 59, optional garnish 15, for serving 15, for garnish 14, divided 12.

### 5.5 Ambiguity

- 16.2% of sampled pairs are borderline. Borderline share by tier: easy 5.2%, medium 16.6%, hard 24.6%, edge 25.9%. By code: E2 55.6%, B8 38.1%, B10 34.2%.
- Haiku gave a different answer on 11 of 208 repeated calls (94.7% stable). In the sample, 3 of the 4 repeated rows that were also in the disagreement set changed label on the repeat, so instability and ambiguity are largely the same rows.

### 5.6 Agreement between label sources (sample, % agreement)

| Pair | Agreement | κ |
|---|---|---|
| Planned – Haiku | 91.0 | 0.818 |
| Planned – blind | 91.1 | 0.822 |
| Planned – generation-time reviewer (n 1,270) | 93.5 | 0.868 |
| Haiku – blind | 95.6 | 0.912 |
| Haiku – reviewer | 94.4 | 0.886 |
| Blind – reviewer | 95.3 | 0.905 |
| gpt-oss (n 127) vs Haiku / blind / planned | 92.1 / 91.3 / 89.8 | – |

## 6. Label check A: are Haiku's 1,500 labels right?

Of the 1,500: 1,434 agreed with the blind review (95.6%). Of the 66 disagreements: 22 were my mistakes (Haiku right), 17 were Haiku's, 27 are ambiguous.

| Slice | Right after review | Wrong | Ambiguous | Borderline share |
|---|---|---|---|---|
| All rows (1,500) | 97.1% | 17 | 27 | 16.2% |
| Pairs I marked clear (1,257) | blind agreement 98.8% | 12 | – | – |
| Pairs I marked borderline (243) | blind agreement 79.0% | 5 | 25 | – |
| Easy | 98.9% | 3 | 2 | 5.2% |
| Medium | 97.7% | 6 | 5 | 16.6% |
| Hard | 95.2% | 8 | 14 | 24.6% |
| Edge | 94.4% | 0 | 6 | 25.9% |

Weak spots: meat (6 of the 17 wrong labels, 96.0% correct), SR_Legacy source (13 of 17), pair types G6, G5, G3, B9, B10 and E2. Extrapolated to 4,179 rows: roughly 47 wrong Haiku labels (range about 29–75) and about 75 ambiguous.

### 6.1 The 17 wrong Haiku labels

Fifteen are Haiku saying "no" to an acceptable match.

- Over-reading USDA descriptors as modifications ("meat only", "bone removed", trim wording such as `trimmed to 0" fat` called lean-only): rows 113, 637, 728, 937, 1258, 1341.
- Parent or generic entry treated as a different variety or cut: 456, 954, 1047.
- Factual slips: Smart Squeeze is fat-free (300); Kretschmer wheat bran is plain (1055); silk gourd and dishcloth gourd are the same Luffa (578); USDA sweet pickles include bread-and-butter (1010); sliceable liverwurst vs spread (353).
- Other: misread ingredient that ignored "cereal" (386), over-read brand name (512), salt descriptor, where real data treats "without salt" as yes (1151).

(Row numbers are positions in the sample; see `sample_1500_labels.csv` and the appendix.)

### 6.2 The 27 ambiguous pairs

These are gaps in the labelling rules more than judge errors: regional name vs different product, vague ingredient, sweetened-as-default plant milks, "with salt", "dehydrated (low-moisture)", variety→generic, and similar. Haiku also contradicts itself: it accepts `tomato puree → …without salt added` but rejects `sunflower seed butter → …without salt`, and accepts "meat only" for chicken flats but rejects it for shredded fried chicken.

### 6.3 Where my blind label was wrong (22 rows)

In 21 of 22 I said yes and Haiku said no. I was too lenient on generic→specific member (`agave spirit → Tequila`, `eating apple, red → Apples, red delicious`), flavoured→plain, named cut→whole-bird entry, and cooking state. Haiku also caught a false friend I missed: USDA "Currants, dried" are Zante grapes, so dried black currants do not match.

## 7. Label check B: are the generator's planned labels right?

Using Haiku as the checker, 135 of 1,500 planned labels (9.0%) were flagged: 80 planned-no that are really yes, 55 planned-yes that are really no. The blind review sides with Haiku on **101 (6.7%)** (75 no→yes, 26 yes→no) and with the generator on 34. Three-way counts (planned, Haiku, mine): 000 732; 001 27; 010 5; 011 75; 100 26; 101 29; 110 5; 111 601. Planned vs blind agreement is 91.1%.

### Causes of the 101 confirmed errors

| Cause | Rows |
|---|---|
| Raw ingredient paired with cooked entry (planned yes, actually no) | 16 |
| Frozen/thawed treated as a different food | 13 |
| Normal low-fat dairy treated as modified | 13 |
| Knife work or handling treated as a different form | 12 |
| Standard descriptor treated as a modification | 11 |
| Edge case that resolves to yes | 10 |
| Standard USDA cut wording treated as a mismatch | 6 |
| Cooking state actually matches | 5 |
| Planned "different food" turned out to be the same | 5 |
| Claimed synonym is not the same food | 4 |
| Brand entry with extra flavour | 2 |
| Entry adds a modifier | 2 |
| Vague catch-all entry | 2 |

The generator's main fault is building a "bad" pair on a difference that the rules treat as no difference (frozen vs raw, ground or shredded vs whole, flavoured yogurt vs its usual low-fat entry). Its main fault in the other direction is pairing a raw ingredient with a cooked entry and calling it a match.

Confirmed error rate by pair type: E2 33.3%, B8 25.0%, G8 18.2%, B7 17.5%, B6 13.0%. By tier: easy 8 of 463, medium 41 of 469, hard 37 of 460, edge 15 of 108.

The existing `audit_polarity_conflict` flag is useful: of 117 flagged sampled rows, 70 (60%) were overturned, against 65 of 1,383 (4.7%) unflagged. `reviewer_disputed` rows: 82, of which 50 changed.

## 8. What to fix, in order

1. **Merge the Haiku labels into `label`** and keep the planned label in its own column.
2. **Patch the judge guidelines and re-judge affected rows only.** Add rules that USDA refuse and trim wording ("meat only", "bone removed", "separable lean and fat", "trimmed to…") is not a modification; that "with salt" and "without salt" do not change the match; and that a general parent entry accepts a named variety or sub-cut. About 190 rows in the full set contain this wording.
3. **Take a majority of three calls on unstable rows.** Stability is 94.7%. Three votes on hard and edge tiers would lift it past the 97% target and settle many borderline rows.
4. **Decide the open rules or drop those rows:** sweetened plant milks, "dehydrated (low-moisture)" fruit, fresh ingredient vs frozen entry, regional names for near-identical products.
5. **Rebalance.** Add about 280 easy yes pairs, or drop easy no pairs, to bring easy to 50%. Consider matching the real 71% yes-share in router and test splits, or plan to recalibrate.
6. **Reduce the overlap shortcut.** Add low-overlap yes pairs and high-overlap no pairs to easy and medium, and the reverse to hard, so overlap AUC moves toward 0.65 overall and toward 0.5 within tiers.
7. **Small repairs.** Add two G9 pairs to test; trim the 47 foods and 78 USDA entries over their caps; review the 24 flip variants that did not flip; shorten ingredient lines and add one-word staples; add more "frozen"-no pairs.
8. **Get human labels on the 151-row gold subset.** Every accuracy figure here is model against model.

## 9. Appendix: disputed rows (66) and flagged planned labels (135)

See `data_synth_v2/audit_1500/sample_1500_labels.csv`: filter `verdict_on_haiku` for `haiku_wrong`, `haiku_right_reviewer_wrong`, `ambiguous` (66 rows, with a `reason` column), and compare `intended_label` against `haiku_v3_label` for the 135 flagged planned labels.
