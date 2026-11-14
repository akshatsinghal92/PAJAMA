import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "plant": "vegan", "purée": "puree"}
_CUTS = set("steak chop fillet filet heart seed segment floret slice piece strip wedge chunk cube round rind bone tail leaf leave stem neck wing breast thigh leg shank loin roast rib flat".split())
_NEUTRAL = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat variety by product".split())
_STATE = set("raw cooked boiled baked braised simmered broiled roasted steamed toasted dried frozen ground whole canned smoked pickled fried".split())
_COOKFAM = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted"}
# plainness cost of descriptor words (processing/additive intensity)
_COST = {"sweetened": 1.5, "salted": 1.0, "flavored": 1.5, "breaded": 2.0, "battered": 2.0, "seasoned": 1.5, "glazed": 1.5, "marinated": 1.5, "candied": 2.0, "fortified": 0.8, "enriched": 0.8, "hydrogenated": 1.5,
         "lowfat": 1.3, "nonfat": 1.3, "reduced": 1.3, "light": 1.0, "diet": 1.0, "lactose": 1.2, "sodium": 1.0, "decaffeinated": 1.2, "skim": 1.3,
         "prepared": 1.2, "mix": 1.5, "entree": 3.0, "sandwich": 3.0, "taco": 3.0, "cookie": 3.0, "gravy": 2.0, "sauce": 1.6, "oat": 1.0, "oats": 1.0, "vegetable": 1.0, "strawberry": 1.4, "peach": 1.4, "chocolate": 1.4, "frozen": 0.0,
         "deli": 1.2, "luncheon": 1.2, "prepackaged": 1.0, "imported": 1.0, "beaked": 1.5, "mountain": 1.5, "zealand": 1.2, "hawaii": 1.2}

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _strip_brand(raw):
    # USDA brand tokens are written in capitals: drop them (keep sentence-initial single capital words)
    toks = raw.split()
    kept = [t for t in toks if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper())]
    return " ".join(kept)

def judging_function(ingredient, usda_match):
    try:
        raw_u = str(usda_match or "")
        brand_present = len(_strip_brand(raw_u).split()) < len(raw_u.split())
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", _strip_brand(raw_u).lower())
        it = _w(ing)
        main = _w(ing.split(",")[0])
        ut = _w(u)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        iset, uset = set(it), set(ut)
        core = [t for t in main if t not in _NEUTRAL and t not in _STATE and t not in _CUTS and t not in _COST]
        if not core:
            core = [t for t in main if t not in _NEUTRAL and t not in _STATE] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = 1.5 if core[-1] in uset else -1.2
        # plainness: cost of descriptors on each side
        cost_u = sum(c for t, c in _COST.items() if t in uset and t not in iset)
        cost_i = sum(c for t, c in _COST.items() if t in iset and t not in uset) * 0.6
        # explicit plain statements reduce cost
        if re.search(r"without salt|unsalted|no salt|unsweetened|no added", u):
            cost_u = max(0.0, cost_u - 0.8)
        if re.search(r"fat added|salt added|sugar added|added fat|added sugar|made with|prepared from", u) and not re.search(r"added|made with|prepared", ing):
            cost_u += 1.2
        # extra unexplained first-segment word that is not a taxon/neutral/cut
        first = segs[0]
        unexplained = [t for t in first if t not in iset and t not in _NEUTRAL and t not in _STATE and t not in _CUTS and t not in _COST and t not in core]
        # state names at the front of USDA (Frozen yogurt) alter identity
        front_state = 1.0 if (first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset) else 0.0
        # states elsewhere
        si, su = iset & _STATE, uset & _STATE
        d = (si ^ su) - {"raw", "whole", "frozen"}
        if si & _COOKFAM and su & _COOKFAM:
            d = d - _COOKFAM
        if "dried" in su and "dried" in iset:
            d = d - {"dried"}
        score = 5.0 * cov + head - 1.0 * min(cost_u, 4.0) - min(cost_i, 2.0) - 0.7 * min(len(unexplained), 3) - 2.5 * front_state - 1.1 * len(d)
        if (set(first) & {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "spice"}) - iset:
            score -= 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        if brand_present and cov > 0.6:
            score += 0.8
        return float(score + 2.0)
    except Exception:
        return 0.0
