import re
import math

_NOISE = {
    "g", "kg", "mg", "ml", "l", "oz", "lb", "lbs", "cup", "cups", "tbsp", "tsp",
    "tablespoon", "tablespoons", "teaspoon", "teaspoons", "gram", "grams",
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "thawed",
    "peeled", "crushed", "to", "taste", "from", "tube", "fresh", "freshly",
    "of", "the", "a", "an", "for", "with", "or", "in", "into", "about",
    "finely", "roughly", "coarsely", "thinly", "cut", "pieces", "piece",
    "large", "small", "medium", "optional", "divided", "packed", "plus",
    "nfs", "ns", "raw", "inch", "lean", "flaked", "trimmed", "rinsed", "drained",
}

_MODIFIERS = {
    "frozen", "canned", "cooked", "uncooked", "dried", "dry", "dehydrated",
    "boneless", "skinless", "regular", "light", "dark", "low", "fat", "lowfat",
    "reduced", "sodium", "added", "no", "unsalted", "salted", "sweetened",
    "unsweetened", "whole", "ground", "soft", "hard", "plain", "organic",
    "smoked", "roasted", "unroasted", "toasted", "baked", "fried", "choice",
    "select", "prime", "farmed", "wild", "shelf", "stable", "ready", "bake",
    "fry", "commercial", "prepared", "household", "blend", "style", "brand",
    "hot", "sweet", "mild", "fine", "coarse", "milkfat", "hydrogenated",
}

# conflicting attribute pairs: if ingredient says one and usda says the other
_CONFLICTS = [
    ("dark", "light"), ("vegan", "regular"), ("vegan", "mayonnaise"),
    ("salted", "unsalted"), ("sweetened", "unsweetened"),
    ("canned", "raw"), ("creamed", "raw"),
]


def _norm(tok):
    t = tok.lower()
    if len(t) > 4 and t.endswith("ies"):
        t = t[:-3] + "y"
    elif len(t) > 4 and t.endswith("oes"):
        t = t[:-2]
    elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    return t


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*%", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*[a-z]{0,3}\b", " ", text)
    raw = re.findall(r"[a-z]+", text)
    return [_norm(t) for t in raw]


def _content(tokens):
    return [t for t in tokens if t not in _NOISE and len(t) > 1]


def _trigrams(word):
    w = "#" + word + "#"
    return {w[i:i + 3] for i in range(len(w) - 2)} if len(w) >= 3 else {w}


def _soft_eq(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    inter = len(ta & tb)
    union = len(ta | tb) or 1
    j = inter / union
    return j if j >= 0.5 else 0.0


def _weight(tok):
    return 0.35 if tok in _MODIFIERS else 1.0


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usd = str(usda_match or "")
        if not ing.strip() or not usd.strip():
            return 0.0

        # ingredient: drop post-comma state
        ing_main = ing.split(",")[0]
        compound = bool(re.search(r"\band\b|&", ing_main.lower()))
        ing_tok = _content(_tokens(ing_main))
        if not ing_tok:
            ing_tok = _content(_tokens(ing))
        if not ing_tok:
            return 0.0

        # usda: segment-position weighting (primary segment heavier)
        segs = [s for s in usd.split(",") if s.strip()]
        usd_items = []  # (token, position weight)
        for si, seg in enumerate(segs):
            pw = 1.0 if si == 0 else max(0.45, 0.9 - 0.12 * (si - 1))
            for t in _content(_tokens(seg)):
                usd_items.append((t, pw))
        if not usd_items:
            return 0.0
        usd_set = {t for t, _ in usd_items}

        # head noun: last content non-modifier token of ingredient
        heads = [t for t in ing_tok if t not in _MODIFIERS]
        head = heads[-1] if heads else ing_tok[-1]

        # greedy soft alignment ingredient -> usda
        used = set()
        gained = 0.0
        total = 0.0
        head_hit = 0.0
        for t in ing_tok:
            w = _weight(t)
            total += w
            best, best_j = 0.0, -1
            for j, (u, pw) in enumerate(usd_items):
                if j in used:
                    continue
                s = _soft_eq(t, u) * pw
                if s > best:
                    best, best_j = s, j
            if best_j >= 0 and best > 0:
                used.add(best_j)
                gained += w * best
                if t == head:
                    head_hit = max(head_hit, best)
        recall = gained / total if total else 0.0

        # precision over usda food-defining tokens
        u_core = [(u, pw) for j, (u, pw) in enumerate(usd_items) if u not in _MODIFIERS]
        u_core_tot = sum(pw for _, pw in u_core) or 1.0
        u_core_hit = 0.0
        for u, pw in u_core:
            if any(_soft_eq(u, t) > 0 for t in ing_tok):
                u_core_hit += pw
        precision = u_core_hit / u_core_tot

        # primary food check: does the first USDA segment's core appear in ingredient?
        prim = [t for t in _content(_tokens(segs[0])) if t not in _MODIFIERS] if segs else []
        prim_hit = 1.0 if (prim and any(_soft_eq(p, t) > 0 for p in prim for t in ing_tok)) else 0.0

        # F-like blend, recall weighted higher
        if recall + precision > 0:
            f = (1.5 * recall * precision) / (0.5 * precision + recall + 1e-9)
        else:
            f = 0.0

        score = 55.0 * f + 20.0 * head_hit + 15.0 * prim_hit + 10.0 * recall

        # conflicts
        ing_set = set(ing_tok) | set(_tokens(ing))
        for a, b in _CONFLICTS:
            if (a in ing_set and b in usd_set and a not in usd_set) or \
               (b in ing_set and a in usd_set and b not in usd_set):
                score -= 18.0

        # unmatched food-defining ingredient tokens
        unmatched = [t for t in heads if not any(_soft_eq(t, u) > 0 for u in usd_set)]
        score -= 9.0 * len(unmatched)

        if compound:
            score -= 15.0

        if head_hit == 0:
            score *= 0.6

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
