import re

# Lexical and Token Overlap, variant 4: Monge-Elkan soft token matching with
# Jaro-Winkler inner similarity.
# Exact set overlap misses plural/derivational variants (berries/berry,
# tomatoes/tomato, yoghurt/yogurt) and compound splits. Here every
# ingredient token is matched to its most similar USDA token using the
# Jaro-Winkler similarity (with a 0.85 floor so unrelated words score 0),
# and the Monge-Elkan mean is taken in both directions. Tokens that are
# mere modifiers carry a lower weight than food-defining tokens.

_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with without the a an in as for fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed finely
roughly large small medium nfs ns""".split())
_MOD = set("""raw cooked boiled baked roasted fried grilled broiled steamed frozen canned
dried low fat lowfat nonfat reduced calorie sodium light lean salted unsalted sweetened
unsweetened whole plain regular prepared ready eat heat dry moist skin not eaten only
meat style type made commercial added sweet""".split())


def _jaro(s, t):
    if s == t:
        return 1.0
    ls, lt = len(s), len(t)
    if not ls or not lt:
        return 0.0
    rng = max(ls, lt) // 2 - 1
    sm, tm = [False] * ls, [False] * lt
    matches = 0
    for i in range(ls):
        lo, hi = max(0, i - rng), min(i + rng + 1, lt)
        for j in range(lo, hi):
            if not tm[j] and s[i] == t[j]:
                sm[i] = tm[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    k = trans = 0
    for i in range(ls):
        if sm[i]:
            while not tm[k]:
                k += 1
            if s[i] != t[k]:
                trans += 1
            k += 1
    m = float(matches)
    return (m / ls + m / lt + (m - trans / 2.0) / m) / 3.0


def _jw(s, t):
    j = _jaro(s, t)
    prefix = 0
    for a, b in zip(s[:4], t[:4]):
        if a != b:
            break
        prefix += 1
    return j + prefix * 0.1 * (1 - j)


def _toks(text, is_ing):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    if is_ing:
        t = t.split(",")[0]
        t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    return [w for w in re.findall(r"[a-z]+", t) if w not in _NOISE and len(w) > 1]


def _monge_elkan(a, b):
    num = den = 0.0
    for x in a:
        w = 0.35 if x in _MOD else 1.0
        best = max(_jw(x, y) for y in b)
        if best < 0.85:
            best = 0.0
        num += w * best
        den += w
    return num / den if den else 0.0


def judging_function(ingredient, usda_match):
    try:
        a = _toks(str(ingredient or ""), True)
        b = _toks(str(usda_match or ""), False)
        if not a or not b:
            return 0.0
        fwd = _monge_elkan(a, b)
        bwd = _monge_elkan(b, a)
        score = 0.65 * fwd + 0.35 * bwd
        # if only modifier tokens matched, the overlap is not food-defining
        food_a = [x for x in a if x not in _MOD]
        if food_a and max(max(_jw(x, y) for y in b) for x in food_a) < 0.85:
            score *= 0.3
        return round(100.0 * score, 2)
    except Exception:
        return 0.0
