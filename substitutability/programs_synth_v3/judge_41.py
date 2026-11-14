import re

_UNITS = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "ounce", "ounces", "lb", "lbs",
    "pound", "pounds", "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pinch", "dash", "clove", "cloves", "piece", "pieces",
}

_NOISE = {
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "crushed", "peeled",
    "fresh", "freshly", "finely", "roughly", "coarsely", "thinly", "thawed", "melted",
    "softened", "to", "taste", "from", "tube", "jar", "can", "of", "and", "with", "or",
    "the", "a", "an", "for", "in", "into", "about", "approx", "large", "small", "medium",
    "whole", "halved", "quartered", "cubed", "trimmed", "rinsed", "drained", "soaked",
    "overnight", "optional", "packed", "loosely", "divided", "room", "temperature",
    "baked", "roasted", "boiled", "steamed", "fried", "grilled", "braised", "cooked",
    "uncooked", "raw", "frozen", "canned", "dried", "dry", "prepared",
}

# Descriptor words common in USDA entries: shared overlap on these is weak evidence.
_MODIFIERS = {
    "raw", "cooked", "boiled", "baked", "roasted", "braised", "dry", "heat", "frozen",
    "canned", "unprepared", "prepared", "mixed", "species", "mature", "seeds",
    "variety", "meats", "products", "by", "nonfat", "lowfat", "fat", "reduced",
    "unsweetened", "sweetened", "plain", "salted", "unsalted", "without", "with",
    "regular", "commercial", "ground", "whole", "red", "black", "white", "green",
    "yellow", "condensed", "solids", "liquids", "drained", "moisture", "enriched",
    "fresh", "uncooked", "skin", "only", "lean", "meat", "style", "type", "added",
}


def _stem(tok):
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("oes"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("es") and tok[-3] in "sxz":
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _clean_ingredient(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.split(",")[0]
    text = re.sub(r"\b\d+(\.\d+)?\s*[a-z]*\b", " ", text)
    toks = re.findall(r"[a-z]+", text)
    out = []
    for t in toks:
        if t in _UNITS or t in _NOISE or len(t) < 2:
            continue
        out.append(_stem(t))
    return out


def _parse_usda(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    segments = [s.strip() for s in text.split(",") if s.strip()]
    toks = []
    for idx, seg in enumerate(segments):
        for t in re.findall(r"[a-z]+", seg):
            if t in _UNITS or len(t) < 2 or t in ("of", "and", "the", "a", "an", "in", "or"):
                continue
            # segment position weighting: primary food first
            toks.append((_stem(t), idx))
    return toks


def _weight(tok):
    return 0.3 if tok in _MODIFIERS else 1.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        usda = _parse_usda(str(usda_match))
        if not ing or not usda:
            return 0.0

        ing_set = set(ing)
        usda_set = set(t for t, _ in usda)
        usda_pos = {}
        for t, idx in usda:
            usda_pos.setdefault(t, idx)

        # Weighted recall: how much of the ingredient's food-defining mass is covered.
        ing_mass = sum(_weight(t) for t in ing_set)
        covered = sum(_weight(t) for t in ing_set if t in usda_set)
        recall = covered / ing_mass if ing_mass else 0.0

        # Weighted Jaccard over both sets.
        union = ing_set | usda_set
        inter = ing_set & usda_set
        u_mass = sum(_weight(t) for t in union)
        jacc = sum(_weight(t) for t in inter) / u_mass if u_mass else 0.0

        # Head-noun match: the ingredient head (last content word) vs USDA primary segment.
        head = ing[-1]
        primary = set(t for t, i in usda if i == 0)
        head_bonus = 0.0
        if head in primary:
            head_bonus = 1.0
        elif head in usda_set:
            head_bonus = 0.6
        elif any(t in primary for t in ing_set if _weight(t) == 1.0):
            head_bonus = 0.35

        # Ordered bigram match on content tokens.
        usda_seq = [t for t, _ in usda]
        ing_bi = set(zip(ing, ing[1:]))
        usda_bi = set(zip(usda_seq, usda_seq[1:])) | set(zip(usda_seq[1:], usda_seq))
        bigram = (len(ing_bi & usda_bi) / len(ing_bi)) if ing_bi else (1.0 if head in usda_set else 0.0)

        # Penalty if overlap is purely modifiers.
        strong_inter = [t for t in inter if _weight(t) == 1.0]
        if inter and not strong_inter:
            recall *= 0.3
            jacc *= 0.3

        # Penalty for ingredient content words that are entirely missing (unmatched food words).
        missing_strong = [t for t in ing_set if _weight(t) == 1.0 and t not in usda_set]
        miss_pen = 0.12 * len(missing_strong)

        score = 4.5 * recall + 1.5 * jacc + 3.0 * head_bonus + 1.0 * bigram - miss_pen
        if not inter:
            score = min(score, 1.0)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
