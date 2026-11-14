import re

# Culinary role lexicon: role -> keywords
_ROLES = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow"],
    "sweetener": ["sugar", "syrup", "honey", "molasses", "agave", "fructose", "sweetener", "nectar"],
    "thickener": ["starch", "flour", "cornstarch", "arrowroot", "gelatin", "tapioca", "pectin"],
    "binder": ["egg", "flaxseed", "flax", "linseed", "chia", "breadcrumb"],
    "aromatic": ["garlic", "onion", "ginger", "shallot", "leek", "sage", "thyme", "basil",
                 "oregano", "rosemary", "parsley", "cilantro", "spice", "spices", "pepper",
                 "cumin", "cinnamon", "vanilla", "mint", "dill"],
    "protein_meat": ["beef", "pork", "chicken", "lamb", "turkey", "veal", "duck", "heart",
                     "liver", "sirloin", "steak", "roast", "sausage", "bacon", "ham"],
    "protein_fish": ["fish", "whitefish", "salmon", "tuna", "cod", "shrimp", "crab", "trout"],
    "dairy": ["cheese", "milk", "yogurt", "cream", "brie", "cottage", "kefir"],
    "starch_staple": ["tortilla", "tortillas", "wrap", "bread", "pasta", "gnocchi", "rice",
                      "noodle", "wheat", "potato", "oats"],
    "legume": ["pea", "peas", "bean", "beans", "lentil", "lentils", "chickpea"],
    "fruit": ["apple", "applesauce", "pomegranate", "durian", "jackfruit", "plum", "berry",
              "banana", "mango", "jamun", "tamarind", "orange", "lemon", "grape"],
    "vegetable": ["squash", "escarole", "spinach", "carrot", "lettuce", "cabbage", "kale",
                  "broccoli", "tomato", "zucchini", "celery"],
    "condiment": ["dressing", "sauce", "ketchup", "mustard", "mayonnaise", "vinegar"],
    "snack": ["chips", "cookies", "cookie", "crackers", "candy", "snack"],
    "nut_spread": ["peanut", "pecan", "almond", "cashew", "walnut", "hazelnut"],
}

_SYNONYMS = {
    "linseed": "flaxseed", "linseeds": "flaxseed", "flax": "flaxseed",
    "puree": "sauce", "purée": "sauce", "applesauce": "apple",
    "jamun": "java-plum", "wrap": "tortilla", "wraps": "tortilla", "tortillas": "tortilla",
    "syrups": "syrup", "seeds": "seed", "peas": "pea", "yogurt": "yogurt",
    "nonfat": "non-fat", "lowfat": "low-fat", "squash": "squash",
}

# Physical-form / state groups; mismatch can force recipe change
_FORMS = {
    "frozen": "frozen", "fresh": "fresh", "raw": "fresh", "cooked": "cooked",
    "boiled": "cooked", "canned": "canned", "dried": "dried", "ground": "ground",
    "whole": "whole", "chopped": "cut", "cubed": "cut", "sliced": "cut",
    "smoked": "smoked", "nectar": "liquid", "juice": "liquid", "chips": "crisp",
    "pulp": "pulp", "puree": "pulp", "purée": "pulp", "sauce": "pulp",
}

_MODIFIERS = {"reduced": "fat", "low": "fat", "non-fat": "fat", "nonfat": "fat",
              "lowfat": "fat", "unsweetened": "sweet", "sweetened": "sweet",
              "sodium": "sodium", "boneless": "bone"}

_STOP = {"and", "or", "with", "of", "the", "a", "in", "for", "from", "nfs", "regular",
         "optional", "to", "fat", "by", "products", "imported", "commercial", "inch",
         "tube", "mature", "s"}


def _norm_tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", text)
    toks = re.findall(r"[a-zà-ÿ][a-zà-ÿ\-]*", text)
    out = []
    for t in toks:
        t = _SYNONYMS.get(t, t)
        out.append(t)
    return out


def _stem(t):
    if len(t) > 4 and t.endswith("es") and not t.endswith("ses"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _roles(tokens):
    found = set()
    ts = set(tokens) | {_stem(t) for t in tokens}
    for role, kws in _ROLES.items():
        for k in kws:
            if k in ts or _stem(k) in ts:
                found.add(role)
                break
    return found


def _forms(tokens):
    return {_FORMS[t] for t in tokens if t in _FORMS}


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0

        ing_main = ing.split(",")[0]
        ing_tail = ing[len(ing_main):]
        ing_tokens = _norm_tokens(ing_main)
        usda_tokens = _norm_tokens(usda)
        if not ing_tokens or not usda_tokens:
            return 0.0

        ing_content = [_stem(t) for t in ing_tokens if t not in _STOP and t not in _FORMS]
        usda_content = [_stem(t) for t in usda_tokens if t not in _STOP]
        usda_set = set(usda_content)
        usda_primary = [_stem(t) for t in _norm_tokens(usda.split(",")[0]) if t not in _STOP]

        score = 20.0

        # 1. Role compatibility (core of the rubric)
        r_ing = _roles(ing_tokens)
        r_usda = _roles(usda_tokens)
        if r_ing and r_usda:
            shared = r_ing & r_usda
            if shared:
                score += 20.0 * len(shared) / max(len(r_ing), 1)
            else:
                score -= 25.0
            # snack/processed entries rarely fill a cooking role
            if "snack" in r_usda and "snack" not in r_ing:
                score -= 20.0
        elif r_ing and not r_usda:
            score -= 5.0

        # 2. Identity of the item: head noun (last content word) and coverage
        head = ing_content[-1] if ing_content else ""
        if head and head in usda_set:
            score += 25.0
            if head in usda_primary:
                score += 8.0
        elif head:
            score -= 12.0
        if ing_content:
            cov = sum(1 for t in ing_content if t in usda_set) / len(ing_content)
            score += 25.0 * cov
            missing = [t for t in ing_content if t not in usda_set]
            # an unmatched descriptive word (variety, cut, species) changes the item
            score -= 6.0 * len(missing)

        # Brand-name collision: primary USDA word matches only as a brand prefix
        if usda_primary and head and head not in usda_primary and \
                any(w[:1].isupper() for w in usda.split(",")[0].split()[:2]) and \
                len(usda.split(",")[0].split()) >= 2 and "snack" in r_usda:
            score -= 10.0

        # 3. Form/behavior compatibility
        f_ing = _forms(_norm_tokens(ing))
        f_usda = _forms(usda_tokens)
        conflicts = {("frozen", "cooked"), ("fresh", "cooked"), ("fresh", "canned"),
                     ("pulp", "liquid"), ("whole", "ground"), ("fresh", "dried"),
                     ("frozen", "canned"), ("pulp", "crisp")}
        for a in f_ing:
            for b in f_usda:
                if (a, b) in conflicts or (b, a) in conflicts:
                    score -= 15.0

        # 4. Modifier compatibility (reduced fat, low sodium, unsweetened ...)
        ing_low = (ing_main + " " + ing_tail).lower()
        usda_low = usda.lower()
        for mod in ("low sodium", "unsweetened", "sweetened", "shelf stable",
                    "ready-to-bake", "lowfat", "low-fat", "reduced fat"):
            in_i = mod in ing_low
            in_u = mod in usda_low
            if in_u and not in_i:
                score -= 8.0
        if ("reduced-fat" in ing_low or "reduced fat" in ing_low) and \
                ("reduced fat" in usda_low or "reduced-fat" in usda_low):
            score += 5.0

        # 5. Excess USDA specificity dilutes certainty slightly
        extra = len([t for t in usda_content if t not in set(ing_content)])
        score -= 1.0 * min(extra, 8)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
