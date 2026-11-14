import re

_ALIAS = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "pinon": "pine", "para": "brazil", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "plant": "vegan"}
# generic / neutral descriptors that do not make an entry "specific"
_NEUTRAL = set("raw nfs regular plain type separable lean fat only trimmed choice select grades all meat mature seeds whole variety flavors other than not eaten fresh drained of and or the a with in for from to into cooked canned frozen dried boiled baked roasted without salt added".split())
# qualifiers that a diner would notice when they appear on only one side
_NOTICE = set("lowfat nonfat reduced low light diet sodium decaffeinated unsweetened sweetened lactose vegetable vegetables oats flavored smoked cured pickled imported hydrogenated fortified enriched prepackaged deli luncheon ground crumbles patties patty breaded fried battered organic wild roasted toasted".split())
_PREP = set("chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot steak fillet seed segment floret slice piece strong brewed round".split())

def _t(s):
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
        it = _t(ing.split(",")[0])
        itail = _t(",".join(ing.split(",")[1:]))
        ut = _t(u)
        if not it or not ut:
            return 0.0
        iall = set(it) | set(itail)
        uset = set(ut)
        # ingredient qualifiers: non-prep, non-neutral words besides the head
        core = [w for w in it if w not in _PREP and w not in _NEUTRAL]
        if not core:
            core = [w for w in it if w not in _PREP] or it
        head = core[-1]
        iq = [w for w in core[:-1]]  # modifiers of the head
        # USDA qualifiers: words other than the head and not neutral
        usegs = [_t(s) for s in u.split(",")]
        uq = []
        for k, seg in enumerate(usegs):
            for w in seg:
                if w == head or w in _NEUTRAL:
                    continue
                uq.append((w, k))
        # head presence
        score = 3.0 if head in uset else 0.0
        # ingredient modifiers: reward if present in USDA, penalise if absent
        for w in iq:
            score += 1.8 if w in uset else -1.4
        # USDA qualifiers not implied by ingredient
        unexplained = []
        for w, k in uq:
            if w in iall or w in set(it):
                continue
            unexplained.append((w, k))
        for w, k in unexplained:
            if w in _NOTICE:
                score -= 1.6
            elif k == 0:
                score -= 0.9   # extra word in the primary name = different specific food
            elif k >= 1:
                score -= 0.25  # tail descriptor, mostly harmless
        # unqualified ingredient + generic USDA is ideal
        if not iq and len(usegs[0]) <= 2:
            score += 1.5
        # qualified ingredient but USDA generic (dropped qualifier)
        if iq and not any(w in uset for w in iq):
            score -= 1.5
        # state agreement on cooked/raw
        cooked = {"cooked", "boiled", "baked", "roasted", "braised", "fried", "steamed", "simmered", "broiled"}
        ic = bool(iall & cooked)
        uc = bool(uset & cooked)
        if ic != uc and not (("raw" in uset) and not ic):
            score -= 1.2
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food|entree|sandwich", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
