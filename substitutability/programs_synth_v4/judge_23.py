import re
import math

_NOISE = {
    "diced", "chopped", "sliced", "minced", "cubed", "grated", "shredded", "crushed",
    "peeled", "trimmed", "thawed", "divided", "garnish", "for", "to", "taste", "from",
    "tube", "fresh", "ripe", "plain", "about", "optional", "the", "a", "an", "of",
    "and", "or", "with", "in", "chunks", "pieces", "piece", "large", "small", "medium",
    "finely", "roughly", "thinly", "cut", "into", "softened", "melted", "packed",
    "whole", "some", "few", "g", "kg", "mg", "ml", "l", "oz", "lb", "cup", "cups",
    "tbsp", "tsp", "pinch", "dash", "serving", "raw", "uncooked", "nfs", "ns",
    "prepared", "commercial", "regular", "type",
}

# Tokens that, if present on only one side, signal a different food form.
_FORM_WORDS = {
    "juice", "oil", "leaves", "leaf", "frozen", "dried", "powder", "flour", "starch",
    "syrup", "sauce", "soup", "crackers", "cracker", "souffle", "paste", "extract",
    "seeds", "seed", "pickled", "smoked", "canned", "liver", "neck", "giblets",
    "butter", "milk", "cream", "chips", "candy", "bar", "pie", "cake", "drink",
    "beverage", "vegetables", "mountain", "turbinado", "granulated", "brown",
}

# Pure modifiers: overlap on these alone is weak evidence.
_MODIFIERS = {
    "sweet", "red", "green", "white", "black", "dark", "light", "lite", "lowfat",
    "nonfat", "fat", "free", "reduced", "low", "sodium", "salted", "unsalted",
    "cooked", "boiled", "baked", "fried", "roasted", "simmered", "steamed", "yellow",
    "fluid", "vanilla", "chocolate", "original", "flavored", "genuine", "boneless",
    "lean", "separable", "meat", "only", "added", "without", "100", "fryers",
    "broilers", "fresh", "prepackaged", "deli",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
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
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    return t


def _tokens(text):
    raw = re.findall(r"[a-z]+|\d+", text.lower())
    return [_stem(w) for w in raw if w not in _NOISE and len(w) > 1]


def _bigrams(seq):
    return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}


def _char_sim(a, b):
    # Dice coefficient on character trigrams, for near-matches like hazelnut/hazelnuts.
    def grams(s):
        s = "#" + s + "#"
        return {s[i:i + 3] for i in range(max(1, len(s) - 2))}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_toks = _tokens(_clean_ingredient(ing))
        if not ing_toks:
            return 0.0

        # USDA: weight each token by the comma segment it appears in.
        segments = [s for s in usda.lower().split(",") if s.strip()]
        usda_weights = {}
        usda_seq = []
        for idx, seg in enumerate(segments):
            w = 1.0 / (1.0 + 0.45 * idx)
            for tok in _tokens(seg):
                usda_seq.append(tok)
                if tok not in usda_weights or usda_weights[tok] < w:
                    usda_weights[tok] = w
        if not usda_weights:
            return 0.0

        # Head noun of the ingredient: last content token (English head-final).
        head = ing_toks[-1]

        def tok_weight(t):
            return 0.35 if t in _MODIFIERS else 1.0

        # Soft alignment: each ingredient token finds its best USDA counterpart.
        matched_mass = 0.0
        total_mass = 0.0
        matched_set = set()
        head_hit = 0.0
        for t in ing_toks:
            tw = tok_weight(t) * (1.6 if t == head else 1.0)
            total_mass += tw
            best, best_u = 0.0, None
            for u, uw in usda_weights.items():
                s = 1.0 if u == t else _char_sim(t, u)
                if s < 0.6:
                    continue
                s *= uw
                if s > best:
                    best, best_u = s, u
            if best_u is not None:
                matched_set.add(best_u)
                matched_mass += tw * best
                if t == head:
                    head_hit = best
        recall = matched_mass / total_mass if total_mass else 0.0

        # Precision: how much of the USDA food-defining content was covered.
        u_mass = sum(tok_weight(u) * w for u, w in usda_weights.items())
        u_hit = sum(tok_weight(u) * w for u, w in usda_weights.items() if u in matched_set)
        precision = u_hit / u_mass if u_mass else 0.0

        # Primary-segment check: the USDA lead food must be named by the ingredient.
        primary = _tokens(segments[0]) if segments else []
        primary_core = [p for p in primary if p not in _MODIFIERS] or primary
        ing_set = set(ing_toks)
        prim_cov = 0.0
        if primary_core:
            prim_cov = sum(
                1.0 for p in primary_core
                if p in ing_set or any(_char_sim(p, x) >= 0.75 for x in ing_set)
            ) / len(primary_core)

        # Ordered bigram bonus.
        bg_i, bg_u = _bigrams(ing_toks), _bigrams(usda_seq)
        bigram = len(bg_i & bg_u) / len(bg_i) if bg_i else 0.0

        # Form-word mismatch penalty (juice vs fruit, oil vs nut, leaves vs fruit).
        u_set = set(usda_weights)
        form_only_u = {w for w in u_set if w in _FORM_WORDS and w not in ing_set}
        form_only_i = {w for w in ing_set if w in _FORM_WORDS and w not in u_set}
        form_pen = 0.0
        for w in form_only_u:
            form_pen += 0.22 * usda_weights[w]
        form_pen += 0.18 * len(form_only_i)
        form_pen = min(form_pen, 0.6)

        # Combine: F-beta weighted to recall, plus head and primary terms.
        beta2 = 2.0
        if recall + precision > 0:
            fbeta = (1 + beta2) * recall * precision / (beta2 * precision + recall)
        else:
            fbeta = 0.0

        raw = (0.38 * fbeta + 0.27 * head_hit + 0.22 * prim_cov
               + 0.13 * bigram) - form_pen
        if head_hit == 0.0 and prim_cov == 0.0:
            raw *= 0.3

        raw = max(0.0, min(1.0, raw))
        # Smooth squashing for separation.
        score = 100.0 / (1.0 + math.exp(-9.0 * (raw - 0.45)))
        return round(score, 4)
    except Exception:
        return 0.0
