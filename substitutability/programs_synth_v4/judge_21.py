import re

_NOISE = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "lb", "lbs", "cup", "cups", "tbsp", "tsp",
    "tablespoon", "tablespoons", "teaspoon", "teaspoons", "pinch", "dash", "piece", "pieces",
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "crushed", "peeled", "thawed",
    "finely", "roughly", "coarsely", "thinly", "fresh", "freshly", "to", "taste", "from", "tube",
    "jar", "can", "package", "of", "and", "or", "with", "the", "a", "an", "for", "in", "made",
    "nfs", "ns", "as", "to", "about", "large", "small", "medium", "optional", "divided", "packed",
    "regular", "type", "style", "prepared", "plus", "more", "uncooked", "added",
}

_MODIFIERS = {
    "raw", "cooked", "frozen", "canned", "dried", "dry", "roasted", "smoked", "boiled", "baked",
    "fried", "unsalted", "salted", "sweet", "sweetened", "unsweetened", "white", "red", "green",
    "yellow", "black", "dark", "light", "fat", "free", "low", "non", "nonfat", "reduced", "whole",
    "ground", "powder", "powdered", "fluid", "plain", "commercial", "fresh", "hot", "cold",
    "lean", "skin", "meat", "boneless", "skinless", "fortified", "enriched", "solids", "liquids",
    "drained", "heated", "high", "natural", "organic", "vanilla", "salad", "cooking",
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
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*[a-z]{0,4}\b", " ", text)
    words = re.findall(r"[a-z]+", text)
    out = []
    for w in words:
        if w in _NOISE or len(w) < 2:
            continue
        out.append(_stem(w))
    return out


def _weight(tok):
    return 0.35 if tok in _MODIFIERS else 1.0


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        # Ingredient: keep pre-comma core heavier, post-comma state lighter
        ing_parts = ing.split(",", 1)
        ing_core = _tokens(ing_parts[0])
        ing_tail = _tokens(ing_parts[1]) if len(ing_parts) > 1 else []
        usda_segs = [s for s in usda.split(",")]
        usda_toks = []
        usda_primary = set(_tokens(usda_segs[0])) if usda_segs else set()
        for s in usda_segs:
            usda_toks.extend(_tokens(s))
        if not ing_core and not ing_tail:
            return 0.0
        if not usda_toks:
            return 0.0

        ing_w = {}
        for t in ing_core:
            ing_w[t] = max(ing_w.get(t, 0), _weight(t))
        for t in ing_tail:
            ing_w[t] = max(ing_w.get(t, 0), 0.5 * _weight(t))
        usda_w = {}
        for t in usda_toks:
            usda_w[t] = max(usda_w.get(t, 0), _weight(t))

        shared = set(ing_w) & set(usda_w)
        inter = sum(min(ing_w[t], usda_w[t]) for t in shared)
        union = sum(max(ing_w.get(t, 0), usda_w.get(t, 0)) for t in set(ing_w) | set(usda_w))
        jacc = inter / union if union else 0.0
        recall = inter / sum(ing_w.values()) if ing_w else 0.0

        # Head noun: last content (non-modifier) token of ingredient core
        heads = [t for t in ing_core if t not in _MODIFIERS] or ing_core
        head = heads[-1] if heads else None
        head_bonus = 0.0
        if head and head in usda_w:
            head_bonus = 1.0 if head in usda_primary else 0.7

        # Primary-segment content hit
        core_content = [t for t in ing_core if t not in _MODIFIERS]
        prim_hit = 0.0
        if core_content:
            prim_hit = sum(1 for t in core_content if t in usda_primary) / len(core_content)

        # Ordered bigram match
        def bigrams(seq):
            return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}
        bi_i = bigrams(ing_core)
        bi_u = bigrams(usda_toks) | {(b, a) for a, b in bigrams(usda_toks)}
        bi = len(bi_i & bi_u) / len(bi_i) if bi_i else 0.0

        content_shared = [t for t in shared if t not in _MODIFIERS]
        if not content_shared:
            # overlap only from modifiers (or none) is heavily discounted
            return round(10.0 * min(0.15, 0.3 * jacc), 4)

        score = 3.0 * recall + 2.0 * jacc + 2.5 * head_bonus + 1.5 * prim_hit + 1.0 * bi
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
