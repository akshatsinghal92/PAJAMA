import re

_PREP = {
    "fresh", "frozen", "thawed", "chopped", "diced", "minced", "sliced", "toasted",
    "warmed", "sifted", "optional", "cooked", "raw", "smoked", "dried", "strong",
    "brewed", "lean", "foraged", "large", "small", "medium", "finely", "roughly",
    "grated", "shredded", "peeled", "crushed", "ground", "whole", "leaves", "leaf",
    "of", "the", "a", "an", "and", "with", "or", "to", "for", "from", "tube",
    "taste", "about", "plus", "extra", "lowfat", "low", "fat", "reduced",
}
_USDA_NOISE = {
    "nfs", "ns", "as", "to", "major", "all", "varieties", "mixed", "species",
    "raw", "cooked", "frozen", "fresh", "regular", "commercial", "separable",
    "and", "or", "with", "without", "grades", "trimmed", "unprepared", "prepared",
    "plain", "canned", "boiled", "baked", "broiled", "roasted", "toasted",
}
_DISH_WORDS = {
    "taco", "candies", "candy", "cookie", "cookies", "ball", "sandwich", "pizza",
    "burrito", "patty", "patties", "casserole", "soup", "pie", "cake", "bar",
    "coating", "chips", "nuggets", "salad", "stew", "dinner", "entree", "mix",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _tokens(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = t.replace("'", "")
    return t


def _ing_core(text):
    toks = _tokens(_clean_ingredient(text))
    core = [w for w in toks if w not in _PREP and len(w) > 1]
    return core or [w for w in toks if len(w) > 1]


def _usda_segments(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).replace("'", "")
    segs = [s.strip() for s in t.split(",") if s.strip()]
    return [[w for w in _tokens(s) if len(w) > 1] for s in segs]


def _compound_clash(a, b):
    # one word embedded in another but not equal, e.g. radish / horseradish
    if a == b or len(a) < 3 or len(b) < 3:
        return False
    return (a in b or b in a) and abs(len(a) - len(b)) >= 3


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        core = _ing_core(str(ingredient))
        segs = _usda_segments(str(usda_match))
        if not core or not segs:
            return 0.0

        head = core[-1]
        core_set = set(core)
        primary = [w for w in segs[0] if w not in _USDA_NOISE]
        # weight per segment position: earlier segments define identity
        weighted = {}
        for i, seg in enumerate(segs):
            wgt = 1.0 / (1 + i * 0.6)
            for w in seg:
                if w in _USDA_NOISE:
                    continue
                weighted[w] = max(weighted.get(w, 0.0), wgt)

        score = 0.0

        # 1. head noun identity
        if head in weighted:
            score += 45.0 * weighted[head]
        else:
            clash = any(_compound_clash(head, w) for w in weighted)
            score -= 25.0 if clash else 10.0

        # 2. USDA primary food must be named by the ingredient
        if primary:
            hits = sum(1 for w in primary if w in core_set)
            if hits:
                score += 25.0 * hits / len(primary)
            else:
                score -= 20.0
                if any(_compound_clash(w, c) for w in primary for c in core_set):
                    score -= 10.0

        # 3. coverage of ingredient core tokens
        cov = sum(weighted.get(w, 0.0) for w in core_set) / len(core_set)
        score += 20.0 * cov

        # 4. foreign identity tokens in USDA (different dish / product)
        usda_all = {w for seg in segs for w in seg}
        foreign_dish = [w for w in usda_all if w in _DISH_WORDS and w not in core_set]
        score -= 12.0 * len(foreign_dish)

        # 5. extra unmatched content nouns in the first two segments
        lead = {w for seg in segs[:2] for w in seg if w not in _USDA_NOISE}
        extra = [w for w in lead if w not in core_set and w not in _PREP]
        score -= 3.0 * min(len(extra), 4)

        # 6. capitalised brand-like start (e.g. "Sage Valley, ...")
        first_raw = str(usda_match).split(",")[0].strip().split()
        if len(first_raw) >= 2 and all(x[:1].isupper() for x in first_raw[:2]):
            score -= 15.0

        return round(max(0.0, min(100.0, score + 10.0)), 3)
    except Exception:
        return 0.0
