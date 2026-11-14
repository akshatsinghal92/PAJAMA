import re

# Lexicon of known compound foods (modifier, head). A compound is a unit, not its parts.
_COMPOUNDS = [
    "sweet potato", "coconut milk", "coconut oil", "coconut water", "coconut cream", "peanut butter",
    "almond milk", "almond butter", "soy milk", "soy sauce", "sea bass", "green tea", "black tea",
    "green bean", "black bean", "kidney bean", "lima bean", "white bean", "green onion", "green pepper",
    "sweet pepper", "bell pepper", "hot dog", "cream cheese", "cottage cheese", "ice cream",
    "sour cream", "corn flake", "corn starch", "corn syrup",
    "corn oil", "olive oil", "sesame oil", "vegetable oil", "rice flour", "rice vinegar", "rice milk",
    "oat milk", "cocoa powder", "chocolate milk", "bean sprout", "brussels sprout",
    "water chestnut", "pine nut", "ground beef", "ground turkey", "apple juice", "orange juice",
    "apple sauce", "tomato sauce", "tomato paste", "fish sauce", "hot sauce", "maple syrup",
    "brown sugar", "powdered sugar", "baking soda", "baking powder", "whole wheat", "white bread",
    "french fry", "potato chip", "sweet corn", "baby corn", "wild rice", "brown rice", "white rice",
    "egg white", "egg yolk", "tuna salad", "chicken broth", "beef broth", "pork rind", "beef jerky",
    "turkey bacon", "red wine", "white wine", "peanut oil", "mustard seed", "sunflower seed",
]
_ALIAS = {"maize": "corn", "poultry": "chicken", "clementine": "tangerine", "capsicum": "pepper",
          "scallion": "onion", "aubergine": "eggplant", "prawn": "shrimp"}
_FILL = set("""fresh frozen thawed chopped sliced diced minced cubed grated shredded crushed cooked raw drained
rinsed peeled cold hot warm toasted roasted large small medium whole boneless skinless organic canned dried
baked boiled steamed melted softened garnish taste for the of and or with without a an to from plain extra
finely thinly wild foraged crispy sweetened unsweetened salted unsalted flaked segments pieces g kg oz lb ml
tsp tbsp cup regular""".split())


def _norm(w):
    w = _ALIAS.get(w, w)
    if len(w) > 3:
        if w.endswith("ies"):
            w = w[:-3] + "y"
        elif w.endswith("oes"):
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
    return _ALIAS.get(w, w)


def _toks(s):
    return [_norm(t) for t in re.findall(r"[a-z]+", s.lower())]


def _found_compounds(toks):
    out = set()
    joined = " " + " ".join(toks) + " "
    for c in _COMPOUNDS:
        cn = " " + " ".join(_norm(x) for x in c.split()) + " "
        if cn in joined:
            out.add(c)
        else:
            a, b = [_norm(x) for x in c.split()]
            # reversed USDA order, e.g. "Cheese, cottage" / "Beans, kidney"
            if a in toks and b in toks and abs(toks.index(a) - toks.index(b)) <= 3:
                out.add(c)
    return out


def _lcs_len(a, b):
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
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        ing = ing.split(",")[0]
        usda = re.sub(r"\([^)]*\)", " ", usda)

        it = _toks(ing)
        ut = _toks(usda)
        icore = [t for t in it if t not in _FILL]
        ucore = [t for t in ut if t not in _FILL]
        if not icore or not ucore:
            return 0.0

        ic = _found_compounds(it)
        uc = _found_compounds(ut)
        kept = ic & uc
        lost = ic - uc
        gained = uc - ic

        score = 5.0
        score += 2.5 * len(kept)
        score -= 3.5 * len(lost)
        score -= 3.0 * len(gained)

        # ordered subsequence agreement between core tokens (position-aware)
        lcs = _lcs_len(icore, ucore)
        score += 3.0 * lcs / float(len(icore))
        score -= 1.0 * (len(icore) - lcs) / float(len(icore))

        # first USDA segment names the food; its first token should be among ingredient tokens
        first_seg = _toks(usda.split(",")[0])
        first_core = [t for t in first_seg if t not in _FILL]
        if first_core:
            overlap = len(set(first_core) & set(icore)) / float(len(set(first_core)))
            if overlap == 0:
                score -= 2.0

        # coverage of every ingredient content word anywhere in USDA text, head noun weighted
        us = set(ucore)
        cov = sum(1 for t in icore if t in us) / float(len(icore))
        score += 4.0 * cov - 3.0 * (1 - cov)
        if icore[-1] not in us:
            score -= 2.0
        # multi-food ingredient vs single USDA food (and vice versa)
        i_multi = bool(re.search(r"\b(and|with)\b", ing))
        u_multi = bool(re.search(r"\b(and|with)\b", usda))
        if i_multi != u_multi:
            score -= 2.0

        # unrelated filler descriptors in USDA
        unrelated = [t for t in ucore if t not in icore]
        score -= min(2.0, 0.25 * len(unrelated))
        return max(0.0, min(15.0, score))
    except Exception:
        return 0.0
