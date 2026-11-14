import re

_FORMS = {
    "fresh": ["fresh", "raw", "uncooked"],
    "frozen": ["frozen"],
    "canned": ["canned", "jarred", "bottled"],
    "dried": ["dried", "dehydrated", "dry"],
    "paste": ["paste", "puree", "purée", "concentrate"],
    "powder": ["powder", "powdered", "ground", "flour", "granulated"],
    "whole": ["whole", "seed", "kernel", "leaf", "leaves"],
    "juice": ["juice", "nectar", "drink", "beverage"],
    "oil": ["oil"],
    "sauce": ["sauce", "dressing", "gravy", "salsa"],
    "cooked": ["cooked", "boiled", "baked", "roasted", "braised", "fried", "steamed", "simmered", "grilled"],
}
# cost of mismatch between form of ingredient and form of usda (symmetric)
_COST = {
    frozenset(["fresh", "frozen"]): 0.5,
    frozenset(["fresh", "cooked"]): 2.0,
    frozenset(["frozen", "cooked"]): 2.0,
    frozenset(["fresh", "canned"]): 1.5,
    frozenset(["fresh", "dried"]): 3.5,
    frozenset(["canned", "dried"]): 3.0,
    frozenset(["frozen", "canned"]): 1.5,
    frozenset(["cooked", "canned"]): 1.0,
    frozenset(["whole", "powder"]): 2.5,
    frozenset(["dried", "powder"]): 1.5,
}
_SKIP = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole lean drained of and or the a with in for from to raw cooked canned dried nfs".split())

def _forms_of(text):
    ws = set(re.findall(r"[a-zé]+", text))
    out = set()
    for k, vs in _FORMS.items():
        if any(v in ws for v in vs):
            out.add(k)
    return out

def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        fi = _forms_of(ing) - {"whole"}
        fu = _forms_of(u) - {"whole"}
        # name-bearing forms: if 'paste' or 'juice' etc. appear in the ingredient it is part of identity
        base_i = fi or {"fresh"}
        base_u = fu or {"fresh"}
        form_pen = 0.0
        if not (base_i & base_u):
            costs = []
            for a in base_i:
                for b in base_u:
                    costs.append(_COST.get(frozenset([a, b]), 4.0))
            form_pen = min(costs)
        # transformed forms (paste/powder/juice/oil/sauce) unique to one side are heavy
        for f in ("paste", "juice", "oil", "sauce"):
            if (f in fi) != (f in fu):
                form_pen += 2.0
        # identity
        iw = [_stem(w) for w in re.findall(r"[a-z]+", ing.split(",")[0]) if w not in _SKIP]
        uw = set(_stem(w) for w in re.findall(r"[a-z]+", u))
        if not iw:
            return 5.0 - form_pen
        cov = sum(1 for w in iw if w in uw) / float(len(iw))
        head = 1.0 if iw[-1] in uw else 0.0
        score = 4.0 * cov + 2.0 * head + (5.0 - form_pen)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|entree|sandwich|cookie", u) and not re.search(r"cookie|sandwich", ing):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
