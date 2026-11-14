import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "plant": "vegan"}
_ADDITIVES = {
    "salt": 1.0, "salted": 1.0, "sugar": 1.2, "sweetened": 1.3, "syrup": 1.0, "honey": 1.0, "oil": 1.2, "butter": 1.0, "fat": 0.0, "cream": 0.8,
    "breaded": 2.0, "battered": 2.0, "batter": 2.0, "seasoned": 1.5, "flavored": 1.3, "marinated": 1.5, "glazed": 1.5, "candied": 2.0,
    "gravy": 2.0, "sauce": 1.8, "cheese": 1.2, "vegetable": 1.0, "vegetables": 1.0, "meat": 0.0, "mix": 1.5, "prepared": 1.2, "fortified": 0.8, "enriched": 0.8,
    "strawberry": 1.5, "peach": 1.5, "chocolate": 1.5, "vanilla": 1.0, "fruit": 1.0, "oats": 1.2, "oat": 1.2, "garlic": 1.2, "pepper": 0.8, "herbs": 1.2, "spices": 1.2,
    "hydrogenated": 1.5, "preservative": 1.0, "additives": 1.5, "lactose": 0.8, "decaffeinated": 1.0, "diet": 1.0, "fried": 1.5,
}
_REMOVERS = {"unsalted": ("salt", 1.0), "unsweetened": ("sugar", 1.0), "plain": (None, 0.0), "nonfat": ("fat", 0.0), "lowfat": ("fat", 0.0), "reduced": ("fat", 0.0), "free": ("fat", 0.0)}
_NEUTRAL = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel".split())
_STATEW = set("raw cooked boiled baked braised fried simmered broiled roasted steamed toasted dried canned smoked pickled frozen ground whole".split())
_COMP_RE = re.compile(r"\b(with|made with|prepared with|and|in|from)\b")

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _w(ing)
        main = _w(ing.split(",")[0])
        ut = _w(u)
        uf = _w(u.split(",")[0])
        if not main or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        # additive load of each side
        def load(tokens, st):
            tot = 0.0
            for t in set(tokens):
                tot += _ADDITIVES.get(t, 0.0)
            return tot
        # words that define the ingredient are not additive for it (e.g. 'cheese' in 'cheese cracker')
        core = [t for t in main if t not in _NEUTRAL and t not in _STATEW]
        if not core:
            core = [t for t in main if t not in _NEUTRAL] or main
        add_u = sum(_ADDITIVES.get(t, 0.0) for t in uset if t not in iset)
        add_i = sum(_ADDITIVES.get(t, 0.0) for t in iset if t not in uset)
        # explicit "no added / without" in USDA is good, "added" in USDA is bad
        raw_u = u
        bonus = 0.0
        if re.search(r"without salt|unsalted|no salt|no added|unsweetened", raw_u):
            bonus += 0.6
        if re.search(r"fat added|added fat|salt added|sugar added|added sugar|with added", raw_u) and not re.search(r"added", ing):
            add_u += 1.5
        # compound structure: connector words in USDA that the ingredient lacks
        comp_u = len(_COMP_RE.findall(raw_u))
        comp_i = len(_COMP_RE.findall(ing))
        comp_pen = 0.5 * max(0, comp_u - comp_i)
        # identity
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = 1.5 if core[-1] in uset else -1.0
        score = 4.5 * cov + head + bonus - 1.1 * min(add_u, 4.0) - 0.7 * min(add_i, 3.0) - comp_pen
        # state mismatch
        cookfam = {"cooked", "boiled", "baked", "braised", "fried", "simmered", "broiled", "roasted", "steamed", "toasted"}
        si, su = iset & _STATEW, uset & _STATEW
        d = (si ^ su) - {"raw", "whole", "frozen"}
        if si & cookfam and su & cookfam:
            d = d - cookfam
        score -= 1.2 * len(d)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food|entree|sandwich|cookie", u) and not re.search(r"cookie|sandwich", ing):
            score -= 3.0
        # transformation to different product
        if (set(uf) & {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "spice"}) - iset:
            score -= 2.5
        return float(score + 2.0)
    except Exception:
        return 0.0
