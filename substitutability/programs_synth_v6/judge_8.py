import re
import math

_CUTS = set("steak fillet filet chunk slice segment floret seed aril leaf leave piece strip wedge stalk cube round hearts heart bone tip tail".split())
_TRIV = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless whole cold hot warm lean ground drained packed of and or the a with in for from to into".split())
_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "plant": "vegan", "pinyon": "pine", "pinon": "pine", "granada": "pomegranate"}
_RARE_Q = set("mountain beaked imported zealand hawaii wild alaska native indians northern babyfood school restaurant".split())
_STATE_WORDS = {"cooked": 0, "boiled": 0, "baked": 0, "roasted": 0, "braised": 0, "steamed": 0, "simmered": 0, "broiled": 0, "fried": 1, "dried": 2, "dehydrated": 2, "canned": 3, "smoked": 4, "pickled": 5, "raw": 6}
_FORMS = ["oil", "juice", "nectar", "syrup", "sauce", "soup", "pudding", "cookie", "cake", "candy", "jerky", "snack", "spices", "flour", "sandwich", "taco", "entree"]

def _t(s):
    r = []
    for w in re.findall(r"[a-zé\-]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_SYN.get(w, w))
    return r

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u_full = str(usda_match or "")
        u = re.sub(r"\([^)]*\)", " ", u_full.lower())
        it = _t(ing.split(",")[0])
        ut = _t(u)
        iall = set(_t(ing))
        uset = set(ut)
        keep = [w for w in it if w not in _TRIV and w not in _STATE_WORDS and w not in ("canned", "toasted")]
        if not keep:
            keep = [w for w in it if w not in _TRIV] or it
        if not keep or not ut:
            return 0.0
        heads = [w for w in keep if w not in _CUTS] or keep
        head = heads[-1]
        logit = -2.0
        # coverage (log-evidence)
        matched = [w for w in heads if w in uset]
        logit += 3.5 * len(matched) / float(len(heads))
        if head in uset:
            logit += 2.0
        else:
            logit -= 1.0
        # cut words are mild bonus if they match
        logit += 0.3 * sum(1 for w in keep if w in _CUTS and w in uset)
        # state compatibility
        si = set(w for w in iall if w in _STATE_WORDS)
        su = set(w for w in uset if w in _STATE_WORDS)
        def klass(s):
            return set(_STATE_WORDS[w] for w in s)
        ki, ku = klass(si), klass(su)
        if ki and ku:
            logit += 1.5 if ki & ku else -1.5
        elif ku and 6 not in ku and not ki:
            logit -= 1.2  # usda is processed, ingredient unmarked
        elif ki and not ku and 6 not in ki:
            logit -= 0.8
        elif ki and 6 in ki and not ku:
            logit += 0.5
        # unwanted product forms
        first = " ".join(_t(u.split(",")[0]))
        for f in _FORMS:
            if re.search(r"\b" + f, first) and f not in iall and f not in " ".join(it):
                logit -= 2.5
                break
        # rare qualifiers
        if any(w in _RARE_Q for w in ut) and not any(w in _RARE_Q for w in it):
            logit -= 1.5
        # a USDA brand all-caps token is neutral; additional fat/sodium qualifiers only for cheese
        if "cheese" in uset and re.search(r"lowfat|low fat|reduced|nonfat|fat free|low sodium|lactose", u) and not re.search(r"low|reduced|free|nonfat|light", ing):
            logit -= 1.5
        return float(1.0 / (1.0 + math.exp(-logit)))
    except Exception:
        return 0.0
