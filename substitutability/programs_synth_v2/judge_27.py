import re
import math

# Nutritional Profile Proximity, variant 3: relative macro-shift model.
# Instead of estimating absolute macros, we estimate how each text's
# modifiers SHIFT the macros of a shared base food, as log-multipliers on
# (energy, protein, carbohydrate, fat). If both texts name the same base food
# the macro gap is just the difference of shifts; if the base foods differ we
# add a base-food gap derived from a coarse macro family of each head noun.

_SHIFTS = {
    # word: (dlog kcal, dlog protein, dlog carb, dlog fat)
    "fried": (0.35, 0.0, 0.15, 0.9), "breaded": (0.4, -0.1, 0.6, 0.7),
    "battered": (0.45, -0.1, 0.6, 0.8), "buttered": (0.25, 0.0, 0.0, 0.8),
    "creamed": (0.3, 0.0, 0.3, 0.6), "creamy": (0.3, 0.0, 0.2, 0.6),
    "sweetened": (0.25, 0.0, 0.45, 0.0), "syrup": (0.35, 0.0, 0.6, 0.0),
    "candied": (0.9, -0.2, 1.1, 0.0), "glazed": (0.3, 0.0, 0.5, 0.1),
    "low": (-0.2, 0.05, 0.0, -0.7), "lowfat": (-0.25, 0.05, 0.05, -0.8),
    "nonfat": (-0.45, 0.1, 0.05, -2.5), "skim": (-0.45, 0.1, 0.05, -2.5),
    "light": (-0.15, 0.0, 0.0, -0.5), "reduced": (-0.2, 0.0, 0.0, -0.4),
    "lean": (-0.15, 0.05, 0.0, -0.5), "skin": (0.2, -0.05, 0.0, 0.8),
    "dried": (1.2, 1.2, 1.2, 1.2), "dehydrated": (1.3, 1.3, 1.3, 1.3),
    "juice": (-0.2, -1.0, -0.1, -1.5), "soup": (-0.8, -0.8, -0.6, -0.8),
    "broth": (-2.5, -1.5, -3.0, -2.5), "unsweetened": (-0.1, 0.0, -0.2, 0.0),
    "frozen": (0.0, 0.0, 0.0, 0.0), "canned": (-0.05, -0.05, 0.0, 0.0),
    "cooked": (0.15, 0.15, 0.05, 0.1), "roasted": (0.2, 0.2, 0.05, 0.15),
    "boiled": (-0.1, 0.0, -0.1, 0.0), "dressing": (0.8, -1.0, 0.0, 2.0),
    "sauce": (0.0, -0.5, 0.3, 0.3), "powder": (1.4, 1.4, 1.4, 1.2),
}
_FAMILY = {
    "protein": ["chicken", "turkey", "beef", "pork", "fish", "swordfish", "salmon", "tuna",
                "shrimp", "egg", "lamb", "meat", "tofu", "patty", "steak", "ham"],
    "fat": ["oil", "butter", "lard", "margarine", "mayonnaise", "ghee"],
    "starch": ["rice", "pasta", "potato", "gnocchi", "bread", "noodle", "corn", "cereal",
               "flour", "oat", "tortilla", "quinoa"],
    "produce": ["tomato", "onion", "spinach", "lettuce", "carrot", "broccoli", "pepper",
                "garlic", "kale", "celery", "mushroom", "cucumber"],
    "fruit": ["fruit", "apple", "banana", "berry", "blueberry", "orange", "guava", "mango",
              "grape", "peach", "pear"],
    "dairy": ["cheese", "milk", "yogurt", "cream", "cottage"],
    "nut": ["nut", "almond", "peanut", "walnut", "seed", "chia", "flaxseed", "cashew"],
    "sugar": ["sugar", "honey", "candy", "jam", "syrup", "chocolate"],
    "spice": ["spices", "spice", "cinnamon", "cumin", "paprika", "ginger", "seasoning"],
}
_FAMILY_VEC = {  # rough log-scale (kcal, protein, carb, fat) family signatures
    "protein": (5.1, 3.2, -2.0, 1.8), "fat": (6.8, -2.0, -2.0, 4.6),
    "starch": (5.0, 1.2, 3.3, 0.0), "produce": (3.4, 0.4, 1.8, -1.2),
    "fruit": (4.0, -0.3, 2.6, -1.3), "dairy": (5.4, 2.6, 0.5, 2.8),
    "nut": (6.4, 3.0, 2.8, 3.9), "sugar": (5.9, -2.0, 4.5, -1.0),
    "spice": (5.7, 2.3, 4.0, 1.8),
}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _family(words):
    fam = None
    for w in words:
        for f, nouns in _FAMILY.items():
            if w in nouns:
                fam = f
    return fam


def _shift(words):
    v = [0.0, 0.0, 0.0, 0.0]
    for i, w in enumerate(words):
        if w in _SHIFTS:
            # "skin not eaten" cancels the skin shift
            if w == "skin" and i + 1 < len(words) and words[i + 1] == "not":
                continue
            v = [a + b for a, b in zip(v, _SHIFTS[w])]
    return v


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        usda = str(usda_match or "").lower()
        iw = [_sing(w) for w in re.findall(r"[a-z]+", ing)]
        fields = [[_sing(w) for w in re.findall(r"[a-z]+", f)] for f in usda.split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        uw = [w for f in fields for w in f]
        si, su = _shift(iw), _shift(uw)
        shift_gap = math.sqrt(sum((a - b) ** 2 for a, b in zip(si, su)))

        # base-food gap
        primary = set(fields[0]) | (set(fields[1]) if len(fields) > 1 else set())
        content_i = [w for w in iw if w not in _SHIFTS and len(w) > 2]
        if content_i and content_i[-1] in primary:
            base_gap = 0.0
        else:
            fi = _family(iw)
            fu = _family(fields[0]) or _family(uw)
            if fi and fu:
                a, b = _FAMILY_VEC[fi], _FAMILY_VEC[fu]
                base_gap = 0.5 * math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
                if fi == fu:
                    base_gap += 0.4      # same family but different food
            else:
                base_gap = 1.6
        total = shift_gap + base_gap
        score = 10.0 / (1.0 + 0.6 * total * total)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
