import re

# Preparation-state equivalence judge (variant 1/8):
# Map every state word to a "state class". Trivial classes (cutting, thawing,
# raw/fresh) are ignorable; transforming classes (heat, preservation, curing)
# must agree between ingredient and USDA entry. Score = food-identity overlap
# gate * state-compatibility from a pairwise class matrix.

TRIVIAL = {
    "raw": "raw", "fresh": "raw", "uncooked": "raw",
    "chopped": "cut", "diced": "cut", "minced": "cut", "sliced": "cut",
    "shredded": "cut", "grated": "cut", "cubed": "cut", "segments": "cut",
    "fillets": "cut", "fillet": "cut", "pieces": "cut", "halved": "cut",
    "crushed": "cut", "peeled": "cut", "trimmed": "cut", "boneless": "cut",
    "skinless": "cut", "julienned": "cut", "quartered": "cut",
    "thawed": "thaw", "defrosted": "thaw", "rinsed": "cut", "drained": "cut",
    "granulated": "form", "ground": "form", "whole": "form",
}

TRANSFORM = {
    "cooked": "heat", "boiled": "heat", "steamed": "heat", "baked": "heat",
    "roasted": "heat", "grilled": "heat", "broiled": "heat", "braised": "heat",
    "stewed": "heat", "simmered": "heat", "poached": "heat", "heat": "heat",
    "microwaved": "heat", "toasted": "heat", "leftover": "heat",
    "fried": "fry", "pan-fried": "fry", "deep-fried": "fry", "sauteed": "fry",
    "breaded": "fry", "battered": "fry",
    "smoked": "smoke", "kippered": "smoke",
    "pickled": "pickle", "brined": "pickle", "marinated": "pickle",
    "cured": "cure", "salted": "cure", "corned": "cure",
    "dried": "dry", "dehydrated": "dry", "sun-dried": "dry",
    "canned": "can", "jarred": "can",
    "frozen": "frozen",
}

FILLER = {
    "and", "or", "with", "for", "of", "the", "a", "an", "in", "to", "from",
    "optional", "serving", "garnish", "tube", "taste", "plus", "more", "about",
    "large", "small", "medium", "ready", "serve", "prepared", "type", "style",
    "commercial", "nfs", "ns", "made", "added", "without", "includes",
}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b", " ", text)
    text = re.sub(r"[^a-z\- ]", " ", text)
    return [t for t in text.split() if t]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _split(text):
    foods, trivial, trans = set(), set(), set()
    for t in _tokens(text):
        if t in TRANSFORM:
            trans.add(TRANSFORM[t])
        elif t in TRIVIAL:
            trivial.add(TRIVIAL[t])
        elif t in FILLER or len(t) < 3:
            continue
        else:
            foods.add(_stem(t))
    return foods, trivial, trans


def _state_compat(ia, ub, fresh=False):
    """Return 0..1 compatibility of transforming states."""
    if ia == ub:
        return 1.0
    only_i = ia - ub
    only_u = ub - ia
    score = 1.0
    for s in only_u:
        # USDA adds a transformation absent from the ingredient.
        if s == "frozen":
            score *= 0.2 if fresh else 0.55  # frozen changes texture of fresh produce
        elif s == "heat":
            score *= 0.35
        else:
            score *= 0.25
    for s in only_i:
        if s == "frozen":
            score *= 0.8  # ingredient frozen, usda raw: thawing is trivial
        elif s == "heat" and "fry" in ub:
            score *= 0.9  # "fried" already implies cooked
        else:
            score *= 0.3
    # Conflicting states such as smoke vs pickle: extra penalty
    if only_i and only_u:
        score *= 0.6
    return score


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        # drop parentheticals (notes like "optional, for serving")
        ing_clean = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"(?i)dry heat|moist heat", "cooked", usda)
        fresh = bool(re.search(r"(?i)\bfresh\b", ing_clean))
        i_food, i_triv, i_trans = _split(ing_clean)
        u_food, u_triv, u_trans = _split(usda)

        # "fried" implies "heat"; normalize
        if "fry" in i_trans:
            i_trans.discard("heat")
        if "fry" in u_trans:
            u_trans.discard("heat")

        # Food identity gate: does the ingredient's food appear in USDA?
        primary = _tokens(" ".join(usda.split(",")[:2]))
        primary = {_stem(t) for t in primary if t not in FILLER and len(t) > 2}
        if i_food:
            covered = len(i_food & u_food) / float(len(i_food))
        else:
            covered = 0.5
        primary_hit = 1.0 if (primary & i_food) else 0.0
        identity = 0.6 * covered + 0.4 * primary_hit
        # Extra USDA qualifiers not in ingredient (e.g. lowfat, low sodium)
        extra = len(u_food - i_food)
        identity *= 1.0 / (1.0 + 0.12 * max(0, extra - 1))

        compat = _state_compat(i_trans, u_trans, fresh)
        # trivial state differences are fine, small bonus for agreement
        triv_bonus = 0.05 * len(i_triv & u_triv)

        # Blend: identity and state compatibility contribute additively so an
        # exact shared transformation (e.g. both fried) is rewarded.
        score = 50.0 * identity + 50.0 * compat + 10.0 * triv_bonus
        if identity < 0.05:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
