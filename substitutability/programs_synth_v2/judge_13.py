import re

# Preparation-State Equivalence, variant 5: category-conditioned sensitivity.
# How much a preparation-state gap matters depends on WHAT the food is:
#   - a raw vs cooked gap on fish or meat changes the whole recipe
#   - on vegetables it matters (texture) but less
#   - on nuts, roasting is a mild flavour change
#   - on oils, cheeses, condiments and spices the state words barely matter
# We detect a coarse category, compute a binary feature mismatch vector
# (heated, fat-cooked, preserved, frozen, texture-altered), and subtract a
# category-scaled penalty from 100.

_CATEGORIES = {
    "flesh": ["fish", "salmon", "tuna", "swordfish", "cod", "shrimp", "beef", "pork",
              "chicken", "turkey", "lamb", "veal", "duck", "steak", "breast", "thigh",
              "meat", "crab", "lobster", "scallop", "tilapia", "ham", "sausage"],
    "veg": ["corn", "tomato", "onion", "pepper", "carrot", "broccoli", "spinach",
            "potato", "bean", "pea", "squash", "zucchini", "cabbage", "kale",
            "mushroom", "celery", "cauliflower", "eggplant", "asparagus", "beet"],
    "fruit": ["apple", "banana", "berry", "berries", "orange", "fruit", "grape",
              "peach", "pear", "mango", "pineapple", "cherry", "lemon", "lime", "melon"],
    "grain": ["rice", "pasta", "noodle", "gnocchi", "spaghetti", "oat", "quinoa",
              "barley", "macaroni", "couscous", "bread", "cereal", "flour"],
    "nut": ["almond", "peanut", "walnut", "cashew", "pecan", "nut", "seed", "pistachio"],
    "stable": ["oil", "cheese", "yogurt", "milk", "butter", "sauce", "dressing",
               "spice", "salt", "sugar", "honey", "vinegar", "syrup", "paste",
               "ketchup", "mustard", "mayonnaise", "cream"],
}
_SENSITIVITY = {"flesh": 1.0, "veg": 0.75, "fruit": 0.7, "grain": 0.6,
                "nut": 0.45, "stable": 0.25, None: 0.6}

_FEATURES = {
    "heated": {"cooked", "boiled", "steamed", "baked", "roasted", "grilled", "broiled",
               "heat", "stewed", "braised", "poached", "toasted", "microwaved", "fried",
               "sauteed", "simmered"},
    "fatcooked": {"fried", "sauteed", "breaded", "battered", "oil"},
    "preserved": {"canned", "pickled", "smoked", "cured", "dried", "dehydrated", "jarred"},
    "frozen": {"frozen"},
    "texture": {"creamed", "pureed", "mashed", "powder", "powdered", "juice", "paste"},
}
_FEATURE_COST = {"heated": 45, "fatcooked": 30, "preserved": 35, "frozen": 12, "texture": 35}


def _category(words):
    joined = " ".join(words)
    for cat, keys in _CATEGORIES.items():
        for k in keys:
            if re.search(r"\b" + k + r"(e?s)?\b", joined):
                return cat
    return None


def _flags(words, field_words=None):
    ws = set(words)
    out = {}
    for f, vocab in _FEATURES.items():
        out[f] = bool(ws & vocab)
    # "oil" in the food name is not a cooking method
    if field_words is not None and "oil" in field_words[:2]:
        out["fatcooked"] = bool(ws & (_FEATURES["fatcooked"] - {"oil"}))
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", usda)
        if not iw or not uw:
            return 0.0
        cat = _category(uw[:4]) or _category(iw)
        sens = _SENSITIVITY.get(cat, 0.6)

        fi = _flags(iw, iw)
        fu = _flags(uw, uw)
        # "uncooked"/"raw" ingredient that will be cooked in the recipe anyway
        explicit_raw = bool({"raw", "fresh", "uncooked"} & set(iw))

        penalty = 0.0
        for f, cost in _FEATURE_COST.items():
            if fi[f] != fu[f]:
                c = cost
                if f == "heated" and fu[f] and explicit_raw:
                    c *= 1.2
                if f == "frozen" and fi["frozen"] and "thawed" in iw:
                    c *= 0.5
                if not fi[f] and fu[f]:
                    c *= 1.0        # USDA carries a state not asked for
                else:
                    c *= 0.8        # ingredient carries a state USDA lacks
                penalty += c
        score = 96.0 - sens * penalty
        # explicit agreement that both are raw / fresh / mechanically prepped
        u_raw = bool({"raw", "fresh", "uncooked"} & set(uw))
        if (explicit_raw or not any(fi.values())) and u_raw and not any(fu.values()):
            score += 4.0
        # shared non-trivial state confirms equivalence of preparation
        if any(fi[f] and fu[f] for f in fi):
            score += 2.0
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
