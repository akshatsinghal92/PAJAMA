import re
import math

_STOP = set("g kg mg oz lb lbs ml cup cups tbsp tsp piece pieces slice slices sliced diced chopped minced grated shredded crushed cubed cubes chunks chunk fresh thawed divided optional taste garnish tube from for to of and or the a an with in into plus about ripe large small medium fillets fillet equal parts part raw".split())


def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", (s or "").lower())
    s = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml)?\b", " ", s)
    return [w for w in re.findall(r"[a-z]+", s) if w not in _STOP and len(w) > 1]


def _grams(w):
    w = "#" + w + "#"
    return set(w[i:i + 3] for i in range(len(w) - 2))


def _sim(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    d = 2.0 * len(ga & gb) / (len(ga) + len(gb))
    return d if d >= 0.6 else 0.0


def _lcs(x, y):
    m = [[0.0] * (len(y) + 1) for _ in range(len(x) + 1)]
    for i in range(len(x)):
        for j in range(len(y)):
            s = _sim(x[i], y[j])
            m[i + 1][j + 1] = max(m[i][j + 1], m[i + 1][j], m[i][j] + s)
    return m[-1][-1]


def judging_function(ingredient, usda_match):
    try:
        ing_str = (ingredient or "").split(",")[0]
        ing = _clean(ing_str)
        segs = [_clean(p) for p in (usda_match or "").split(",")]
        segs = [s for s in segs if s]
        if not ing or not segs:
            return 0.0
        prim = segs[0]
        rest = [t for s in segs[1:] for t in s]
        full = prim + rest
        # soft token alignment of ingredient to USDA tokens
        cover = sum(max(_sim(t, u) for u in full) for t in ing) / len(ing)
        # head noun (last ingredient word) must appear in primary segment
        head = max(_sim(ing[-1], u) for u in prim)
        # how much of USDA primary food is explained by the ingredient
        explained = sum(max(_sim(u, t) for t in ing) for u in prim) / len(prim)
        # ordered match between ingredient and the whole description
        order = _lcs(ing, full) / max(len(ing), 1)
        # extra USDA descriptor tokens that the ingredient never mentions = specificity risk
        extra = sum(1 for u in rest if max(_sim(u, t) for t in ing) == 0)
        extra_pen = 1.0 / (1.0 + 0.25 * extra)
        # primary-only unexplained tokens are strong evidence of different food
        base = (0.45 * cover + 0.25 * head + 0.3 * explained)
        score = 100.0 * base * (0.7 + 0.3 * order) * (0.6 + 0.4 * extra_pen)
        if cover < 0.5:
            score *= 0.5
        return score
    except Exception:
        return 0.0
