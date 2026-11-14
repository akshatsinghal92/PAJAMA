import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "cos": "romaine", "granada": "pomegranate", "plant": "vegan", "puree": "sauce", "purée": "sauce"}
_STATE_OF = {"raw": "raw", "uncooked": "raw", "unroasted": "raw", "fresh": "raw",
             "cooked": "cooked", "boiled": "cooked", "baked": "cooked", "roasted": "cooked", "braised": "cooked", "steamed": "cooked", "simmered": "cooked", "broiled": "cooked", "grilled": "cooked", "toasted": "cooked", "pan-broiled": "cooked", "sauteed": "cooked", "sautéed": "cooked", "poached": "cooked", "stewed": "cooked", "heat": "cooked",
             "fried": "fried", "deep-fried": "fried", "pan-fried": "fried",
             "dried": "dried", "dehydrated": "dried", "dry": "dried",
             "canned": "canned", "jarred": "canned", "bottled": "canned",
             "smoked": "smoked", "cured": "smoked", "pickled": "pickled"}
_STATE_COMPAT = {("raw", "cooked"): 2.0, ("cooked", "raw"): 2.0, ("raw", "fried"): 3.0, ("fried", "raw"): 3.0, ("cooked", "fried"): 1.5, ("fried", "cooked"): 1.5,
                 ("raw", "dried"): 3.2, ("dried", "raw"): 3.2, ("cooked", "dried"): 2.5, ("dried", "cooked"): 2.5, ("raw", "canned"): 1.5, ("canned", "raw"): 1.5, ("cooked", "canned"): 0.8, ("canned", "cooked"): 0.8,
                 ("raw", "smoked"): 2.5, ("smoked", "raw"): 2.5, ("cooked", "smoked"): 1.5, ("smoked", "cooked"): 1.5, ("raw", "pickled"): 2.5, ("pickled", "raw"): 2.5}
_SHAPE = {"ground": "ground", "powder": "ground", "powdered": "ground", "whole": "whole", "flaked": "flaked", "crumble": "ground", "patty": "ground"}
_PREP = set("chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot steak fillet seed segment floret slice piece strong brewed round bone drained of and or the a with in for from to into lean fat trimmed separable choice select grade all meat only mature variety flavor other than not eaten regular plain type nfs without salt added free range farmed wild mixed species".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk".split())
_FORMS = {"oil", "juice", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "flour", "snack", "taco", "sandwich", "entree", "spice", "stew", "nectar"}
_DIET = set("lowfat nonfat reduced low light diet sodium decaffeinated unsweetened sweetened lactose vegetable oat imported hydrogenated fortified deli luncheon prepackaged beaked mountain zealand hawaii".split())

def _t(s):
    r = []
    for w in re.findall(r"[a-zé\-]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_ALIAS.get(w, w))
    return r

def _record(tokens):
    state = None
    shape = None
    ids = []
    for w in tokens:
        if w in _STATE_OF and w != "fresh":
            state = state or _STATE_OF[w]
            if _STATE_OF[w] == "raw":
                state = "raw"
        elif w == "fresh":
            state = state or "raw"
        if w in _SHAPE:
            shape = shape or _SHAPE[w]
    return state, shape

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _t(ing)
        main = _t(ing.split(",")[0])
        usegs = [_t(s) for s in u.split(",") if s.strip()]
        if not main or not usegs:
            return 0.0
        ut = [w for s in usegs for w in s]
        si, shi = _record(it)
        su, shu = _record(ut)
        ids_i = [w for w in main if w not in _PREP and w not in _STATE_OF and w not in _SHAPE] or [w for w in main if w not in _PREP] or main
        uset = set(ut)
        head = ids_i[-1]
        score = 0.0
        # identity
        cov = sum(1 for w in ids_i if w in uset) / float(len(ids_i))
        score += 5.0 * cov + (2.0 if head in uset else -1.0)
        # state compatibility: unspecified ingredient state ~ raw, unspecified usda ~ raw
        a = si or "raw"
        b = su or "raw"
        if a != b:
            score -= _STATE_COMPAT.get((a, b), 1.5)
            if not si or not su:
                score += 0.8  # one side silent: softer
        # shape: whole vs ground
        if shi and shu and shi != shu:
            score -= 1.5
        elif (shu == "ground" and not shi) or (shi == "ground" and not shu):
            score -= 1.0
        # specificity: extras in primary USDA name
        first = usegs[0]
        iset = set(it)
        extra = [w for w in first if w not in iset and w not in _TAXON and w not in _PREP and w not in _STATE_OF and w not in _SHAPE]
        score -= 0.8 * len(extra)
        # product-form swap
        if (set(first) & _FORMS) - iset:
            score -= 3.0
        for w in (set(ut) & _DIET) - iset:
            score -= 0.9
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
