import re
import math

_NOISE = {
    "diced", "chopped", "minced", "sliced", "shredded", "grated", "crumbled", "fresh",
    "frozen", "thawed", "to", "taste", "from", "tube", "jar", "can", "canned", "of", "and",
    "or", "the", "a", "an", "with", "without", "for", "into", "in", "on", "trimmed",
    "visible", "finely", "roughly", "coarsely", "thinly", "thick", "thin", "large", "small",
    "medium", "about", "plus", "more", "optional", "divided", "peeled", "seeded", "cut",
    "pieces", "piece", "cubed", "cubes", "softened", "melted", "packed", "rinsed", "drained",
    "beaten", "room", "temperature", "halved", "quartered", "whole", "parts", "equal",
    "g", "gram", "grams", "kg", "ml", "l", "oz", "lb", "cup", "cups", "tbsp", "tsp",
    "nfs", "ns", "raw", "cooked", "choice", "select", "prime", "separable", "lean", "fat",
    "only", "salt", "added", "boiled", "type", "style", "made", "prepared", "ready", "eat",
    "ready-to-eat", "fluid", "regular", "plain", "commercial", "home", "includes", "unenriched",
    "enriched", "fried", "baked", "roasted", "grilled", "uncooked", "unprepared", "1/8",
}

_MODIFIERS = {
    "toasted", "honey", "crispy", "battered", "batter", "breakfast", "powder", "powdered",
    "ground", "dried", "dry", "sweet", "sweetened", "unsweetened", "light", "dark", "low",
    "reduced", "smoked", "salted", "unsalted", "spicy", "hot", "mild", "red", "green",
    "white", "yellow", "black", "brown", "skin", "leaves", "leaf", "half",
}

_SYNONYMS = {
    "poultry": "chicken", "confectioners": "powdered", "icing": "powdered",
    "scallion": "onion", "scallions": "onion", "cilantro": "coriander",
    "garbanzo": "chickpea", "chickpeas": "chickpea", "aubergine": "eggplant",
    "courgette": "zucchini", "prawn": "shrimp", "prawns": "shrimp",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", text)
    raw = re.findall(r"[a-z][a-z\-']*", text)
    out = []
    for w in raw:
        w = w.strip("-'")
        if not w or w in _NOISE:
            continue
        w = _SYNONYMS.get(w, w)
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

        # Ingredient: drop post-comma state.
        ing_main = ing.split(",")[0]
        ing_toks = _tokens(ing_main)
        if not ing_toks:
            ing_toks = _tokens(ing)
        if not ing_toks:
            return 0.0

        # USDA: positional weighting of comma segments (primary food first).
        segs = [s for s in usda.split(",") if s.strip()]
        usda_w = {}
        usda_seq = []
        for i, seg in enumerate(segs):
            pos_w = 1.0 / (1.0 + 0.45 * i)
            for t in _tokens(seg):
                usda_seq.append(t)
                usda_w[t] = max(usda_w.get(t, 0.0), pos_w)
        if not usda_w:
            return 0.0

        primary = set(_tokens(segs[0])) if segs else set()

        # Head noun of the ingredient = last content token (English head-final NPs).
        head = ing_toks[-1]

        # Weighted recall over ingredient tokens.
        ing_set = list(dict.fromkeys(ing_toks))
        total = 0.0
        hit = 0.0
        for t in ing_set:
            w = _weight(t) * (2.0 if t == head else 1.0)
            total += w
            if t in usda_w:
                hit += w * (0.5 + 0.5 * usda_w[t])
        recall = hit / total if total else 0.0

        # Weighted precision over USDA tokens (penalize extra food-defining words).
        utotal = 0.0
        uhit = 0.0
        ing_lookup = set(ing_set)
        for t, pw in usda_w.items():
            w = _weight(t) * pw
            utotal += w
            if t in ing_lookup:
                uhit += w
        precision = uhit / utotal if utotal else 0.0

        # Ordered bigram match.
        ib = set(zip(ing_toks, ing_toks[1:]))
        ub = set(zip(usda_seq, usda_seq[1:]))
        bigram = len(ib & ub) / len(ib) if ib else 0.0

        # Head anchoring bonus: does the head or any primary-segment token match?
        head_in_primary = 1.0 if head in primary else (0.5 if head in usda_w else 0.0)
        primary_hit = 1.0 if (primary & ing_lookup) else 0.0

        # Only-modifier overlap discount.
        shared = ing_lookup & set(usda_w)
        if shared and all(t in _MODIFIERS for t in shared):
            mod_penalty = 0.4
        else:
            mod_penalty = 1.0

        if not shared:
            return round(max(0.0, 5.0 * bigram), 3)

        f = (0.4 * recall + 0.15 * precision) / 0.55
        score = 100.0 * mod_penalty * (
            0.45 * f
            + 0.25 * head_in_primary
            + 0.20 * primary_hit
            + 0.10 * bigram
        )
        score = 100.0 / (1.0 + math.exp(-(score - 45.0) / 12.0))
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
