import re
import math

STOP = set("""a an the of and or with to for in on from as at by optional taste diced chopped sliced minced shredded
grated crushed fresh large small medium peeled cut into about extra plus tube thawed rinsed softened melted divided
g kg mg oz lb lbs ml tbsp tsp cup cups pinch dash ns nfs""".split())


def _clean(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|kg|mg|oz|lb|lbs|ml)\b", " ", text)
    return re.sub(r"[^a-z ]", " ", text)


def _words(text):
    return [w for w in _clean(text).split() if w not in STOP and len(w) > 1]


def _grams(words, n=3):
    s = []
    for w in words:
        w = "^" + w + "$"
        for i in range(max(1, len(w) - n + 1)):
            s.append(w[i:i + n])
    return s


def _lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = ingredient or ""
        us_raw = usda_match or ""
        # post-comma state of the ingredient is a modifier; keep the main phrase separately
        ing_main = ing_raw.split(",")[0]
        iw = _words(ing_main) or _words(ing_raw)
        uw_all = _words(us_raw)
        if not iw or not uw_all:
            return 0.0
        # character trigram cosine (handles plural/spelling variants, compound words)
        ci = {}
        for g in _grams(iw):
            ci[g] = ci.get(g, 0) + 1
        cu = {}
        for g in _grams(uw_all):
            cu[g] = cu.get(g, 0) + 1
        dot = sum(v * cu.get(k, 0) for k, v in ci.items())
        ni = math.sqrt(sum(v * v for v in ci.values()))
        nu = math.sqrt(sum(v * v for v in cu.values()))
        cos = dot / (ni * nu) if ni and nu else 0.0
        # asymmetric containment: how much of the ingredient's name is found in USDA text
        def fuzzy_in(w, pool):
            return any(w == p or (len(w) > 3 and len(p) > 3 and (w.startswith(p[:-1]) or p.startswith(w[:-1]))) for p in pool)
        contain = sum(1 for w in iw if fuzzy_in(w, uw_all)) / len(iw)
        # reverse containment over the first USDA segment (the primary food name)
        seg = _words(us_raw.split(",")[0]) or uw_all
        prim = sum(1 for w in seg if fuzzy_in(w, iw)) / len(seg)
        # ordered match via LCS ratio
        lcs = _lcs(iw, uw_all) / max(len(iw), len(uw_all))
        # extra descriptors in USDA that are not in ingredient: log penalty
        DESC = set("raw cooked braised canned frozen drained solids only lean separable meat imported regular dried ground baked boiled roasted fried broilers fryers fat eaten".split())
        extra = sum(1 for w in uw_all if w not in DESC and not fuzzy_in(w, iw))
        pen = 0.45 * min(extra, 4)
        score = 4.0 * contain + 2.0 * cos + 1.0 * lcs + 1.0 * prim - pen
        if contain == 0:
            score -= 1.0
        return round(score, 4)
    except Exception:
        return 0.0
