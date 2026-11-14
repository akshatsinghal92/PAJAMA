import re

_PREP = set("fresh frozen dried dry canned raw cooked boiled diced chopped sliced minced ground grated shredded "
            "thawed drained peeled whole large small medium fine coarse organic ripe smoked roasted toasted "
            "crushed mashed packed lean boneless skinless of the a an and or with in from tube to taste "
            "g kg mg oz lb ml".split())
_CATEGORY = set("fish crustaceans mollusks nuts seeds spices beans cereals snacks sweets candies beverages "
                "fruit fruits vegetables restaurant fast foods babyfood game meat".split())
_DISH = set("soup pie sauce stew cake cookie cookies bread muffin salad dressing candy drink juice syrup "
            "milk yogurt cream ice pudding snack bar bars cereal chips patty sandwich pizza entree "
            "relish jam jelly gravy dip spread pastry tart flavored extract".split())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = (ingredient or "").lower()
        usda = (usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml)?\b", " ", ing)
        main = ing.split(",")[0]
        itoks = [t for t in _tokens(main) if t not in {_stem(p) for p in _PREP}]
        if not itoks:
            itoks = _tokens(main)
        if not itoks:
            return 0.0
        head = itoks[-1]
        usda = re.sub(r"\([^)]*\)", " ", usda)
        segs = [s.strip() for s in usda.split(",") if s.strip()]
        if not segs:
            return 0.0
        seg_toks = [_tokens(s) for s in segs]
        # effective primary segment: skip pure category segments
        p = 0
        while p < len(segs) - 1 and all(t in _CATEGORY for t in seg_toks[p]):
            p += 1
        prim = seg_toks[p]
        iset = set(itoks)
        score = 0.0
        # head position
        pos = None
        for i, st in enumerate(seg_toks):
            if head in st:
                pos = (i, st.index(head))
                break
        if pos is None:
            overlap = len(iset & {t for st in seg_toks for t in st})
            score = 1.0 + 2.0 * overlap / len(iset)
        else:
            si, wi = pos
            if si == p:
                if len(prim) == 1:
                    score = 8.0
                elif wi == 0:
                    # head first; trailing words decide
                    extra = [t for t in prim[1:] if t not in iset]
                    score = 7.0 - 2.5 * sum(1 for t in extra if t in _DISH) - 0.3 * len(extra)
                else:
                    # head after other words: head is last noun => ok if the modifiers are in ingredient
                    mods = prim[:wi]
                    bad = [t for t in mods if t not in iset]
                    score = 6.5 - 2.0 * len(bad)
                    if head in _DISH:
                        score -= 1.0
            elif si > p:
                score = 6.0 - 0.7 * (si - p)
            else:
                score = 4.0
            # ingredient head is a dish word but USDA first segment differs
        # ingredient modifiers coverage across all USDA tokens
        alltok = {t for st in seg_toks for t in st}
        mods = [t for t in itoks[:-1]]
        if mods:
            cov = sum(1 for t in mods if t in alltok) / len(mods)
            score += 2.0 * cov - 1.0
        # first segment dominated by other food than ingredient
        if prim and prim[0] not in iset and pos is not None and pos[0] == p and pos[1] > 0:
            score -= 0.5
        # processing-state mismatch penalty (head-adjacent states)
        if "cooked" in usda and "cooked" not in ing and "boiled" not in ing:
            score -= 0.7
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
