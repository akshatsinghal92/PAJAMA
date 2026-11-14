import re

_PREP = {
    "fresh", "frozen", "chopped", "diced", "sliced", "minced", "plain", "raw", "cooked",
    "thawed", "trimmed", "grated", "shredded", "large", "small", "medium", "whole",
    "boneless", "skinless", "dried", "ground", "finely", "roughly", "peeled", "organic",
    "of", "and", "or", "with", "the", "a", "an", "for", "to", "in", "fat", "visible",
    "lowfat", "nonfat", "reduced", "light", "unsalted", "salted", "optional", "cut",
    "pieces", "piece", "crushed", "toasted", "roasted", "baked", "steamed", "boiled",
}

_CATEGORY_HEADS = {
    "fish", "crustaceans", "mollusks", "beef", "pork", "lamb", "veal", "chicken", "turkey",
    "spices", "cereal", "cereals", "beverages", "cheese", "nuts", "seeds", "oil", "cream",
    "milk", "game", "meat", "candies", "snacks", "soup", "sauce", "bread", "vegetables",
    "fruit", "beans", "peppers", "lettuce", "squash", "cabbage", "mushrooms", "rice",
    "pasta", "flour", "sugar", "syrup", "egg", "eggs", "yogurt", "butter", "sausage",
}

_SECONDARY_HEADS = {
    "milk", "soup", "pie", "sauce", "juice", "bread", "cake", "muffin", "cookie", "cookies",
    "jam", "jelly", "yogurt", "ice", "candy", "drink", "beverage", "cereal", "bar", "bars",
    "spread", "butter", "oil", "flavored", "flavor", "filling", "dressing", "salad",
    "chips", "crackers", "pudding", "smoothie", "tea", "wine", "vinegar", "mix", "paste",
    "shortening", "patty", "nuggets", "puree", "nectar", "cocktail", "sorbet", "custard",
}


def _stem(w):
    w = w.lower()
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _words(s):
    return [_stem(t) for t in re.findall(r"[a-zA-Z]+", s or "")]


def _ingredient_core(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", s, flags=re.I)
    toks = [t for t in _words(s) if t not in _PREP and len(t) > 1]
    return toks


def _segments(usda):
    s = re.sub(r"\([^)]*\)", " ", str(usda or ""))
    return [seg.strip() for seg in s.split(",") if seg.strip()]


def judging_function(ingredient, usda_match):
    try:
        core = _ingredient_core(ingredient)
        segs = _segments(usda_match)
        if not core or not segs:
            return 0.0
        head = core[-1]
        core_set = set(core)

        seg_words = [[w for w in _words(sg) if w not in ("nfs", "raw")] for sg in segs]

        # Determine effective primary segment: skip leading category-only segment
        # if the ingredient's food is not itself that category.
        primary_idx = 0
        first = seg_words[0]
        if (len(first) == 1 and first[0] in _CATEGORY_HEADS and first[0] not in core_set
                and len(seg_words) > 1):
            primary_idx = 1

        # locate where ingredient terms appear
        hits = []
        for i, ws in enumerate(seg_words):
            for j, w in enumerate(ws):
                if w in core_set or (len(w) > 3 and any(w.startswith(c) or c.startswith(w) for c in core_set if len(c) > 3)):
                    hits.append((i, j, w))
        if not hits:
            return 5.0 if seg_words[0] and seg_words[0][0] in _CATEGORY_HEADS else 3.0

        score = 50.0
        first_seg_i = min(h[0] for h in hits)

        # Position reward: hit in effective primary segment is best
        dist = abs(first_seg_i - primary_idx)
        score += 30.0 - 12.0 * dist

        # Is the head word itself present?
        head_hits = [h for h in hits if h[2] == head or h[2].startswith(head) or head.startswith(h[2])]
        if head_hits:
            score += 10.0
            hi = min(h[0] for h in head_hits)
            if hi == primary_idx:
                score += 10.0
        else:
            score -= 15.0

        # Modifier demotion: in primary segment, ingredient word followed by a different noun
        pseg = seg_words[primary_idx] if primary_idx < len(seg_words) else []
        if pseg:
            last = pseg[-1]
            if last not in core_set and any(w in core_set for w in pseg[:-1]):
                score -= 25.0
                if last in _SECONDARY_HEADS:
                    score -= 10.0
            # primary food is a compound/secondary item the ingredient does not name
            if pseg[0] in _SECONDARY_HEADS and pseg[0] not in core_set:
                score -= 12.0
        # Ingredient asks for a secondary product but USDA's primary isn't it
        if head in _SECONDARY_HEADS and head not in set(pseg):
            score -= 10.0

        # Fraction of ingredient core covered anywhere
        all_words = set(w for ws in seg_words for w in ws)
        cov = sum(1 for c in core_set if c in all_words) / float(len(core_set))
        score += 15.0 * cov - 7.0

        # Penalize many descriptor segments that introduce mixtures
        txt = str(usda_match or "").lower()
        if " and " in txt and " and " not in str(ingredient or "").lower():
            score -= 6.0
        if "syrup" in txt or "with " in txt:
            score -= 4.0

        return max(0.0, min(100.0, round(score, 2)))
    except Exception:
        return 0.0
