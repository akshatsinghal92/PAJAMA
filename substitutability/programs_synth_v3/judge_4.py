import re
import math
from collections import Counter

_STOP = {
    "a", "an", "the", "of", "and", "or", "with", "without", "in", "for", "to", "as",
    "from", "on", "at", "by", "into", "ns", "nfs", "type", "style", "made",
}
_PREP = {
    "fresh", "frozen", "thawed", "chopped", "diced", "sliced", "minced", "grated",
    "shredded", "cooked", "raw", "uncooked", "toasted", "roasted", "baked", "boiled",
    "broiled", "fried", "grilled", "steamed", "warmed", "heated", "chilled", "cold",
    "hot", "dried", "dry", "canned", "large", "small", "medium", "whole", "lean",
    "finely", "coarsely", "roughly", "thinly", "peeled", "trimmed", "rinsed", "drained",
    "softened", "melted", "beaten", "packed", "ripe", "organic", "plain", "prepared",
    "ready", "to", "serve", "tube", "jar", "bottled", "store", "bought", "homemade",
    "leaves", "leaf", "sprigs", "sprig", "pieces", "piece", "cut", "cubed", "halved",
    "quartered", "salad", "cooking", "commercial", "regular", "unenriched", "enriched",
}
# words that, when they appear on only one side, mean a different composite food
_COMPOSITE = {
    "sauce", "relish", "taco", "burrito", "sandwich", "cookie", "cookies", "pie",
    "soup", "stew", "casserole", "salad", "dressing", "patty", "patties", "nugget",
    "nuggets", "pizza", "cake", "bar", "bars", "cereal", "candy", "chips", "dip",
    "spread", "jam", "jelly", "paste", "juice", "drink", "beverage", "mix", "oats",
    "sausage", "babyfood", "puree", "flavored", "sweetened",
}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            return w[: -len(suf)]
    return w


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?\s*%", " ", t)
    t = re.sub(r"[^a-z,\s-]", " ", t)
    return t


def _tokens(s):
    out = []
    for w in re.split(r"[\s,\-]+", s):
        w = w.strip()
        if len(w) < 2 or w in _STOP:
            continue
        out.append(_stem(w))
    return out


def _grams(word, n=3):
    w = "^" + word + "$"
    if len(w) <= n:
        return Counter([w])
    return Counter(w[i:i + n] for i in range(len(w) - n + 1))


def _gram_cos(a, b):
    if not a or not b:
        return 0.0
    ga, gb = Counter(), Counter()
    for w in a:
        ga.update(_grams(w))
    for w in b:
        gb.update(_grams(w))
    dot = sum(ga[k] * gb[k] for k in ga if k in gb)
    na = math.sqrt(sum(v * v for v in ga.values()))
    nb = math.sqrt(sum(v * v for v in gb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _ingredient_core(ingredient):
    t = _clean(ingredient)
    t = t.split(",")[0]  # drop post-comma state
    toks = [w for w in _tokens(t) if w not in _PREP]
    return toks


def _usda_segments(usda):
    t = _clean(usda)
    segs = [s.strip() for s in t.split(",") if s.strip()]
    return [[w for w in _tokens(s)] for s in segs]


def judging_function(ingredient, usda_match):
    try:
        core = _ingredient_core(ingredient)
        segs = _usda_segments(usda_match)
        if not core or not segs:
            return 0.0

        head = core[-1]  # head noun of ingredient (English: last word)
        ing_mod = set(core[:-1])
        primary = segs[0]
        if not primary:
            return 0.0
        all_usda = [w for s in segs for w in s]
        usda_content = [w for w in all_usda if w not in _PREP]
        usda_set = set(usda_content)

        # 1. head identity: where does the ingredient's head noun appear in the USDA string?
        head_pos = None
        for i, s in enumerate(segs):
            if head in s:
                head_pos = i
                break
        if head_pos is None:
            # fuzzy head match via char trigram similarity against each USDA word
            best = 0.0
            for i, s in enumerate(segs):
                for w in s:
                    sim = _gram_cos([head], [w])
                    if sim > best:
                        best = sim
                        if sim >= 0.75:
                            head_pos = i
            head_score = 0.6 * best if head_pos is None else 0.7
        else:
            head_score = 1.0

        # positional weight: head in primary segment is best
        if head_pos is None:
            pos_w = 0.3
        else:
            pos_w = 1.0 / (1.0 + 0.6 * head_pos)

        # 2. primary-segment coverage: USDA primary food must be explained by ingredient
        core_set = set(core)
        prim_content = [w for w in primary if w not in _PREP]
        if prim_content:
            explained = sum(1 for w in prim_content if w in core_set) / len(prim_content)
        else:
            explained = 0.5
        # substring trap: a word of the primary includes ingredient head but is longer
        # e.g. 'radish' inside 'horseradish', 'sage' inside 'sage valley' brand
        trap = 0.0
        for w in primary:
            if head != w and head in w and len(w) > len(head) + 2:
                trap = 1.0

        # 3. composite / different-substance penalty
        extra_comp = [w for w in usda_set if w in _COMPOSITE and w not in core_set]
        missing_comp = [w for w in core_set if w in _COMPOSITE and w not in usda_set]
        comp_pen = 0.18 * len(extra_comp) + 0.15 * len(missing_comp)

        # 4. ingredient modifiers covered by USDA (e.g. 'greek', 'flour', 'olive')
        if ing_mod:
            mod_cov = sum(1 for w in ing_mod if w in usda_set) / len(ing_mod)
        else:
            mod_cov = 1.0

        # 5. unexplained USDA content words (descriptors beyond primary) -> dilution
        unexplained = [w for w in usda_content if w not in core_set]
        dil = 1.0 / (1.0 + 0.12 * len(unexplained))

        # 6. global character-level similarity of the cores as a soft prior
        g = _gram_cos(core, prim_content or primary)

        raw = (
            0.40 * head_score * pos_w
            + 0.20 * explained
            + 0.15 * mod_cov
            + 0.10 * g
            + 0.15 * dil
        )
        raw -= comp_pen
        raw -= 0.35 * trap
        raw = max(0.0, min(1.0, raw))
        return round(100.0 * raw, 3)
    except Exception:
        return 0.0
