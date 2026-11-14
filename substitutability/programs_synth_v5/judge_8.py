import re

# State families: tokens that indicate a preparation state.
TRIVIAL = {"raw", "fresh", "chopped", "diced", "minced", "sliced", "shredded", "thawed",
           "cubed", "grated", "crushed", "peeled", "trimmed", "whole", "florets", "flaked",
           "halved", "torn", "julienned", "ground", "mashed"}
COOKED = {"cooked", "boiled", "baked", "roasted", "fried", "grilled", "broiled", "steamed",
          "braised", "stewed", "sauteed", "toasted", "microwaved", "pan-fried", "deep-fried",
          "leftover", "poached"}
PRESERVED = {"canned", "dried", "dehydrated", "pickled", "smoked", "cured", "salted", "frozen",
             "condensed", "sweetened", "powder", "powdered", "paste", "juice", "puree", "purée",
             "sauce", "soup", "stew", "candied", "brined", "fermented", "instant"}
STOP = {"of", "the", "and", "a", "an", "with", "for", "in", "from", "or", "to", "style",
        "serving", "g", "nfs", "regular", "type", "tube", "overnight", "soaked", "cold",
        "hot", "warm", "lean", "large", "small", "medium"}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", text)
    return re.findall(r"[a-zçéèñ\-]+", text)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _state_class(toks):
    cooked = [t for t in toks if t in COOKED]
    pres = [t for t in toks if t in PRESERVED]
    triv = [t for t in toks if t in TRIVIAL]
    return len(cooked), len(pres), len(triv)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        it = _tokens(ing)
        ut = _tokens(usda)
        if not it or not ut:
            return 0.0

        # Content words (food identity) after removing state and filler words.
        state_all = TRIVIAL | COOKED | PRESERVED | STOP
        ic = set(_stem(t) for t in it if t not in state_all and len(t) > 1)
        uc = set(_stem(t) for t in ut if t not in state_all and len(t) > 1)

        # Primary food of USDA = first comma segment.
        primary = [_stem(t) for t in _tokens(usda.split(",")[0]) if t not in state_all]
        primary_set = set(primary)

        # Identity coverage: how much of the ingredient's food words are explained.
        if ic:
            cov_i = len(ic & uc) / float(len(ic))
        else:
            cov_i = 0.5
        if uc:
            cov_u = len(ic & uc) / float(len(uc))
        else:
            cov_u = 0.5
        prim_hit = 1.0 if (primary_set & ic) else 0.0
        identity = 0.45 * cov_i + 0.25 * cov_u + 0.30 * prim_hit

        # Preparation-state transition penalty.
        ci, pi, ti = _state_class(it)
        cu, pu, tu = _state_class(ut)
        penalty = 0.0
        # cooking mismatch changes the dish
        if (ci > 0) != (cu > 0):
            penalty += 0.35
        # preservation mismatch (canned/dried/frozen vs fresh) changes outcome
        ip = set(t for t in it if t in PRESERVED) - {"frozen"}
        up = set(t for t in ut if t in PRESERVED) - {"frozen"}
        diff = ip ^ up
        penalty += min(0.4, 0.2 * len(diff))
        # a frozen/thawed pair is trivially reversible; frozen in USDA only is mild
        if "frozen" in ut and "frozen" not in it and "thawed" not in it:
            penalty += 0.05
        # specific cook-method disagreement
        cm_i = set(t for t in it if t in COOKED)
        cm_u = set(t for t in ut if t in COOKED)
        if cm_i and cm_u and not (cm_i & cm_u):
            penalty += 0.15

        # Trivial-state difference bonus: raw/fresh/chopped etc. are free to ignore.
        bonus = 0.0
        if tu > 0 and ci == 0 and cu == 0 and not diff:
            bonus += 0.1
        if ti > 0 and cu == 0 and ci == 0:
            bonus += 0.05

        # Extra unexplained descriptors in USDA (cuts, parts) suggest different item.
        extra = len(uc - ic)
        extra_pen = min(0.25, 0.05 * extra)

        score = identity + bonus - penalty - extra_pen
        score = max(-1.0, min(1.5, score))
        return round(score * 10.0, 3)
    except Exception:
        return 0.0
