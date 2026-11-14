import re

# Processing / additive marker lexicon: marker -> (category, weight a diner would taste)
_MARKERS = {
    # added salt
    "salted": ("salt", 2.0), "salt": ("salt", 1.5), "brined": ("salt", 2.0),
    "cured": ("salt", 2.0), "pickled": ("salt", 2.5),
    # added sugar / sweetening
    "sweetened": ("sugar", 2.5), "sugar": ("sugar", 1.5), "candied": ("sugar", 3.0),
    "honey": ("sugar", 2.0), "syrup": ("sugar", 2.0), "glazed": ("sugar", 2.5),
    "frosted": ("sugar", 3.0), "sugared": ("sugar", 2.5),
    # added fat / oil
    "fried": ("fat", 2.5), "oil": ("fat", 1.0), "butter": ("fat", 1.5),
    "buttered": ("fat", 2.0), "margarine": ("fat", 2.0), "fat": ("fat", 0.8),
    # sauces / compounds
    "sauce": ("sauce", 3.0), "gravy": ("sauce", 3.0), "dressing": ("sauce", 2.5),
    "marinated": ("sauce", 2.5), "teriyaki": ("sauce", 3.0), "barbecue": ("sauce", 3.0),
    "bbq": ("sauce", 3.0), "creamed": ("sauce", 2.5), "cheese": ("sauce", 1.5),
    "pepper": ("seasoning", 1.5),
    # coating
    "breaded": ("coating", 3.0), "battered": ("coating", 3.0), "coated": ("coating", 2.5),
    "crumbs": ("coating", 2.0), "tempura": ("coating", 3.0),
    # seasoning / flavor
    "seasoned": ("seasoning", 2.5), "spiced": ("seasoning", 2.5), "flavored": ("flavor", 2.5),
    "vanilla": ("flavor", 2.0), "chocolate": ("flavor", 2.5), "strawberry": ("flavor", 2.0),
    "smoked": ("flavor", 2.0), "lemon": ("flavor", 1.5), "garlic": ("flavor", 1.2),
    "spicy": ("seasoning", 2.0), "herbs": ("seasoning", 1.5),
    # composition modification
    "lowfat": ("modified", 1.5), "nonfat": ("modified", 1.5), "reduced": ("modified", 1.8),
    "decaffeinated": ("modified", 2.0), "light": ("modified", 0.8), "diet": ("modified", 2.0),
    "fortified": ("modified", 1.0), "enriched": ("modified", 0.5), "imitation": ("modified", 3.0),
    "substitute": ("modified", 3.0), "lactose": ("modified", 1.5), "sodium": ("modified", 1.0),
    "instant": ("modified", 1.5), "dehydrated": ("modified", 0.6), "canned": ("modified", 0.8),
}

# Words in a USDA entry that NEGATE an additive (plain indicators)
_PLAIN_FLAGS = {"plain", "unsalted", "unsweetened", "unprepared", "raw", "unenriched",
                "unseasoned", "natural", "fresh", "regular"}
_NEGATORS = {"no", "without", "not", "unsalted", "un"}

_STOP = {"and", "or", "with", "of", "the", "a", "in", "for", "to", "nfs", "ns", "as",
         "made", "from", "type", "style", "commercial", "prepared", "cooked", "raw",
         "boiled", "frozen", "fresh", "chopped", "sliced", "diced", "minced", "shredded",
         "grated", "trimmed", "visible", "leftover", "taste", "tube", "large", "small",
         "medium", "whole", "uncooked", "unprepared", "plain", "regular", "choice", "boneless",
         "added", "eaten", "only", "include", "includes", "g", "kg", "ml"}


def _norm(word):
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    return [_norm(t) for t in re.findall(r"[a-zA-Z]+", text or "")]


def _clean_ingredient(text):
    t = str(text or "")
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b\.?", " ", t, flags=re.I)
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    head, _, tail = t.partition(",")
    return head, tail, paren


def _marker_profile(tokens):
    """Return dict marker->weight for markers present, honoring local negation."""
    found = {}
    for i, tok in enumerate(tokens):
        if tok in _MARKERS:
            prev = tokens[i - 1] if i > 0 else ""
            prev2 = tokens[i - 2] if i > 1 else ""
            if prev in _NEGATORS or prev2 in ("no", "without"):
                continue
            found[tok] = _MARKERS[tok]
    return found


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        head, tail, paren = _clean_ingredient(ingredient)
        ing_head_toks = _tokens(head)
        ing_all_toks = ing_head_toks + _tokens(tail) + _tokens(paren)
        usda_toks = _tokens(usda_match)
        if not ing_head_toks or not usda_toks:
            return 0.0

        ing_set = set(ing_all_toks)
        usda_set = set(usda_toks)

        # --- 1. Anchor: is it even the same food? (gate for processing analysis)
        ing_core = {t for t in ing_head_toks if t not in _STOP and len(t) > 2}
        usda_core = {t for t in usda_toks if t not in _STOP and len(t) > 2}
        if not ing_core:
            ing_core = set(ing_head_toks)
        shared = ing_core & usda_core
        # partial (prefix) matching for compound forms like "cornflakes" / "flakes"
        partial = 0
        for a in ing_core - shared:
            for b in usda_core:
                if len(a) > 3 and len(b) > 3 and (a.startswith(b) or b.startswith(a)):
                    partial += 1
                    break
        anchor = (len(shared) + 0.5 * partial) / max(len(ing_core), 1)
        anchor = min(anchor, 1.0)

        # Compound ingredient: "X and Y" where the USDA covers only one side
        compound_pen = 0.0
        if re.search(r"\band\b", head, flags=re.I) and not re.search(r"\band\b", usda_match, re.I):
            parts = re.split(r"\band\b", head, flags=re.I)
            covered = 0
            for p in parts:
                pt = {t for t in _tokens(p) if t not in _STOP and len(t) > 2}
                if pt and pt & usda_core:
                    covered += 1
            if covered < len(parts):
                compound_pen = 2.5

        # --- 2. Additive / processing asymmetry
        ing_markers = _marker_profile(ing_all_toks)
        usda_markers = _marker_profile(usda_toks)

        added_pen = 0.0
        added_cats = set()
        for m, (cat, w) in usda_markers.items():
            if m in ing_set or m in ing_core:
                continue
            # the ingredient mentions same category with another word -> half penalty
            if any(c == cat for (c, _) in ing_markers.values()):
                added_pen += 0.4 * w
            else:
                added_pen += w
                added_cats.add(cat)

        missing_pen = 0.0
        for m, (cat, w) in ing_markers.items():
            if m in usda_set:
                continue
            if any(c == cat for (c, _) in usda_markers.values()):
                missing_pen += 0.3 * w
            else:
                missing_pen += 0.6 * w

        # extra unknown descriptor tokens in USDA that aren't in ingredient (mild)
        extra = [t for t in usda_core - ing_set if t not in _MARKERS and t not in _PLAIN_FLAGS]
        extra_pen = 0.25 * min(len(extra), 6)

        # plain-for-plain bonus
        plain_bonus = 0.0
        if not usda_markers or all(m in ing_set for m in usda_markers):
            plain_bonus += 1.0
        if usda_set & _PLAIN_FLAGS and not ing_markers:
            plain_bonus += 0.5
        if len(added_cats) >= 2:
            added_pen += 1.0  # multiple additive families compound perceptibly

        # --- 3. Combine
        base = 2.0 + 6.0 * anchor
        score = base + plain_bonus - added_pen - missing_pen - extra_pen - compound_pen
        if anchor == 0:
            score = min(score, 2.0) - 1.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
