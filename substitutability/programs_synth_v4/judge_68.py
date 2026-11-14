import re
import math

# Each processing state is embedded as a vector of physical attributes:
# (heat_applied, added_fat, moisture_change, surface_browning, smoke_flavour, preservation)
# Distances in this space approximate perceived differences in taste/texture/appearance.
_STATE_VECTORS = {
    "raw":        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "fresh":      (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "uncooked":   (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "crude":      (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "cooked":     (0.6, 0.1, 0.3, 0.2, 0.0, 0.0),
    "boiled":     (0.6, 0.0, 0.6, 0.0, 0.0, 0.0),
    "simmered":   (0.6, 0.0, 0.6, 0.0, 0.0, 0.0),
    "poached":    (0.5, 0.0, 0.5, 0.0, 0.0, 0.0),
    "stewed":     (0.6, 0.1, 0.7, 0.1, 0.0, 0.0),
    "braised":    (0.7, 0.2, 0.6, 0.4, 0.0, 0.0),
    "steamed":    (0.5, 0.0, 0.4, 0.0, 0.0, 0.0),
    "blanched":   (0.3, 0.0, 0.2, 0.0, 0.0, 0.0),
    "baked":      (0.8, 0.1, -0.4, 0.6, 0.0, 0.0),
    "roasted":    (0.9, 0.2, -0.5, 0.8, 0.0, 0.0),
    "grilled":    (0.9, 0.0, -0.4, 0.9, 0.3, 0.0),
    "broiled":    (0.9, 0.0, -0.4, 0.8, 0.1, 0.0),
    "barbecued":  (0.9, 0.1, -0.4, 0.9, 0.6, 0.0),
    "fried":      (0.9, 0.8, -0.5, 0.8, 0.0, 0.0),
    "pan-fried":  (0.9, 0.6, -0.4, 0.8, 0.0, 0.0),
    "stir-fried": (0.8, 0.5, -0.3, 0.6, 0.0, 0.0),
    "deep-fried": (1.0, 1.0, -0.6, 0.9, 0.0, 0.0),
    "sauteed":    (0.7, 0.5, -0.2, 0.5, 0.0, 0.0),
    "microwaved": (0.5, 0.0, 0.1, 0.0, 0.0, 0.0),
    "smoked":     (0.4, 0.0, -0.3, 0.4, 1.0, 0.6),
    "toasted":    (0.7, 0.0, -0.6, 0.8, 0.0, 0.0),
    "dried":      (0.2, 0.0, -1.0, 0.1, 0.0, 0.8),
    "dehydrated": (0.2, 0.0, -1.0, 0.1, 0.0, 0.8),
    "canned":     (0.5, 0.0, 0.4, 0.0, 0.0, 0.9),
    "cured":      (0.0, 0.0, -0.3, 0.1, 0.1, 0.9),
    "fermented":  (0.0, 0.0, 0.0, 0.1, 0.0, 0.8),
    "pickled":    (0.1, 0.0, 0.3, 0.0, 0.0, 0.9),
    "frozen":     (0.0, 0.0, 0.0, 0.0, 0.0, 0.3),
    "rehydrated": (0.4, 0.0, 0.6, 0.0, 0.0, 0.4),
}

# Weight of each attribute dimension in the perceptual distance.
_DIM_WEIGHTS = (1.0, 2.2, 1.3, 1.6, 1.8, 1.0)

# Surface forms (regex) -> canonical state.
_SURFACE = [
    (r"\bdeep[\s-]?fried\b|\bdeep[\s-]?fry\b", "deep-fried"),
    (r"\bpan[\s-]?fried\b|\bpan[\s-]?fry\b", "pan-fried"),
    (r"\bstir[\s-]?fried\b|\bstir[\s-]?fry\b", "stir-fried"),
    (r"\bfried\b|\bbreaded and fried\b", "fried"),
    (r"\bsaut[eé]ed\b|\bsaut[eé]\b", "sauteed"),
    (r"\broasted\b|\broast\b", "roasted"),
    (r"\bbaked\b", "baked"),
    (r"\bgrilled\b|\bchargrilled\b", "grilled"),
    (r"\bbroiled\b", "broiled"),
    (r"\bbarbecued\b|\bbbq\b", "barbecued"),
    (r"\bboiled\b", "boiled"),
    (r"\bsimmered\b", "simmered"),
    (r"\bpoached\b", "poached"),
    (r"\bstewed\b", "stewed"),
    (r"\bbraised\b", "braised"),
    (r"\bsteamed\b", "steamed"),
    (r"\bblanched\b", "blanched"),
    (r"\bmicrowaved?\b", "microwaved"),
    (r"\bsmoked\b", "smoked"),
    (r"\btoasted\b", "toasted"),
    (r"\bdehydrated\b", "dehydrated"),
    (r"\bfrom dried\b", "rehydrated"),
    (r"\bdried\b|\bdry\b|\bsun[\s-]?dried\b", "dried"),
    (r"\bcanned\b|\btinned\b|\bjarred\b", "canned"),
    (r"\bcured\b", "cured"),
    (r"\bfermented\b", "fermented"),
    (r"\bpickled\b", "pickled"),
    (r"\bfrozen\b", "frozen"),
    (r"\bthawed\b|\bdefrosted\b", "thawed"),
    (r"\buncooked\b|\bunheated\b", "uncooked"),
    (r"\braw\b", "raw"),
    (r"\bfresh\b|\bripe\b", "fresh"),
    (r"\bcrude\b", "crude"),
    (r"\bcooked\b|\bprepared\b", "cooked"),
]
_COMPILED = [(re.compile(p), s) for p, s in _SURFACE]

# Phrases describing intended use (not current state) in recipe text.
_INTENT = re.compile(r"\b(for|to)\s+(deep[\s-]?frying|frying|roasting|baking|grilling|"
                     r"boiling|steaming|sauteing|toasting|smoking|broiling|serving|garnish)\b")
_STOP = {"and", "or", "with", "the", "of", "a", "in", "for", "to", "only", "made", "from",
         "g", "kg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "piece", "pieces"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", t)
    t = _INTENT.sub(" ", t)
    t = t.replace("(", " ").replace(")", " ")
    return re.sub(r"\s+", " ", t).strip()


_STORAGE_ONLY = {"raw", "fresh", "uncooked", "crude", "frozen", "thawed"}


def _states(text):
    found = []
    consumed = text
    for rx, state in _COMPILED:
        if rx.search(consumed):
            # Storage words (frozen/thawed/fresh) are not cooking methods: fold into raw.
            canon = "raw" if state in _STORAGE_ONLY else state
            if canon not in found:
                found.append(canon)
            consumed = rx.sub(" ", consumed)
    return found


_HEATED = {"cooked", "boiled", "simmered", "poached", "stewed", "braised", "steamed",
           "blanched", "baked", "roasted", "grilled", "broiled", "barbecued", "fried",
           "pan-fried", "stir-fried", "deep-fried", "sauteed", "microwaved", "toasted",
           "smoked", "canned", "rehydrated"}
_NEUTRAL_STATES = {"raw", "fresh", "uncooked", "crude", "frozen"}


def _distance(a, b):
    total = 0.0
    for i in range(6):
        total += _DIM_WEIGHTS[i] * (a[i] - b[i]) ** 2
    return math.sqrt(total)


def _pair_distance(a, b):
    if a == b:
        return 0.0
    # Generic "cooked" is compatible with any specific heated method.
    if (a == "cooked" and b in _HEATED) or (b == "cooked" and a in _HEATED):
        return 0.25
    if a in _NEUTRAL_STATES and b in _NEUTRAL_STATES:
        return 0.1
    va = _STATE_VECTORS.get(a, (0.0,) * 6)
    vb = _STATE_VECTORS.get(b, (0.0,) * 6)
    return _distance(va, vb)


def _set_distance(src, dst):
    """Mean over src states of the nearest-state distance in dst (directed Chamfer)."""
    if not src:
        return 0.0
    total = 0.0
    for s in src:
        total += min(_pair_distance(s, d) for d in dst)
    return total / len(src)


def _tokens(text):
    return {w.rstrip("s") for w in re.findall(r"[a-z]+", text) if len(w) > 2 and w not in _STOP}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        ing_states = _states(ing)
        usda_states = _states(usda)

        # Unstated method: treat as compatible with raw or generic (the "raw" state).
        ing_set = ing_states or ["raw"]
        usda_set = usda_states or ["raw"]
        forward = _set_distance(ing_set, usda_set)
        backward = _set_distance(usda_set, ing_set)
        if not ing_states:
            # Recipe silent: only extra processing on the USDA side matters.
            method_dist = 0.9 * backward
        elif not usda_states:
            # Generic USDA entry: mild penalty if recipe demands a strong process.
            method_dist = 0.5 * forward
        else:
            method_dist = 0.6 * forward + 0.4 * backward

        # Convert distance to similarity via a Gaussian kernel.
        method_sim = math.exp(-(method_dist ** 2) / 1.2)

        # Bonus for exact shared method words (explicit agreement).
        shared = (set(ing_states) & set(usda_states)) - {"raw"}
        agreement_bonus = min(1.0, 0.5 * len(shared))

        # Food-identity gate: method agreement is meaningless if foods differ.
        it = _tokens(ing)
        ut = _tokens(usda)
        state_words = {s.replace("-", "") for s in _STATE_VECTORS} | {"thawed", "defrosted"}
        it = {w for w in it if w not in state_words}
        ut = {w for w in ut if w not in state_words}
        primary = re.split(r",", usda)[0]
        pt = {w for w in _tokens(primary) if w not in state_words}
        if it and ut:
            overlap = len(it & ut) / max(1, min(len(it), len(ut)))
            jaccard = len(it & ut) / max(1, len(it | ut))
            primary_hit = 1.0 if (pt & it) else 0.0
            identity = 0.3 + 0.35 * min(1.0, overlap) + 0.15 * jaccard + 0.2 * primary_hit
        else:
            identity = 0.4

        score = 100.0 * identity * (0.8 * method_sim + 0.2 * agreement_bonus)
        if not math.isfinite(score):
            return 0.0
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
