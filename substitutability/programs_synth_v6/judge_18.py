import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "plant": "vegan", "cos": "romaine", "poultry": "chicken"}
_CATEGORY = set("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean cereal oil fruit vegetable spice sausage snack syrup sauce soup beverage bread cracker pasta candy mollusk game".split())
_NEUTRAL = set("raw nfs regular plain type separable lean fat only trimmed choice select grade all meat mature whole variety flavor other than not eaten fresh drained of and or the a with in for from to into without salt added free range farmed wild mixed species".split())
_STATE = set("cooked canned frozen dried boiled baked roasted braised fried steamed simmered broiled smoked pickled toasted".split())
_NOTICE = set("lowfat nonfat reduced low light diet sodium decaffeinated unsweetened sweetened lactose vegetable oat imported hydrogenated fortified enriched prepackaged deli luncheon crumble patty breaded battered organic beaked mountain zealand hawaii".split())
_PREP = set("chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot steak fillet seed segment floret slice piece strong brewed round bone".split())
_BRAND_RE = re.compile(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food|entree|sandwich")

def _t(s):
    r = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_ALIAS.get(w, w))
    return r

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        main = _t(ing.split(",")[0])
        tail = _t(",".join(ing.split(",")[1:]))
        usegs = [_t(s) for s in u.split(",") if s.strip()]
        if not main or not usegs:
            return 0.0
        uall = [w for s in usegs for w in s]
        uset = set(uall)
        iall = set(main) | set(tail)
        terms = [w for w in main if w not in _PREP and w not in _NEUTRAL and w not in _STATE] or [w for w in main if w not in _PREP] or main
        head = terms[-1]
        gain = 0.0
        loss = 0.0
        # identity terms
        for k, w in enumerate(terms):
            wgt = 2.5 if w == head else 1.5
            if w in uset:
                gain += wgt
            else:
                loss += wgt * 0.9
        # USDA descriptor terms not in ingredient
        for k, seg in enumerate(usegs):
            for w in seg:
                if w in iall or w in _NEUTRAL or w == head:
                    continue
                if w in _CATEGORY and k == 0:
                    continue
                if w in _NOTICE:
                    loss += 1.4
                elif w in _STATE:
                    loss += 1.2 if k <= 1 else 0.8
                elif k == 0:
                    loss += 0.8
                else:
                    loss += 0.2
        # ingredient state not found in usda
        for w in iall & _STATE:
            if w not in uset and w != "frozen":
                loss += 0.9
        # ingredient unqualified & usda carries a state that is not raw
        if not (iall & _STATE) and (uset & _STATE) - {"frozen", "canned"}:
            loss += 0.6
        if _BRAND_RE.search(u):
            loss += 3.0
        denom = gain + loss
        ratio = gain / denom if denom > 0 else 0.0
        # specificity-balance bonus: similar number of segments
        bal = 0.3 if abs(len(usegs[0]) - len(terms)) <= 1 else 0.0
        return float(10.0 * ratio + bal + 0.1 * gain)
    except Exception:
        return 0.0
