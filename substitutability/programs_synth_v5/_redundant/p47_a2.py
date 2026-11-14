import re

_STOP = set("""fresh frozen thawed dried dry canned cooked raw chopped minced diced sliced ground crushed
crumbled grated shredded peeled large small medium whole fine finely roughly of and or with in from
the a an to for into boneless skinless trimmed organic tube g kg mg oz lb ml cup cups tbsp tsp only""".split())
_DEMOTERS = {"soup", "pie", "milk", "juice", "sauce", "cake", "cookie", "candy", "dressing", "syrup",
             "drink", "beverage", "snack", "pudding", "jam", "jelly", "extract", "soda", "babyfood",
             "flavored", "imitation", "substitute", "restaurant", "fast"}


def _stem(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxh":
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        ing = ing.split(",")[0]
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(kg|mg|g|oz|lb|ml)?\b", " ", ing)
        iw = [w for w in _words(ing) if w not in _STOP]
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or ""))
        segs = [s for s in usda.split(",") if s.strip()]
        if not iw or not segs:
            return 0.0
        # position-weighted coverage: each ingredient word credited by where it
        # first shows up in the USDA description (segment 0 = primary food).
        seg_w = [_words(s) for s in segs]
        total = 0.0
        for k, w in enumerate(iw):
            best = 0.0
            for si, sw in enumerate(seg_w):
                if w in sw:
                    weight = 1.0 if si == 0 else 0.6 / si + 0.2
                    best = max(best, weight)
                    break
            # head noun (last word) counts double
            total += best * (2.0 if k == len(iw) - 1 else 1.0)
        denom = len(iw) + 1.0
        cover = total / denom  # 0..1
        score = 10.0 * cover
        first = seg_w[0]
        # demotion: primary segment is a different food flavoured/derived by ingredient
        if any(w in _DEMOTERS for w in first) and not any(w in _DEMOTERS for w in iw):
            score -= 3.0
        # conciseness of primary segment relative to ingredient
        surplus = len([w for w in first if w not in iw])
        if cover > 0:
            score -= 0.5 * min(surplus, 4)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
