import re

# Variant 4: multiplicative "survival" model over an additive/processing ledger.
# Each component family the USDA entry adds (and the ingredient does not claim)
# multiplies the score by a retention factor. Components the ingredient asks for
# but the USDA entry lacks also decay the score. A core-food anchor check gates it.

_FAMILIES = {
    "salt": (0.55, ["salt", "salted", "sodium", "brine", "brined", "pickled", "cured", "corned"]),
    "sugar": (0.50, ["sugar", "sweetened", "sweet", "honey", "syrup", "candied", "glazed", "frosted", "caramel", "sugared"]),
    "fat": (0.60, ["fried", "oil", "butter", "buttered", "lard", "shortening", "creamed", "cream"]),
    "breading": (0.35, ["breaded", "battered", "batter", "crumbs", "coated", "crusted", "tempura"]),
    "sauce": (0.35, ["sauce", "gravy", "dressing", "marinade", "marinated", "teriyaki", "barbecue", "bbq", "ketchup", "mayonnaise"]),
    "seasoning": (0.55, ["seasoned", "seasoning", "spiced", "pepper", "herbs", "garlic", "onion", "chili", "flavored", "flavor", "smoked"]),
    "flavor": (0.50, ["vanilla", "chocolate", "strawberry", "cinnamon", "lemon", "honey", "maple", "fruit", "cocoa", "mint"]),
    "dish": (0.20, ["taco", "sandwich", "souffle", "casserole", "pie", "pizza", "burrito", "soup", "stew", "salad", "patty",
                    "nuggets", "roll", "burger", "dumpling", "lasagna", "quiche", "omelet", "with", "and", "mixture", "mix", "blend"]),
    "cooked": (0.65, ["cooked", "boiled", "roasted", "baked", "grilled", "steamed", "braised", "stewed", "broiled", "sauteed", "toasted"]),
    "dried": (0.55, ["dried", "dehydrated", "ground", "powder", "powdered", "flakes", "freeze-dried"]),
    "canned": (0.70, ["canned", "jarred", "bottled"]),
}

_NEUTRAL = {"raw", "fresh", "plain", "unsalted", "unsweetened", "nonfat", "lowfat", "commercially", "prepared",
            "regular", "whole", "frozen", "uncooked", "all", "varieties", "type", "unenriched", "enriched",
            "spices", "ns", "as", "to", "includes", "or", "of", "the", "a", "in", "made", "from", "unprepared",
            "reduced", "fat", "low", "light", "solids", "liquids", "drained", "unheated"}

_PREP_ING = {"chopped", "diced", "minced", "sliced", "thawed", "warmed", "fresh", "large", "small", "medium",
             "finely", "roughly", "peeled", "trimmed", "leaves", "taste", "to", "for", "about", "cup", "tbsp", "tsp"}

# words in the ingredient that legitimize a USDA family
_ING_CLAIMS = {
    "paste": {"dish": 0.0}, "tube": {}, "toasted": {"cooked": 1.0}, "roasted": {"cooked": 1.0},
}


def _toks(s):
    s = s.lower()
    s = re.sub(r"\(([^)]*)\)", r" \1 ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", s)
    s = re.sub(r"[^a-z\- ]", " ", s)
    out = []
    for t in s.replace("-", " ").split():
        if len(t) > 3 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("es") and t[-3] in "sxh":
            t = t[:-2]
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def _norm(word):
    w = word
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def _families_of(tokens):
    hit = {}
    tset = set(tokens)
    for fam, (_, words) in _FAMILIES.items():
        n = sum(1 for w in words if _norm(w) in tset)
        if n:
            hit[fam] = n
    return hit


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0

        ing_t = _toks(ing)
        usda_t = _toks(usda)
        if not ing_t or not usda_t:
            return 0.0

        # Primary USDA food = first comma segment (or second when first is a generic class)
        segs = [x.strip().lower() for x in usda.split(",") if x.strip()]
        primary = _toks(segs[0]) if segs else []
        if primary and primary[0] in ("spice", "syrup", "cheese", "beverage", "candie") and len(segs) > 1:
            primary = primary + _toks(segs[1])

        ing_core = [t for t in ing_t if t not in _PREP_ING and t not in _NEUTRAL]
        ing_set = set(ing_t)
        usda_set = set(usda_t)

        # Anchor: does the primary food appear in the ingredient?
        anchor_hits = [p for p in primary if p in ing_set and p not in _NEUTRAL]
        anchor_strength = len(anchor_hits) / max(1, len([p for p in primary if p not in _NEUTRAL]))
        score = 100.0 * (0.25 + 0.75 * anchor_strength)
        if not anchor_hits:
            # fallback: any shared content token
            shared = set(ing_core) & usda_set
            score = 40.0 if shared else 12.0

        ing_fam = _families_of(ing_t)
        usda_fam = _families_of(usda_t)

        # Added components: families in USDA not claimed by ingredient
        for fam, cnt in usda_fam.items():
            factor, words = _FAMILIES[fam]
            if fam in ing_fam:
                # same family; check exact word agreement
                ing_words = {_norm(w) for w in words if _norm(w) in ing_set}
                usda_words = {_norm(w) for w in words if _norm(w) in usda_set}
                extra = usda_words - ing_words - set(anchor_hits)
                if extra:
                    score *= (1.0 + factor) / 2.0
                continue
            # words that are themselves part of the anchor (e.g. "salt" in "Salt, table") are not additions
            fam_words = {_norm(w) for w in words}
            if fam_words & set(anchor_hits) and fam != "dish":
                continue
            score *= factor ** min(cnt, 2) if fam == "dish" else factor

        # Missing components: ingredient asks for a flavor/additive the entry lacks
        for fam, cnt in ing_fam.items():
            if fam in usda_fam:
                continue
            factor, _ = _FAMILIES[fam]
            if fam in ("cooked", "dried"):
                score *= (1.0 + factor) / 2.0
            else:
                score *= 0.5 + 0.5 * factor

        # Compound ingredient (e.g. "salt and sesame seeds") matched to a single plain item
        if re.search(r"\b(and|&|with|or)\b", ing.lower()) and not re.search(r"\b(and|with)\b", usda.lower()):
            score *= 0.45

        # Unexplained descriptor load: USDA content tokens absent from ingredient
        known = set()
        for _, words in _FAMILIES.values():
            known |= {_norm(w) for w in words}
        unexplained = [t for t in usda_set if t not in ing_set and t not in _NEUTRAL and t not in known
                       and t not in primary and len(t) > 2]
        score *= 0.88 ** min(len(unexplained), 4)

        # Plain-for-plain bonus
        if not usda_fam and not ing_fam and anchor_hits:
            score = min(100.0, score * 1.1)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
