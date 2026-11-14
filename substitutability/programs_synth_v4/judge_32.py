import re


# Ledger of "processing components": each maps to a set of cue phrases and a
# weight reflecting how noticeable that component is to a diner.
_COMPONENT_CUES = {
    "salted": (("salted", "with salt", "brined", "cured", "corned"), 1.6),
    "sweetened": (("sweetened", "sugar", "syrup", "honey", "candied", "glazed", "frosted"), 2.0),
    "oiled": (("in oil", "with oil", "oil-roasted", "fried", "deep-fried"), 1.5),
    "sauced": (("sauce", "gravy", "dressing", "with cheese", "creamed", "in sauce"), 2.4),
    "breaded": (("breaded", "battered", "coated", "crusted"), 2.2),
    "seasoned": (("seasoned", "spiced", "flavored", "flavoured", "marinated", "and pepper", "with herbs"), 1.8),
    "prepared": (("prepared from", "from mix", "entree", "dinner", "meal", "pie filling", "filling",
                  "mixture", "mix", "nfs", "patty", "patties", "bar", "chips", "frankfurter",
                  "sausage", "snack", "canned", "frozen entree"), 2.0),
    "cooked": (("cooked", "boiled", "baked", "broiled", "roasted", "braised", "grilled",
                "dry heat", "moist heat", "stewed", "simmered", "steamed", "microwaved"), 1.4),
    "dried": (("dried", "dehydrated", "ground", "powder", "powdered", "flakes"), 1.3),
    "smoked": (("smoked",), 1.5),
}

# Words in the ingredient that "license" a component (the ingredient already has it).
_LICENSES = {
    "cooked": ("cooked", "boiled", "baked", "broiled", "roasted", "grilled", "toasted",
               "steamed", "fried", "braised", "leftover"),
    "dried": ("dried", "ground", "powder", "powdered", "dry", "flakes", "crushed"),
    "salted": ("salted", "salt", "cured", "brined", "corned"),
    "sweetened": ("sweet", "sweetened", "sugar", "syrup", "honey", "candied", "glazed"),
    "oiled": ("oil", "fried"),
    "sauced": ("sauce", "gravy", "dressing", "creamed"),
    "breaded": ("breaded", "battered", "crusted", "coated"),
    "seasoned": ("seasoned", "spiced", "flavored", "marinated", "seasoning"),
    "prepared": ("sausage", "patty", "patties", "bar", "chips", "mix", "filling", "entree",
                 "frankfurter", "hot dog", "canned", "wrap", "tortilla", "bread", "cornbread"),
    "smoked": ("smoked",),
}

_PLAIN_MARKERS = ("raw", "fresh", "unroasted", "unsalted", "without salt", "plain",
                  "unsweetened", "all commercial varieties", "untreated")

_STOP = {"g", "kg", "ml", "of", "and", "or", "the", "a", "with", "for", "from", "in",
         "fresh", "optional", "garnish", "large", "small", "medium", "slices", "sliced",
         "chopped", "diced", "cubed", "minced", "trimmed", "visible", "fat", "to", "nfs",
         "raw", "segments", "pieces", "whole", "lean", "inch"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb)\b", " ", t)
    return t


def _has(text, cue):
    return re.search(r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])", text) is not None


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _STOP and len(w) > 2}


def _bigrams(word):
    w = "#" + word + "#"
    return {w[i:i + 2] for i in range(len(w) - 1)}


def _soft_overlap(a_tokens, b_tokens):
    """Fraction of ingredient tokens with a near match (bigram Dice >= 0.6) in USDA tokens."""
    if not a_tokens or not b_tokens:
        return 0.0
    hits = 0.0
    for a in a_tokens:
        ba = _bigrams(a)
        best = 0.0
        for b in b_tokens:
            bb = _bigrams(b)
            d = 2.0 * len(ba & bb) / (len(ba) + len(bb))
            if d > best:
                best = d
        if best >= 0.6:
            hits += best
    return hits / len(a_tokens)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        ing_head = ing_main.split(",")[0]
        ing_paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_all = ing_main + " " + ing_paren

        segments = [s.strip() for s in usda.split(",") if s.strip()]
        primary = segments[0] if segments else usda

        # 1) Component ledger: components the USDA adds that the ingredient lacks.
        penalty = 0.0
        added = 0
        for comp, (cues, weight) in _COMPONENT_CUES.items():
            in_usda = any(_has(usda, c) for c in cues)
            if not in_usda:
                continue
            licensed = any(_has(ing_all, c) for c in _LICENSES.get(comp, ()))
            if licensed:
                continue
            # Components appearing in the primary segment change the food itself.
            in_primary = any(_has(primary, c) for c in cues)
            penalty += weight * (1.5 if in_primary else 1.0)
            added += 1
        # Compounding: multiple added components are worse than the sum.
        if added >= 2:
            penalty *= 1.0 + 0.15 * (added - 1)

        # Ingredient states processed but USDA says raw -> mild mismatch.
        state_gap = 0.0
        if _has(usda, "raw") and any(_has(ing_head, w) for w in _LICENSES["cooked"]):
            state_gap = 1.2

        # 2) Plainness bonus.
        plain_bonus = sum(0.8 for m in _PLAIN_MARKERS if _has(usda, m))
        plain_bonus = min(plain_bonus, 1.6)
        if len(segments) == 1 and added == 0:
            plain_bonus += 0.8

        # 3) Identity anchor: is the same base food being described?
        it = _tokens(ing_head + " " + ing_paren)
        ut = _tokens(usda)
        pt = _tokens(primary)
        coverage = _soft_overlap(it, ut)
        primary_hit = _soft_overlap(pt, it) if pt else 0.0
        identity = 4.0 * coverage + 2.0 * primary_hit

        # Unrelated foods: processing comparison is meaningless, cap the score.
        score = 3.0 + identity + plain_bonus - penalty - state_gap
        if coverage < 0.2 and primary_hit < 0.2:
            score = min(score, 2.0) - 1.0

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
