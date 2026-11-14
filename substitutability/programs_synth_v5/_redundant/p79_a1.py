import re

_PREP = set("""fresh frozen thawed chopped sliced diced minced cubed grated shredded crushed ground cooked raw
drained rinsed peeled cold hot warm toasted roasted large small medium whole fine coarse boneless skinless
organic canned dried packed bagged baked boiled steamed melted softened optional garnish taste for the of
and or with without a an to from into plain extra finely thinly roughly freshly lightly wild foraged crispy
sweetened unsweetened salted unsalted flaked segments pieces piece bunch can cup tsp tbsp g kg oz lb ml""".split())

_COMPOUND_MODS = set("""sweet coconut peanut sea green black white red yellow brown wild sour cream butter
almond soy rice oat cocoa chocolate corn hot cottage cream""".split())

_SYN = {"maize": "corn", "poultry": "chicken", "clementine": "tangerine", "mandarin": "tangerine",
        "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro", "prawn": "shrimp",
        "garbanzo": "chickpea", "scallion": "onion", "capsicum": "pepper", "swede": "rutabaga"}


def _stem(w):
    w = _SYN.get(w, w)
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ves", "f"), ("es", ""), ("s", "")):
        if len(w) > 3 and w.endswith(suf) and not w.endswith("ss"):
            w = w[:-len(suf)] + rep
            break
    return _SYN.get(w, w)


def _words(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        ing = ing.split(",")[0]
        usda = re.sub(r"\([^)]*\)", " ", usda)

        iw_all = _words(ing)
        # split on ' and ' / ' with ' : multi-food ingredients
        parts = re.split(r"\b(?:and|with|or|in)\b", ing)
        multi = len([p for p in parts if _words(p)]) > 1
        iw = [w for w in iw_all if w not in _PREP and len(w) > 1]
        if not iw:
            return 0.0

        segs = [s.strip() for s in usda.split(",")]
        uw_all = _words(usda)
        uset = set(uw_all)
        prim = _words(segs[0])
        prim_set = set(prim)
        uw_list = []
        for s in segs:
            uw_list.extend(_words(s))

        # 1. unigram coverage of ingredient content words
        cov = sum(1 for w in iw if w in uset) / float(len(iw))

        # 2. compound integrity: adjacent ingredient pairs found (either order, within window) in usda
        pairs = list(zip(iw[:-1], iw[1:]))
        if pairs:
            ok = 0
            for a, b in pairs:
                if a in uset and b in uset:
                    ia = [i for i, w in enumerate(uw_list) if w == a]
                    ib = [i for i, w in enumerate(uw_list) if w == b]
                    d = min(abs(x - y) for x in ia for y in ib)
                    ok += 1.0 if d <= 2 else 0.5
            comp = ok / float(len(pairs))
        else:
            comp = cov
        # head noun (last content word) must be present
        head = iw[-1]
        head_ok = 1.0 if head in uset else 0.0
        if head_ok == 0.0 and iw[0] in uset:
            head_ok = 0.6  # e.g. "lamb loin chop" style reordering

        # 3. USDA extras: modifiers forming different foods
        extra = [w for w in prim if w not in iw_all and w not in _PREP and len(w) > 2]
        pen = 0.0
        for w in extra:
            pen += 1.5 if w in _COMPOUND_MODS else 0.6
        # modifier mismatch: ingredient compound modifier dropped
        for w in iw:
            if w in _COMPOUND_MODS and w not in uset:
                pen += 2.0
        # usda primary food different from ingredient head
        if head not in prim_set and not (set(iw) & prim_set):
            pen += 2.5
        # trailing "and X" style in usda that ingredient lacks
        if " and " in usda and not multi:
            pen += 1.5
        if multi and " and " not in usda:
            pen += 2.0

        # 4. usda descriptor noise (long USDA text relative to match)
        extra_n = len([w for w in uw_all if w not in iw_all and w not in _PREP])
        noise = min(1.5, 0.12 * extra_n)

        score = 4.0 * comp + 3.0 * cov + 3.0 * head_ok - pen - noise
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
