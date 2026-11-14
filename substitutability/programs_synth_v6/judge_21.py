import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "cos": "romaine", "granada": "pomegranate", "plant": "vegan"}
_NOISE = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot to taste tube jar store bought homemade of and or the a with in for from into drained packed equal parts nfs regular plain type separable trimmed choice select grade all only mature variety flavor other than not eaten without salt added".split())
_STATEW = set("raw cooked canned frozen dried boiled baked roasted braised fried steamed simmered broiled smoked pickled toasted ground whole".split())
_FORMS = {"oil", "juice", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "flour", "snack", "taco", "sandwich", "entree", "spice", "stew", "nectar"}
_MODS = set("lowfat nonfat reduced low light diet sodium decaffeinated unsweetened sweetened lactose oat imported hydrogenated deli luncheon prepackaged beaked mountain zealand hawaii".split())

def _toks(s):
    r = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_ALIAS.get(w, w))
    return r

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = [w for w in _toks(ing) if w not in _NOISE]
        ut = [w for w in _toks(u) if w not in _NOISE]
        if not it or not ut:
            return 0.0
        content_i = [w for w in it if w not in _STATEW]
        content_u = [w for w in ut if w not in _STATEW]
        if not content_i:
            content_i = it
        if not content_u:
            content_u = ut
        ci, cu = set(content_i), set(content_u)
        inter = ci & cu
        jac = len(inter) / float(len(ci | cu))
        # asymmetric: how much of ingredient is covered vs how much of usda's first segment is explained
        rec = len(inter) / float(len(ci))
        first = set(w for w in _toks(u.split(",")[0]) if w not in _NOISE and w not in _STATEW)
        prec = len(first & ci) / float(len(first)) if first else 0.0
        # bigram agreement on content order
        bi_i = set(zip(content_i, content_i[1:]))
        bi_u = set(zip(content_u, content_u[1:])) | set(zip(content_u[::-1], content_u[::-1][1:]))
        bi = len(bi_i & bi_u) / float(len(bi_i)) if bi_i else rec
        head = content_i[-1]
        head_hit = 1.0 if head in cu else 0.0
        score = 3.0 * rec + 2.5 * prec + 1.5 * jac + 1.0 * bi + 2.0 * head_hit
        # state overlap: agreeing state words add, conflicting subtract
        si = set(it) & _STATEW
        su = set(ut) & _STATEW
        score += 0.6 * len((si & su) - {"whole"})
        score -= 0.9 * len(((si ^ su) - {"raw", "whole", "frozen"}))
        # overlap coming from modifiers only: head not matched and rec low
        if not head_hit and rec < 0.7:
            score -= 1.5
        if (set(first) & _FORMS) - set(it):
            score -= 2.5
        for w in (set(ut) & _MODS) - set(it):
            score -= 0.8
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
