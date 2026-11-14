import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "plant": "vegan"}
_PART = set("slice seed segment floret piece chop steak fillet heart tail leaf leave strip wedge chunk cube round rind bone".split())
_FILLER = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot taste tube jar store bought homemade drained packed equal parts plain regular type separable trimmed choice select grade nfs only lean fat and of the with in for from or a all mature variety flavor other than not eaten without salt added free range farmed wild mixed species commercial".split())
_COOK = set("cooked boiled baked braised fried simmered broiled roasted steamed toasted grilled sauteed poached".split())
_FORM = set("oil juice syrup sauce soup pudding cookie cake candy jerky flour snack taco sandwich entree spice stew nectar".split())
_DIET = set("lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated".split())

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
        tail = _w(",".join(ing.split(",")[1:]))
        ut = _w(u)
        if not main or not ut:
            return 0.0
        iall = set(main) | set(tail)
        uset = set(ut)
        first = [x for x in _w(u.split(",")[0])]
        # content tokens = non filler, non state, non part
        ci = [x for x in main if x not in _FILLER and x not in _COOK and x not in _PART and x not in ("raw", "dried", "canned", "frozen", "smoked", "ground", "whole")]
        if not ci:
            ci = [x for x in main if x not in _FILLER] or main
        # token-weighted overlap: head=3, others=1.5 ; USDA side first segment (hierarchy category words weigh 0.5)
        wsum, hit = 0.0, 0.0
        for k, x in enumerate(ci):
            wt = 3.0 if k == len(ci) - 1 else 1.5
            wsum += wt
            if x in uset:
                hit += wt
        recall = hit / wsum
        cu = [x for x in first if x not in _FILLER and x not in _COOK and x not in _PART and x not in ("raw", "dried", "canned", "frozen", "smoked", "ground", "whole")]
        precision = (sum(1 for x in cu if x in iall) / float(len(cu))) if cu else 0.5
        base = recall ** 1.0 * (0.55 + 0.45 * precision)
        # multiplicative gates
        g = 1.0
        if (set(first) & _FORM) - iall:
            g *= 0.35
        icook = bool(iall & _COOK)
        ucook = bool(uset & _COOK) and "raw" not in uset
        if icook != ucook:
            g *= 0.6 if not (icook and "dry" in uset) else 0.8
        idry = bool(iall & {"dried", "powder", "powdered"})
        udry = bool(uset & {"dried", "powder", "powdered", "dry"})
        if idry != udry:
            g *= 0.55
        if ("ground" in iall) != ("ground" in uset):
            g *= 0.8
        nd = len((uset & _DIET) - iall)
        g *= 0.8 ** nd
        if main and ci and ci[-1] not in uset:
            g *= 0.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            g *= 0.3
        # specificity: extra descriptive words in first segment
        extra = [x for x in cu if x not in iall]
        g *= 0.88 ** min(len(extra), 3)
        return float(10.0 * base * g)
    except Exception:
        return 0.0
