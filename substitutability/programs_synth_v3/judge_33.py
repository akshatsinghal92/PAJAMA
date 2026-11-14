import re

_STOP = {"a", "an", "the", "of", "and", "or", "with", "for", "to", "in", "from",
         "optional", "about", "approx", "g", "gram", "grams", "into", "plus", "as"}

_PREP = {"chopped", "diced", "minced", "sliced", "cubed", "grated", "shredded",
         "thawed", "peeled", "crushed", "halved", "quartered", "trimmed", "rinsed",
         "drained", "softened", "melted", "beaten", "divided", "finely", "roughly",
         "thinly", "large", "small", "medium", "fresh", "packed", "cut", "pieces",
         "piece", "whole", "taste", "needed"}

# Qualifier groups: tokens within a group are mutually exclusive variants a diner notices.
_GROUPS = {
    "state": {"raw", "cooked", "boiled", "fried", "roasted", "baked", "grilled",
              "steamed", "braised", "broiled", "stewed", "microwaved", "toasted"},
    "preserve": {"frozen", "canned", "dried", "dehydrated", "smoked", "pickled",
                 "cured", "salted", "fresh", "shelf", "stable"},
    "fat": {"lowfat", "nonfat", "skim", "reduced", "lite", "light", "whole", "fat"},
    "sugar": {"sweetened", "unsweetened", "sugar", "sugarfree"},
    "grade": {"extra", "virgin", "refined", "unrefined", "enriched", "unenriched",
              "bleached", "unbleached", "instant", "quick"},
    "flavor": {"vanilla", "chocolate", "strawberry", "honey", "cinnamon", "spicy",
               "barbecue", "flavored"},
    "form": {"ground", "powder", "paste", "flakes", "leaves", "seeds", "juice",
             "concentrate", "sauce", "chips", "cookies", "patty", "bar", "mix"},
}
# Descriptors that add no noticeable difference for a diner (neutral USDA filler).
_NEUTRAL = {"raw", "mature", "imported", "commercial", "prepared", "regular",
            "plain", "all", "varieties", "type", "includes", "usda", "by",
            "products", "separable", "lean", "solids", "liquids", "ns", "nfs",
            "made", "unprepared", "ready", "to", "eat", "bake", "fry", "variety",
            "meats", "edible", "portion", "only"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 3 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and w[-3] in "sxz":
                return w[:-2]
            if suf == "s" and not w.endswith("ss"):
                return w[:-1]
    return w


def _tok(s):
    s = s.lower().replace("-", " ").replace("/", " ")
    return [_stem(t) for t in re.findall(r"[a-z]+", s)]


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.,/]+\s*(g|gram|grams|kg|ml|l)?\b", " ", s)
    head, _, tail = s.partition(",")
    return head, tail


def _group_of(tok):
    out = []
    for name, members in _GROUPS.items():
        if tok in members or _stem(tok) in {_stem(m) for m in members}:
            out.append(name)
    return out


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        head, tail = _clean_ingredient(str(ingredient))
        head_t = [t for t in _tok(head) if t not in _STOP]
        tail_t = [t for t in _tok(tail) if t not in _STOP]
        ing_all = set(head_t) | set(tail_t)
        ing_core = [t for t in head_t if t not in _PREP]
        if not ing_core:
            ing_core = head_t
        if not ing_core:
            return 0.0

        segs = [seg.strip() for seg in str(usda_match).split(",") if seg.strip()]
        if not segs:
            return 0.0
        seg_toks = [[t for t in _tok(sg) if t not in _STOP] for sg in segs]
        usda_all = set(t for st in seg_toks for t in st)
        primary = set(seg_toks[0])

        # 1. Anchor: the ingredient's head noun (last core token) must appear.
        head_noun = ing_core[-1]
        anchor = 0.0
        if head_noun in primary:
            anchor = 1.0
        elif head_noun in usda_all:
            anchor = 0.7
        elif any(head_noun in u or u in head_noun for u in usda_all if len(u) > 3):
            anchor = 0.5
        if anchor == 0.0:
            if any(t in usda_all for t in ing_core):
                anchor = 0.25
            else:
                return 0.5

        # 2. Qualifier coverage: ingredient-specified qualifiers present in USDA.
        quals = [t for t in ing_core if t != head_noun]
        covered = sum(1 for q in quals if q in usda_all)
        coverage = covered / len(quals) if quals else 1.0

        # 3. Extra qualifiers in USDA beyond the ingredient (specificity drift).
        extra = [t for t in usda_all
                 if t not in ing_all and t not in _NEUTRAL and len(t) > 2]
        # 4. Group conflicts: same qualifier dimension but different value.
        ing_groups = {}
        for t in ing_all:
            for g in _group_of(t):
                ing_groups.setdefault(g, set()).add(t)
        conflicts = 0
        added_dims = 0
        for t in extra:
            gs = _group_of(t)
            for g in gs:
                if g in ing_groups:
                    conflicts += 1
                else:
                    added_dims += 1
        # Primary segment containing a foreign leading word (brand / other species).
        foreign_primary = [t for t in primary if t not in ing_all and t not in _NEUTRAL]
        brand_like = 1 if (len(segs[0].split()) >= 2 and foreign_primary
                           and head_noun not in primary) else 0

        unmarked_extra = max(0, len(extra) - conflicts - added_dims)

        score = 40.0 * anchor
        score += 25.0 * coverage
        score -= 12.0 * conflicts
        score -= 5.0 * added_dims
        score -= 2.0 * min(unmarked_extra, 6)
        score -= 8.0 * brand_like
        # Bonus for generic entry when ingredient is unqualified.
        if not quals and len(segs) <= 2 and conflicts == 0:
            score += 10.0
        # Bonus when USDA primary is exactly the ingredient core set.
        if set(ing_core) <= usda_all and conflicts == 0:
            score += 15.0
        # Normalize to 0-100
        score = max(0.0, min(100.0, score + 20.0))
        return round(score, 3)
    except Exception:
        return 0.0
