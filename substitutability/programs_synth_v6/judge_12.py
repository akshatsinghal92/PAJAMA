import re

_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "para": "brazil", "linseed": "flaxseed", "plant": "vegan", "concord": "grape"}
_NOISE = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole lean drained of and or the a with in for from to into cold hot toasted strong brewed round buttery".split())
_PARTS = {"seed", "leaf", "skin", "bone", "peel", "stem", "stalk", "shell", "rind", "flower", "root", "tail"}
_FORM_NOUNS = ["oil", "juice", "nectar", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "snack", "taco", "sandwich", "entree", "frozen yogurt", "flour", "spices"]

def _t(s):
    r = []
    for w in re.findall(r"[a-zé\-]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_SYN.get(w, w))
    return r

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _t(ing)
        main = _t(ing.split(",")[0])
        ut = _t(u)
        if not main or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        core = [w for w in main if w not in _NOISE] or main
        cov = sum(1 for w in core if w in uset) / float(len(core))
        head_hit = core[-1] in uset
        # tier by identity
        if cov == 1.0:
            tier = 8.0
        elif head_hit and cov >= 0.5:
            tier = 5.5
        elif head_hit:
            tier = 4.0
        elif cov > 0:
            tier = 2.0
        else:
            tier = 0.0
        # gates (each applies once)
        pen = 0.0
        # gate A: USDA first segment is a different product form
        flat_first = " ".join(_t(u.split(",")[0]))
        ing_text = " ".join(it)
        for fn in _FORM_NOUNS:
            if re.search(r"\b" + fn, flat_first) and not re.search(r"\b" + fn, ing_text):
                pen += 3.0
                break
        # gate B: plant part mismatch
        pi = iset & _PARTS
        pu = uset & _PARTS
        if pi != pu and (pi or pu):
            pen += 1.5
        # gate C: preservation
        def pres(s):
            out = set()
            for w, c in (("canned", "c"), ("frozen", "f"), ("dried", "d"), ("dehydrated", "d"), ("dry", "d"), ("cooked", "k"), ("boiled", "k"), ("baked", "k"), ("roasted", "k"), ("braised", "k"), ("fried", "k"), ("steamed", "k"), ("raw", "r"), ("smoked", "s"), ("pickled", "p")):
                if w in s:
                    out.add(c)
            return out
        a, b = pres(iset) - {"f"}, pres(uset) - {"f"}
        if a and b and not (a & b):
            pen += 2.0
        elif b and "r" not in b and not a:
            pen += 1.5
        elif a and "r" not in a and not b:
            pen += 1.0
        # gate D: dietary/composition modifiers only in USDA
        mods = set("decaffeinated lactose reduced vegetable deli imported hydrogenated entree prepackaged luncheon sodium nonfat lowfat fat-free added".split())
        if (uset & mods) - iset:
            pen += 1.0
        # gate E: brand/restaurant
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            pen += 3.0
        # gate F: bonus for exact first segment
        bonus = 1.5 if set(_t(u.split(",")[0])) <= (iset | set(["raw"])) else 0.0
        return float(tier + bonus - pen)
    except Exception:
        return 0.0
