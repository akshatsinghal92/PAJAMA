import re

_STATES = {
    "raw": ["raw", "fresh", "uncooked"],
    "cooked": ["cooked", "boiled", "baked", "roasted", "braised", "broiled", "grilled", "steamed", "simmered", "stewed", "pan-broiled", "sauteed", "sautéed", "poached"],
    "fried": ["fried", "deep-fried", "pan-fried"],
    "dried": ["dried", "dehydrated", "dry"],
    "canned": ["canned", "drained"],
    "frozen": ["frozen"],
    "smoked": ["smoked", "cured"],
    "pickled": ["pickled", "brined"],
    "ground": ["ground", "powder", "powdered", "flour"],
}
_TRIVIAL = set("chopped diced minced sliced shredded thawed grated cubed crushed peeled trimmed halved torn crumbled julienned shelled drained rinsed warmed melted softened".split())
_FILL = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled trimmed halved torn crumbled ripe large small medium finely optional boneless skinless shelled drained rinsed warmed melted softened whole of and or the a with in raw cooked dried canned lean".split())

def _states(text):
    found = set()
    ws = set(re.findall(r"[a-zé\-]+", text))
    for k, vs in _STATES.items():
        if any(v in ws for v in vs):
            found.add(k)
    return found

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        si = _states(ing)
        su = _states(u)
        # implicit default: unmarked USDA entries and unmarked ingredients are treated as raw
        # (USDA 'Chard, cooked' marks; plain 'Radish' is raw)
        ei = set(si) if si else {"raw"}
        eu = set(su) if su else {"raw"}
        # frozen alone is trivial relative to raw
        ei2 = ei - {"frozen"} or {"raw"}
        eu2 = eu - {"frozen"} or {"raw"}
        # state score
        if ei2 & eu2:
            st = 4.0
        elif (ei2 <= {"raw"} and eu2 <= {"raw", "ground"}) or (ei2 <= {"ground"} and eu2 <= {"raw"}):
            st = 3.0
        else:
            st = 0.0
            # mild pairs: cooked <-> canned, cooked<->smoked
            mild = [{"cooked", "canned"}, {"cooked", "smoked"}, {"dried", "ground"}]
            for m in mild:
                if ei2 <= m and eu2 <= m:
                    st = 1.5
        # identity base: fraction of core ingredient words found in usda
        iw = [w.rstrip("s") for w in re.findall(r"[a-z]+", ing.split(",")[0]) if w not in _FILL]
        uw = set(w.rstrip("s") for w in re.findall(r"[a-z]+", u))
        if not iw:
            return float(st)
        cov = sum(1 for w in iw if w in uw) / float(len(iw))
        head = 1.0 if iw[-1] in uw else 0.0
        base = 4.0 * cov + 2.0 * head
        # ingredient post-comma state e.g. "cubed" is trivial, no penalty
        # converting to a different food form
        if re.search(r"\b(oil|juice|syrup|sauce|powder|jerky|soup)\b", u.split(",")[0]) and not re.search(r"\b(oil|juice|syrup|sauce|powder|jerky|soup)\b", ing):
            base -= 3.0
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|entree|sandwich", u):
            base -= 2.5
        return float(base + st)
    except Exception:
        return 0.0
