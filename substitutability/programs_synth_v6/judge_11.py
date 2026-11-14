import re

_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "para": "brazil", "granada": "pomegranate", "plant": "vegan"}
_IGN = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole lean drained of and or the a with in for from to into steak fillet seed segment floret slice piece cold hot toasted strong brewed".split())
_USDA_MODS = set("decaffeinated lactose reduced vegetable deli imported hydrogenated entree prepackaged luncheon babyfood fortified enriched sweetened unsweetened sodium nonfat lowfat fat-free added".split())
_FORMWORDS = {"oil", "juice", "nectar", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "snack", "taco", "sandwich", "spice", "powder", "flour", "paste", "puree"}
_PRESERVE = {"canned", "frozen", "dried", "dehydrated", "cooked", "boiled", "baked", "roasted", "braised", "fried", "steamed", "smoked", "pickled", "raw"}

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
        ut = _t(u)
        main = _t(ing.split(",")[0])
        if not it or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        core = [w for w in main if w not in _IGN and w not in _PRESERVE] or [w for w in main if w not in _IGN] or main
        f = {}
        f["cov"] = sum(1 for w in core if w in uset) / float(len(core))
        f["head"] = 1.0 if core[-1] in uset else 0.0
        first = _t(u.split(",")[0])
        f["head_first"] = 1.0 if core[-1] in first else 0.0
        f["exact_first"] = 1.0 if set(first) == set(core) else 0.0
        f["extra_first"] = min(3, len([w for w in first if w not in iset and w not in _IGN and w not in _PRESERVE]))
        f["usda_form_new"] = 1.0 if any(w in _FORMWORDS and w not in iset for w in first) else 0.0
        f["ing_form_lost"] = 1.0 if any(w in _FORMWORDS and w not in uset for w in main) else 0.0
        pi = iset & _PRESERVE
        pu = uset & _PRESERVE
        f["pres_agree"] = 1.0 if (pi & pu) else 0.0
        pi2 = pi - {"frozen"}
        pu2 = pu - {"raw", "frozen"}
        f["pres_usda_only"] = 1.0 if (pu2 and not pi2) else 0.0
        f["pres_ing_only"] = 1.0 if (pi2 - {"raw"} and not pu) else 0.0
        f["pres_conflict"] = 1.0 if (pi2 and pu2 and not (pi2 & pu2)) else 0.0
        f["usda_mods"] = min(3, len((uset & _USDA_MODS) - iset))
        f["brand"] = 1.0 if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u) else 0.0
        f["long_usda"] = 1.0 if len(u.split(",")) > 5 else 0.0
        w = {"cov": 4.0, "head": 2.0, "head_first": 1.0, "exact_first": 1.5, "extra_first": -0.5,
             "usda_form_new": -3.5, "ing_form_lost": -2.5, "pres_agree": 1.5, "pres_usda_only": -2.0,
             "pres_ing_only": -1.5, "pres_conflict": -2.5, "usda_mods": -0.9, "brand": -3.0, "long_usda": -0.3}
        return float(sum(w[k] * v for k, v in f.items()))
    except Exception:
        return 0.0
