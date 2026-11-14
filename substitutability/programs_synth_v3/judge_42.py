import re
import math

_NOISE = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "ounce", "ounces", "lb", "lbs",
    "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons", "teaspoon", "teaspoons",
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "crushed", "peeled",
    "thawed", "softened", "melted", "beaten", "divided", "optional", "taste", "to",
    "from", "tube", "jar", "can", "canned", "fresh", "freshly", "large", "small", "medium",
    "finely", "roughly", "coarsely", "thinly", "and", "or", "of", "the", "a", "an", "for",
    "with", "into", "plus", "more", "about", "approx", "pieces", "piece", "cut", "trimmed",
    "rinsed", "drained", "packed", "loosely", "lightly", "room", "temperature", "whole",
    "ns", "nfs", "as", "ingredient", "in", "made", "type", "prepared", "brand", "inc",
    "other", "products", "by", "variety", "meats", "domesticated",
}

# Words that describe state/form rather than identity: overlap on them counts little.
_MODIFIERS = {
    "raw", "cooked", "boiled", "braised", "roasted", "baked", "fried", "grilled", "steamed",
    "frozen", "dried", "dry", "uncooked", "unprepared", "ground", "powder", "nonfat",
    "lowfat", "fat", "low", "reduced", "free", "sodium", "salted", "unsalted", "sweetened",
    "unsweetened", "plain", "regular", "red", "green", "white", "black", "yellow", "brown",
    "light", "dark", "organic", "natural", "commercial", "enriched", "skinless", "boneless",
    "skin", "bone", "lean", "only", "added", "without", "all", "purpose", "style",
    "simmered", "stewed", "microwaved", "heated", "ready", "eat", "solids", "liquids",
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", text)
    raw = re.findall(r"[a-z]+", text)
    out = []
    for w in raw:
        s = _stem(w)
        if w in _NOISE or s in _NOISE or len(s) < 2:
            continue
        out.append(s)
    return out


def _weight(tok):
    return 0.25 if tok in _MODIFIERS else 1.0


def _fuzzy_eq(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.8
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = _tokens(ingredient)
        usda_full = _tokens(usda_match)
        if not ing or not usda_full:
            return 0.0

        # USDA primary segment = text before first comma (food identity head)
        head_seg = _tokens(str(usda_match).split(",")[0])
        head_set = set(head_seg)

        ing_set = list(dict.fromkeys(ing))
        usda_set = list(dict.fromkeys(usda_full))

        # Weighted soft matching: each ingredient token finds best USDA partner
        matched_w = 0.0
        total_w = 0.0
        head_hit = 0.0
        for t in ing_set:
            w = _weight(t)
            total_w += w
            best = 0.0
            best_u = None
            for u in usda_set:
                f = _fuzzy_eq(t, u)
                if f > best:
                    best, best_u = f, u
            matched_w += w * best
            if best_u is not None and best_u in head_set and t not in _MODIFIERS:
                head_hit = max(head_hit, best)
        recall = matched_w / total_w if total_w else 0.0

        # Precision over USDA content tokens, but only core (non-modifier) ones penalize
        u_core = [u for u in usda_set if u not in _MODIFIERS]
        if u_core:
            covered = sum(max(_fuzzy_eq(u, t) for t in ing_set) for u in u_core)
            precision = covered / len(u_core)
        else:
            precision = 0.5

        # Food-defining word: last core token of the ingredient (English head noun)
        ing_core = [t for t in ing if t not in _MODIFIERS]
        head_noun = ing_core[-1] if ing_core else ing[-1]
        head_noun_found = max(_fuzzy_eq(head_noun, u) for u in usda_set)

        # Ordered bigram agreement (order-insensitive pair since USDA inverts order)
        def pairs(seq):
            return {frozenset((seq[i], seq[i + 1])) for i in range(len(seq) - 1)
                    if seq[i] != seq[i + 1]}
        ip, up = pairs(ing_core), set()
        uc = [u for u in usda_full if u not in _MODIFIERS]
        for i in range(len(uc)):
            for j in range(i + 1, min(len(uc), i + 3)):
                if uc[i] != uc[j]:
                    up.add(frozenset((uc[i], uc[j])))
        bigram = (len(ip & up) / len(ip)) if ip else (1.0 if head_noun_found else 0.0)

        # Core modifier conflict: ingredient core token not present while USDA has
        # its own unmatched core tokens (e.g. "coconut sugar" vs "sugar, brown")
        unmatched_ing_core = sum(1 for t in set(ing_core)
                                 if max(_fuzzy_eq(t, u) for u in usda_set) == 0)
        conflict = min(unmatched_ing_core, 3) / 3.0

        score = (
            3.5 * recall
            + 1.5 * precision
            + 2.5 * head_noun_found
            + 1.0 * head_hit
            + 1.5 * bigram
            - 2.5 * conflict
        )
        if recall == 0:
            score = min(score, 0.5)
        score = max(0.0, min(10.0, score))
        return round(score, 4)
    except Exception:
        return 0.0
