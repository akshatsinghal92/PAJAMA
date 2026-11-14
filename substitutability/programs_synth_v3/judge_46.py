import re
import math


_NOISE = {
    "diced", "chopped", "minced", "sliced", "fresh", "freshly", "to", "taste", "from", "tube",
    "finely", "roughly", "coarsely", "thinly", "thawed", "peeled", "grated", "shredded",
    "and", "or", "of", "the", "a", "an", "for", "with", "in", "about", "large", "small",
    "medium", "optional", "divided", "packed", "plus", "more", "as", "needed", "into",
    "cut", "pieces", "piece", "trimmed", "rinsed", "drained", "softened", "melted",
    "room", "temperature", "beaten", "lightly", "whole", "g", "kg", "mg", "ml", "l",
    "oz", "lb", "cup", "cups", "tbsp", "tsp", "tablespoon", "teaspoon", "pinch", "dash",
}

# USDA descriptors that signal a different preparation/form than a raw recipe item
_FORM_SHIFT = {
    "cooked", "boiled", "canned", "entree", "fried", "roasted", "baked", "braised",
    "stewed", "dehydrated", "frozen", "prepared", "breaded", "microwaved", "grilled",
    "broiled", "steamed", "rehydrated", "mix", "dinner", "meal", "soup", "salad",
    "sandwich", "imitation", "substitute", "patty", "nuggets", "casserole",
}

# USDA modifier-ish descriptors (overlap from these counts little)
_MODIFIERS = {
    "raw", "low", "fat", "nonfat", "reduced", "lean", "regular", "plain", "unsalted",
    "salt", "without", "added", "sweetened", "unsweetened", "enriched", "farmed", "wild",
    "domesticated", "commercial", "ns", "nfs", "brand", "drained", "solids", "liquids",
    "light", "dark", "red", "green", "white", "yellow", "smoked", "dried", "dry",
    "vanilla", "fresh", "ground", "whole", "frozen", "all", "varieties", "type",
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    return [_stem(t) for t in re.findall(r"[a-z]+", text.lower())]


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"\d+(\.\d+)?\s*[a-z]{0,4}\b", " ", t)
    return [w for w in _words(t) if w not in _NOISE and len(w) > 1]


def _usda_segments(text):
    segs = []
    for part in text.lower().split(","):
        toks = [w for w in _words(part) if len(w) > 1]
        if toks:
            segs.append(toks)
    return segs


def _char_grams(word, n=3):
    w = "#" + word + "#"
    return {w[i:i + n] for i in range(max(1, len(w) - n + 1))}


def _soft_match(a, b):
    """Similarity in [0,1] between two words via char-trigram Dice."""
    if a == b:
        return 1.0
    ga, gb = _char_grams(a), _char_grams(b)
    inter = len(ga & gb)
    if not ga or not gb:
        return 0.0
    d = 2.0 * inter / (len(ga) + len(gb))
    return d if d >= 0.6 else 0.0


def _best(word, pool):
    best = 0.0
    for p in pool:
        s = _soft_match(word, p)
        if s > best:
            best = s
            if best == 1.0:
                break
    return best


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not ing or not segs:
            return 0.0

        usda_flat = [w for s in segs for w in s]
        usda_set = set(usda_flat)
        primary = segs[0]

        # Positional weights for USDA tokens: earlier segments define the food
        u_weight = {}
        for idx, seg in enumerate(segs):
            w = 1.0 / (1.0 + 0.6 * idx)
            for tok in seg:
                if tok in _MODIFIERS:
                    w_tok = w * 0.3
                else:
                    w_tok = w
                u_weight[tok] = max(u_weight.get(tok, 0.0), w_tok)

        # Ingredient token weights: head noun (last token) dominates
        n = len(ing)
        i_weight = []
        for pos, tok in enumerate(ing):
            base = 0.5 + 1.5 * ((pos + 1) / n) ** 2
            if tok in _MODIFIERS:
                base *= 0.35
            i_weight.append(base)

        # Recall of ingredient content into USDA (weighted soft)
        rec_num = sum(wt * _best(tok, usda_set) for tok, wt in zip(ing, i_weight))
        rec_den = sum(i_weight) or 1.0
        recall = rec_num / rec_den

        # Precision: USDA content tokens explained by ingredient (weighted soft)
        ing_set = set(ing)
        prec_num = 0.0
        prec_den = 0.0
        for tok, wt in u_weight.items():
            if tok in _FORM_SHIFT:
                continue
            prec_den += wt
            prec_num += wt * _best(tok, ing_set)
        precision = prec_num / prec_den if prec_den else 0.0

        # Head alignment: ingredient's head noun vs USDA primary segment
        head = ing[-1]
        head_hit = _best(head, set(primary))
        if head_hit == 0.0:
            head_hit = 0.5 * _best(head, usda_set)

        # Primary segment coverage: every primary word should appear in ingredient
        prim_cov = sum(_best(p, ing_set) for p in primary) / len(primary)

        # Ordered bigram agreement (ingredient bigrams found in USDA in any order)
        bigram_bonus = 0.0
        if n >= 2:
            hits = 0
            for a, b in zip(ing, ing[1:]):
                if _best(a, usda_set) > 0 and _best(b, usda_set) > 0:
                    hits += 1
            bigram_bonus = hits / (n - 1)

        # Penalties
        ing_raw = str(ingredient).lower()
        shift_pen = 0.0
        for tok in usda_set:
            if tok in _FORM_SHIFT and tok not in ing_set and tok not in ing_raw:
                shift_pen += 1.0
        shift_pen = min(shift_pen, 3.0)

        missing_content = [t for t, wt in zip(ing, i_weight)
                           if t not in _MODIFIERS and _best(t, usda_set) == 0.0]
        miss_pen = len(missing_content)

        f = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        raw = (
            4.0 * f
            + 2.5 * head_hit
            + 1.5 * prim_cov
            + 1.0 * bigram_bonus
            - 1.3 * shift_pen
            - 1.6 * miss_pen
        )
        # squash to 0-10
        score = 10.0 / (1.0 + math.exp(-(raw - 3.5)))
        return round(score, 4)
    except Exception:
        return 0.0
