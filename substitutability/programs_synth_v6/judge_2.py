import re

_STOP = set("fresh frozen thawed chopped diced sliced minced grated shredded cubed melted ripe large small medium finely roughly softened packed of and or the a for to in with from into optional whole lean skin on off trimmed drained rinsed toasted equal parts raw cooked dried canned plain nfs".split())
_SYN = {"crawfish": "crayfish", "plant": "vegan", "based": "", "granada": "pomegranate", "maize": "corn", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "prawn": "shrimp"}
_CATS = set("beef pork fish chicken turkey cheese nut seed oil lamb veal crustacean sausage fruit vegetable".split())
_PROC = set("juice nectar sauce pudding soup oil powder jerky candy snack yogurt cereal bread cake cookie".split())

def _tok(s):
    out = []
    for w in re.findall(r"[a-z]+", s.lower()):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        w = _SYN.get(w, w)
        if w:
            out.append(w)
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        core = [w for w in _tok(ing.split(",")[0]) if w not in _STOP]
        if not core:
            return 0.0
        useg = [_tok(s) for s in u.split(",")]
        uall = set(w for s in useg for w in s)
        # weight later ingredient words (head) more
        n = len(core)
        wts = [1.0 + 1.5 * (i == n - 1) for i in range(n)]
        hit = 0.0
        for w, wt in zip(core, wts):
            if w in uall:
                hit += wt
            elif any(len(w) > 4 and len(x) > 4 and (w.startswith(x[:5]) or x.startswith(w[:5])) for x in uall):
                hit += 0.6 * wt
        recall = hit / sum(wts)
        # USDA name precision: the leading segment words not explained by ingredient
        lead = [w for w in useg[0] if w not in _STOP]
        cset = set(core)
        unexplained = [w for w in lead if w not in cset and w not in _CATS and not any(w in c or c in w for c in cset if len(c) > 3)]
        prec_pen = 0.0
        for w in unexplained:
            prec_pen += 0.9 if w in _PROC else 0.35
        # head noun of ingredient must appear within leading two segments
        head = core[-1]
        lead2 = set(useg[0]) | (set(useg[1]) if len(useg) > 1 else set())
        head_ok = 1.0 if head in lead2 else (0.4 if head in uall else 0.0)
        score = 5.0 * recall + 3.0 * head_ok - 2.0 * prec_pen
        # processed-form words in USDA that ingredient lacks
        for w in uall:
            if w in _PROC and w not in cset and w not in core:
                score -= 1.5
                break
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|kfc|restaurant|fast food|chobani", u) and "chobani" not in u:
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
