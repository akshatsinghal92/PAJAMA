import re

_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "para": "brazil"}
_IGN = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole lean drained of and or the a with in for from to into steak fillet seed segment floret slice piece cold hot".split())
# tail descriptor classes in USDA that signal specific preserved forms
_PRESERVE = {"canned": "canned", "frozen": "frozen", "dried": "dried", "dehydrated": "dried", "dry": "dried", "jarred": "canned", "bottled": "canned", "concentrate": "paste", "paste": "paste", "puree": "paste", "powder": "powder", "mix": "powder", "juice": "juice", "pickled": "pickled", "smoked": "smoked", "cured": "smoked"}

def _t(s):
    r = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_SYN.get(w, w))
    return r

def _pres(tokens):
    return set(_PRESERVE[w] for w in tokens if w in _PRESERVE)

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        raw_u = str(usda_match or "")
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        segs = [_t(s) for s in u.split(",") if s.strip()]
        if not segs:
            return 0.0
        it_all = _t(ing)
        it_main = _t(ing.split(",")[0])
        core = [w for w in it_main if w not in _IGN and w not in _PRESERVE and w not in ("cooked", "raw", "canned", "toasted", "ground", "baked", "roasted")]
        if not core:
            core = [w for w in it_main if w not in _IGN] or it_main
        if not core:
            return 0.0
        # position weighted identity: each core word found in segment k gets weight 1/(1+0.4k)
        tot = 0.0
        for w in core:
            best = 0.0
            for k, s in enumerate(segs):
                if w in s:
                    best = max(best, 1.0 / (1.0 + 0.35 * k))
            tot += best
        ident = tot / len(core)
        score = 7.0 * ident
        # head must appear in first two segments for the bonus
        head = core[-1]
        if any(head in s for s in segs[:2]):
            score += 1.0
        # preservation agreement: ingredient (name + post-comma) vs usda tail
        pi = _pres(it_all)
        pu = _pres([w for s in segs for w in s])
        if pi == pu:
            score += 2.0
        elif not pi and pu:
            # usda preserved but ingredient says nothing: fresh ingredient vs preserved entry
            score -= 1.5 * len(pu - {"frozen"}) + 0.3
        elif pi and not pu:
            score -= 1.0 * len(pi - {"frozen"})
        else:
            score -= 1.5 * len(pi ^ pu)
        # name-bearing product words in segment 0
        for f in ("oil", "juice", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "snack", "spice", "taco", "sandwich", "entree"):
            if f in segs[0] and f not in it_all:
                score -= 3.0
                break
        # extra specificity in usda first segment
        extra = [w for w in segs[0] if w not in it_all and w not in _IGN]
        score -= 0.4 * min(len(extra), 3)
        return float(score)
    except Exception:
        return 0.0
