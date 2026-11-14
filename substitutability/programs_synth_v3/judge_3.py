import re


_MODIFIERS = {
    "fresh", "frozen", "thawed", "chopped", "diced", "minced", "sliced", "grated",
    "ground", "whole", "large", "small", "medium", "raw", "cooked", "boiled", "fried",
    "roasted", "toasted", "smoked", "pickled", "canned", "dried", "drained", "leftover",
    "peeled", "skin", "on", "with", "without", "and", "or", "of", "the", "a", "an",
    "to", "from", "for", "in", "baked", "steamed", "uncooked", "unprepared", "prepared",
    "plain", "organic", "finely", "roughly", "coarsely", "lightly", "extra", "virgin",
    "high", "low", "yellow", "red", "green", "white", "black", "brown", "tube", "jar",
    "package", "packaged", "store", "bought", "homemade", "salted", "unsalted",
    "sweetened", "unsweetened", "all", "purpose", "enriched", "regular", "style",
    "type", "variety", "varieties", "by", "products", "meats", "broilers", "fryers",
    "ns", "nfs", "as", "ingredient", "solids", "liquids", "heated", "commercial",
}

# Generic category words that often lead USDA descriptions but are not the food itself.
_CATEGORY = {"fish", "spices", "oil", "beverages", "cheese", "nuts", "seeds",
             "vegetables", "fruit", "cereals", "snacks", "soup", "sauce", "beef",
             "pork", "lamb", "chicken", "turkey", "candies", "alcoholic"}


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("oes", "ches", "shes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|grams?)\b", " ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    return [_singular(t) for t in text.split() if t]


def _ingredient_core(ingredient):
    main = ingredient.split(",")[0]
    toks = [t for t in _tokens(main) if t not in _MODIFIERS]
    if not toks:
        toks = _tokens(main)
    return toks


def _usda_segments(usda):
    segs = []
    for part in usda.split(","):
        toks = [t for t in _tokens(part) if t not in _MODIFIERS]
        if toks:
            segs.append(toks)
    return segs


def _trigrams(word):
    w = "^" + word + "$"
    return {w[i:i + 3] for i in range(max(1, len(w) - 2))}


def _word_sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _ingredient_core(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not ing or not segs:
            return 0.0

        head = ing[-1]  # head noun is usually the last word of the noun phrase
        quals = ing[:-1]

        # Position weights: early USDA segments carry the primary food identity.
        best_head = 0.0
        best_pos = len(segs)
        for idx, seg in enumerate(segs):
            pos_w = 1.0 / (1.0 + 0.35 * idx)
            for w in seg:
                s = _word_sim(head, w)
                # Generic category word matching contributes less unless head itself is generic.
                if w in _CATEGORY and head not in _CATEGORY:
                    s *= 0.5
                s *= pos_w
                if s > best_head:
                    best_head = s
                    best_pos = idx

        # Qualifier coverage: do the ingredient's specifying words appear in USDA?
        usda_words = [w for seg in segs for w in seg]
        if quals:
            qcov = sum(max(_word_sim(q, w) for w in usda_words) for q in quals) / len(quals)
        else:
            qcov = 1.0

        # Primary-food check: does the first USDA segment relate to the ingredient at all?
        first_seg = segs[0]
        primary = max(_word_sim(t, w) for t in ing for w in first_seg)

        # Penalize when the USDA primary food is a different concrete food than our head.
        conflict = 0.0
        if primary < 0.3 and best_head < 0.6:
            conflict = 1.0

        score = 10.0 * (0.55 * best_head + 0.2 * qcov + 0.25 * primary) - 3.0 * conflict
        if best_pos > 2:
            score -= 1.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
