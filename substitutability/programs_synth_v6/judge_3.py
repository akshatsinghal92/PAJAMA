import re

_SYNS = [("clementine", "tangerine"), ("mandarin", "tangerine"), ("fava", "broadbean"), ("shungiku", "chrysanthemum"),
         ("maize", "corn"), ("crawfish", "crayfish"), ("granada", "pomegranate"), ("garbanzo", "chickpea"),
         ("plant-based", "vegan"), ("prawn", "shrimp"), ("cilantro", "coriander")]
_NOISE = set("fresh frozen thawed chopped diced sliced minced grated shredded cubed melted ripe large small medium finely softened packed optional boneless skinless drained rinsed toasted shelled warmed strong brewed canned dried cooked raw whole lean".split())
_BRAND = re.compile(r"taco bell|mcdonald|burger king|wendy|pizza hut|kfc|subway|restaurant|fast food|cookies|sandwich|entree|\bnfs\b.*mix|school lunch|babyfood")

def _norm(s):
    s = s.lower()
    for a, b in _SYNS:
        s = s.replace(a, b)
    return s

def _grams(s, n=3):
    s = " " + s + " "
    return set(s[i:i + n] for i in range(len(s) - n + 1)) if len(s) >= n else set([s])

def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", _norm(str(ingredient or "")))
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", _norm(str(usda_match or "")))
        iw = [w for w in re.findall(r"[a-z]+", ing.split(",")[0]) if w not in _NOISE]
        if not iw:
            return 0.0
        phrase = " ".join(iw)
        useg = [s.strip() for s in u.split(",")]
        # best segment-level similarity of the full ingredient phrase to any of the first 3 segments
        best = 0.0
        for s in useg[:3]:
            sw = " ".join(w for w in re.findall(r"[a-z]+", s) if w not in _NOISE)
            best = max(best, _dice(_grams(phrase), _grams(sw)))
        # reordered USDA name (USDA lists category first): concatenate segments reversed
        rev = " ".join(re.findall(r"[a-z]+", " ".join(reversed(useg[:3]))))
        best = max(best, _dice(_grams(phrase), _grams(rev)))
        # head noun via char-grams in whole USDA string
        head = iw[-1]
        hs = head[:-1] if head.endswith("s") and len(head) > 3 else head
        head_in_first = hs in useg[0]
        head_any = hs in u
        head_score = 1.0 if head_in_first else (0.6 if head_any else 0.0)
        # first-word-of-ingredient (modifier) conflict: ingredient is X-Y but USDA first segment is Z-Y
        conflict = 0.0
        if len(iw) >= 2 and head_in_first:
            mod = iw[-2]
            if mod[:4] not in u:
                conflict = 0.5
        score = 5.0 * best + 4.0 * head_score - 1.5 * conflict
        if _BRAND.search(u) and not _BRAND.search(ing):
            score -= 3.0
        # extra long USDA descriptions are less specific
        score -= 0.1 * max(0, len(useg) - 4)
        return float(score)
    except Exception:
        return 0.0
