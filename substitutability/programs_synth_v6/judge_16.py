import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "plant": "vegan", "granada": "pomegranate", "cilantro": "coriander", "purée": "puree"}
# low-information words: contribute little weight either way
_LOW = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless drained of and or the a with in for from to into raw nfs regular plain type separable lean fat only trimmed choice select grades all meat mature seeds whole variety flavor other than not eaten without added salt".split())
# macro-relevant words: weight high because they flip macros
_MACRO_W = {"oil": 3.0, "juice": 2.5, "syrup": 2.5, "sauce": 2.0, "soup": 2.0, "powder": 2.0, "dried": 2.0, "flour": 2.0, "fried": 1.8, "cooked": 1.0, "canned": 1.0, "nonfat": 1.5, "lowfat": 1.5, "reduced": 1.2, "sweetened": 1.5, "smoked": 1.2, "cookie": 3.0, "cake": 3.0, "candy": 3.0, "jerky": 2.5, "pudding": 3.0, "sandwich": 3.0, "taco": 3.0, "entree": 3.0, "frozen": 0.7}
_PRODUCT = {"oil", "juice", "syrup", "sauce", "soup", "cookie", "cake", "candy", "jerky", "pudding", "sandwich", "taco", "entree"}

def _t(s):
    r = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_ALIAS.get(w, w))
    return r

def _wt(w, pos, n):
    if w in _MACRO_W:
        return _MACRO_W[w]
    if w in _LOW:
        return 0.15
    base = 1.0 + 0.25 * len(w) / 8.0
    return base + (0.5 if pos == n - 1 else 0.0)

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _t(ing.split(",")[0])
        itail = _t(",".join(ing.split(",")[1:]))
        ut = _t(u)
        if not it or not ut:
            return 0.0
        # ingredient state words in the tail count at half weight
        n = len(it)
        wi = {}
        for k, w in enumerate(it):
            wi[w] = max(wi.get(w, 0.0), _wt(w, k, n))
        for w in itail:
            if w not in wi:
                wi[w] = 0.5 * _wt(w, 0, 2)
        wu = {}
        m = len(ut)
        # USDA: words in first segment weigh full, later segments 0.5 (hierarchy tail)
        first_len = len(_t(u.split(",")[0]))
        for k, w in enumerate(ut):
            f = 1.0 if k < first_len else 0.55
            wu[w] = max(wu.get(w, 0.0), f * _wt(w, -1, 2))
        inter = sum(min(wi[w], wu[w]) for w in wi if w in wu)
        # missing-from-USDA ingredient weight is bad, extra USDA weight is mildly bad
        miss = sum(wi[w] for w in wi if w not in wu)
        extra = sum(wu[w] for w in wu if w not in wi)
        score = inter - 0.9 * miss - 0.35 * extra
        # product swap hard penalty
        pu = set(ut[:first_len]) & _PRODUCT
        if pu - set(it) - set(itail):
            score -= 3.0
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
