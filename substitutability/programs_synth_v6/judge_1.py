import re

_PREP = set("fresh frozen thawed chopped diced sliced minced grated shredded cubed melted ripe large small medium cooked raw dried ground crushed peeled optional finely roughly softened packed boiled whole of and or the a for to in with from into halved trimmed drained rinsed toasted hearts".split())
_NOTHEAD = set("sauce oil juice nectar pudding puddings powder soup candy frozen restaurant babyfood cereals cereal".split())

def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w

def _words(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        main = ing.split(",")[0]
        ing_w = [w for w in _words(main) if w not in _PREP]
        if not ing_w:
            ing_w = _words(main)
        if not ing_w:
            return 0.0
        usda_clean = re.sub(r"\([^)]*\)", " ", usda)
        segs = usda_clean.split(",")
        first = _words(segs[0])
        allw = set(_words(usda_clean))
        rest = set(_words(" ".join(segs[1:])))
        head = ing_w[-1]
        score = 0.0
        # head noun identity
        if head in first:
            score += 4.0
            if first and first[-1] == head or first[0] == head:
                score += 1.0
        elif head in allw:
            score += 2.0
        else:
            score -= 1.0
        # coverage of all ingredient content words
        cov = sum(1 for w in ing_w if w in allw) / float(len(ing_w))
        score += 4.0 * cov
        # modifier words of ingredient that conflict: first segment foreign nouns
        extra = [w for w in first if w not in ing_w and w not in _PREP]
        score -= 0.8 * min(len(extra), 3)
        # transformed product mismatch
        for w in first:
            if w in _NOTHEAD and w not in ing_w:
                score -= 3.0
        if "bone" in ing_w and "removed" in allw:
            score -= 2.0
        # restaurant / branded
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|kfc|restaurant|fast food", usda):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
