import re

# Preparation states grouped into "state families". Each family has a position on a
# rough processing axis; moving between families costs according to TRANSITION.
STATE_LEXICON = {
    # trivial mechanical cuts -> collapse into the RAW family (cook can apply/ignore)
    "chopped": "raw", "diced": "raw", "minced": "raw", "sliced": "raw",
    "shredded": "raw", "grated": "raw", "cubed": "raw", "julienned": "raw",
    "halved": "raw", "quartered": "raw", "trimmed": "raw", "peeled": "raw",
    "crushed": "raw", "torn": "raw", "pitted": "raw", "seeded": "raw",
    "seeds": "raw", "leaves": "raw", "raw": "raw", "fresh": "raw",
    "uncooked": "raw", "thawed": "raw", "defrosted": "raw", "whole": "raw",
    "rinsed": "raw", "washed": "raw", "drained": "neutral",
    # frozen: equivalent to raw once thawed
    "frozen": "frozen",
    # preserved
    "canned": "canned", "tinned": "canned", "jarred": "canned", "pickled": "canned",
    "dried": "dried", "dry": "dried", "dehydrated": "dried", "powder": "dried",
    "powdered": "dried", "ground": "dried",
    # wet-heat cooking
    "boiled": "wetcook", "steamed": "wetcook", "poached": "wetcook",
    "simmered": "wetcook", "stewed": "wetcook", "braised": "wetcook",
    "blanched": "wetcook", "cooked": "wetcook",
    # dry-heat cooking
    "roasted": "drycook", "baked": "drycook", "toasted": "drycook",
    "grilled": "drycook", "broiled": "drycook", "smoked": "drycook",
    "prepared": "drycook",
    # fat cooking
    "fried": "fatcook", "sauteed": "fatcook", "sautéed": "fatcook",
    "breaded": "fatcook", "battered": "fatcook", "crispy": "fatcook",
}

FAMILIES = ["raw", "frozen", "canned", "dried", "wetcook", "drycook", "fatcook"]

# Cost (0 = interchangeable, 1 = changes the dish) of ingredient-state -> usda-state.
TRANSITION = {
    ("raw", "frozen"): 0.15, ("frozen", "raw"): 0.1,
    ("raw", "canned"): 0.55, ("canned", "raw"): 0.5,
    ("raw", "dried"): 0.6, ("dried", "raw"): 0.6,
    ("raw", "wetcook"): 0.85, ("wetcook", "raw"): 0.7,
    ("raw", "drycook"): 0.9, ("drycook", "raw"): 0.75,
    ("raw", "fatcook"): 1.0, ("fatcook", "raw"): 0.9,
    ("frozen", "canned"): 0.5, ("canned", "frozen"): 0.5,
    ("frozen", "wetcook"): 0.8, ("wetcook", "frozen"): 0.7,
    ("frozen", "drycook"): 0.85, ("frozen", "fatcook"): 0.95,
    ("canned", "wetcook"): 0.35, ("wetcook", "canned"): 0.35,
    ("canned", "drycook"): 0.7, ("canned", "fatcook"): 0.85,
    ("dried", "wetcook"): 0.7, ("dried", "drycook"): 0.6,
    ("dried", "canned"): 0.6, ("canned", "dried"): 0.65,
    ("wetcook", "drycook"): 0.6, ("drycook", "wetcook"): 0.6,
    ("wetcook", "fatcook"): 0.75, ("fatcook", "wetcook"): 0.75,
    ("drycook", "fatcook"): 0.55, ("fatcook", "drycook"): 0.5,
}

FILLER = {
    "g", "kg", "mg", "ml", "l", "oz", "lb", "tbsp", "tsp", "cup", "cups", "of", "and",
    "or", "with", "without", "the", "a", "an", "from", "in", "for", "to", "salt",
    "added", "size", "small", "large", "medium", "extra", "single", "serving",
    "tube", "cup", "ready", "eat", "style", "type", "plain", "regular", "all",
    "includes", "commercial", "products", "by", "variety", "meats",
}


def _norm(s):
    s = str(s or "").lower()
    s = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)?\b", " ", s)
    return s


def _words(s):
    return re.findall(r"[a-zé]+", s)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _states(words):
    found = set()
    for w in words:
        fam = STATE_LEXICON.get(w)
        if fam and fam != "neutral":
            found.add(fam)
    return found


def _content(words):
    return {_stem(w) for w in words if w not in FILLER and w not in STATE_LEXICON and len(w) > 1}


def _state_distance(ing_states, usda_states):
    # Unspecified states: assume the default "raw/as-sold" form, with low certainty.
    a = ing_states or {"raw"}
    b = usda_states or {"raw"}
    # Each ingredient state must be matched by its cheapest USDA counterpart and vice
    # versa (a symmetric Hausdorff-like average over the cost matrix).
    def cost(x, y):
        if x == y:
            return 0.0
        return TRANSITION.get((x, y), 0.65)
    fwd = sum(min(cost(x, y) for y in b) for x in a) / len(a)
    bwd = sum(min(cost(x, y) for x in a) for y in b) / len(b)
    d = 0.6 * max(fwd, bwd) + 0.4 * (fwd + bwd) / 2.0
    # An explicit cooking state on the USDA side the ingredient never mentions is the
    # classic "fresh vs boiled" failure; penalise more when the ingredient says fresh/raw.
    cooked = {"wetcook", "drycook", "fatcook"}
    if (usda_states & cooked) and not (ing_states & cooked):
        d += 0.1
    if (ing_states & cooked) and not (usda_states & cooked):
        d += 0.1
    return min(1.0, d)


def _identity(ing_words, usda_desc):
    ing_c = _content(ing_words)
    if not ing_c:
        return 0.3
    segs = [seg for seg in usda_desc.split(",") if seg.strip()]
    if not segs:
        return 0.0
    all_c = _content(_words(usda_desc))
    primary = _content(_words(segs[0]))
    hits_all = len(ing_c & all_c)
    hits_primary = len(ing_c & primary)
    # prefix / substring matching for compounds (e.g. pomegranate vs pomegranates)
    fuzzy = 0
    for w in ing_c - all_c:
        if len(w) >= 4 and any(u.startswith(w[:4]) or w in u or u in w for u in all_c if len(u) >= 4):
            fuzzy += 1
    cover = (hits_all + 0.6 * fuzzy) / len(ing_c)
    primary_bonus = 0.25 if (hits_primary or any(w in seg for w in ing_c for seg in [segs[0].lower()])) else 0.0
    return max(0.0, min(1.0, 0.75 * cover + primary_bonus))


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _norm(ingredient)
        # parentheticals in the ingredient are usually packaging notes; keep words but
        # drop their states influence
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        usda = str(usda_match).lower()
        usda_clean = re.sub(r"\([^)]*\)", " ", usda)

        ing_words = _words(ing_main)
        usda_words = _words(usda_clean)
        if not ing_words or not usda_words:
            return 0.0

        ing_states = _states(ing_words)
        usda_states = _states(usda_words)
        dist = _state_distance(ing_states, usda_states)

        ident = _identity(ing_words + _words(paren), usda_clean)

        # State equivalence only matters if the foods are the same; gate it by identity.
        state_sim = 1.0 - dist
        score = 10.0 * (ident ** 0.8) * (0.25 + 0.75 * state_sim)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
