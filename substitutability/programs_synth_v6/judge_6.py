import re

_HARMFUL = set("cooked boiled baked roasted braised broiled grilled steamed simmered stewed fried deep-fried pan-broiled dried dehydrated canned frozen smoked cured pickled sweetened unsweetened decaffeinated lowfat nonfat fat-free reduced low light diet added lactose sodium salt juice oil syrup sauce powder flour jerky soup cookie cake pie bread restaurant entree sandwich crumbles patties patty".split())
_HARMLESS = set("raw nfs fresh separable lean fat trimmed choice select all grades whole meat only skin with without drained mature seeds regular plain type variety flavors other than the of and or in a from".split())
_ING_STATE_HARM = {"cooked": ["cooked", "boiled", "baked", "roasted", "braised", "grilled", "steamed", "simmered", "fried", "sautéed", "sauteed", "poached", "baked"],
                   "dried": ["dried", "dehydrated"], "canned": ["canned"], "smoked": ["smoked"], "frozen": ["frozen"]}
_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea"}

def _toks(s):
    out = []
    for w in re.findall(r"[a-zé\-]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(_SYN.get(w, w))
    return out

def judging_function(ingredient, usda_match):
    try:
        raw_ing = str(ingredient or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", raw_ing)
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _toks(ing)
        ut = _toks(u)
        if not it or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        trivial = set("chopped diced minced sliced shredded thawed grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole".split())
        # content words in ingredient
        content = [w for w in it if w not in trivial and w not in _HARMFUL and w not in _HARMLESS]
        if not content:
            content = [w for w in it if w not in trivial] or it
        covered = sum(1 for w in content if w in uset)
        ident = covered / float(len(content))
        score = 6.0 * ident
        if content[-1] in uset:
            score += 1.5
        # harmful residual words in USDA not matched by ingredient
        resid_harm = [w for w in ut if w in _HARMFUL and w not in iset]
        resid_harm = list(dict.fromkeys(resid_harm))
        score -= 1.6 * min(len(resid_harm), 4)
        # harmful words in ingredient state not found in USDA
        miss = 0
        for grp, vs in _ING_STATE_HARM.items():
            if any(v in iset for v in vs) and not any(v in uset for v in vs):
                if grp == "frozen":
                    continue
                miss += 1
        score -= 1.2 * miss
        # explicit raw in usda while ingredient says cooked-like
        if "raw" in uset and any(v in iset for v in _ING_STATE_HARM["cooked"]):
            score -= 1.5
        # unexplained extra substantive words in first segment
        first = _toks(u.split(",")[0])
        extra = [w for w in first if w not in iset and w not in _HARMLESS and w not in _HARMFUL]
        score -= 0.5 * max(0, len(extra) - 1)
        return float(score)
    except Exception:
        return 0.0
