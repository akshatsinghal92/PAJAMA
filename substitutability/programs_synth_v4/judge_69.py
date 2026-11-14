import re

# Anatomical part taxonomy: group -> (family, keywords)
_PART_GROUPS = {
    "leaf": ("plant", ["greens", "leaves", "leaf", "leafy", "tops", "fronds"]),
    "root": ("plant", ["root", "roots", "tuber", "tubers", "bulb", "rhizome"]),
    "stem": ("plant", ["stem", "stems", "stalk", "stalks", "shoots", "shoot", "spears"]),
    "seed": ("plant", ["seed", "seeds", "kernel", "kernels", "germ", "bran", "hull", "hulls"]),
    "flower": ("plant", ["flower", "flowers", "blossom", "blossoms", "florets", "buds"]),
    "peel": ("plant", ["peel", "zest", "rind", "skin", "skins"]),
    "pulp": ("plant", ["flesh", "pulp", "juice", "meat"]),
    "breast": ("animal", ["breast", "breasts"]),
    "thigh": ("animal", ["thigh", "thighs"]),
    "wing": ("animal", ["wing", "wings"]),
    "leg": ("animal", ["drumstick", "drumsticks", "leg", "legs", "shank", "shanks"]),
    "back": ("animal", ["back", "neck", "giblets"]),
    "organ": ("animal", ["liver", "kidney", "heart", "gizzard", "tongue", "tripe", "brain", "sweetbread"]),
    "loin": ("animal", ["loin", "tenderloin", "sirloin", "strip", "porterhouse", "t-bone", "ribeye", "chop", "chops"]),
    "shoulder": ("animal", ["shoulder", "chuck", "blade", "butt", "brisket"]),
    "rib": ("animal", ["rib", "ribs", "spareribs"]),
    "round": ("animal", ["round", "rump", "ham", "flank", "skirt", "plate"]),
    "belly": ("animal", ["belly", "bacon", "pancetta"]),
    "tritip": ("animal", ["tri-tip", "tritip", "bottom"]),
    "yolk": ("egg", ["yolk", "yolks"]),
    "white": ("egg", ["white", "whites", "albumen"]),
    "fat": ("animal", ["fat", "lard", "tallow", "suet", "cracklings"]),
}

# Form / cut granularity (whole vs ground vs fillet etc.)
_FORM_GROUPS = {
    "ground": ["ground", "minced", "mince", "hamburger", "meal", "flour", "powder"],
    "fillet": ["fillet", "fillets", "filet", "cutlet", "cutlets", "steak", "steaks"],
    "whole": ["whole"],
    "sliced": ["sliced", "diced", "chopped", "cubed", "strips"],
}

# Forms that are effectively interchangeable for a cook
_FORM_COMPAT = {
    frozenset(["ground", "whole"]): 0.4,
    frozenset(["sliced", "whole"]): 0.8,
    frozenset(["fillet", "whole"]): 0.5,
    frozenset(["fillet", "sliced"]): 0.6,
    frozenset(["ground", "fillet"]): 0.1,
    frozenset(["ground", "sliced"]): 0.3,
}

_STOP = set("""a an and or the of with without in on for to from as by raw cooked
fresh frozen thawed canned dried prepared ns eaten made home recipe regular
mixed species not further specified style type plain unsalted salted salt
added low sodium reduced fat free nonfat lowfat lean separable trimmed choice
select all grades boiled drained baked roasted toasted fried dry heat""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)\b", " ", t)
    t = t.replace("'", "")
    return t


def _tokens(text):
    return re.findall(r"[a-z][a-z\-]*", text)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _detect(tokens, groups):
    found = set()
    tokset = set(tokens)
    joined = " ".join(tokens)
    for g, val in groups.items():
        kws = val[1] if isinstance(val, tuple) else val
        for k in kws:
            if ("-" in k and k in joined) or k in tokset:
                found.add(g)
                break
    return found


def _part_score(ip, up):
    """Return (score in [-1,1], note)."""
    if not ip and not up:
        return 0.6
    if ip and not up:
        return 0.3  # USDA unspecified part: mild reward
    if up and not ip:
        # USDA names a specific part; ingredient doesn't. Fine if it's a common default
        if up & {"pulp", "seed"}:
            return 0.2
        return -0.1
    inter = ip & up
    if inter == ip or inter == up:
        return 1.0 if inter else 0.0
    if inter:
        return 0.4
    fam_i = {_PART_GROUPS[p][0] for p in ip}
    fam_u = {_PART_GROUPS[p][0] for p in up}
    if fam_i & fam_u:
        return -1.0  # same family, different part -> cooks/tastes differently
    return -0.5


def _form_score(iform, uform):
    if not iform or not uform:
        return 0.0
    if iform & uform:
        return 0.5
    best = 0.0
    for a in iform:
        for b in uform:
            best = max(best, _FORM_COMPAT.get(frozenset([a, b]), 0.0))
    return best - 0.5


def _content_overlap(itoks, utoks):
    ic = {_stem(w) for w in itoks if w not in _STOP and len(w) > 2}
    uc = {_stem(w) for w in utoks if w not in _STOP and len(w) > 2}
    if not ic or not uc:
        return 0.0, False
    inter = ic & uc
    cov = len(inter) / float(len(ic))
    return cov, bool(inter)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        itoks = _tokens(ing)
        utoks = _tokens(usda)
        if not itoks or not utoks:
            return 0.0

        ipart = _detect(itoks, _PART_GROUPS)
        upart = _detect(utoks, _PART_GROUPS)
        iform = _detect(itoks, _FORM_GROUPS)
        uform = _detect(utoks, _FORM_GROUPS)

        ps = _part_score(ipart, upart)
        fs = _form_score(iform, uform)
        cov, any_shared = _content_overlap(itoks, utoks)

        # Primary USDA food (first segment) must relate to ingredient
        head = _tokens(usda.split(",")[0])
        head_c = {_stem(w) for w in head if w not in _STOP and len(w) > 2}
        ing_c = {_stem(w) for w in itoks if len(w) > 2}
        head_hit = bool(head_c & ing_c)

        score = 4.0
        score += 3.0 * ps
        score += 1.0 * fs
        score += 2.0 * cov
        if head_hit:
            score += 1.0
        elif not any_shared:
            score -= 3.0  # different food entirely, part question moot

        # Explicit part mismatch where a part word is present only on one side,
        # and that part word is a strong anatomical marker (e.g. greens, yolk, zest)
        strong = {"leaf", "peel", "yolk", "white", "organ", "flower"}
        if (upart - ipart) & strong and not (ipart & upart):
            score -= 1.5
        if (ipart - upart) & strong and upart:
            score -= 1.0

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
