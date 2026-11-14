import re

# Identity-transforming "product form" markers: if one side has the marker and the
# other does not, the two name different foods (oil vs nut, juice vs fruit ...).
_TRANSFORM = {
    "oil": "oil", "butter": "spread", "nectar": "drink", "juice": "drink", "drink": "drink",
    "beverage": "drink", "pudding": "dessert", "cake": "baked", "cookie": "baked",
    "pie": "baked", "bread": "baked", "taco": "meal", "burrito": "meal", "sandwich": "meal",
    "pizza": "meal", "soup": "meal", "sauce": "sauce", "paste": "paste", "syrup": "syrup",
    "extract": "extract", "flour": "flour", "powder": "powder", "patty": "patty",
    "nugget": "patty", "sausage": "sausage", "candy": "candy", "ice": "frozen dessert",
    "vinegar": "vinegar", "yogurt": "yogurt", "cheese": "cheese", "milk": "milk",
    "cream": "cream",
}
_FILLER = set("""chopped diced sliced minced cubed melted thawed fresh ripe large small medium
finely roughly boneless skinless peeled shredded grated crushed the a of and with without
in for from to style type hearts florets pieces piece bits whole""".split())
_STATE = set("raw cooked boiled dried dry frozen canned prepared fresh baked roasted".split())
_CHAIN = ("taco bell", "mcdonald", "burger king", "wendy", "kfc", "subway", "pizza hut", "restaurant", "applebee")
_MOD = set("vegan vanilla chocolate red white black green brown sweet light dark low fat lowfat nonfat powdered balsamic".split())


def _words(s):
    out = []
    for w in re.findall(r"[a-z]+", s):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)?\b", " ", ing)
        if not ing.strip() or not usda.strip():
            return 0.0
        i_parts = ing.split(",")
        iw = [w for w in _words(i_parts[0]) if w not in _FILLER]
        i_state = set(_words(" ".join(i_parts[1:]))) | set(w for w in iw if w in _STATE)
        iw = [w for w in iw if w not in _STATE] or iw
        u_parts = [p for p in usda.split(",") if p.strip()]
        uw = [_words(p) for p in u_parts]
        uflat = [w for p in uw for w in p if w not in _FILLER]
        if not iw or not uflat:
            return 0.0
        iset, uset = set(iw), set(uflat)

        score = 5.0
        # 1. identity words: ingredient content words found anywhere in USDA entry
        hit = [w for w in iw if w in uset]
        miss = [w for w in iw if w not in uset]
        head = iw[-1]
        score += 3.0 if head in uset else -3.0
        score += 1.0 * (len(hit) - len(miss)) / len(iw)

        # 2. transformation classes must agree
        itf = set(_TRANSFORM[w] for w in iset if w in _TRANSFORM)
        utf = set(_TRANSFORM[w] for w in uset if w in _TRANSFORM)
        # the USDA primary segment dominates its class
        uprim = set(_TRANSFORM[w] for w in uw[0] if w in _TRANSFORM)
        clash = (itf ^ utf)
        # words that are in both strings are not clashes
        score -= 1.5 * min(2, len(clash))
        if uprim and not (uprim & itf) and head not in uw[0]:
            score -= 1.0

        # 3. USDA qualifiers that the ingredient lacks (variety/colour modifiers)
        for w in uset & _MOD:
            if w not in iset:
                score -= 1.0
        for w in iset & _MOD:
            if w not in uset:
                score -= 1.0

        # 4. preparation state conflict (frozen vs not, dry vs fresh)
        u_state = set(w for w in uflat if w in _STATE)
        for s in ("frozen", "dried", "dry", "canned"):
            if (s in u_state) != (s in i_state or s in ing):
                score -= 0.6

        # 5. restaurant / chain items are never plain ingredients
        for c in _CHAIN:
            if c in usda:
                score -= 4.0

        # 6. concise USDA entries (few extra words) are closer stand-ins
        extra = len([w for w in uset if w not in iset and w not in _STATE])
        score -= 0.15 * min(extra, 10)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
