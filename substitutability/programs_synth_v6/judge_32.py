import re

_PHRASES = [("half and half", "halfandhalf"), ("half & half", "halfandhalf"), ("equal parts milk and cream", "halfandhalf"), ("skin-on", "withskin"), ("skin on", "withskin"), ("meat and skin", "withskin"), ("dairy-free", "vegan"), ("plant-based", "vegan"), ("plant based", "vegan"), ("made with tofu", "vegan"), ("high fructose", "highfructose"), ("high-fructose", "highfructose"), ("stew meat", "stewmeat"), ("pot roast", "roast")]
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "puree": "sauce", "purée": "sauce", "concord": "grape"}
_BENIGN = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat by product raw fat without salt added dry heat moist".split())
_CUTS = set("steak chop fillet filet heart segment floret slice piece strip wedge chunk cube round rind tail neck wing breast thigh leg shank loin roast rib flat tongue".split())
_PARTS = {"seed": 2.0, "leaf": 2.0, "leave": 2.0, "bone": 2.0, "skin": 1.0, "peel": 2.0, "stem": 1.5, "shell": 1.5}
_STATEF = {"cooked": "k", "boiled": "k", "baked": "k", "braised": "k", "simmered": "k", "broiled": "k", "roasted": "k", "steamed": "k", "toasted": "k", "fried": "f", "dried": "d", "canned": "c", "smoked": "s", "pickled": "p", "frozen": "z"}
_HEAVY = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter".split())
_DESC = {"lowfat": 1.3, "nonfat": 1.3, "reduced": 1.3, "light": 1.0, "diet": 1.0, "lactose": 1.2, "sodium": 1.0, "decaffeinated": 1.2, "skim": 1.3, "sweetened": 1.5, "salted": 1.0, "flavored": 1.5, "breaded": 2.0, "battered": 2.0, "seasoned": 1.5, "fortified": 0.8, "hydrogenated": 1.5, "prepared": 1.2, "mix": 1.5, "deli": 1.2, "luncheon": 1.2, "prepackaged": 1.0, "imported": 1.0, "beaked": 1.5, "mountain": 1.5, "zealand": 1.2, "hawaii": 1.2, "oat": 1.0, "vegetable": 1.0, "strawberry": 1.4, "peach": 1.4, "chocolate": 1.4, "vanilla": 0.5, "pickled": 0.0}

def _pre(s):
    s = s.lower()
    for a, b in _PHRASES:
        s = s.replace(a, b)
    return s

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
        ing = re.sub(r"\([^)]*\)", " ", _pre(str(ingredient or "")))
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", _pre(raw_u))
        main = _w(ing.split(",")[0])
        iset = set(_w(ing))
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        uset = set(t for s in segs for t in s)
        ident_i = [t for t in main if t not in _BENIGN and t not in _CUTS and t not in _PARTS and t not in _STATEF and t not in _DESC and t not in ("ground", "whole")]
        if not ident_i:
            ident_i = [t for t in main if t not in _BENIGN] or main
        # per-segment explainability: fraction of tokens that are benign, explained by ingredient, or cuts
        def explained(seg):
            if not seg:
                return 1.0
            n = 0.0
            for t in seg:
                if t in _BENIGN or t in iset or t in _CUTS or t in ident_i or t in ("ground", "whole"):
                    n += 1.0
                elif t in _STATEF and (t in iset):
                    n += 1.0
                elif t in _STATEF or t in _DESC or t in _PARTS:
                    n += 0.0
                elif t in ("fish", "beef", "pork", "lamb", "chicken", "turkey", "nut", "cheese", "lettuce", "crustacean", "cereal", "fruit", "vegetable", "sausage"):
                    n += 0.8
                else:
                    n += 0.25
            return n / len(seg)
        w0 = 3.0
        tot = 0.0
        wsum = 0.0
        for k, s in enumerate(segs):
            wt = w0 if k == 0 else 1.0
            tot += wt * explained(s)
            wsum += wt
        expl = tot / wsum
        cov = sum(1 for t in ident_i if t in uset) / float(len(ident_i))
        head = ident_i[-1] in uset
        base = 6.0 * cov * (0.4 + 0.6 * expl) + (1.2 if head else -1.5)
        # descriptor cost
        dc = sum(c for t, c in _DESC.items() if t in uset and t not in iset)
        dc += 0.5 * sum(c for t, c in _DESC.items() if t in iset and t not in uset)
        # part nouns: mismatch is heavy
        pi = set(t for t in iset if t in _PARTS)
        pu = set(t for t in uset if t in _PARTS)
        part_pen = sum(_PARTS[t] for t in (pi ^ pu))
        # states
        fi = set(_STATEF[t] for t in iset if t in _STATEF)
        fu = set(_STATEF[t] for t in uset if t in _STATEF)
        sp = len((fi ^ fu) - {"z"}) * 1.1
        if "raw" in uset and not (fu - {"z"}) and (fi - {"z"}):
            sp += 0.2
        front = 2.0 if (segs[0] and segs[0][0] in ("frozen", "dried", "canned", "smoked") and segs[0][0] not in iset) else 0.0
        heavy = 2.5 if (set(segs[0]) & _HEAVY) - iset else 0.0
        score = base - min(dc, 4.0) - part_pen - sp - front - heavy
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score + 2.0)
    except Exception:
        return 0.0
