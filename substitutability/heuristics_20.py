"""
20 substitutability rubrics for the v4 program set (programs_synth_v4/).

Rubrics 1-10 are the original set from heuristics.py, unchanged. Rubrics 11-20 are new.
They were written by brainstorming further dimensions that string code can express
(the first step of paper appendix A.2), with the v3 failure analysis in mind
(PROGRAM_ANALYSIS_V3.md). Their examples are made up and are not rows from the data.
"""

from heuristics import SUBSTITUTABILITY_HEURISTICS as _BASE

EXTRA_HEURISTICS = {
    11: {
        "name": "Synonym and Alias Resolution",
        "description": (
            "Judge whether the two names refer to the same food even when they share few or "
            "no words, because one uses a regional, common, culinary or scientific name for "
            "the other (e.g. 'aubergine' vs 'Eggplant', 'garbanzo beans' vs 'Chickpeas', "
            "'scallion' vs 'Onions, spring or scallions', 'courgette' vs 'Squash, zucchini'). "
            "Use alias knowledge, including aliases the USDA entry gives in parentheses. Reward "
            "matches that resolve to the same food; penalize matches that resolve to "
            "different foods even if words overlap."
        ),
    },
    12: {
        "name": "Head Food Position",
        "description": (
            "USDA descriptions put the primary food first and descriptors after commas. Judge "
            "whether the ingredient's main food is the USDA entry's PRIMARY food, or only "
            "appears as a modifier of a different food (e.g. 'almond' vs 'Almond milk', "
            "'tomato' vs 'Tomato soup', 'apple' vs 'Apple pie'). Reward entries whose leading "
            "food term is the ingredient's food; penalize entries where the ingredient's food "
            "is demoted to a flavour, filling, or modifier."
        ),
    },
    13: {
        "name": "Unstated Added Qualifier",
        "description": (
            "Judge asymmetrically: does the USDA entry add a qualifier the ingredient never "
            "stated and a diner would notice? Typical added qualifiers: low or reduced sodium, "
            "fat free, nonfat, low fat, reduced fat, light, sweetened, sugar free, with salt, "
            "salted, flavored, enriched, fortified, with added vitamins. Reward entries that "
            "add nothing beyond neutral descriptors (raw, plain, regular); penalize each "
            "unstated qualifier that changes taste or composition."
        ),
    },
    14: {
        "name": "Polarity and Negation Conflict",
        "description": (
            "Judge whether the two sides state OPPOSITE values of the same attribute: 'no "
            "added fat' vs 'fat added', 'unsalted' vs 'salted', 'unsweetened' vs 'sweetened', "
            "'skinless' vs 'with skin', 'boneless' vs 'bone-in', 'hulled' vs 'unhulled', "
            "'seedless' vs 'with seeds', 'decaffeinated' vs regular. Detect negation prefixes "
            "and words (un-, no, without, free) and their positive counterparts. Strongly "
            "penalize any contradiction; stay neutral when only one side mentions the attribute."
        ),
    },
    15: {
        "name": "Brand and Commercial Product",
        "description": (
            "Judge whether brand names or commercial product markers change the match. Signs "
            "include all-caps tokens, trademark-like words, and parenthetical brand names. A "
            "branded entry can match a generic ingredient when it is the standard example of "
            "that product (e.g. 'cream-filled chocolate sandwich cookies' vs a well-known brand "
            "of them). It should be penalized when the brand implies a different variant, "
            "flavour, or base (e.g. a plain ingredient vs a branded flavoured or plant-based "
            "version)."
        ),
    },
    16: {
        "name": "Single Ingredient vs Composite Dish",
        "description": (
            "Judge whether one side is a single ingredient and the other a prepared dish or "
            "mixture: entries containing 'with', 'and', 'in sauce', 'stuffed', 'salad', 'soup', "
            "'casserole', 'sandwich', 'mix', 'blend', 'dinner', 'prepared'. Reward single-for-"
            "single and dish-for-same-dish matches; penalize a single ingredient matched to a "
            "dish that contains it, or the reverse."
        ),
    },
    17: {
        "name": "Cooking Method Agreement",
        "description": (
            "Judge agreement on cooking method and doneness: raw, cooked, boiled, steamed, "
            "baked, roasted, grilled, fried, deep-fried, sauteed, broiled, microwaved, "
            "smoked, toasted. Treat an unstated method as compatible with raw or a generic "
            "entry. Reward matching or compatible methods; penalize methods that change "
            "texture, fat content or flavour (fried vs baked, raw vs roasted, toasted vs plain)."
        ),
    },
    18: {
        "name": "Anatomical Part and Cut",
        "description": (
            "Judge whether the same part of the plant or animal is meant: leaves vs root vs "
            "stem vs seed vs flower (e.g. 'beet greens' vs 'Beets'), breast vs thigh vs wing vs "
            "drumstick, loin vs shoulder, whole vs ground vs fillet, yolk vs white, flesh vs "
            "peel or zest. Reward the same part or an unspecified part; penalize a different "
            "part that cooks or tastes differently."
        ),
    },
    19: {
        "name": "Ingredient Detail Coverage",
        "description": (
            "Judge how much of the ingredient's meaningful description the USDA entry accounts "
            "for, using the WHOLE ingredient string, including text after commas and inside "
            "parentheses (but ignoring gram weights and recipe notes like 'optional', 'to "
            "taste', 'for garnish'). Reward entries that cover the ingredient's food and its "
            "material qualifiers (variety, form, state); penalize entries that leave material "
            "qualifiers unaccounted for or contradict them."
        ),
    },
    20: {
        "name": "Compound Food Name Integrity",
        "description": (
            "Many food names are compounds where a modifier changes the food itself: 'sweet "
            "potato' is not 'potato', 'coconut milk' is not 'milk', 'peanut butter' is not "
            "'butter', 'green tea' is not 'tea leaves' in general, 'sea bass' is not 'bass'. "
            "Judge whether the ingredient's compound food name is kept intact in the USDA "
            "entry. Reward intact or equivalent compounds; penalize matches that keep only part "
            "of the compound, or that add a modifier forming a different food."
        ),
    },
}

HEURISTICS_20 = {**_BASE, **EXTRA_HEURISTICS}
assert len(HEURISTICS_20) == 20
