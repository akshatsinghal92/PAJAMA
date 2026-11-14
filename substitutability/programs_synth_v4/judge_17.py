import re

_NEUTRAL_USDA = {
    "raw", "nfs", "ns", "plain", "regular", "unprepared", "fresh", "whole",
    "all", "purpose", "commercial", "prepared", "ready", "to", "eat", "or",
    "and", "with", "without", "of", "the", "a", "in", "type", "style",
    "inch", "8", "includes", "made", "from", "added", "solids", "liquids",
    "drained", "unheated", "edible", "portion", "only", "meat", "boneless",
    "broilers", "fryers", "mature", "seeds", "100", "foods", "brand",
}

_PREP_ING = {
    "chopped", "diced", "minced", "sliced", "shelled", "peeled", "thawed",
    "trimmed", "grated", "shredded", "crushed", "rinsed", "drained",
    "halved", "quartered", "cubed", "softened", "melted", "packed",
    "finely", "roughly", "large", "small", "medium", "fresh", "about",
    "of", "a", "the", "and", "or", "to", "taste", "for", "from", "tube",
}

# Qualifiers that change taste/texture/appearance in a way a diner notices.
_NOTICEABLE = {
    "cooked", "boiled", "simmered", "roasted", "fried", "baked", "broiled",
    "grilled", "braised", "stewed", "dried", "dehydrated", "canned",
    "smoked", "cured", "pickled", "sweetened", "unsweetened", "salted",
    "unsalted", "low", "reduced", "sodium", "fat", "free", "lite", "light",
    "nonfat", "skim", "extra", "virgin", "lean", "flavored", "instant",
    "frozen", "concentrate", "powder", "powdered", "ground", "paste",
    "sauce", "juice", "syrup", "flour", "mix", "relish", "slices", "chips",
    "brown", "white", "red", "green", "black", "yellow", "wild",
    "muscadine", "concord", "coconut", "blood", "breakfast", "laver",
    "kombu", "choice", "select", "prime", "tri", "tip", "bottom",
    "separable", "high", "fructose", "whole", "grain", "vanilla",
}

_SYN = {
    "cos": "romaine", "romaine": "romaine", "hearts": "romaine",
    "wrap": "tortilla", "wraps": "tortilla", "tortillas": "tortilla",
    "frankfurter": "frankfurter", "hot": "hot", "hotdog": "frankfurter",
    "syrups": "syrup", "nuts": "nut", "nut": "nut", "grapes": "grape",
    "crackers": "cracker", "spices": "spice", "high-fructose": "highfructose",
    "seaweed": "seaweed", "lettuce": "lettuce",
}


def _stem(w):
    w = w.lower().strip("-'")
    if w in _SYN:
        return _SYN[w]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    return [t for t in re.findall(r"[a-z][a-z\-']*|\d+", text.lower()) if t]


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", s)
    parts = [p.strip() for p in s.split(",")]
    head = parts[0] if parts else ""
    tail = " ".join(parts[1:])
    return head, tail


def _split_usda(u):
    s = re.sub(r"\([^)]*\)", " ", u.lower())
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = str(ingredient)
        usda = str(usda_match)

        head, tail = _clean_ingredient(ing)
        # Tail descriptors on the ingredient that are not mere prep count as qualifiers.
        ing_core = [_stem(w) for w in _words(head) if w not in _PREP_ING and not w.isdigit()]
        ing_tail = [_stem(w) for w in _words(tail) if w not in _PREP_ING and not w.isdigit()]
        ing_all = set(ing_core) | set(ing_tail)
        if not ing_all:
            return 0.0

        usda_parts = _split_usda(usda)
        if not usda_parts:
            return 0.0
        # Brand-style entries: drop leading segments that look like manufacturer names
        # if they share nothing with the ingredient.
        usda_tokens_by_part = []
        for p in usda_parts:
            toks = [_stem(w) for w in _words(p) if not w.isdigit()]
            usda_tokens_by_part.append(toks)

        usda_all = set()
        for toks in usda_tokens_by_part:
            usda_all.update(toks)

        # 1) Identity anchor: the ingredient's head noun (last core word) must appear.
        head_noun = ing_core[-1] if ing_core else next(iter(ing_all))
        anchor = 1.0 if head_noun in usda_all else 0.0
        primary = set(usda_tokens_by_part[0])
        primary_hit = 1.0 if (primary & ing_all) else 0.0

        # 2) Coverage: how many ingredient qualifiers the USDA entry honours.
        covered = [w for w in ing_all if w in usda_all]
        coverage = len(covered) / float(len(ing_all))

        # Qualifiers the ingredient specified but USDA dropped.
        dropped = [w for w in ing_all if w not in usda_all and w != head_noun]
        dropped_noticeable = sum(1 for w in dropped if w in _NOTICEABLE)
        dropped_other = len(dropped) - dropped_noticeable

        # 3) Qualifiers USDA added that the ingredient did not imply.
        added = [w for w in usda_all if w not in ing_all and w not in _NEUTRAL_USDA]
        added_noticeable = sum(1 for w in added if w in _NOTICEABLE)
        added_other = len(added) - added_noticeable
        # Brand entries add many proper-name tokens; damp their weight.
        brandish = len(usda_parts) >= 3 and primary_hit == 0.0 and coverage >= 0.6
        if brandish:
            added_other = min(added_other, 2) * 0.3

        # 4) Specificity balance: specific ingredient -> want specific entry.
        ing_spec = len(ing_all)
        usda_spec = len([w for w in usda_all if w not in _NEUTRAL_USDA])
        gap = abs(usda_spec - ing_spec)
        balance = 1.0 / (1.0 + 0.25 * gap)

        score = 0.0
        score += 3.0 * anchor
        score += 1.0 * primary_hit
        score += 3.5 * coverage
        score += 1.5 * balance
        score -= 1.4 * dropped_noticeable
        score -= 0.7 * dropped_other
        score -= 1.1 * added_noticeable
        score -= 0.25 * added_other

        if anchor == 0.0 and coverage == 0.0:
            score = min(score, 0.5)

        score = max(0.0, min(10.0, score + 1.0))
        return round(score, 4)
    except Exception:
        return 0.0
