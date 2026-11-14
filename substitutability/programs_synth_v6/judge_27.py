import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "plant": "vegan"}
_CATEGORY_HEADS = set("beef pork lamb veal chicken turkey duck fish cheese nut seed lettuce crustacean cereal fruit vegetable sausage game mollusk poultry".split())
_SKIP = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a with in for from or nfs regular plain type separable trimmed choice select grade only mature variety flavor other than not eaten without salt added lean fat free range farmed wild mixed species commercial all meat strong brewed round".split())
_PARTS = set("seed leaf leave bone skin peel stem shell rind root tail".split())
# per-segment descriptor classes and their penalties
_TRANSFORM = set("oil juice syrup sauce soup pudding cookie cake candy jerky flour snack taco sandwich entree spice stew nectar".split())
_STATE = set("cooked boiled baked braised fried simmered broiled roasted steamed toasted dried canned smoked pickled frozen".split())
_DIET = set("lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated vegetable oat strawberry".split())

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
        main = _w(ing.split(",")[0])
        iall = set(_w(ing))
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        content = [t for t in main if t not in _SKIP and t not in _STATE and t not in _PARTS and t not in ("raw", "ground", "whole")]
        if not content:
            content = [t for t in main if t not in _SKIP] or main
        head = content[-1]
        # level at which each content token first appears
        def level(t):
            for k, s in enumerate(segs):
                if t in s:
                    return k
            return None
        score = 0.0
        hl = level(head)
        if hl is None:
            score -= 3.0
        else:
            score += 4.0 - 0.7 * min(hl, 4)
            if segs[0] and set(segs[0]) <= (iall | _CATEGORY_HEADS | {"raw"}):
                score += 1.5   # USDA primary name is fully explained by the ingredient
        for t in content[:-1]:
            tl = level(t)
            if tl is None:
                score -= 2.0
            else:
                score += 1.6
        # category-only first segment: ingredient head must then be found in later segments (already scored).
        # descriptors per segment
        used = set(content) | iall
        for k, s in enumerate(segs):
            w = 1.0 if k == 0 else (0.7 if k == 1 else 0.4)
            for t in s:
                if t in used or t in _SKIP:
                    continue
                if t in _TRANSFORM:
                    score -= 3.0 * w
                elif t in _STATE:
                    score -= 1.5 * w
                elif t in _DIET:
                    score -= 1.2 * w
                elif t in _PARTS:
                    score -= 1.8 * w
                elif t in _CATEGORY_HEADS:
                    pass
                elif k == 0:
                    score -= 0.8
        # ingredient-side state/part not reflected
        for t in iall:
            if t in _STATE and t != "frozen" and t not in set(x for s in segs for x in s):
                if not (t in ("roasted", "baked", "boiled", "toasted", "simmered", "steamed", "braised", "broiled") and {"cooked"} & set(x for s in segs for x in s)):
                    score -= 1.2
            if t in _PARTS and t not in set(x for s in segs for x in s):
                score -= 1.0
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
