import re
import math

_NOISE = set("""g kg mg oz lb lbs ml l cup cups tbsp tsp tablespoon teaspoon piece pieces slice slices sliced diced chopped
minced grated shredded crushed cubed cubes chunks chunk fresh thawed divided optional taste garnish tube from for to of and or
the a an with in into plus about ripe large small medium whole raw cooked frozen plain light fillets fillet equal parts part
white sweet dark red""".split())
_FORM = set("juice oil crackers cracker souffle syrup leaves leaf powder dried canned pickled candied flour starch paste sauce soup patty frozen smoked fried baked".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)?\b", " ", s)
    return re.findall(r"[a-z]+", s)


def judging_function(ingredient, usda_match):
    try:
        ingredient = ingredient or ""
        usda_match = usda_match or ""
        ing_all = [_stem(t) for t in _tokens(ingredient.split(",")[0])]
        ing = [t for t in ing_all if t not in _NOISE and len(t) > 1]
        parts = [p for p in usda_match.split(",")]
        if not ing or not usda_match.strip():
            return 0.0
        # weighted USDA tokens: primary food segment heavy, descriptors light
        u = []
        for i, p in enumerate(parts):
            w = 3.0 if i == 0 else 1.0 / (1 + 0.3 * i)
            for t in _tokens(p):
                st = _stem(t)
                if st in _NOISE and st not in ing_all:
                    continue
                u.append((st, w, i == 0))
        if not u:
            return 0.0
        ing_set = set(ing)
        usda_set = set(t for t, _, _ in u)
        # weighted recall of ingredient tokens in usda (later ingredient tokens = head noun, heavier)
        n = len(ing)
        tot = rec = 0.0
        for k, t in enumerate(ing):
            w = 1.0 + 1.5 * (k == n - 1)
            tot += w
            if t in usda_set:
                rec += w
        recall = rec / tot
        # weighted precision on usda primary tokens
        ptot = pmatch = 0.0
        for t, w, prim in u:
            ptot += w
            if t in ing_set or t in set(ing_all):
                pmatch += w
        prec = pmatch / ptot if ptot else 0.0
        # primary food coverage
        prim_tokens = [t for t, _, p in u if p]
        prim_hit = sum(1 for t in prim_tokens if t in ing_set) / max(1, len(prim_tokens))
        # bigram bonus
        ibg = set(zip(ing, ing[1:]))
        ubg = set(zip([t for t, _, _ in u], [t for t, _, _ in u][1:]))
        bg = len(ibg & ubg) / len(ibg) if ibg else 0.0
        score = 4.0 * recall + 2.5 * prim_hit + 2.0 * prec + 1.0 * bg
        # form-shift penalty: USDA has a form word the ingredient lacks
        ing_text = set(_stem(t) for t in _tokens(ingredient))
        for t in usda_set:
            if t in _FORM and t not in ing_text:
                score -= 2.0
        for t in ing_text:
            if t in _FORM and t not in usda_set:
                score -= 1.0
        return max(0.0, score)
    except Exception:
        return 0.0
