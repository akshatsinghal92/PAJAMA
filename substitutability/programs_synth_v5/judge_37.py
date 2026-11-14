import re

_COLORS = {"red", "green", "yellow", "white", "black", "brown", "orange", "purple", "golden", "blue", "pink"}
_FAT = {"skim", "nonfat", "lowfat", "low-fat", "whole", "reduced", "light", "lean", "fat-free", "fatfree"}
_PARTS = {"breast", "thigh", "leg", "wing", "drumstick", "heart", "liver", "tongue", "shank", "chuck",
          "loin", "sirloin", "round", "rib", "shoulder", "belly", "tenderloin", "feet", "kidney", "neck",
          "leaves", "seeds", "root", "stem", "skin", "flank", "brisket", "oil", "juice", "flour", "powder"}
_ANIMALS = {"beef", "pork", "chicken", "lamb", "turkey", "duck", "veal", "mutton", "goat", "fish", "salmon", "tuna"}
_STATE = {"raw", "cooked", "dried", "dry", "frozen", "canned", "smoked", "roasted", "boiled", "braised",
          "fried", "pickled", "creamed", "ground", "fresh", "processed", "sweetened", "unsweetened",
          "salted", "unsalted", "baked", "grilled"}
_SWEET = {"sweet", "sweetened", "unsweetened", "sour", "salted", "unsalted", "spicy", "vanilla",
          "chocolate", "plain", "flavored", "smoked"}
_FLAV = {"coconut", "soy", "almond", "oat", "rice", "vegan", "chocolate", "strawberry", "honey"}
_DERIV = {"loaf", "patty", "cookies", "cookie", "sandwich", "tapenade", "sauce", "soup", "candy", "snack",
          "bar", "cereal", "pie", "cake", "bread", "babyfood", "restaurant", "gluten"}
_STOP = {"the", "a", "of", "and", "or", "with", "in", "from", "to", "for", "optional", "fresh", "pure",
         "type", "style", "regular", "all", "raw", "g", "kg", "ml", "oz", "boneless", "trimmed", "diced",
         "chopped", "sliced", "minced", "thawed", "warmed", "skin-on"}


def _norm(w):
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _toks(s):
    return [_norm(w) for w in re.findall(r"[a-z][a-z\-]*", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\(.*?\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b", " ", ing)
        ing_main = ing.split(",")[0]
        ing_all = _toks(ing)
        ing_main_t = _toks(ing_main)
        parts = [p.strip() for p in usda.split(",")]
        usda_head = _toks(parts[0])
        usda_all = _toks(usda)
        usda_set = set(usda_all)
        ing_set = set(ing_all)

        def norm_set(S):
            return {_norm(x) for x in S}

        score = 5.0

        # Core content coverage: ingredient content words found in usda
        content = [w for w in ing_main_t if w not in _STOP and len(w) > 1]
        if content:
            hit = sum(1 for w in content if w in usda_set)
            cov = hit / len(content)
        else:
            cov = 0.5
        score += 3.0 * cov - 1.5

        # Head noun: first usda word should appear in ingredient
        if usda_head:
            if any(w in ing_set for w in usda_head):
                score += 1.5
            else:
                score -= 1.5

        # Qualifier categories
        def cat_check(cat, penalty, bonus):
            nonlocal score
            c = norm_set(cat)
            a = ing_set & c
            b = usda_set & c
            if a and b:
                if a & b:
                    score += bonus
                else:
                    score -= penalty
            elif a and not b:
                score -= penalty * 0.5
            elif b and not a:
                score -= penalty * 0.3

        cat_check(_COLORS, 2.5, 0.8)
        cat_check(_FAT, 2.0, 0.6)
        cat_check(_PARTS, 2.5, 0.8)
        cat_check(_ANIMALS, 4.0, 0.8)
        cat_check(_SWEET, 1.8, 0.6)
        cat_check(_FLAV, 2.5, 0.5)

        # State mismatch (diner would notice)
        st_i = ing_set & norm_set(_STATE)
        st_u = usda_set & norm_set(_STATE)
        if st_i and st_u and not (st_i & st_u):
            score -= 1.2
        elif st_i & st_u:
            score += 0.5
        if "creamed" in ing_set and "creamed" not in usda_set:
            score -= 1.5
        if "smoked" in ing_set and "smoked" not in usda_set:
            score -= 1.5

        # Derived product words in usda but not in ingredient
        d = norm_set(_DERIV)
        extra = (usda_set & d) - ing_set
        score -= 2.0 * len(extra)

        # Part-of-plant: ingredient is leaves/seeds/etc. while usda head differs
        if "oil" in usda_set and "oil" not in ing_set:
            score -= 3.0
        if "leaf" in ing_set and "leaf" not in usda_set:
            score -= 2.0

        # Extra unmatched usda head tokens
        extra_head = [w for w in usda_head if w not in ing_set and w not in _STOP]
        score -= 0.4 * len(extra_head)

        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
