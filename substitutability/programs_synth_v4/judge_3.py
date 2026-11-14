import re

_PREP = {
    "fresh", "frozen", "thawed", "canned", "drained", "chopped", "sliced", "diced",
    "minced", "cubed", "grated", "shredded", "toasted", "roasted", "smoked", "pickled",
    "leftover", "fried", "cooked", "raw", "store", "bought", "store-bought", "large",
    "small", "medium", "optional", "garnish", "whole", "boneless", "skinless", "peeled",
    "flaked", "crushed", "ground", "dried", "baked", "boiled", "steamed", "for", "frying",
    "and", "or", "of", "the", "a", "with", "skin", "on", "cup", "cups", "slices", "slice",
    "leaves", "leaf", "pieces", "piece", "high", "low", "fat", "regular", "plain",
}

_GENERIC_USDA = {
    "fish", "oil", "spices", "spice", "sauce", "beverages", "cheese", "beef", "pork",
    "chicken", "lamb", "duck", "turkey", "veal", "nuts", "seeds", "cereals", "soup",
    "candies", "snacks", "babyfood", "vegetables", "fruit", "game", "meat", "flour",
}


def _stem(w):
    w = w.lower()
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ses", "s"), ("ves", "f")):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)] + rep
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _grams(w, n=3):
    w = "^" + w + "$"
    if len(w) < n:
        return {w}
    return {w[i:i + n] for i in range(len(w) - n + 1)}


def _dice(a, b):
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def _ingredient_core(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    toks = [_stem(x) for x in re.findall(r"[a-z]+(?:-[a-z]+)?", t)]
    content = [x for x in toks if x not in _PREP]
    return content if content else toks


def _usda_segments(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    segs = []
    for s in t.split(","):
        toks = [_stem(x) for x in re.findall(r"[a-z]+", s)]
        if toks:
            segs.append(toks)
    return segs


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        core = _ingredient_core(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not core or not segs:
            return 0.0

        head = core[-1]
        modifiers = core[:-1]

        # Identity region of the USDA string: first segment, plus the next one
        # when the first is a generic category ("Fish, swordfish").
        identity = list(segs[0])
        if len(segs) > 1 and all(w in _GENERIC_USDA for w in segs[0]):
            identity += segs[1]
        rest = [w for s in segs[1:] for w in s if w not in identity]

        # Head noun: best fuzzy character-trigram match, position-weighted.
        best_id = max((_dice(head, w) for w in identity), default=0.0)
        # Compound handling ("applesauce" vs "apple")
        for w in identity:
            if len(head) >= 4 and (head in w or w in head):
                best_id = max(best_id, 0.85)
        best_rest = max((_dice(head, w) for w in rest), default=0.0)
        head_score = max(best_id, 0.6 * best_rest)

        # Modifier support anywhere in the USDA string.
        all_usda = identity + rest
        if modifiers:
            sup = [max((_dice(m, w) for w in all_usda), default=0.0) for m in modifiers]
            mod_score = sum(1.0 if s >= 0.7 else s * 0.5 for s in sup) / len(sup)
        else:
            mod_score = 0.7

        # Penalty for unexplained USDA identity words (different core substance).
        unexplained = 0
        for w in identity:
            if w in _GENERIC_USDA or w in _PREP:
                continue
            if max((_dice(w, c) for c in core), default=0.0) < 0.5:
                unexplained += 1
        penalty = min(3.0, 1.2 * unexplained)

        if head_score < 0.45:
            score = 2.0 * head_score + 1.0 * mod_score - penalty * 0.3
        else:
            score = 3.0 + 5.0 * head_score + 2.0 * mod_score - penalty

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
