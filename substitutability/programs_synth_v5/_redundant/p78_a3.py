import re

_DROP = set("""fresh frozen thawed cooked raw uncooked dried dry chopped sliced diced minced melted
crumbled shredded grated peeled boiled steamed roasted simmered large small medium skin on
boneless skinless organic ripe finely optional garnish for and or of the a with plain lean
whole nfs unprepared trimmed choice separable fat lowfat low diet golden delicious yellow
red green white purple""".split())


def _norm(w):
    for suf, rep in (("ies", "y"), ("oes", "o"), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
            return w[:-len(suf)] + rep
    return w


def _grams(s, n=3):
    s = "#" + s + "#"
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}


def _dice(a, b):
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s", " ", ing + " ")
        usda = re.sub(r"\([^)]*\)", " ", usda)
        segs = [s for s in usda.split(",")]
        prim_raw = re.findall(r"[a-z]+", segs[0])
        rest_raw = re.findall(r"[a-z]+", " ".join(segs[1:]))

        iw_all = [_norm(w) for w in re.findall(r"[a-z]+", ing)]
        iw = [w for w in iw_all if w not in _DROP] or iw_all
        if not iw:
            return 0.0
        prim = [_norm(w) for w in prim_raw]
        rest = [_norm(w) for w in rest_raw]

        # Reassemble USDA name in "natural" order: descriptors that follow the primary
        # food are re-attached in front of it (Cherries, sweet -> sweet cherry).
        rest_keep = [w for w in rest if w not in _DROP]
        reassembled = rest_keep + prim
        glued_ing = "".join(iw)
        glued_prim = "".join(prim)
        glued_re = "".join(reassembled)

        # Tier 1: identical compound after normalisation (any ordering of rest/primary)
        tier = 0.0
        if glued_ing == glued_prim or glued_ing == glued_re:
            tier = 10.0
        else:
            sims = []
            for cand in (prim, reassembled, prim + rest_keep):
                sims.append(_dice(_grams(" ".join(iw)), _grams(" ".join(cand))))
            best = max(sims)
            tier = 8.0 * best
            # all ingredient words present in some USDA position -> compound is kept
            union = set(prim) | set(rest)
            missing = [w for w in iw if w not in union]
            tier -= 2.5 * len(missing)
            if not missing:
                tier += 2.0
            # words in USDA primary name not in ingredient: new modifier / different food
            extra = [w for w in prim if w not in iw_all]
            tier -= 2.2 * len(extra)
            # head noun anchor: the ingredient's last word must be the primary head
            if iw[-1] not in prim:
                tier -= 2.5
            # primary head order: USDA head (first primary word) should be ingredient head
            if prim and prim[0] != iw[-1] and prim[-1] != iw[-1]:
                tier -= 1.0
        if "nfs" in usda:
            tier -= 1.5
        return max(0.0, min(10.0, tier))
    except Exception:
        return 0.0
