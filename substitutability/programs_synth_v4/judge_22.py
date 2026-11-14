import re

_NOISE = {
    "diced", "chopped", "minced", "sliced", "shredded", "grated", "crumbled", "flaked",
    "optional", "taste", "to", "from", "tube", "fresh", "freshly", "finely", "roughly",
    "thinly", "thawed", "drained", "rinsed", "peeled", "trimmed", "cut", "into", "pieces",
    "of", "and", "or", "the", "a", "an", "with", "for", "about", "large", "small", "medium",
    "nfs", "ns", "as", "eaten", "made", "type", "style", "pieces", "piece", "whole",
}
_MODIFIERS = {
    "raw", "cooked", "frozen", "canned", "smoked", "boiled", "braised", "baked", "fried",
    "roasted", "grilled", "uncooked", "dried", "dry", "ground", "lean", "fat", "nonfat",
    "lowfat", "regular", "plain", "sweetened", "unsweetened", "salted", "unsalted",
    "simmered", "stewed", "solids", "liquids", "only", "meat", "separable", "imported",
    "prepared", "condensed", "powdered", "light", "reduced", "broiled", "pan",
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


def _tokens(text, strip_amount):
    text = str(text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    if strip_amount:
        text = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|cups?|tbsp|tsp)?\b", " ", text)
    text = re.sub(r"\d+%?", " ", text)
    words = re.findall(r"[a-z]+", text)
    return [_stem(w) for w in words if w not in _NOISE and len(w) > 1]


def _ingredient_core(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    head = s.split(",")[0]
    return _tokens(head, True), _tokens(s, True)


def _weight(tok):
    return 0.35 if tok in _MODIFIERS else 1.0


def judging_function(ingredient, usda_match):
    try:
        core, full = _ingredient_core(ingredient)
        if not core:
            core = full
        usda_parts = [p for p in str(usda_match or "").split(",") if p.strip()]
        if not core or not usda_parts:
            return 0.0
        usda_all = _tokens(usda_match, False)
        if not usda_all:
            return 0.0
        primary = _tokens(usda_parts[0], False)
        usda_set = set(usda_all)
        full_set = set(full)

        # 1. Weighted recall: how much of the ingredient's food words appear in the USDA text
        rec_num = sum(_weight(t) for t in set(core) if t in usda_set)
        rec_den = sum(_weight(t) for t in set(core)) or 1.0
        recall = rec_num / rec_den

        # 2. Weighted precision over the first three USDA segments (the food-defining part)
        lead = []
        for p in usda_parts[:3]:
            lead.extend(_tokens(p, False))
        lead_set = set(lead) or usda_set
        pre_num = sum(_weight(t) for t in lead_set if t in full_set)
        pre_den = sum(_weight(t) for t in lead_set) or 1.0
        precision = pre_num / pre_den

        # 3. Head-noun check: last content token of ingredient core is usually the food name
        content_core = [t for t in core if t not in _MODIFIERS] or core
        head = content_core[-1]
        head_hit = 1.0 if head in usda_set else 0.0
        primary_hit = 1.0 if (head in set(primary) or set(primary) & set(content_core)) else 0.0

        # 4. Order-insensitive bigram pairs (handles "beef and pork" vs "pork and beef")
        def pairs(seq):
            return {frozenset((seq[i], seq[i + 1])) for i in range(len(seq) - 1)}
        cp, up = pairs(content_core), pairs([t for t in usda_all if t not in _MODIFIERS])
        bigram = len(cp & up) / len(cp) if cp else head_hit

        # 5. Modifier-only overlap discount
        content_overlap = set(content_core) & usda_set
        if not content_overlap:
            recall *= 0.3
            precision *= 0.3

        # 6. Extra content in USDA's primary that's absent from ingredient (different food)
        extra = [t for t in set(primary) if t not in full_set and t not in _MODIFIERS]
        extra_pen = min(0.3, 0.15 * len(extra))

        score = (
            3.0 * recall
            + 2.0 * precision
            + 2.5 * head_hit
            + 1.0 * primary_hit
            + 1.5 * bigram
            - 2.0 * extra_pen
        )
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
