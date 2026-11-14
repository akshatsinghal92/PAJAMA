import re

_GEN_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "bison": "buffalo", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "scallion": "onion", "maize": "corn", "capsicum": "pepper", "swede": "rutabaga", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "purée": "puree", "cos": "romaine", "pinyon": "pine"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed"}
_BENIGN = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat by product fat without salt added dry heat moist steak chop fillet heart tail neck wing breast thigh leg shank loin roast rib flat segment floret slice piece strip wedge chunk cube rind kernel".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk".split())
_FORMNOUN = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_DIET = {"lowfat": 0.35, "nonfat": 0.35, "reduced": 0.35, "light": 0.25, "diet": 0.3, "lactose": 0.35, "sodium": 0.3, "decaffeinated": 0.35, "skim": 0.35, "sweetened": 0.35, "flavored": 0.3, "breaded": 0.5, "battered": 0.5, "seasoned": 0.4, "prepared": 0.3, "mix": 0.35, "deli": 0.3, "luncheon": 0.3, "prepackaged": 0.25, "beaked": 0.4, "mountain": 0.4, "hawaii": 0.3, "hydrogenated": 0.35, "oat": 0.25, "vegetable": 0.25, "strawberry": 0.35, "peach": 0.3, "chocolate": 0.3}

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_GEN_SYN.get(t, t))
    return out

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def judging_function(ingredient, usda_match):
    try:
        orig_u = str(usda_match or "")
        raw_u = _nobrand(orig_u)
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        ut = _w(u)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        iall, uset = set(it), set(ut)
        first = segs[0]
        # --- sub-score 1: identity in [0,1]
        core = [t for t in main if t not in _BENIGN and t not in _COOK and t not in _DIET and t not in ("raw", "dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "whole", "seed", "powdered")]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        ident = 0.65 * cov + (0.35 if core[-1] in uset else 0.0)
        # brand cereal rule: ingredient says cereal and USDA is a ready-to-eat cereal entry
        if "cereal" in iall and "cereal" in uset and "ready" in uset:
            ident = max(ident, 0.8)
        # compound ingredient: 'and' listing several foods, USDA covers one
        n_and = len(re.findall(r"\band\b", ing.split(",")[0]))
        if n_and and len(core) >= 2 and cov < 1.0:
            ident *= 0.75
        # --- sub-score 2: state fidelity in [0,1]
        st = 1.0
        ic = bool(iall & _COOK)
        uc = bool(uset & _COOK) or "heat" in uset
        if uc and not ic and "raw" not in uset:
            st -= 0.40
        if ic and not uc:
            st -= 0.30
        for s_, p_ in (("dried", 0.45), ("pickled", 0.4), ("smoked", 0.4), ("canned", 0.25), ("fried", 0.25)):
            if (s_ in iall) != (s_ in uset):
                if s_ == "fried" and ic and uc:
                    continue
                st -= p_
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iall:
            st -= 0.4
        if ("ground" in iall) != ("ground" in uset) or ("powdered" in iall) != ("powdered" in uset):
            st -= 0.25
        st = max(st, 0.0)
        # --- sub-score 3: plainness in [0,1]
        d = sum(c for t, c in _DIET.items() if t in uset and t not in iall) + 0.5 * sum(c for t, c in _DIET.items() if t in iall and t not in uset)
        plain = max(0.0, 1.0 - d)
        # --- sub-score 4: form/part in [0,1]
        fp = 1.0
        if (set(first) & _FORMNOUN) - iall:
            fp -= 0.6
        if (iall & _FORMNOUN) - uset:
            fp -= 0.3
        for t in ("leaf", "leave", "bone", "peel", "stem", "skin"):
            if (t in iall) != (t in uset):
                fp -= 0.35
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            fp -= 0.7
        fp = max(fp, 0.0)
        # blend: weakest-link emphasised
        parts = [ident, st, plain, fp]
        weights = [3.0, 2.0, 1.2, 1.8]
        wavg = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        floor = min(parts)
        return float(10.0 * (0.6 * wavg + 0.4 * floor) + 0.2 * cov)
    except Exception:
        return 0.0
