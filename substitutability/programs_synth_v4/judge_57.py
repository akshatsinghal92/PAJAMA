import re

_STOP = {
    "and", "or", "with", "of", "the", "a", "in", "for", "to", "from", "fresh",
    "chopped", "sliced", "diced", "minced", "thawed", "shelled", "leftover",
    "trimmed", "visible", "fat", "flaked", "peeled", "whole", "large", "small",
    "medium", "raw", "uncooked", "unprepared", "all", "varieties", "regular",
}

# Variant / flavour / base markers that a commercial product may carry.
_FLAVOURS = {
    "strawberry", "vanilla", "chocolate", "blueberry", "raspberry", "peach",
    "cherry", "lemon", "orange", "honey", "mint", "caramel", "coffee", "mocha",
    "banana", "maple", "cinnamon", "apple", "grape", "mango", "coconut",
    "cheddar", "bbq", "barbecue", "ranch", "garlic", "onion", "spicy", "hot",
}
_BASES = {
    "vegan", "plant", "soy", "almond", "oat", "rice", "coconut", "dairy-free",
    "gluten-free", "meatless", "veggie", "vegetarian", "imitation", "substitute",
}
_MODIFIERS = {
    "lowfat", "low", "nonfat", "fat-free", "free", "reduced", "light", "lite",
    "diet", "sodium", "sugar", "unsweetened", "sweetened", "salted", "unsalted",
}
_GENERIC_CAPS = {"USDA", "NFS", "NS", "USA", "US", "UPC"}
_COMMERCIAL_WORDS = {
    "brand", "inc", "co", "company", "kraft", "nabisco", "oreo", "lifeway",
    "kellogg", "kelloggs", "general", "mills", "heinz", "campbell", "hormel",
    "tyson", "dannon", "yoplait", "chobani", "ocean", "spray", "pillsbury",
    "quaker", "post", "nestle", "hershey", "hersheys", "mccormick", "starbucks",
    "subway", "mcdonalds", "burger", "king", "wendys", "kfc", "taco", "bell",
    "pizza", "hut", "dominos", "silk", "kroger", "martha", "white",
}


def _clean_ingredient(text):
    t = text.strip()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|grams?|kg|ml|l|oz)\b\.?\s*", "", t, flags=re.I)
    paren = re.findall(r"\(([^)]*)\)", t)
    t = re.sub(r"\([^)]*\)", " ", t)
    head = t.split(",")[0]
    return head, " ".join(paren)


def _words(text):
    return [w for w in re.findall(r"[a-z][a-z\-']*", text.lower())]


def _stem(w):
    w = w.strip("'-")
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _brand_tokens(usda_raw):
    """Detect brand-like tokens: ALL-CAPS words, trademark symbols, known brand words."""
    found = set()
    for tok in re.findall(r"[A-Za-z][A-Za-z'&\.\-]*", usda_raw):
        core = tok.strip(".'-")
        if len(core) >= 3 and core.isupper() and core not in _GENERIC_CAPS:
            found.add(core.lower())
    if re.search(r"[®™]|\(R\)|\(TM\)", usda_raw):
        found.add("_tm_")
    for w in _words(usda_raw):
        if w in _COMMERCIAL_WORDS and w not in ("white", "general", "king", "post", "pizza", "taco", "bell", "ocean", "spray", "burger", "hut"):
            found.add(w)
    return found


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        head, paren = _clean_ingredient(ingredient)
        ing_words = [_stem(w) for w in _words(head)]
        ing_all = set(ing_words) | {_stem(w) for w in _words(paren)}
        ing_core = {w for w in ing_words if w not in _STOP and len(w) > 1}

        usda_parts = [p.strip() for p in usda_match.split(",") if p.strip()]
        primary = usda_parts[0] if usda_parts else usda_match
        usda_words = [_stem(w) for w in _words(usda_match)]
        usda_set = set(usda_words)
        primary_set = {_stem(w) for w in _words(primary)}

        # --- 1. Base identity agreement (gate for brand analysis) ---
        if ing_core:
            covered = sum(1 for w in ing_core if w in usda_set)
            coverage = covered / float(len(ing_core))
        else:
            coverage = 0.0
        primary_hit = bool(primary_set & ing_core)

        score = 20.0 + 40.0 * coverage + (15.0 if primary_hit else 0.0)

        # --- 2. Brand / commercial-product analysis ---
        brands = _brand_tokens(usda_match)
        brand_in_ing = {b for b in brands if b in ing_all}
        foreign_brands = brands - brand_in_ing

        # Markers carried by the USDA entry but not asked for by the ingredient.
        extra_flav = {w for w in usda_set if w in _FLAVOURS and w not in ing_all}
        extra_base = {w for w in usda_set if w in _BASES and w not in ing_all}
        extra_mod = {w for w in usda_set if w in _MODIFIERS and w not in ing_all}
        # Base markers in ingredient (e.g. vegan) absent from USDA entry.
        missing_base = {w for w in ing_all if w in _BASES and w not in usda_set}
        missing_flav = {w for w in ing_core if w in _FLAVOURS and w not in usda_set}

        if brand_in_ing:
            score += 10.0  # explicitly requested brand
        if foreign_brands:
            # Brand alone is tolerable if it's the standard version of the product.
            if extra_flav or extra_base or extra_mod:
                score -= 30.0  # brand implies a distinct variant
            elif coverage >= 0.99:
                score -= 3.0   # canonical branded example
            else:
                score -= 10.0

        score -= 14.0 * len(extra_flav)
        score -= 18.0 * len(extra_base)
        score -= 9.0 * min(len(extra_mod), 2)
        score -= 20.0 * len(missing_base)
        score -= 8.0 * len(missing_flav)

        # Exact simple match bonus (e.g. "Peanut oil")
        if len(usda_parts) == 1 and primary_set and primary_set <= (ing_core | ing_all) and coverage >= 0.99:
            score += 10.0

        if score < 0.0:
            score = 0.0
        if score > 100.0:
            score = 100.0
        return round(score, 3)
    except Exception:
        return 0.0
