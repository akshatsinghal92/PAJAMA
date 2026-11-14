import re
import math

# Form classes and the cue words that signal them.
_FORM_CUES = {
    "fresh": ["fresh", "raw", "uncooked", "unprocessed", "whole", "skin on", "with skin"],
    "frozen": ["frozen", "thawed", "ice"],
    "canned": ["canned", "tinned", "can", "jarred", "jar", "bottled", "in syrup", "in brine", "in oil", "drained"],
    "dried": ["dried", "dry", "dehydrated", "freeze-dried", "sun-dried", "jerky", "dried-frozen"],
    "powder": ["powder", "powdered", "ground", "flour", "starch", "meal", "granulated", "confectioners"],
    "paste": ["paste", "puree", "pureed", "pulp", "concentrate", "concentrated", "tube", "mash", "mashed"],
    "liquid": ["juice", "nectar", "broth", "stock", "soup", "drink", "beverage", "fluid", "syrup", "ready-to-serve", "milk"],
    "cooked": ["cooked", "braised", "boiled", "roasted", "baked", "fried", "pan-fried", "broiled",
               "pan-broiled", "grilled", "steamed", "stewed", "sauteed", "crumbles", "smoked"],
    "formed": ["chopped and formed", "patty", "formed", "restructured", "loaf", "nuggets"],
    "mixture": ["mixture", "mixed", "blend", "substitute", "imitation", "nfs"],
}

# Compatibility between ingredient form (row) and USDA form (column), 0..1.
_COMPAT = {
    "fresh":   {"fresh": 1.0, "frozen": 0.75, "canned": 0.35, "dried": 0.15, "powder": 0.1, "paste": 0.2, "liquid": 0.1, "cooked": 0.3, "formed": 0.15, "mixture": 0.2},
    "frozen":  {"fresh": 0.8, "frozen": 1.0, "canned": 0.35, "dried": 0.15, "powder": 0.1, "paste": 0.2, "liquid": 0.1, "cooked": 0.35, "formed": 0.3, "mixture": 0.3},
    "canned":  {"fresh": 0.45, "frozen": 0.45, "canned": 1.0, "dried": 0.15, "powder": 0.1, "paste": 0.3, "liquid": 0.35, "cooked": 0.6, "formed": 0.2, "mixture": 0.2},
    "dried":   {"fresh": 0.15, "frozen": 0.15, "canned": 0.2, "dried": 1.0, "powder": 0.55, "paste": 0.2, "liquid": 0.05, "cooked": 0.15, "formed": 0.2, "mixture": 0.2},
    "powder":  {"fresh": 0.1, "frozen": 0.05, "canned": 0.1, "dried": 0.55, "powder": 1.0, "paste": 0.2, "liquid": 0.05, "cooked": 0.1, "formed": 0.1, "mixture": 0.2},
    "paste":   {"fresh": 0.25, "frozen": 0.2, "canned": 0.45, "dried": 0.15, "powder": 0.2, "paste": 1.0, "liquid": 0.25, "cooked": 0.3, "formed": 0.1, "mixture": 0.2},
    "liquid":  {"fresh": 0.1, "frozen": 0.2, "canned": 0.5, "dried": 0.05, "powder": 0.15, "paste": 0.3, "liquid": 1.0, "cooked": 0.2, "formed": 0.05, "mixture": 0.3},
    "cooked":  {"fresh": 0.3, "frozen": 0.35, "canned": 0.55, "dried": 0.15, "powder": 0.05, "paste": 0.2, "liquid": 0.15, "cooked": 1.0, "formed": 0.3, "mixture": 0.3},
    "formed":  {"fresh": 0.2, "frozen": 0.4, "canned": 0.2, "dried": 0.2, "powder": 0.05, "paste": 0.1, "liquid": 0.05, "cooked": 0.5, "formed": 1.0, "mixture": 0.4},
    "mixture": {"fresh": 0.2, "frozen": 0.3, "canned": 0.3, "dried": 0.2, "powder": 0.2, "paste": 0.2, "liquid": 0.3, "cooked": 0.3, "formed": 0.3, "mixture": 0.8},
}

_DEFAULT_ING_FORM = "fresh"

_STOP = set("""a an and or of the with without in on for to from by as at
    nfs ns not further specified style type made plus about approx g kg mg ml l oz lb
    cup cups tbsp tsp large small medium piece pieces prepared regular plain
    raw fresh frozen canned dried dry cooked""".split())

_EQUIV = {
    "linseed": "flaxseed", "linseeds": "flaxseed", "flax": "flaxseed",
    "confectioner": "powdered", "icing": "powdered",
    "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro",
    "prawn": "shrimp", "prawns": "shrimp", "garbanzo": "chickpea", "chickpeas": "chickpea",
    "scallion": "onion", "rocket": "arugula", "sugars": "sugar",
}


def _norm_text(s):
    s = str(s or "").lower()
    s = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)\b\.?\s*", " ", s)
    s = s.replace("_", " ")
    return s


def _stem(w):
    w = _EQUIV.get(w, w)
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and w[-3] in "sxz":
                return w[:-2]
            if suf == "s" and not w.endswith("ss"):
                return w[:-1]
    return _EQUIV.get(w, w)


def _form_vector(text, default=None):
    """Soft distribution over form classes from cue-phrase hits."""
    t = " " + re.sub(r"[^a-z0-9%\- ]", " ", text) + " "
    weights = {}
    for form, cues in _FORM_CUES.items():
        hit = 0.0
        for c in cues:
            if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", t):
                hit += 1.0 + 0.3 * c.count(" ")
        if hit:
            weights[form] = hit
    if not weights:
        if default:
            return {default: 1.0}, False
        return {}, False
    tot = sum(weights.values())
    return {k: v / tot for k, v in weights.items()}, True


def _expected_compat(iv, uv):
    if not iv or not uv:
        return 0.6
    s = 0.0
    for fi, pi in iv.items():
        row = _COMPAT.get(fi, {})
        best = 0.0
        acc = 0.0
        for fu, pu in uv.items():
            c = row.get(fu, 0.2)
            acc += pu * c
            best = max(best, c)
        # blend expected value with best-case (recoverable forms)
        s += pi * (0.6 * acc + 0.4 * best)
    return s


def _tokens(text):
    out = []
    for w in re.findall(r"[a-z]+", text):
        if len(w) < 3 or w in _STOP:
            continue
        out.append(_stem(w))
    return out


def _trigrams(w):
    w = "  " + w + " "
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _soft_match(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    j = len(ta & tb) / float(len(ta | tb) or 1)
    return j if j >= 0.45 else 0.0


def _identity_score(ing_text, usda_text):
    """How well the core food is preserved, 0..1 (weighted to ingredient head noun)."""
    ing_main = re.sub(r"\([^)]*\)", " ", ing_text).split(",")[0]
    ing_t = _tokens(ing_main)
    if not ing_t:
        ing_t = _tokens(ing_text)
    usda_parts = [p.strip() for p in usda_text.split(",") if p.strip()]
    usda_t = _tokens(usda_text)
    if not ing_t or not usda_t:
        return 0.0, 0.0
    primary_t = _tokens(usda_parts[0]) if usda_parts else []
    # ingredient head noun = last content token of the main phrase
    weights = []
    n = len(ing_t)
    for i in range(n):
        weights.append(1.0 + (1.5 if i == n - 1 else 0.0))
    cov = 0.0
    for w, wt in zip(ing_t, weights):
        cov += wt * max(_soft_match(w, u) for u in usda_t)
    cov /= sum(weights)
    prim = 0.0
    if primary_t:
        prim = max(_soft_match(w, p) for w in ing_t for p in primary_t)
    return cov, prim


def judging_function(ingredient, usda_match):
    try:
        ing = _norm_text(ingredient)
        usda = _norm_text(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # --- Form / preservation analysis ---
        iv, ing_explicit = _form_vector(ing, default=_DEFAULT_ING_FORM)
        uv, usda_explicit = _form_vector(usda, default=None)
        if not usda_explicit:
            # USDA entry without a form qualifier is normally the raw/plain item
            uv = {"fresh": 1.0}
        form = _expected_compat(iv, uv)

        # Recoverable thawed-frozen pattern bonus
        if re.search(r"\bfrozen\b", ing) and re.search(r"\bfrozen\b", usda):
            form = min(1.0, form + 0.1)
        # Concentration / water-content shifts: liquid vs solid of same food
        ing_liquid = bool(re.search(r"\b(juice|nectar|broth|stock|soup|drink|syrup)\b", ing))
        usda_liquid = bool(re.search(r"\b(juice|nectar|broth|stock|soup|drink|beverage|ready-to-serve)\b", usda))
        if ing_liquid != usda_liquid:
            form *= 0.55
        # Substitutes / imitation alter the food entirely
        if re.search(r"\b(substitute|imitation|analog)\b", usda) and not re.search(r"\b(substitute|imitation)\b", ing):
            form *= 0.5
        # Mixtures replacing a single specific item
        if re.search(r"\bmixture\b|\bmixed\b", usda) and not re.search(r"\bmix", ing):
            form *= 0.6

        # --- Identity gate (form only matters if the food is the same) ---
        cov, prim = _identity_score(ing, usda)
        identity = 0.65 * cov + 0.35 * prim
        gate = 1.0 / (1.0 + math.exp(-10.0 * (identity - 0.45)))

        score = 100.0 * gate * (0.35 + 0.65 * form)
        # small tie-breaker on raw overlap
        score += 5.0 * cov
        return round(max(0.0, min(100.0, score)), 4)
    except Exception:
        return 0.0
