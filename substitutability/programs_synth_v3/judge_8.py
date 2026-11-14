import re

_PREP = {
    "fresh", "frozen", "thawed", "chopped", "diced", "minced", "sliced", "cubed",
    "grated", "shredded", "peeled", "crushed", "lean", "large", "small", "medium",
    "for", "serving", "garnish", "optional", "from", "tube", "jar", "can", "canned",
    "the", "a", "an", "of", "and", "or", "to", "taste", "finely", "roughly",
    "thinly", "trimmed", "boneless", "skinless", "cooked", "raw", "dried", "whole",
    "about", "plus", "more", "extra", "packed", "drained", "rinsed", "halved",
    "quartered", "torn", "toasted", "softened", "melted", "room", "temperature",
    "florets", "leaves", "pieces", "piece", "strips", "chunks",
}

_USDA_NOISE = {
    "nfs", "ns", "raw", "cooked", "includes", "usda", "commodity", "separable",
    "lean", "fat", "only", "trimmed", "choice", "select", "prime", "all", "grades",
    "imported", "new", "zealand", "fresh", "frozen", "unprepared", "prepared",
    "with", "without", "salt", "added", "and", "or", "the", "of", "to", "in",
    "light", "dark", "unheated", "regular", "plain", "solids", "liquids",
}

# Prepared-dish words: if the USDA primary is one of these but the ingredient
# doesn't name it, the core identity is a different (composite) food.
_DISH_WORDS = {
    "soup", "stew", "patty", "patties", "salad", "sandwich", "pie", "casserole",
    "pizza", "burrito", "sauce", "dressing", "dip", "cake", "cookie", "candy",
    "beverage", "drink", "mix", "babyfood", "snack", "bar", "nuggets", "loaf",
}

_ALIASES = {
    "shungiku": "chrysanthemum",
    "garbanzo": "chickpea",
    "chickpeas": "chickpea",
    "cilantro": "coriander",
    "scallion": "onion",
    "scallions": "onion",
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "prawn": "shrimp",
    "prawns": "shrimp",
    "capsicum": "pepper",
    "kidneys": "kidney",
    "flaxseed": "flax",
    "linseed": "flax",
}


def _stem(w):
    w = _ALIASES.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("oes"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return _ALIASES.get(w, w)


def _words(text):
    return re.findall(r"[a-z]+", text.lower())


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    toks = [_stem(w) for w in _words(t) if w not in _PREP and len(w) > 1]
    return toks


def _usda_segments(text):
    segs = []
    for i, seg in enumerate(text.lower().split(",")):
        seg = re.sub(r"\([^)]*\)", " ", seg)
        toks = [_stem(w) for w in _words(seg) if w not in _USDA_NOISE and len(w) > 1]
        if toks:
            segs.append(toks)
    return segs


def _bigrams(w):
    w = "#" + w + "#"
    return {w[i:i + 2] for i in range(len(w) - 1)}


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    d = 2.0 * len(ba & bb) / (len(ba) + len(bb))
    # Dice on short food words is noisy (garlic/guava); keep only strong overlaps
    return d if d >= 0.7 else 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        itoks = _clean_ingredient(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not itoks or not segs:
            return 0.0

        head = itoks[-1]
        modifiers = itoks[:-1]

        # Positional weights for USDA segments: primary food dominates.
        weights = [1.0 / (1 + 0.6 * k) for k in range(len(segs))]

        # Locate the ingredient head noun within the USDA description.
        best_head, best_pos = 0.0, None
        for k, seg in enumerate(segs):
            for t in seg:
                s = _sim(head, t) * (0.6 + 0.4 * weights[k])
                if s > best_head:
                    best_head, best_pos = s, k

        # Also allow a modifier to be the identity anchor (e.g. "turkey skin").
        anchor = 0.0
        for m in modifiers:
            for k, seg in enumerate(segs):
                for t in seg:
                    anchor = max(anchor, _sim(m, t) * weights[k])

        # Fraction of ingredient core tokens covered anywhere in USDA.
        flat = [t for seg in segs for t in seg]
        cov = 0.0
        for t in itoks:
            cov += max((_sim(t, u) for u in flat), default=0.0)
        cov /= len(itoks)

        # Fraction of USDA primary segment explained by the ingredient.
        primary = segs[0]
        prim_cov = sum(max((_sim(p, t) for t in itoks), default=0.0) for p in primary) / len(primary)

        score = 50.0 * best_head + 15.0 * anchor + 20.0 * cov + 15.0 * prim_cov

        # Composite-dish penalty: USDA primary is a prepared dish not in ingredient.
        if any(p in _DISH_WORDS for p in primary) and not any(t in _DISH_WORDS for t in itoks):
            score *= 0.35

        # Head noun absent: core substance likely differs.
        if best_head == 0.0:
            score *= 0.4

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
