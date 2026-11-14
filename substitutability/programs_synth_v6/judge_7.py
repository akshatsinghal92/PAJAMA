import re

_LEVELS = [
    (0.0, ["raw", "fresh", "uncooked", "unprepared"]),
    (1.0, ["cooked", "boiled", "baked", "roasted", "braised", "steamed", "simmered", "stewed", "poached", "grilled", "broiled", "pan-broiled", "sauteed", "sautéed", "toasted"]),
    (2.0, ["canned", "drained", "jarred", "bottled"]),
    (3.0, ["dried", "dehydrated", "dry", "powdered", "ground"]),
    (4.0, ["smoked", "cured", "pickled", "salted", "brined"]),
    (5.0, ["fried", "deep-fried", "breaded", "battered", "candied", "sweetened"]),
]
_IGN = set("the of and or in with a from to for fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole lean raw cooked canned dried nfs".split())

def _level(text):
    ws = re.findall(r"[a-zé\-]+", text)
    hits = []
    for lv, vs in _LEVELS:
        for w in ws:
            if w in vs:
                hits.append(lv)
    return hits

def _bigrams(ws):
    return set(zip(ws, ws[1:]))

def _norm(w):
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
        li, lu = _level(ing), _level(u)
        # if either is unmarked, assume raw(0) for ingredient; plain USDA name is mostly raw/as-sold
        pi = max(li) if li else 0.0
        pu = max(lu) if lu else 0.0
        gap = abs(pi - pu)
        # cooked<->canned<->raw adjacency is cheap; distant levels expensive
        state = 5.0 - 1.6 * gap
        if li and lu and set(li) & set(lu):
            state = 5.0
        # identity
        iw = [_norm(w) for w in re.findall(r"[a-z]+", ing.split(",")[0])]
        uw = [_norm(w) for w in re.findall(r"[a-z]+", u)]
        core = [w for w in iw if w not in _IGN]
        if not core or not uw:
            return float(state) * 0.2
        uset = set(uw)
        cov = sum(1 for w in core if w in uset) / float(len(core))
        bi_i = _bigrams(core)
        bi_u = _bigrams(uw)
        bonus = 0.0
        if bi_i:
            bonus = 1.5 * len(bi_i & bi_u) / float(len(bi_i))
        head = 1.0 if core[-1] in uset else 0.0
        ident = 5.0 * cov + 2.0 * head + bonus
        score = ident + 0.8 * state
        # product-type switch
        first = u.split(",")[0]
        for f in ["oil", "juice", "syrup", "sauce", "soup", "pudding", "cookie", "snack", "candy", "jerky"]:
            if re.search(r"\b" + f, first) and not re.search(r"\b" + f, ing):
                score -= 3.0
                break
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|entree|sandwich", u):
            score -= 2.5
        # low-fat / reduced modifiers missing in ingredient
        if re.search(r"low sodium|reduced|fat free|nonfat|lowfat|low fat|no salt|lactose", u) and not re.search(r"low|reduced|free|nonfat|lean|light|diet", ing):
            score -= 1.2
        return float(score)
    except Exception:
        return 0.0
