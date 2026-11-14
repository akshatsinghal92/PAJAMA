import re

# Each cooking method is placed in a small "process space":
#   heat   : 0 = no heat, 1 = gentle/moist heat, 2 = dry heat, 3 = fat-medium heat
#   brown  : surface browning / crust (0..2)
#   fat    : added fat from the process (0..2)
#   water  : moisture gained (+1) or lost (-1)
_METHODS = {
    "raw":        (0, 0, 0, 0),
    "fresh":      (0, 0, 0, 0),
    "uncooked":   (0, 0, 0, 0),
    "cooked":     (1, 0, 0, 1),
    "boiled":     (1, 0, 0, 1),
    "simmered":   (1, 0, 0, 1),
    "poached":    (1, 0, 0, 1),
    "stewed":     (1, 0, 0, 1),
    "braised":    (1, 1, 0, 1),
    "steamed":    (1, 0, 0, 1),
    "blanched":   (1, 0, 0, 1),
    "microwaved": (1, 0, 0, 0),
    "baked":      (2, 1, 0, -1),
    "roasted":    (2, 2, 0, -1),
    "grilled":    (2, 2, 0, -1),
    "broiled":    (2, 2, 0, -1),
    "toasted":    (2, 2, 0, -1),
    "smoked":     (2, 1, 0, -1),
    "sauteed":    (3, 1, 1, -1),
    "stir-fried": (3, 1, 1, -1),
    "pan-fried":  (3, 2, 1, -1),
    "fried":      (3, 2, 2, -1),
    "deep-fried": (3, 2, 2, -1),
}

_SYNONYMS = {
    "roast": "roasted", "bake": "baked", "grill": "grilled", "broil": "broiled",
    "toast": "toasted", "smoke": "smoked", "steam": "steamed", "boil": "boiled",
    "fry": "fried", "saute": "sauteed", "sautéed": "sauteed", "sauté": "sauteed",
    "pan-broiled": "broiled", "panbroiled": "broiled", "barbecued": "grilled",
    "bbq": "grilled", "charred": "grilled", "chargrilled": "grilled",
    "deepfried": "deep-fried", "panfried": "pan-fried", "stirfried": "stir-fried",
    "microwave": "microwaved", "poach": "poached", "stew": "stewed",
    "braise": "braised", "simmer": "simmered", "blanch": "blanched",
    "prepared": "cooked", "heated": "cooked", "precooked": "cooked",
    "pre-cooked": "cooked", "leftover": "cooked", "frozen": None,
    "unheated": "raw", "unprepared": "raw",
}

# States that are neutral regarding cooking (don't count as a method).
_NEUTRAL = {"frozen", "thawed", "chilled", "cold", "dried", "dehydrated", "canned"}

_STOP = {"and", "or", "with", "without", "the", "a", "of", "for", "in", "to", "from",
         "nfs", "ns", "salt", "added", "fat", "no", "regular", "type", "made"}


def _clean(text):
    t = str(text or "").lower()
    t = t.replace("é", "e")
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    return t


def _tokens(text):
    return re.findall(r"[a-z]+(?:-[a-z]+)?", text)


def _methods(text):
    toks = _tokens(text)
    found = []
    for i, tok in enumerate(toks):
        cand = tok
        # Handle "deep fried", "pan fried", "stir fried"
        if tok in ("fried", "fry") and i > 0 and toks[i - 1] in ("deep", "pan", "stir"):
            cand = toks[i - 1] + "-fried"
        if cand in _SYNONYMS:
            cand = _SYNONYMS[cand]
            if cand is None:
                continue
        if cand in _METHODS:
            # "from dried" / "dry roasted" handled naturally; skip "raw or frozen" noise
            found.append(cand)
    # Deduplicate, keep the most processed descriptor dominant
    uniq = []
    for m in found:
        if m not in uniq:
            uniq.append(m)
    return uniq


def _profile(methods):
    if not methods:
        return None
    # Generic "cooked" is overridden by more specific methods
    specific = [m for m in methods if m not in ("cooked", "raw", "fresh", "uncooked")]
    if specific:
        vecs = [_METHODS[m] for m in specific]
        return tuple(max(v[k] for v in vecs) for k in range(3)) + (
            min(v[3] for v in vecs),)
    if any(m in ("cooked",) for m in methods) and not any(
            m in ("raw", "fresh", "uncooked") for m in methods):
        return _METHODS["cooked"]
    if any(m in ("raw", "fresh", "uncooked") for m in methods) and "cooked" in methods:
        # e.g. "raw or cooked" -> ambiguous, treat midway
        return (0.5, 0, 0, 0.5)
    return _METHODS["raw"]


def _distance(p, q):
    weights = (1.6, 1.2, 1.5, 0.6)
    return sum(w * abs(a - b) for w, a, b in zip(weights, p, q))


def _food_overlap(ing, usda):
    a = {t for t in _tokens(ing) if len(t) > 2 and t not in _STOP}
    b = {t for t in _tokens(usda) if len(t) > 2 and t not in _STOP}

    def stem(w):
        for suf in ("es", "s"):
            if w.endswith(suf) and len(w) > 4:
                return w[: -len(suf)]
        return w
    a = {stem(t) for t in a if t not in _METHODS and t not in _SYNONYMS and t not in _NEUTRAL}
    b = {stem(t) for t in b if t not in _METHODS and t not in _SYNONYMS and t not in _NEUTRAL}
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / float(min(len(a), len(b)))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Parentheticals in the ingredient often describe form; keep but de-weight
        ing_main = re.sub(r"\([^)]*\)", " ", ing)

        m_ing = _methods(ing_main)
        m_usda = _methods(usda)
        p_ing = _profile(m_ing)
        p_usda = _profile(m_usda)

        # Method agreement component (0..60)
        if p_ing is None and p_usda is None:
            method_score = 50.0
        elif p_ing is None:
            # Unstated ingredient method: compatible with raw/generic entries,
            # increasingly penalized as the USDA process diverges from raw.
            d = _distance(_METHODS["raw"], p_usda)
            method_score = max(0.0, 55.0 - 7.0 * d)
        elif p_usda is None:
            # Generic USDA entry: compatible with raw, less with heavy processes
            d = _distance(p_ing, _METHODS["raw"])
            method_score = max(0.0, 50.0 - 5.0 * d)
        else:
            d = _distance(p_ing, p_usda)
            method_score = max(0.0, 60.0 - 9.0 * d)
            if set(m_ing) & set(m_usda):
                method_score = min(60.0, method_score + 5.0)

        # Explicit raw-vs-heat contradictions get an extra penalty
        ing_raw = any(m in ("raw", "fresh", "uncooked") for m in m_ing)
        usda_heat = p_usda is not None and p_usda[0] >= 1 and not any(
            m in ("raw", "uncooked") for m in m_usda)
        if ing_raw and usda_heat:
            method_score -= 15.0

        # Food identity gate (0..40): a method match is meaningless on a different food
        ov = _food_overlap(ing_main, usda)
        food_score = 40.0 * ov

        score = method_score + food_score
        if ov == 0.0:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
