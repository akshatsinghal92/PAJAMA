import re
import math

_NOISE = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "lb", "lbs", "cup", "cups", "tbsp", "tsp",
    "tablespoon", "tablespoons", "teaspoon", "teaspoons", "pinch", "dash", "of", "and", "or", "a",
    "an", "the", "to", "taste", "for", "with", "from", "tube", "jar", "can", "pack", "package",
    "diced", "chopped", "minced", "sliced", "fresh", "freshly", "finely", "roughly", "coarsely",
    "thawed", "peeled", "trimmed", "grated", "shredded", "crushed", "plain", "large", "small",
    "medium", "whole", "about", "approx", "optional", "cut", "into", "pieces", "piece", "halved",
    "quartered", "rinsed", "drained", "washed", "cubed", "julienned", "torn", "ripe", "good",
    "quality", "nfs", "ns", "raw", "uncooked", "mixed", "species", "imported", "domestic",
    "may", "contain", "additives", "retain", "moisture", "as", "purchased", "in", "on",
}

# USDA descriptors that signal a different form/preparation than an unqualified ingredient.
_FORM_SHIFT = {
    "canned", "frozen", "syrup", "dried", "dehydrated", "powder", "powdered", "fried", "breaded",
    "sweetened", "juice", "concentrate", "pickled", "smoked", "cured", "instant", "patty",
    "patties", "sauce", "soup", "baby", "pudding", "candied", "salted", "roasted", "cooked",
    "boiled", "baked", "stewed", "light", "heavy", "solids", "liquids", "flavored", "imitation",
}

# Part/organ words: if the ingredient names one, the USDA entry must too.
_PARTS = {
    "leaves", "leaf", "bone", "bones", "skin", "seeds", "seed", "kidney", "kidneys", "liver",
    "heart", "tongue", "stems", "stem", "roots", "root", "peel", "zest", "juice", "oil", "flour",
    "paste", "broth", "stock", "fat", "wing", "wings", "thigh", "thighs", "breast", "breasts",
    "tofu", "sprouts", "greens", "flowers", "blossoms", "neck", "feet", "tail",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and w[-3] in "sxz":
                return w[:-2]
            if suf == "s" and not w.endswith("ss"):
                return w[:-1]
    return w


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"\d+(\.\d+)?\s*[a-z]{0,4}\b", " ", t)
    return [w for w in re.findall(r"[a-z]+", t)]


def _usda_segments(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    return [re.findall(r"[a-z]+", seg) for seg in t.split(",") if seg.strip()]


def _trigrams(w):
    p = "#" + w + "#"
    return {p[i:i + 3] for i in range(len(p) - 2)} if len(p) >= 3 else {p}


def _sim(a, b):
    if a == b:
        return 1.0
    if _stem(a) == _stem(b):
        return 0.95
    ta, tb = _trigrams(a), _trigrams(b)
    d = 2.0 * len(ta & tb) / (len(ta) + len(tb))
    return d if d >= 0.6 else 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        raw_ing = _clean_ingredient(str(ingredient))
        ing = [w for w in raw_ing if w not in _NOISE and len(w) > 1]
        segs = _usda_segments(str(usda_match))
        if not ing or not segs:
            return 0.0

        # Positional weights over USDA segments: primary food weighs most.
        usda_tokens = []
        for idx, seg in enumerate(segs):
            seg_w = 1.0 / (1.0 + 0.45 * idx)
            for w in seg:
                if w in _NOISE or len(w) < 2:
                    continue
                usda_tokens.append((w, seg_w))
        if not usda_tokens:
            return 0.0

        # Head noun = last content token of ingredient; it carries the most weight.
        n = len(ing)
        ing_weights = [0.6 + 0.4 * (i + 1) / n for i in range(n)]
        ing_weights[-1] = 1.6
        for i, w in enumerate(ing):
            if w in _PARTS:
                ing_weights[i] = max(ing_weights[i], 1.4)

        # Greedy soft alignment: each ingredient token picks the best USDA token.
        covered = 0.0
        total = sum(ing_weights)
        used = set()
        head_hit = 0.0
        for i, w in enumerate(ing):
            best, best_j = 0.0, -1
            for j, (u, sw) in enumerate(usda_tokens):
                s = _sim(w, u) * (0.55 + 0.45 * sw)
                if s > best:
                    best, best_j = s, j
            if best_j >= 0:
                used.add(best_j)
            covered += ing_weights[i] * best
            if i == n - 1:
                head_hit = best
        recall = covered / total

        # Precision side: how much of the USDA content is explained by the ingredient,
        # counting only food-defining tokens (form-shift words handled separately).
        usda_food = [(j, u, sw) for j, (u, sw) in enumerate(usda_tokens) if u not in _FORM_SHIFT]
        food_mass = sum(sw for _, _, sw in usda_food) or 1.0
        explained = sum(sw for j, _, sw in usda_food if j in used)
        precision = explained / food_mass

        # Primary-segment check: does the first USDA segment name an ingredient token?
        primary = [w for w in segs[0] if w not in _NOISE]
        primary_hit = 0.0
        for p in primary:
            for w in ing:
                primary_hit = max(primary_hit, _sim(p, w))

        # Penalties.
        ing_set = {_stem(w) for w in raw_ing}
        shift = sum(1 for u, _ in usda_tokens if u in _FORM_SHIFT and _stem(u) not in ing_set)
        shift_pen = 1.0 - math.exp(-0.55 * shift)

        usda_stems = {_stem(u) for u, _ in usda_tokens}
        missing_parts = sum(1 for w in ing if w in _PARTS and _stem(w) not in usda_stems)
        part_pen = min(1.0, 0.6 * missing_parts)

        unmatched = sum(1 for w in ing if max(_sim(w, u) for u, _ in usda_tokens) == 0.0)
        extra_pen = min(1.0, 0.25 * unmatched)

        if recall + precision > 0:
            f = (1.25 * recall * precision) / (0.25 * precision + recall + 1e-9)
        else:
            f = 0.0

        score = (
            45.0 * f
            + 20.0 * head_hit
            + 15.0 * primary_hit
            + 20.0 * recall
        )
        score *= (1.0 - 0.45 * shift_pen)
        score *= (1.0 - 0.55 * part_pen)
        score *= (1.0 - 0.4 * extra_pen)
        return round(max(0.0, min(100.0, score)), 4)
    except Exception:
        return 0.0
