import re

_PREP = set("""chopped diced sliced minced cubed melted thawed fresh ripe large small medium
finely roughly cooked raw dried frozen hearts florets pulp ground powdered whole boneless
skinless peeled shredded grated crushed soft hard unsweetened sweetened plant based""".split())
_FORM = set("oil nectar pudding puddings frozen juice syrup sauce soup candy cookie cookies cake pie powder flour extract".split())
_BRANDS = ("taco bell", "mcdonald", "burger king", "wendy", "kfc", "subway", "pizza hut", "applebee", "restaurant", "fast food")


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)?\b", " ", ing)
        main = ing.split(",")[0]
        itoks = _tokens(main)
        core = [t for t in itoks if t not in _PREP]
        if not core:
            core = itoks
        if not core:
            return 0.0
        head = core[-1]
        segs = [s.strip() for s in usda.split(",") if s.strip()]
        usegs = [_tokens(re.sub(r"\([^)]*\)", " ", s)) for s in segs]
        if not usegs:
            return 0.0
        allu = set(t for s in usegs for t in s)
        first = usegs[0]
        score = 0.0
        # head noun presence
        if head in first:
            score += 5.0
            if first[-1] == head or first[0] == head:
                score += 1.0
        elif head in allu:
            score += 3.0
        else:
            # partial char overlap of head with any token
            if any(len(head) > 4 and (head[:5] == t[:5]) for t in allu):
                score += 1.5
        # fraction of core ingredient words covered
        cov = sum(1 for t in core if t in allu) / float(len(core))
        score += 3.0 * cov
        # category word mismatch: USDA first segment is a form word absent from ingredient
        itokset = set(itoks)
        ftok = set(first)
        for f in _FORM:
            if f in ftok and _stem(f) not in itokset:
                score -= 3.0
        low = " " + " ".join(re.findall(r"[a-z]+", usda)) + " "
        for b in _BRANDS:
            if b in low:
                score -= 4.0
        for f in ("frozen", "powder", "dry mix", "canned", "juice", "oil"):
            if f in low and f not in ing:
                score -= 0.7
        # extra unrelated words in first segment
        extra = [t for t in first if t not in set(core) and t not in itokset]
        score -= 0.4 * min(len(extra), 4)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
