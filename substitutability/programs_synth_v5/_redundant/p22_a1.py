import re

NOISE = set("""a an the of and or with to for in on from as at by optional taste diced chopped sliced minced
shredded grated crushed fresh freshly large small medium thin thick fine finely roughly peeled cut pieces piece
into about extra more less plus tube thawed drained rinsed softened melted divided packed room temperature
g kg mg oz lb lbs ml l tbsp tsp cup cups pinch dash ns nfs raw solids only""".split())

STATE = set("cooked braised frozen canned dried ground smoked baked boiled roasted fried powdered".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _toks(text):
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|lbs|ml|l)\b", " ", text)
    return [_stem(t) for t in re.findall(r"[a-z]+", text)]


def judging_function(ingredient, usda_match):
    try:
        ing = _toks(ingredient or "")
        usda = _toks(usda_match or "")
        ic = [t for t in ing if t not in NOISE and t not in STATE]
        uc = [t for t in usda if t not in NOISE and t not in STATE]
        if not ic or not uc:
            return 0.0
        iset, uset = set(ic), set(uc)
        # position weights for USDA tokens: earlier = more food-defining
        uw = {}
        for i, t in enumerate(uc):
            w = 1.0 / (1.0 + 0.35 * i)
            uw[t] = max(uw.get(t, 0), w)
        iw = {}
        n = len(ic)
        for i, t in enumerate(ic):
            # last word of ingredient is usually the head noun
            w = 1.0 + (0.6 if i == n - 1 else 0.0)
            iw[t] = max(iw.get(t, 0), w)
        shared = iset & uset
        ing_cov = sum(iw[t] for t in shared) / sum(iw.values())
        usda_cov = sum(uw[t] for t in shared) / sum(uw.values())
        # F-style harmonic combination of coverage both ways
        if ing_cov + usda_cov == 0:
            return 0.0
        f = 2 * ing_cov * usda_cov / (ing_cov + usda_cov)
        # ordered bigram match on content tokens (order-insensitive pair bonus)
        ib = {frozenset(p) for p in zip(ic, ic[1:])}
        ub = {frozenset(p) for p in zip(uc, uc[1:])}
        bg = len(ib & ub) / max(1, min(len(ib), len(ub))) if ib and ub else 0.0
        # head noun check: ingredient's head word must appear in USDA
        head = ic[-1] in uset
        # primary USDA food (first token) present in ingredient
        prim = uc[0] in iset
        # penalty for extra unmatched USDA tokens (specialised entries)
        extra = len(uset - iset)
        pen = 0.12 * max(0, extra - 1)
        # state mismatch (e.g. powdered vs not)
        istate = {_stem(t) for t in ing if t in STATE}
        ustate = {_stem(t) for t in usda if t in STATE}
        smis = 0.1 * len(istate ^ ustate) if (istate or ustate) else 0
        score = 6 * f + 1.5 * bg + (1.0 if head else -1.0) + (1.0 if prim else 0.0) - pen - smis
        return round(score, 4)
    except Exception:
        return 0.0
