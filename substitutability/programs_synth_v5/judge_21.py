import re
from collections import Counter

_NOISE = set("""a an the of and or with without in to for from into on at by as is are be
diced chopped sliced minced shredded grated crushed fresh freshly large small medium
fine finely coarsely thinly taste optional extra about approximately style type
cut pieces piece cubed cubes peeled halved quartered divided plus more needed
tube thawed softened melted room temperature g kg mg oz lb lbs ml l tsp tbsp cup cups
nfs regular made""".split())
_MODS = set("""raw cooked frozen canned dried dry ground whole unsalted salted sweetened
unsweetened boiled baked roasted fried smoked lean fat added drained solid liquids
prepared reduced low nonfat non-fat fluid""".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ches", "shes", "oes", "xes")):
                return w[:-1]
            return w[:-len(suf)] if suf != "es" else w[:-2]
    return w


def _tokens(text, drop_paren=True):
    text = (text or "").lower()
    if drop_paren:
        text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)?\b", " ", text)
    return [_stem(w) for w in re.findall(r"[a-z]+", text)]


def judging_function(ingredient, usda_match):
    try:
        ing = _tokens(ingredient)
        usda_full = (usda_match or "").lower()
        ing_core = [w for w in ing if w not in _NOISE and _stem(w) not in _NOISE]
        parts = [p.strip() for p in usda_full.split(",")]
        usda = _tokens(usda_full)
        usda_core = [w for w in usda if w not in _NOISE]
        if not ing_core or not usda_core:
            return 0.0
        food_i = [w for w in ing_core if w not in _MODS]
        food_u = [w for w in usda_core if w not in _MODS]
        if not food_i or not food_u:
            food_i, food_u = ing_core, usda_core
        ci, cu = Counter(food_i), Counter(food_u)
        inter = sum((ci & cu).values())
        # weight: ingredient coverage matters most (all food words found in USDA)
        cov_i = inter / float(len(food_i))
        cov_u = inter / float(len(food_u))
        # head noun: last ingredient food word vs first USDA part words
        head_i = food_i[-1]
        first_part = set(_tokens(parts[0]))
        head_hit = 1.0 if head_i in set(food_u) else 0.0
        lead_hit = 1.0 if (first_part & set(food_i)) else 0.0
        # bigram overlap (unordered adjacent pairs)
        bi_i = set(frozenset(p) for p in zip(food_i, food_i[1:]))
        bi_u = set(frozenset(p) for p in zip(food_u, food_u[1:]))
        bi = len(bi_i & bi_u) / float(len(bi_i)) if bi_i else cov_i
        # modifier agreement
        mi = set(w for w in ing_core if w in _MODS)
        mu = set(w for w in usda_core if w in _MODS)
        mod_pen = 0.0
        if mi and mu:
            mod_pen = 0.5 * len(mi ^ mu) / float(len(mi | mu))
        score = 4.0 * cov_i + 2.0 * cov_u + 1.5 * head_hit + 1.0 * lead_hit + 1.5 * bi
        score -= 1.5 * mod_pen
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
