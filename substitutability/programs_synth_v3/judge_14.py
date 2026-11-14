import re

# State families. Each family maps surface words to a canonical "process class".
_STATE_CLASSES = {
    "raw": {"raw", "fresh", "uncooked", "crude", "unprepared"},
    "cut": {"chopped", "diced", "minced", "sliced", "shredded", "grated", "cubed",
            "julienned", "segments", "segment", "halved", "quartered", "crushed",
            "trimmed", "peeled", "pitted", "cut", "torn", "leaves", "florets"},
    "thawed": {"thawed", "defrosted"},
    "frozen": {"frozen"},
    "moist_cook": {"boiled", "simmered", "stewed", "steamed", "poached", "braised", "blanched"},
    "dry_cook": {"roasted", "baked", "grilled", "broiled", "toasted", "seared", "pan-broiled"},
    "fried": {"fried", "deep-fried", "pan-fried", "sauteed", "breaded"},
    "cooked": {"cooked", "prepared", "heated"},
    "canned": {"canned", "drained", "jarred", "bottled", "pickled"},
    "dried": {"dried", "dehydrated", "dry", "powder", "powdered", "ground"},
    "rts": {"ready-to-serve", "ready-to-eat", "ready-to-heat"},
}

_WORD_TO_CLASS = {}
for _cls, _words in _STATE_CLASSES.items():
    for _w in _words:
        _WORD_TO_CLASS[_w] = _cls

# Classes that a cook can trivially apply or ignore (neutral).
_NEUTRAL = {"raw", "cut", "thawed", "rts"}

# Pairwise compatibility between a recipe-side class and a USDA-side class (0..1).
_COMPAT = {
    ("raw", "frozen"): 0.7, ("thawed", "frozen"): 0.95, ("frozen", "raw"): 0.75,
    ("thawed", "raw"): 0.8, ("frozen", "thawed"): 0.95,
    ("moist_cook", "cooked"): 0.9, ("dry_cook", "cooked"): 0.75, ("fried", "cooked"): 0.45,
    ("cooked", "moist_cook"): 0.85, ("cooked", "dry_cook"): 0.75, ("cooked", "fried"): 0.4,
    ("moist_cook", "dry_cook"): 0.45, ("dry_cook", "moist_cook"): 0.45,
    ("moist_cook", "fried"): 0.2, ("dry_cook", "fried"): 0.3,
    ("fried", "moist_cook"): 0.2, ("fried", "dry_cook"): 0.3,
    ("raw", "cooked"): 0.15, ("raw", "moist_cook"): 0.15, ("raw", "dry_cook"): 0.12,
    ("raw", "fried"): 0.05, ("cooked", "raw"): 0.2, ("moist_cook", "raw"): 0.2,
    ("dry_cook", "raw"): 0.15, ("fried", "raw"): 0.1,
    ("canned", "raw"): 0.15, ("raw", "canned"): 0.2, ("canned", "cooked"): 0.5,
    ("canned", "frozen"): 0.3, ("frozen", "canned"): 0.3,
    ("dried", "raw"): 0.15, ("raw", "dried"): 0.15, ("dried", "cooked"): 0.15,
    ("cooked", "dried"): 0.1, ("dried", "frozen"): 0.2, ("frozen", "dried"): 0.2,
}

_FILLER = {
    "and", "or", "with", "the", "a", "an", "of", "for", "to", "in", "from", "into",
    "optional", "serving", "taste", "plus", "more", "about", "large", "small",
    "medium", "whole", "tube", "fine", "finely", "roughly", "coarsely", "thinly",
    "lightly", "freshly", "style", "type", "ns", "nfs", "as", "made", "commercial",
    "brand", "inch", "pieces", "piece",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokenize(text):
    text = (text or "").lower()
    text = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", text)
    text = re.sub(r"\d+(\.\d+)?", " ", text)
    return [t for t in re.findall(r"[a-z][a-z\-]*", text)]


def _split(text):
    """Return (core token set, set of state classes)."""
    core, states = set(), set()
    for t in _tokenize(text):
        if t in _WORD_TO_CLASS:
            states.add(_WORD_TO_CLASS[t])
            continue
        parts = t.split("-")
        hit = False
        for p in parts:
            if p in _WORD_TO_CLASS:
                states.add(_WORD_TO_CLASS[p])
                hit = True
        if hit and all(p in _WORD_TO_CLASS or p in _FILLER for p in parts):
            continue
        if t in _FILLER or len(t) < 2:
            continue
        core.add(_stem(t))
    return core, states


def _primary(usda):
    head = (usda or "").split(",")[0]
    return {_stem(t) for t in _tokenize(head) if t not in _FILLER}


def _fuzzy_hit(tok, pool):
    if tok in pool:
        return 1.0
    for p in pool:
        if len(tok) >= 4 and len(p) >= 4 and (tok.startswith(p) or p.startswith(tok)):
            return 0.8
    return 0.0


def _state_score(ing_states, usda_states):
    """Average best-pair compatibility of the 'significant' (non-neutral) states."""
    a = ing_states - _NEUTRAL
    b = usda_states - _NEUTRAL
    if not a and not b:
        return 1.0
    # Treat absent side as implicitly raw/unspecified.
    if not a:
        a = {"raw"}
    if not b:
        b = {"raw"}
    total = 0.0
    n = 0
    for side_from, side_to, flip in ((a, b, False), (b, a, True)):
        for s in side_from:
            best = 0.0
            for t in side_to:
                key = (t, s) if flip else (s, t)
                v = 1.0 if s == t else _COMPAT.get(key, 0.35)
                best = max(best, v)
            total += best
            n += 1
    return total / n if n else 1.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = re.sub(r"\(([^)]*)\)", r" \1 ", str(ingredient))
        usda = str(usda_match)

        ing_core, ing_states = _split(ing)
        usda_core, usda_states = _split(usda)
        prim = _primary(usda) - set(_WORD_TO_CLASS)

        if not ing_core or not usda_core:
            return 5.0

        # Food identity: ingredient core covered by USDA core.
        cover = sum(_fuzzy_hit(t, usda_core) for t in ing_core) / len(ing_core)
        # Primary-food anchor: USDA head noun should appear in ingredient.
        anchor = 0.0
        if prim:
            anchor = sum(_fuzzy_hit(p, ing_core) for p in prim) / len(prim)
        # Extra USDA descriptors that the ingredient never asked for (variety drift).
        extra = [t for t in usda_core if _fuzzy_hit(t, ing_core) == 0.0]
        drift = min(1.0, len(extra) / 4.0)

        identity = 0.5 * cover + 0.4 * anchor + 0.1 * (1.0 - drift)
        state = _state_score(ing_states, usda_states)

        # Preparation-state dimension dominates, but is gated by identity:
        # a state match is meaningless if the foods are different.
        gate = identity ** 1.5
        score = 100.0 * gate * (0.45 + 0.55 * state)
        if identity < 0.25:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
