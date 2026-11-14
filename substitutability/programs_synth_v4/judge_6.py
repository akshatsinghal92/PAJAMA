import re

# State lexicon: word -> (state class, is_trivial)
# Trivial states can be applied or ignored by a cook without changing the dish.
_STATE = {
    "raw": ("raw", True), "fresh": ("raw", True), "uncooked": ("raw", True),
    "chopped": ("cut", True), "diced": ("cut", True), "minced": ("cut", True),
    "sliced": ("cut", True), "shredded": ("cut", True), "cubed": ("cut", True),
    "chunks": ("cut", True), "chunk": ("cut", True), "grated": ("cut", True),
    "crumbled": ("cut", True), "crumbles": ("cut", True), "halved": ("cut", True),
    "quartered": ("cut", True), "trimmed": ("cut", True), "peeled": ("cut", True),
    "whole": ("cut", True), "thawed": ("thaw", True), "frozen": ("thaw", True),
    "warmed": ("temp", True), "chilled": ("temp", True), "cold": ("temp", True),
    "softened": ("temp", True), "melted": ("temp", True), "room": ("temp", True),
    "cooked": ("cooked", False), "boiled": ("cooked", False), "steamed": ("cooked", False),
    "baked": ("cooked", False), "roasted": ("cooked", False), "grilled": ("cooked", False),
    "broiled": ("cooked", False), "pan-broiled": ("cooked", False), "braised": ("cooked", False),
    "stewed": ("cooked", False), "simmered": ("cooked", False), "poached": ("cooked", False),
    "microwaved": ("cooked", False), "toasted": ("cooked", False),
    "fried": ("fried", False), "deep-fried": ("fried", False), "sauteed": ("fried", False),
    "breaded": ("fried", False), "battered": ("fried", False),
    "dried": ("dried", False), "dehydrated": ("dried", False), "dry": ("dried", False),
    "smoked": ("cured", False), "cured": ("cured", False), "pickled": ("cured", False),
    "salted": ("cured", False), "canned": ("canned", False), "jarred": ("canned", False),
    "juice": ("liquid", False), "puree": ("liquid", False), "pureed": ("liquid", False),
    "powder": ("powder", False), "powdered": ("powder", False), "ground": ("ground", False),
    "mashed": ("mashed", False),
}

# Pairs of state classes that are mutually compatible even though both are non-trivial-ish
_COMPAT = {
    frozenset(["raw", "cut"]), frozenset(["raw", "thaw"]), frozenset(["raw", "temp"]),
    frozenset(["cut", "thaw"]), frozenset(["cut", "temp"]), frozenset(["thaw", "temp"]),
    frozenset(["cooked", "fried"]),  # both heat-treated, close
    frozenset(["canned", "cooked"]),
}

# Severity of moving between state classes (used when not compatible)
_SEVERITY = {
    "cooked": 3.0, "fried": 3.5, "dried": 3.0, "cured": 3.0, "canned": 2.0,
    "liquid": 4.5, "powder": 3.5, "ground": 1.5, "mashed": 2.0,
}

_FILLER = {
    "and", "or", "with", "of", "the", "a", "an", "for", "in", "to", "from", "all",
    "varieties", "regular", "plain", "mixed", "species", "style", "type", "brand",
    "prepackaged", "deli", "ready", "serve", "ready-to-serve", "made", "commercially",
    "prepared", "nfs", "ns", "include", "includes", "separable", "lean", "fat",
    "boneless", "bone-in", "skinless", "garnish", "tube", "salad", "cooking",
}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|%)\b", " ", text)
    text = re.sub(r"\d+(\.\d+)?%?", " ", text)
    text = re.sub(r"[^a-z\- ]", " ", text)
    out = []
    for t in text.split():
        t = t.strip("-")
        if not t:
            continue
        out.append(t)
    return out


def _stem(t):
    for suf in ("ies", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def _split(tokens):
    core, states = [], []
    for t in tokens:
        if t in _STATE:
            states.append(_STATE[t])
        elif t not in _FILLER and len(t) > 1:
            core.append(_stem(t))
    return core, states


def _trigrams(words):
    grams = set()
    for w in words:
        s = "##" + w + "#"
        for i in range(len(s) - 2):
            grams.add(s[i:i + 3])
    return grams


def _core_similarity(ing_core, usda_core, usda_head):
    if not ing_core or not usda_core:
        return 0.0
    a, b = set(ing_core), set(usda_core)
    exact = len(a & b) / float(len(a))
    ga, gb = _trigrams(ing_core), _trigrams(usda_core)
    tri = len(ga & gb) / float(len(ga | gb)) if (ga | gb) else 0.0
    head_bonus = 0.0
    if usda_head:
        for h in usda_head:
            if h in a:
                head_bonus = 0.25
                break
            if any(len(h) > 3 and (h in w or w in h) for w in a):
                head_bonus = 0.15
    return min(1.0, 0.55 * exact + 0.45 * min(1.0, tri * 1.6) + head_bonus)


def _state_penalty(ing_states, usda_states):
    ing_cls = {c for c, _ in ing_states}
    usda_cls = {c for c, _ in usda_states}
    # Classes that only appear on one side and are non-trivial
    penalty = 0.0
    nontrivial_ing = {c for c, triv in ing_states if not triv}
    nontrivial_usda = {c for c, triv in usda_states if not triv}
    for c in nontrivial_usda - nontrivial_ing:
        # USDA is transformed in a way the ingredient is not
        if any(frozenset([c, x]) in _COMPAT for x in nontrivial_ing):
            penalty += 0.5
        else:
            penalty += _SEVERITY.get(c, 2.0)
    for c in nontrivial_ing - nontrivial_usda:
        if any(frozenset([c, x]) in _COMPAT for x in nontrivial_usda):
            penalty += 0.5
        elif "raw" in usda_cls or not usda_cls:
            # ingredient is processed but USDA is raw/unspecified
            penalty += 0.6 * _SEVERITY.get(c, 2.0)
        else:
            penalty += 0.8 * _SEVERITY.get(c, 2.0)
    # explicit raw vs cooked/fried conflict
    if "raw" in ing_cls and (usda_cls & {"cooked", "fried"}):
        penalty += 1.0
    if "raw" in usda_cls and (ing_cls & {"cooked", "fried"}) and not (usda_cls & {"cooked", "fried"}):
        penalty += 1.0
    return penalty


def _structure_penalty(ingredient, usda_match, ing_core, usda_core):
    pen = 0.0
    low_i = ingredient.lower()
    # Blends/mixes in ingredient that USDA covers only partly
    if re.search(r"\b(and|&)\b", low_i.split(",")[0]) or "mix" in low_i:
        if not re.search(r"\band\b", usda_match.lower()):
            pen += 2.0
    # Plant part mismatch (leaves vs fruit, bone vs meat, skin)
    parts = {"leaf", "leave", "leaves", "bone", "skin", "stem", "seed", "peel", "root"}
    ip = {w for w in ing_core if w in parts}
    up = {w for w in usda_core if w in parts}
    if ip and not (ip & up):
        pen += 2.0
    # Health/modified variants on USDA side not asked for
    if re.search(r"\b(low sodium|reduced|light|lite|unsalted|fat free|sugar free|low fat)\b", usda_match.lower()):
        if not re.search(r"\b(low|reduced|light|lite|unsalted|free)\b", low_i):
            pen += 1.5
    return pen


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0
        ing_tokens = _tokens(ingredient)
        usda_tokens = _tokens(usda_match)
        ing_core, ing_states = _split(ing_tokens)
        usda_core, usda_states = _split(usda_tokens)
        head_tokens = _tokens(usda_match.split(",")[0])
        usda_head, _ = _split(head_tokens)

        sim = _core_similarity(ing_core, usda_core, usda_head)
        if sim <= 0.05:
            return round(max(0.0, sim * 10.0), 3)

        state_pen = _state_penalty(ing_states, usda_states)
        struct_pen = _structure_penalty(ingredient, usda_match, ing_core, usda_core)

        # State equivalence factor: smooth decay with penalty
        state_factor = 1.0 / (1.0 + 0.35 * state_pen)
        score = 10.0 * sim * state_factor - struct_pen
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
