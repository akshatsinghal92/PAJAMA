import re
import math

# Preparation-state lattice: each state word maps to (axis, level).
# Axis "cut" states are trivially applied/ignored by a cook; other axes alter outcome.
_STATE_LATTICE = {
    # trivial / neutral
    "raw": ("heat", 0), "fresh": ("heat", 0), "uncooked": ("heat", 0), "unprepared": ("heat", 0),
    "thawed": ("cut", 0), "frozen": ("cut", 0), "chopped": ("cut", 0), "diced": ("cut", 0),
    "minced": ("cut", 0), "sliced": ("cut", 0), "shredded": ("cut", 0), "cubed": ("cut", 0),
    "grated": ("cut", 0), "ground": ("cut", 0), "crushed": ("cut", 0), "halved": ("cut", 0),
    "quartered": ("cut", 0), "peeled": ("cut", 0), "trimmed": ("cut", 0), "pieces": ("cut", 0),
    "whole": ("cut", 0), "julienned": ("cut", 0), "mashed": ("cut", 0), "pureed": ("cut", 0),
    "purée": ("cut", 0), "puree": ("cut", 0), "drained": ("cut", 0), "rinsed": ("cut", 0),
    "seeded": ("cut", 0), "pitted": ("cut", 0), "cored": ("cut", 0), "softened": ("cut", 0),
    "melted": ("cut", 0), "beaten": ("cut", 0), "torn": ("cut", 0),
    # moist heat
    "cooked": ("heat", 2), "boiled": ("heat", 2), "simmered": ("heat", 2), "steamed": ("heat", 2),
    "poached": ("heat", 2), "stewed": ("heat", 2), "blanched": ("heat", 1), "brewed": ("heat", 1),
    "braised": ("heat", 3),
    # dry heat
    "roasted": ("heat", 3), "baked": ("heat", 3), "grilled": ("heat", 3), "broiled": ("heat", 3),
    "toasted": ("heat", 3), "sauteed": ("heat", 3), "seared": ("heat", 3), "smoked": ("heat", 3),
    "fried": ("heat", 4), "deep-fried": ("heat", 4), "pan-fried": ("heat", 4), "breaded": ("heat", 4),
    # preservation
    "canned": ("pres", 2), "syrup": ("pres", 3), "pickled": ("pres", 3), "cured": ("pres", 2),
    "dried": ("pres", 1), "dehydrated": ("pres", 2), "candied": ("pres", 3), "sweetened": ("pres", 1),
    "jarred": ("pres", 2), "brined": ("pres", 2),
}

_NOISE = {
    "nfs", "ns", "regular", "plain", "with", "without", "and", "or", "of", "the", "a", "an",
    "for", "in", "from", "added", "salt", "made", "type", "style", "pack", "solids", "liquids",
    "separable", "lean", "fat", "only", "meat", "to", "all", "varieties", "commercial",
    "prepared", "large", "small", "medium", "tube", "strong", "fortified", "vitamin", "d",
    "mature", "seeds", "by", "products", "variety", "meats", "mixed",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", text)
    text = re.sub(r"\d+", " ", text)
    return [t for t in re.findall(r"[a-zà-ÿ\-]+", text) if t]


def _split_state(tokens):
    food, states = [], []
    for t in tokens:
        key = t if t in _STATE_LATTICE else _stem(t)
        if t in _STATE_LATTICE:
            states.append(t)
        elif key in _STATE_LATTICE:
            states.append(key)
        elif t not in _NOISE and len(t) > 1:
            food.append(_stem(t))
    return food, states


def _grams(w):
    w = "^" + w + "$"
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _word_sim(a, b):
    if a == b:
        return 1.0
    if len(a) > 3 and len(b) > 3 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / float(len(ga | gb))


def _identity(ing_food, usda_food, usda_head):
    """Soft alignment of ingredient food words to USDA food words, weighted to USDA head."""
    if not ing_food or not usda_food:
        return 0.0
    total = 0.0
    for w in ing_food:
        best = max(_word_sim(w, u) for u in usda_food)
        total += best if best >= 0.45 else 0.0
    coverage = total / len(ing_food)
    head_hit = 0.0
    if usda_head:
        head_hit = max(_word_sim(h, w) for h in usda_head for w in ing_food)
    # extra USDA food words beyond the ingredient dilute the match mildly
    extra = max(0, len(usda_food) - len(ing_food) - 2)
    dilution = 1.0 / (1.0 + 0.08 * extra)
    return (0.6 * coverage + 0.4 * head_hit) * dilution


def _state_profile(states):
    prof = {"heat": 0, "pres": 0}
    for s in states:
        axis, lvl = _STATE_LATTICE[s]
        if axis in prof:
            prof[axis] = max(prof[axis], lvl)
    return prof


def _state_compat(ing_states, usda_states, ing_tokens):
    pi = _state_profile(ing_states)
    pu = _state_profile(usda_states)
    penalty = 0.0
    # heat axis: distance in processing level; USDA cooked where ingredient raw is worst
    dh = pu["heat"] - pi["heat"]
    if dh > 0:
        penalty += 0.22 * dh
    elif dh < 0:
        penalty += 0.08 * (-dh)  # ingredient cooked, USDA raw: cook can apply
    # same moist-heat family counts as equal
    if pi["heat"] and pu["heat"] and set(ing_states) & set(usda_states):
        penalty *= 0.4
    # preservation axis
    dp = pu["pres"] - pi["pres"]
    if dp > 0:
        penalty += 0.2 * dp
    elif dp < 0:
        penalty += 0.05 * (-dp)
    # "dried" ingredient matched with "mature seeds" type entries is fine
    if "dried" in ing_states and pu["pres"] == 0:
        penalty *= 0.5
    return max(0.0, 1.0 - penalty)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0
        ing_tokens = _tokens(ing)
        usda_tokens = _tokens(usda)
        if not ing_tokens or not usda_tokens:
            return 0.0
        ing_food, ing_states = _split_state(ing_tokens)
        usda_food, usda_states = _split_state(usda_tokens)
        if not ing_food:
            ing_food = [_stem(t) for t in ing_tokens]
        if not usda_food:
            usda_food = [_stem(t) for t in usda_tokens]

        # identity: fraction of ingredient food words that align with some USDA word
        hits = 0.0
        for w in ing_food:
            best = max(_word_sim(w, u) for u in usda_food)
            if best >= 0.45:
                hits += best
        ident = hits / len(ing_food)

        compat = _state_compat(ing_states, usda_states, ing_tokens)

        if re.search(r"\band\b", ing.lower()) and not re.search(r"\band\b", usda.lower()):
            ident *= 0.7

        # additive blend keeps ordering monotone in both identity and state agreement;
        # state only counts once the food itself is recognised
        score = 60.0 * ident + 40.0 * compat * ident
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
