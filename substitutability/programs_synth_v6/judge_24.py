import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "plant": "vegan", "puree": "sauce", "purée": "sauce"}
_FREE = set("raw nfs regular plain type separable trimmed choice select grade all mature variety flavor other than not eaten fresh and of the with in for from or a to into only meat free range farmed wild mixed species commercial lean fat".split())
_PREPW = set("thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot taste tube jar store bought homemade drained packed equal parts strong brewed round".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk seed".split())
_COST = {}
for _w in "oil juice syrup sauce soup pudding cookie cake candy jerky flour snack taco sandwich entree spice stew nectar".split():
    _COST[_w] = 3.0
for _w in "lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated vegetable oat strawberry".split():
    _COST[_w] = 1.3
for _w in "cooked boiled baked braised fried simmered broiled roasted steamed toasted dried canned smoked pickled ground frozen".split():
    _COST[_w] = 1.6
for _w in "seed leaf leave bone skin peel stem shell rind root tail".split():
    _COST[_w] = 2.0
_STATE_EQ = [{"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "fried", "heat", "dry", "moist"}, {"dried", "dehydrated", "dry"}, {"canned", "drained"}]

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _equiv(a, b):
    if a == b:
        return True
    for g in _STATE_EQ:
        if a in g and b in g and a not in ("dry", "dried", "fried") and b not in ("dry", "dried", "fried"):
            return True
    return False

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        itoks = _w(ing)
        main = _w(ing.split(",")[0])
        usegs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not usegs:
            return 0.0
        # ledger pass over USDA tokens: explained / free / costed
        ledger = 0.0
        explained = 0
        unexplained_cost = 0.0
        for k, seg in enumerate(usegs):
            discount = 1.0 if k == 0 else (0.6 if k == 1 else 0.3)
            for t in seg:
                if t in itoks or any(_equiv(t, x) for x in itoks if t in _COST and x in _COST):
                    explained += 1
                    ledger += 1.0 * (1.2 if k == 0 else 0.8)
                elif t in _FREE or t in _PREPW:
                    continue
                elif t in _TAXON and k == 0:
                    continue
                elif t in _COST:
                    unexplained_cost += _COST[t] * discount
                else:
                    unexplained_cost += 0.9 * discount if k == 0 else 0.15
        # ledger pass over ingredient main tokens: unmatched ones cost
        uflat = set(t for s in usegs for t in s)
        miss_cost = 0.0
        head = None
        content = [t for t in main if t not in _FREE and t not in _PREPW]
        for k, t in enumerate(content):
            if t in uflat or any(_equiv(t, x) for x in uflat if t in _COST and x in _COST):
                continue
            if t in _COST:
                miss_cost += 0.8 * _COST[t] / 1.6
            else:
                miss_cost += 2.2 if k == len(content) - 1 else 1.6
        denom = float(max(1, len([t for t in content if t not in _COST])))
        score = 2.0 * ledger / (denom + 1.0) - unexplained_cost - miss_cost
        score += 4.0
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
