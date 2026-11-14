import re

_TRIVIAL = {"raw", "fresh", "chopped", "diced", "minced", "sliced", "shredded", "thawed",
            "cubed", "grated", "crushed", "peeled", "whole", "ground", "trimmed", "large",
            "small", "medium", "finely", "coarsely", "pieces", "leaves", "separable",
            "lean", "fat", "and", "or", "of", "the", "a", "with", "without", "nfs",
            "g", "choice", "select", "regular", "salt", "added", "solids", "liquids"}
_COOKED = {"cooked", "fried", "braised", "roasted", "baked", "boiled", "grilled",
           "stewed", "simmered", "steamed", "broiled", "sauteed", "microwaved",
           "pan-fried", "deep-fried", "toasted", "smoked", "cured"}
_PRESERVED = {"canned", "pickled", "dried", "frozen", "dehydrated", "juice", "syrup",
              "jarred", "candied", "powder", "paste", "freeze-dried"}
_STOP = {"g", "kg", "oz", "ml", "tbsp", "tsp", "cup", "cups", "lb"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|oz|ml|lb|lbs)?\b", " ", s)
    return [_stem(w) for w in re.findall(r"[a-z][a-z\-']*", s)]


def judging_function(ingredient, usda_match):
    try:
        ing = (ingredient or "")
        usda = (usda_match or "")
        it = _tokens(ing)
        ut = _tokens(usda)
        if not it or not ut:
            return 0.0
        core_i = {w for w in it if w not in _TRIVIAL and w not in _STOP}
        core_u_list = [w for w in ut if w not in _TRIVIAL and w not in _STOP]
        core_u = set(core_u_list)
        if not core_i or not core_u:
            return 0.5

        # content-word coverage of the ingredient by the USDA description
        cov = len(core_i & core_u) / float(len(core_i))
        # primary food (first segment of USDA) must relate to ingredient
        first = set(_tokens(usda.split(",")[0])) - _TRIVIAL
        prim = 1.0 if (first & core_i) else 0.0
        # stricter: does ingredient's head noun (last core word) appear in USDA?
        head = [w for w in it if w in core_i]
        head_hit = 1.0 if head and head[-1] in core_u else 0.0

        score = 6.0 * cov + 3.0 * prim + 2.0 * head_hit

        # preparation-state comparison
        iset, uset = set(it), set(ut)
        i_cook = bool(iset & _COOKED)
        u_cook = bool(uset & _COOKED)
        if u_cook and not i_cook:
            score -= 4.5
        elif i_cook and not u_cook and "raw" in uset:
            score -= 3.0
        elif i_cook and u_cook:
            score += 1.0
        i_pres = iset & _PRESERVED
        u_pres = uset & _PRESERVED
        extra = u_pres - i_pres
        if extra:
            score -= 3.0 * min(len(extra), 2) / 1.0 * 0.8
        if "raw" in uset and not i_cook:
            score += 1.0

        # unexplained extra USDA descriptors (mild penalty)
        extra_u = core_u - core_i
        score -= 0.25 * max(0, len(extra_u) - 3)
        # ingredient mixtures
        if re.search(r"\b(and|mixed|or)\b", ing.lower()):
            score -= 1.0
        return max(0.0, min(15.0, score))
    except Exception:
        return 0.0
