import re

_DIFF_FORMS = ["oil", "juice", "nectar", "syrup", "sauce", "soup", "pudding", "candy", "jerky", "powder", "flour", "extract", "spice", "frozen yogurt", "snack", "babyfood", "pie", "cake", "cookie"]
_DIET_MODS = ["low fat", "lowfat", "reduced fat", "fat free", "nonfat", "low sodium", "no salt", "without salt", "lactose reduced", "unsweetened", "sweetened", "decaffeinated", "sugar free", "light", "diet"]
_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "shungiku": "chrysanthemum", "maize": "corn", "crawfish": "crayfish", "granada": "pomegranate", "garbanzo": "chickpea", "prawn": "shrimp"}
_FILL = set("fresh frozen thawed chopped diced sliced minced grated shredded cubed melted ripe large small medium finely softened packed optional boneless skinless drained rinsed toasted shelled warmed whole of and or the a for with in cooked raw dried canned lean ground".split())

def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w

def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    return re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", s)

def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ""))
        u = _clean(str(usda_match or ""))
        ing_main = ing.split(",")[0]
        iw = [_SYN.get(_stem(w), _stem(w)) for w in re.findall(r"[a-z]+", ing_main)]
        iw_core = [w for w in iw if w not in _FILL] or iw
        uw = [_SYN.get(_stem(w), _stem(w)) for w in re.findall(r"[a-z]+", u)]
        if not iw_core or not uw:
            return 0.0
        uset = set(uw)
        score = 10.0
        # rule 1: every core word of the ingredient must be somewhere in USDA
        missing = [w for w in iw_core if w not in uset]
        score -= 3.5 * len(missing)
        # rule 2: head noun (last core word) must be present, otherwise heavy penalty
        if iw_core[-1] not in uset:
            score -= 3.0
        # rule 3: USDA's leading segment adds a different form word
        first = u.split(",")[0]
        for f in _DIFF_FORMS:
            if re.search(r"\b" + f, first) and not re.search(r"\b" + f, ing):
                score -= 4.0
                break
        # rule 4: USDA is a prepared dish / brand: more than one capitalised-style marker
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|kfc|subway|restaurant|fast food|entree|sandwich|cookie|\bwith meat|made with", u) and not re.search(r"entree|sandwich|cookie|made with", ing):
            score -= 3.0
        # rule 5: diet modifier asymmetry
        for m in _DIET_MODS:
            if (m in u) != (m in ing):
                score -= 0.8 if m in u else 0.4
        # rule 6: positions - ingredient head ideally is the first USDA noun or immediately in 2nd segment
        segs = [s.strip() for s in u.split(",")]
        head = iw_core[-1]
        if head in [_stem(w) for w in re.findall(r"[a-z]+", segs[0])]:
            score += 1.5
        elif len(segs) > 1 and head in [_stem(w) for w in re.findall(r"[a-z]+", segs[1])]:
            score += 0.8
        # rule 7: extra unexplained nouns in first segment (different compound)
        extra = [w for w in re.findall(r"[a-z]+", segs[0]) if _stem(w) not in iw and _stem(w) not in ("raw", "cooked", "nfs")]
        if len(extra) >= 2:
            score -= 0.6 * (len(extra) - 1)
        return float(score)
    except Exception:
        return 0.0
