import re

# Additive / processing categories: each maps to trigger phrases and a penalty weight
_ADDITIVE_CATEGORIES = {
    "salt": (["salted", "with salt", "added salt", "brined", "cured", "corned", "pickled"], 2.0),
    "sugar": (["sweetened", "with sugar", "sugar added", "candied", "glazed", "honey", "syrup", "frosted", "sugared"], 2.5),
    "fat": (["fried", "with oil", "added fat", "with butter", "buttered", "in oil", "oil-roasted", "with margarine"], 2.0),
    "sauce": (["sauce", "gravy", "with cheese", "in sauce", "dressing", "marinated"], 2.5),
    "breading": (["breaded", "battered", "coated", "crusted", "tempura", "with breading"], 3.0),
    "seasoning": (["seasoned", "spiced", "flavored", "flavoured", "herbed", "smoked", "barbecue", "bbq", "and pepper", "with garlic", "teriyaki"], 2.5),
    "compound": (["patty", "nuggets", "sticks", "mix", "prepared", "dish", "casserole", "sandwich", "soup", "stew", "with vegetables", "with noodles", "frozen dinner", "entree", "imitation", "substitute"], 2.5),
    "reformulated": (["low fat", "lowfat", "fat free", "fat-free", "nonfat", "reduced fat", "light", "lite", "low sodium", "reduced sodium", "no salt", "sugar free", "diet", "unsweetened"], 2.0),
}

# Neutral / plain descriptors that should not be penalized
_PLAIN_TOKENS = {
    "raw", "fresh", "plain", "regular", "whole", "uncooked", "unprepared", "all",
    "varieties", "dried", "dry", "frozen", "ground", "boiled", "cooked", "drained",
}

_STOP = {"and", "or", "with", "of", "the", "a", "in", "for", "from", "to", "without",
         "fresh", "large", "small", "medium", "chopped", "sliced", "diced", "minced"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb)\b\.?", " ", t)
    t = re.sub(r"\(([^)]*)\)", r" \1 ", t)
    t = re.sub(r"[^a-z\s,-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 1}


def _categories_present(text):
    found = {}
    padded = " " + text.replace(",", " , ") + " "
    for cat, (phrases, weight) in _ADDITIVE_CATEGORIES.items():
        for p in phrases:
            if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", padded):
                found[cat] = weight
                break
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        ing_tok = _tokens(ing)
        usda_tok = _tokens(usda)
        if not ing_tok or not usda_tok:
            return 0.5

        # Primary-food anchoring: the USDA head segment should share content with ingredient
        head = usda.split(",")[0]
        head_tok = _tokens(head)
        head_hit = len(head_tok & ing_tok) / max(1, len(head_tok))
        overall_hit = len(ing_tok & usda_tok) / max(1, len(ing_tok))
        anchor = 0.6 * head_hit + 0.4 * overall_hit
        if anchor == 0:
            # Without any shared food identity, processing comparison is meaningless
            return 1.0

        ing_cats = _categories_present(ing)
        usda_cats = _categories_present(usda)

        # Additives introduced by USDA but not present in the ingredient
        added = {c: w for c, w in usda_cats.items() if c not in ing_cats}
        # Processing the ingredient has that the USDA plain entry lacks (e.g. sauce vs raw fruit)
        missing = {c: w for c, w in ing_cats.items() if c not in usda_cats}

        penalty = sum(added.values()) + 0.8 * sum(missing.values())

        # Extra non-plain descriptors in USDA beyond the head that ingredient never mentions
        tail_segments = [s.strip() for s in usda.split(",")[1:] if s.strip()]
        unexplained = 0
        for seg in tail_segments:
            seg_tok = _tokens(seg) - _PLAIN_TOKENS
            if seg_tok and not (seg_tok & ing_tok):
                unexplained += 1
        penalty += 0.5 * min(unexplained, 4)

        # Plain-for-plain bonus: neither side carries additive markers
        bonus = 1.5 if not ing_cats and not usda_cats else 0.0
        # Matching processing on both sides (e.g. sauce vs sauce) gives mild reward
        shared = set(ing_cats) & set(usda_cats)
        bonus += 0.5 * len(shared)

        base = 4.0 + 4.0 * anchor + bonus
        score = base - penalty
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
