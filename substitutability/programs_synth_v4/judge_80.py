import re

_PREP = {
    "fresh", "frozen", "thawed", "diced", "chopped", "minced", "sliced", "cubed",
    "crumbled", "drained", "canned", "dried", "cooked", "raw", "whole", "large",
    "small", "medium", "finely", "roughly", "grated", "shredded", "peeled",
    "segmented", "mixed", "bagged", "for", "the", "a", "an", "of", "and", "or",
    "with", "to", "in", "into", "from", "lean", "boneless", "skinless", "trimmed",
    "halved", "quartered", "rinsed", "packed", "softened", "melted", "beaten",
    "optional", "taste", "about", "plus", "extra", "pieces", "piece",
}

# Modifiers known to form a *different* food when attached to a head noun.
_COMPOUND_MODS = {
    "sweet", "coconut", "peanut", "almond", "soy", "soya", "oat", "rice", "sea",
    "green", "black", "white", "red", "cream", "sour", "butter", "buttermilk",
    "blood", "fish", "ice", "cottage", "goat", "sheep", "corn", "egg", "nut",
    "apple", "pumpkin", "sesame", "maple", "brown", "powdered", "evaporated",
    "condensed", "baking", "bread", "pie", "rock", "spring", "wild", "pearl",
    "jelly", "bean", "pork", "beef", "chicken", "turkey", "duck", "lamb",
    "tomato", "potato", "onion", "garlic", "vanilla", "chocolate", "cocoa",
    "plum", "barbecue", "hot", "chili", "chile", "cashew", "hazelnut", "fruit",
    "vegetable", "olive", "canola", "palm", "cod", "liver", "heart", "tongue",
    "stew", "loaf", "patty", "jerky", "juice", "flour", "starch", "tea",
}

_GENERIC_USDA = {
    "nfs", "ns", "commercial", "regular", "all", "varieties", "variety",
    "prepared", "made", "with", "without", "salt", "added", "unprepared",
    "uncooked", "raw", "cooked", "boiled", "baked", "imported", "domesticated",
    "by", "products", "meats", "and", "or", "only", "separable", "includes",
    "type", "style", "plain", "the", "from", "for", "in", "of", "to",
}


def _stem(w):
    w = w.lower()
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ves", "f"), ("ses", "s"),
                     ("es", "e"), ("s", "")):
        if len(w) > 3 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)] + rep
    return w


def _words(text):
    return [_stem(t) for t in re.findall(r"[a-zA-Z]+", text or "")]


def _ingredient_core(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s, flags=re.I)
    s = s.replace("-", " ")
    toks = [t for t in _words(s) if t not in _PREP and len(t) > 1]
    return toks


def _usda_segments(usda):
    s = str(usda or "")
    s = re.sub(r"\(([^)]*)\)", r", \1", s)
    segs = []
    for part in s.split(","):
        toks = [t for t in _words(part.replace("-", " ")) if len(t) > 1]
        if toks:
            segs.append(toks)
    return segs


def _pair_kept(mod, head, segs, all_tokens):
    """Is the compound (mod head) represented in the USDA description?"""
    # adjacent within one segment, either order
    for seg in segs:
        for i in range(len(seg) - 1):
            if (seg[i] == mod and seg[i + 1] == head) or (seg[i] == head and seg[i + 1] == mod):
                return 1.0
    # USDA inversion: head is primary food, modifier is a descriptor
    if segs and head in segs[0] and mod in all_tokens:
        return 0.85
    # fused form ("buttermilk", "sweetpotato")
    fused = mod + head
    if fused in all_tokens:
        return 1.0
    if mod in all_tokens and head in all_tokens:
        return 0.6
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        core = _ingredient_core(ingredient)
        segs = _usda_segments(usda_match)
        if not core or not segs:
            return 0.0
        all_tokens = set(t for seg in segs for t in seg)
        primary = segs[0]
        core_set = set(core)
        head = core[-1]

        # 1. Head noun anchor
        if head in primary:
            head_score = 1.0
        elif head in all_tokens:
            head_score = 0.7
        elif any(len(head) > 3 and (head in t or t in head) and len(t) > 3 for t in all_tokens):
            head_score = 0.5
        else:
            head_score = 0.0

        # 2. Compound integrity: every adjacent pair in the ingredient core
        pairs = list(zip(core, core[1:]))
        if pairs:
            weights, kept = 0.0, 0.0
            for mod, h in pairs:
                w = 2.0 if mod in _COMPOUND_MODS else 1.0
                weights += w
                kept += w * _pair_kept(mod, h, segs, all_tokens)
            pair_score = kept / weights
        else:
            pair_score = 1.0 if head_score > 0 else 0.0

        # 3. Foreign modifiers attached to the ingredient head (forming a new food)
        foreign = 0.0
        for seg in segs:
            for i, t in enumerate(seg):
                if t != head:
                    continue
                for j in (i - 1, i + 1):
                    if 0 <= j < len(seg):
                        m = seg[j]
                        if m not in core_set and m in _COMPOUND_MODS:
                            foreign += 1.0
        # primary food differing from ingredient vocabulary entirely
        primary_overlap = len(set(primary) & core_set) / float(len(set(primary)) or 1)
        if primary_overlap == 0 and head_score < 1.0:
            foreign += 1.0
        # extra compound-forming words in the primary segment
        extra_mods = [t for t in primary if t in _COMPOUND_MODS and t not in core_set and t != head]
        foreign += 0.5 * len(extra_mods)

        # 4. Coverage of ingredient core tokens (fused forms count)
        covered = 0
        for t in core:
            if t in all_tokens or any(t in u and len(t) > 3 for u in all_tokens):
                covered += 1
        coverage = covered / float(len(core))

        # 5. USDA leftover specificity (descriptors that are not generic and not in ingredient)
        leftovers = [t for t in all_tokens if t not in core_set and t not in _GENERIC_USDA]
        leftover_pen = min(1.0, len(leftovers) / 6.0)

        score = (
            35.0 * head_score
            + 30.0 * pair_score
            + 20.0 * coverage
            + 15.0 * (1.0 - leftover_pen)
            - 18.0 * min(foreign, 2.5)
        )
        if head_score == 0.0:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
