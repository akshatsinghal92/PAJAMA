import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "bison": "buffalo", "cilantro": "coriander", "maize": "corn", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine", "pinyon": "pine", "purée": "puree", "ox": "beef", "calf": "veal", "mutton": "lamb", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "scallion": "onion", "capsicum": "pepper", "innard": "giblet", "flat": "wing", "battered": "batter", "buttered": "butter"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_INEDIBLE = {"leaf", "leave", "bone", "peel", "stem", "shell", "rind"}
_DIETW = set("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk seed".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        iset, uset = set(it), set(ut)
        first = segs[0]
        core = [t for t in main if t not in _BENIGN and t not in _COOK and t not in _DIETW and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter", "butter") and t not in _INEDIBLE]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        head = core[-1]
        cov = sum(1 for t in core if t in uset) / float(len(core))
        # ---------- stage 1: vetoes (hard failures) ----------
        veto = 0.0
        if head not in uset and cov < 0.5:
            veto = max(veto, 4.0)
        if (set(first) & _FORMS) - iset:
            veto = max(veto, 3.5)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            veto = max(veto, 4.0)
        if (iset & _INEDIBLE) ^ (uset & _INEDIBLE):
            veto = max(veto, 3.0)
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
            veto = max(veto, 2.8)
        # reconstituted: dried + cooked in the ingredient is not a dried-state claim
        ing_dried = "dried" in iset and not (iset & _COOK)
        usda_dried = "dried" in uset and "from" not in uset
        if ing_dried != usda_dried:
            veto = max(veto, 2.8)
        for st in ("pickled", "smoked"):
            if (st in iset) != (st in uset):
                veto = max(veto, 2.8)
        # ---------- stage 2: soft consistency ----------
        soft = 0.0
        ic = bool(iset & _COOK)
        uc = bool(uset & _COOK)
        if uc and not ic and "raw" not in uset:
            soft += 2.0
        if ic and not uc:
            soft += 1.5
        if (("fried" in iset) != ("fried" in uset)) and not (ic and uc):
            soft += 1.5
        if ("canned" in iset) != ("canned" in uset):
            soft += 1.1
        if ("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset):
            soft += 1.3
        dd = len((uset & _DIETW) - iset) + 0.5 * len((iset & _DIETW) - uset)
        soft += 1.0 * min(dd, 3.0)
        colors = {"red", "green", "yellow", "white", "black", "brown", "orange", "purple"}
        ci, cu = iset & colors, uset & colors
        if ci and cu and not (ci & cu):
            soft += 1.8
        extra = [t for t in first if t not in iset and t not in _BENIGN and t not in _DIETW and t not in core and t not in _TAXA and t not in _COOK and t not in colors and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground")]
        soft += 0.6 * min(len(extra), 3)
        n_and = len(re.findall(r"\band\b", ing.split(",")[0]))
        if n_and and len(core) >= 2 and cov < 1.0:
            soft += 0.8
        base = 4.5 * cov + (1.5 if head in uset else 0.0)
        if veto > 0:
            return float(max(0.0, 3.0 - veto + 0.6 * base / 6.0 * 2.0 - 0.3 * soft))
        return float(4.0 + base - soft)
    except Exception:
        return 0.0
