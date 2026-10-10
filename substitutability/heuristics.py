"""
Substitutability rubrics for programmatic-judge synthesis.

These are the pointwise-binary analog of PAJAMA's 10 pairwise-preference rubrics
(see ``synthesized_programmatic_judges/generate_programs.py:HEURISTICS``).

Each rubric steers an LLM to synthesize a ``judging_function(ingredient, usda_match)``
that returns a numeric score where HIGHER = the USDA entry is a BETTER (more
substitutable) match for the recipe ingredient. "Substitutable" follows the LLM
judge we are distilling (``backend/rerun_subjudge.py``): the USDA entry could be
used in place of the ingredient (1) without changing how the dish is prepared and
(2) without a diner noticing any difference in taste, texture, or appearance.
"""

SUBSTITUTABILITY_HEURISTICS = {
    1: {
        "name": "Core Food Identity Match",
        "description": (
            "Judge whether the ingredient and the USDA entry name the SAME fundamental "
            "food. Compare the head food noun of each (e.g. 'olive oil' vs 'Olive oil', "
            "'chicken breast' vs 'chicken patty'). Reward exact or near-exact identity of "
            "the primary food; penalize cases where the core substance differs (e.g. "
            "'garlic paste' vs 'guava paste', 'chia seed' vs 'flaxseed') even if other "
            "words overlap."
        ),
    },
    2: {
        "name": "Preparation-State Equivalence",
        "description": (
            "Judge whether the two differ only in a preparation state that a cook could "
            "trivially apply or ignore (raw, chopped, diced, minced, sliced, shredded, "
            "thawed). Reward matches where the state difference does not change the dish "
            "(e.g. 'fresh diced tomato' vs 'Tomatoes, raw'); penalize state differences "
            "that change cooking or outcome (e.g. 'fresh' vs 'fried', 'raw' vs 'cooked')."
        ),
    },
    3: {
        "name": "Preservation and Form Match",
        "description": (
            "Judge agreement on how the food is preserved or physically delivered: fresh, "
            "frozen, canned, dried, jarred, paste, powder. Reward matching or recoverable "
            "forms (e.g. 'frozen blueberries, thawed' vs 'Blueberries, frozen'); penalize "
            "mismatches that alter water content, concentration, or handling (e.g. a plain "
            "broth vs a ready-to-serve soup, fresh herb vs dried spice when it changes the "
            "dish)."
        ),
    },
    4: {
        "name": "Nutritional Profile Proximity",
        "description": (
            "Judge whether the two foods would carry a SIMILAR per-100g macronutrient "
            "profile (calories, protein, carbs, fat). Reward matches between foods of the "
            "same macro class (two lean proteins, two leafy greens, two pure fats); "
            "penalize matches that would swing macros substantially (a pure spice standing "
            "in for a seasoning blend, a sauce standing in for a raw vegetable)."
        ),
    },
    5: {
        "name": "Specificity and Generality Alignment",
        "description": (
            "Judge whether the USDA entry sits at an appropriate level of specificity for "
            "an unqualified ingredient. Reward the generic entry when the ingredient is "
            "unqualified (e.g. 'olive oil' -> 'Olive oil', not 'extra virgin'); reward the "
            "specific entry when the ingredient specifies a variant. Penalize entries that "
            "add or drop qualifiers the ingredient did not imply in a way a diner would "
            "notice."
        ),
    },
    6: {
        "name": "Lexical and Token Overlap",
        "description": (
            "Judge substitutability from shared food-name tokens after stripping amounts, "
            "units, and noise words (diced, chopped, to taste, from tube). Measure overlap "
            "of the meaningful content tokens (set overlap, Jaccard, ordered n-gram match) "
            "between the ingredient text and the USDA description. Reward high overlap of "
            "the food-defining words; discount overlap that comes only from modifiers."
        ),
    },
    7: {
        "name": "Food Category Consistency",
        "description": (
            "Judge whether both items belong to the same food category (dairy, produce, "
            "meat/poultry/fish, grain, legume, spice/herb, oil/fat, sweetener, condiment). "
            "Reward same-category matches; penalize cross-category matches (a spice for a "
            "vegetable, a sauce for a seed) which almost always change the dish."
        ),
    },
    8: {
        "name": "Processing and Additive Difference",
        "description": (
            "Judge whether the USDA entry introduces processing, additives, or compound "
            "ingredients the plain ingredient lacks: added salt, sugar, oil, sauces, "
            "breading, seasoning blends, sweetened/flavored variants. Reward plain-for-plain "
            "matches; penalize entries that add components a diner would taste (e.g. 'garlic "
            "paste' vs 'Garlic sauce', 'salt' vs 'salt and pepper')."
        ),
    },
    9: {
        "name": "Culinary Role Interchangeability",
        "description": (
            "Judge whether the USDA entry can play the SAME role in a dish as the ingredient "
            "(binder, fat for sauteing, bulk vegetable, aromatic, sweetener, thickener). "
            "Reward matches that preserve the ingredient's function even if the exact item "
            "differs slightly; penalize matches whose different texture or behavior (e.g. "
            "chia gel vs ground flax, whole vs chopped when shape matters) would force a "
            "recipe change."
        ),
    },
    10: {
        "name": "Modifier and Qualifier Consistency",
        "description": (
            "Judge agreement on discriminating qualifiers: color, variety, cut, fat level, "
            "sweetness, part of the plant/animal (red vs green bell pepper, whole milk vs "
            "skim, bell vs sweet pepper, breast vs thigh). Reward matching or unspecified "
            "qualifiers; penalize contradicted qualifiers that a diner would notice."
        ),
    },
}
