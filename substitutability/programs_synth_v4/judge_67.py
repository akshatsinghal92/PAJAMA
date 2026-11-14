import re
import math


# Each cooking state is embedded in a 4-D "transformation space":
# (heat intensity, surface browning, added fat, moisture change)
# moisture change: negative = drier, positive = wetter.
_METHOD_VECTORS = {
    "raw":        (0.0, 0.0, 0.0, 0.0),
    "fresh":      (0.0, 0.0, 0.0, 0.0),
    "uncooked":   (0.0, 0.0, 0.0, 0.0),
    "dried":      (0.2, 0.0, 0.0, -0.9),
    "dehydrated": (0.2, 0.0, 0.0, -0.9),
    "dry":        (0.1, 0.0, 0.0, -0.5),
    "cooked":     (0.5, 0.2, 0.0, 0.1),
    "boiled":     (0.5, 0.0, 0.0, 0.6),
    "poached":    (0.4, 0.0, 0.0, 0.5),
    "simmered":   (0.5, 0.0, 0.0, 0.5),
    "steamed":    (0.5, 0.0, 0.0, 0.4),
    "blanched":   (0.3, 0.0, 0.0, 0.3),
    "braised":    (0.6, 0.3, 0.1, 0.6),
    "stewed":     (0.6, 0.1, 0.1, 0.7),
    "baked":      (0.7, 0.4, 0.0, -0.2),
    "roasted":    (0.8, 0.7, 0.1, -0.3),
    "grilled":    (0.9, 0.8, 0.0, -0.3),
    "broiled":    (0.9, 0.7, 0.0, -0.3),
    "barbecued":  (0.9, 0.8, 0.1, -0.3),
    "fried":      (0.9, 0.7, 0.8, -0.3),
    "pan-fried":  (0.8, 0.6, 0.6, -0.2),
    "deep-fried": (1.0, 0.8, 1.0, -0.4),
    "sauteed":    (0.7, 0.5, 0.5, -0.1),
    "stir-fried": (0.8, 0.5, 0.5, -0.1),
    "microwaved": (0.5, 0.0, 0.0, 0.0),
    "smoked":     (0.4, 0.5, 0.0, -0.4),
    "toasted":    (0.7, 0.7, 0.0, -0.5),
    "canned":     (0.5, 0.0, 0.0, 0.3),
}

# Surface forms -> canonical state
_ALIASES = [
    (r"deep[\s-]?fried|deep[\s-]?fry", "deep-fried"),
    (r"pan[\s-]?fried|pan[\s-]?fry|pan[\s-]?seared|seared", "pan-fried"),
    (r"stir[\s-]?fried|stir[\s-]?fry", "stir-fried"),
    (r"dry[\s-]roasted", "roasted"),
    (r"dry heat", "roasted"),
    (r"moist heat", "braised"),
    (r"\bfried\b|\bfry\b|\bbreaded and fried\b", "fried"),
    (r"saut[eé]ed?|saut[eé]", "sauteed"),
    (r"\broast(ed)?\b", "roasted"),
    (r"\bgrill(ed)?\b|\bchar(red|grilled)\b", "grilled"),
    (r"\bbroil(ed)?\b", "broiled"),
    (r"\bbarbecue(d)?\b|\bbbq\b", "barbecued"),
    (r"\bbak(ed|e)\b", "baked"),
    (r"\bboil(ed)?\b", "boiled"),
    (r"\bpoach(ed)?\b", "poached"),
    (r"\bsimmer(ed)?\b", "simmered"),
    (r"\bsteam(ed)?\b", "steamed"),
    (r"\bblanch(ed)?\b", "blanched"),
    (r"\bbrais(ed|e)\b", "braised"),
    (r"\bstew(ed)?\b", "stewed"),
    (r"\bmicrowav(ed|e)\b", "microwaved"),
    (r"\bsmok(ed|e)\b|\blox\b", "smoked"),
    (r"\btoast(ed)?\b", "toasted"),
    (r"\bdehydrated\b|\bfreeze[\s-]dried\b", "dehydrated"),
    (r"\bdried\b|\bsun[\s-]dried\b", "dried"),
    (r"\bcanned\b", "canned"),
    (r"\buncooked\b|\bunheated\b|\bunprepared\b", "uncooked"),
    (r"\braw\b|\bcrude\b", "raw"),
    (r"\bfresh\b", "fresh"),
    (r"\bcooked\b|\bprepared\b", "cooked"),
]

_NEUTRAL = {"raw", "fresh", "uncooked"}

_STOP = {
    "and", "or", "with", "without", "the", "a", "of", "in", "from", "for",
    "added", "salt", "regular", "mixed", "species", "fresh", "raw", "cooked",
    "to", "fat", "lean", "separable", "trimmed", "all", "grades", "type",
    "frozen", "thawed", "chopped", "sliced", "diced", "minced", "drained",
    "whole", "large", "small", "medium", "dry", "dried",
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    t = t.replace("(", " ").replace(")", " ")
    return re.sub(r"\s+", " ", t).strip()


def _states(text):
    found = []
    remaining = text
    for pat, canon in _ALIASES:
        if re.search(pat, remaining):
            found.append(canon)
            remaining = re.sub(pat, " ", remaining)
    return found


def _centroid(states):
    if not states:
        return None
    vecs = [_METHOD_VECTORS[s] for s in states if s in _METHOD_VECTORS]
    if not vecs:
        return None
    n = float(len(vecs))
    return tuple(sum(v[i] for v in vecs) / n for i in range(4))


def _tokens(text):
    out = set()
    for w in re.findall(r"[a-z]+", text):
        if len(w) < 3 or w in _STOP:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and not w.endswith("ses"):
            w = w[:-2]
        elif w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def _method_affinity(ing_states, usda_states):
    """Returns affinity in [0,1] computed from distance in transformation space."""
    ing_active = [s for s in ing_states if s not in _NEUTRAL]
    usda_active = [s for s in usda_states if s not in _NEUTRAL]

    # Unstated method in recipe -> compatible with raw or generic entries.
    if not ing_active:
        if not usda_active:
            return 0.9
        v = _centroid(usda_active)
        # unstated recipe vs heavily transformed entry: mild penalty by magnitude
        mag = math.sqrt(v[0] ** 2 + v[1] ** 2 + (1.5 * v[2]) ** 2 + v[3] ** 2)
        # preserved forms (dried, canned) are often how the item is bought
        if all(s in ("dried", "dehydrated", "dry", "canned", "cooked") for s in usda_active):
            return max(0.55, 0.85 - 0.25 * mag)
        return max(0.15, 0.85 - 0.45 * mag)

    vi = _centroid(ing_active)
    if not usda_active:
        # recipe asks for a transformation the entry lacks (toasted vs plain, roast vs generic)
        base = _METHOD_VECTORS["raw"]
    else:
        base = _centroid(usda_active)
    weights = (1.0, 1.4, 2.0, 0.9)
    d = math.sqrt(sum(weights[i] * (vi[i] - base[i]) ** 2 for i in range(4)))
    aff = math.exp(-1.8 * d)
    # exact shared state bonus
    if set(ing_active) & set(usda_active):
        aff = min(1.0, aff + 0.15)
    return aff


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        # Main ingredient phrase: before first comma; USDA primary food first
        ing_head = ing.split(",")[0]
        ing_states = _states(ing_head)
        usda_states = _states(usda)

        affinity = _method_affinity(ing_states, usda_states)

        # Food identity anchor so method agreement is judged on the same food
        it = _tokens(ing_head)
        ut = _tokens(usda)
        if it and ut:
            inter = it & ut
            # partial stem match (e.g. cherry/cherries, pinyon)
            fuzzy = 0
            for a in it - inter:
                for b in ut - inter:
                    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b[:4]) and b.startswith(a[:4])):
                        fuzzy += 1
                        break
            hits = len(inter) + 0.6 * fuzzy
            identity = hits / max(1.0, float(len(it)))
            primary = _tokens(usda.split(",")[0])
            if primary & it:
                identity += 0.25
            identity = min(1.0, identity)
        else:
            identity = 0.0

        # Combine: method affinity gated by identity (geometric-ish blend)
        score = 10.0 * (0.6 * affinity * (0.3 + 0.7 * identity) + 0.4 * identity)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
