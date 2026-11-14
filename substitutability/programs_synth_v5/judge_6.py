import re

TRIVIAL = {"raw", "fresh", "chopped", "diced", "minced", "sliced", "shredded", "thawed", "whole",
           "grated", "crushed", "peeled", "cubed", "crumbled", "warmed", "chunks", "chunk", "pieces",
           "lean", "boneless", "separable", "fat", "all", "varieties", "regular", "mixed", "species",
           "plain", "salad", "cooking", "ground", "large", "small", "medium"}
CHANGING = {"fried", "cooked", "baked", "roasted", "boiled", "grilled", "canned", "dried", "dry",
            "smoked", "pickled", "cured", "juice", "sauce", "soup", "paste", "powder", "flour",
            "frozen", "steamed", "braised", "broiled", "stewed", "candied", "sweetened", "syrup",
            "breaded", "battered", "creamed", "fermented", "dehydrated", "toasted", "pan-broiled",
            "canned", "jarred", "prepared", "mix", "mixed", "leaves", "skin", "bone", "bones", "oil",
            "ready-to-serve", "sauerkraut", "patty", "dressing", "spread", "puree", "concentrate"}
STOP = {"and", "or", "of", "the", "a", "with", "for", "in", "from", "to", "g", "kg", "ml", "oz", "style",
        "garnish", "tube", "type", "all", "mixed"}
CANON = {"fried": "cooked", "baked": "cooked", "roasted": "cooked", "boiled": "cooked", "grilled": "cooked",
         "steamed": "cooked", "braised": "cooked", "broiled": "cooked", "stewed": "cooked",
         "pan-broiled": "cooked", "toasted": "cooked", "dry": "dried", "dehydrated": "dried",
         "jarred": "canned", "bones": "bone"}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(s):
    s = s.lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\s*", "", s)
    s = re.sub(r"\(([^)]*)\)", r" \1 ", s)
    return [CANON.get(t, t) for t in re.findall(r"[a-z][a-z\-]*", s)]


def judging_function(ingredient, usda_match):
    try:
        ing = _tokens(str(ingredient or ""))
        usda_raw = str(usda_match or "")
        usda = _tokens(usda_raw)
        if not ing or not usda:
            return 0.0
        # primary food of USDA = first comma segment
        primary = _tokens(usda_raw.split(",")[0])
        ing_core = {_stem(t) for t in ing if t not in TRIVIAL and t not in CHANGING and t not in STOP}
        us_core = {_stem(t) for t in usda if t not in TRIVIAL and t not in CHANGING and t not in STOP}
        pri_core = {_stem(t) for t in primary if t not in TRIVIAL and t not in CHANGING and t not in STOP}
        if not ing_core or not us_core:
            return 1.0
        shared = ing_core & us_core
        # coverage of ingredient food words by USDA, and USDA primary words by ingredient
        cov_i = len(shared) / len(ing_core)
        cov_u = len(ing_core & pri_core) / max(1, len(pri_core))
        # allow substring partial matches (e.g. linseed/flaxseed share 'seed')
        if not shared:
            for a in ing_core:
                for b in us_core:
                    if len(a) > 4 and len(b) > 4 and (a in b or b in a or a[-4:] == b[-4:]):
                        shared.add(a)
            cov_i = 0.5 * len(shared) / len(ing_core)
            cov_u = 0.5 * cov_u
        identity = 6.0 * (0.6 * cov_i + 0.4 * cov_u)
        if not shared:
            identity = 0.0
        # preparation states
        ing_state = {t for t in ing if t in CHANGING}
        us_state = {t for t in usda if t in CHANGING}
        mismatch = (ing_state ^ us_state)
        penalty = 0.0
        for t in mismatch:
            penalty += 1.0 if t in ("cooked", "dried", "juice", "frozen", "canned", "smoked", "sauce",
                                    "soup", "paste", "powder", "flour", "pickled", "cured", "sweetened") else 0.6
        # leaves/skin/bone/oil parts in ingredient mismatching usda part
        penalty = min(penalty, 4.0)
        # trivial-state bonus: both sides show raw/fresh-ish or no state
        bonus = 0.0
        if not mismatch:
            bonus = 2.0
        ing_triv = {t for t in ing if t in TRIVIAL}
        us_triv = {t for t in usda if t in TRIVIAL}
        if ing_triv & us_triv:
            bonus += 0.5
        # extra USDA qualifiers unrelated to ingredient dilute match
        extra = len(us_core - ing_core)
        dilute = min(1.5, 0.3 * extra)
        score = identity + bonus - penalty - dilute
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
