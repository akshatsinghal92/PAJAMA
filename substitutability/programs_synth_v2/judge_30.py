import re

# Nutritional Profile Proximity, variant 6: macro RANK ordering, energy tier,
# and single-food vs composite detection.
# Precise macro numbers are unreliable from text, but the ORDER of the
# macros (which supplies most energy, which second) and a coarse energy tier
# are robust. We compare:
#   * macro rank order (pairwise concordance over P/C/F, Kendall-style)
#   * energy tier (1 very light .. 5 very dense)
#   * composite-ness: a pure spice vs a seasoning blend, a raw vegetable vs a
#     sauce or prepared dish, a plain food vs a branded multi-ingredient product.

# keyword -> (rank string highest..lowest energy source, energy tier)
_PROFILE = {
    "oil": ("fpc", 5), "butter": ("fpc", 5), "lard": ("fpc", 5), "mayonnaise": ("fcp", 5),
    "nut": ("fcp", 5), "almond": ("fcp", 5), "peanut": ("fpc", 5), "walnut": ("fcp", 5),
    "seed": ("fcp", 5), "chia": ("fcp", 5), "flaxseed": ("fcp", 5), "chocolate": ("fcp", 5),
    "bacon": ("fpc", 5), "cheese": ("fpc", 4), "cream": ("fcp", 4), "sausage": ("fpc", 4),
    "patty": ("fpc", 3), "beef": ("pfc", 3), "pork": ("pfc", 3), "lamb": ("fpc", 3),
    "chicken": ("pfc", 2), "turkey": ("pfc", 2), "breast": ("pfc", 2), "fish": ("pfc", 2),
    "swordfish": ("pfc", 2), "salmon": ("pfc", 3), "tuna": ("pfc", 2), "shrimp": ("pfc", 1),
    "egg": ("fpc", 2), "tofu": ("pfc", 1), "cottage": ("pfc", 1), "yogurt": ("cfp", 1),
    "milk": ("cfp", 1), "rice": ("cpf", 2), "pasta": ("cpf", 2), "noodle": ("cpf", 2),
    "gnocchi": ("cpf", 2), "potato": ("cpf", 1), "bread": ("cpf", 3), "cereal": ("cpf", 4),
    "flour": ("cpf", 4), "oat": ("cpf", 4), "cracker": ("cfp", 4), "corn": ("cpf", 1),
    "bean": ("cpf", 2), "lentil": ("cpf", 2), "pea": ("cpf", 1), "sugar": ("cpf", 4),
    "honey": ("cpf", 4), "syrup": ("cpf", 4), "candy": ("cfp", 4), "jam": ("cpf", 3),
    "fruit": ("cpf", 1), "apple": ("cpf", 1), "banana": ("cpf", 1), "berry": ("cfp", 1),
    "blueberry": ("cfp", 1), "guava": ("cpf", 1), "orange": ("cpf", 1), "juice": ("cpf", 1),
    "tomato": ("cpf", 1), "onion": ("cpf", 1), "garlic": ("cpf", 2), "carrot": ("cpf", 1),
    "spinach": ("pcf", 1), "lettuce": ("cpf", 1), "kale": ("cpf", 1), "broccoli": ("cpf", 1),
    "pepper": ("cpf", 1), "mushroom": ("pcf", 1), "avocado": ("fcp", 3),
    "dressing": ("fcp", 4), "pesto": ("fpc", 5), "sauce": ("cfp", 1), "ketchup": ("cpf", 2),
    "paste": ("cpf", 2), "soup": ("cfp", 1), "broth": ("pcf", 1), "stock": ("pcf", 1),
    "spice": ("cpf", 4), "spices": ("cpf", 4), "ginger": ("cpf", 1), "cinnamon": ("cpf", 4),
    "cumin": ("cfp", 4), "paprika": ("cfp", 4), "seasoning": ("cpf", 3), "ice": ("cfp", 3),
}
_COMPOSITE_CUES = {"with", "and", "in", "mix", "blend", "seasoning", "salad", "casserole",
                   "sandwich", "pie", "stew", "soup", "sauce", "dressing", "prepared",
                   "recipe", "dinner", "entree", "meal", "kit", "style", "flavored"}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _profile(words):
    prof = None
    for w in words:
        for cand in (w, _sing(w)):
            if cand in _PROFILE:
                prof = _PROFILE[cand]
                break
    return prof


def _fry_adjust(prof, words):
    """Frying / breading pushes fat up the rank order and raises the tier."""
    rank, tier = prof
    if set(words) & {"fried", "breaded", "battered"}:
        rank = "f" + rank.replace("f", "")
        tier = min(5, tier + 1)
    if set(words) & {"dried", "dehydrated"} and tier <= 2:
        tier += 2
    return rank, tier


def _concordance(r1, r2):
    pairs = [("p", "c"), ("p", "f"), ("c", "f")]
    agree = 0
    for a, b in pairs:
        if (r1.index(a) < r1.index(b)) == (r2.index(a) < r2.index(b)):
            agree += 1
    return agree / 3.0


def _composite_level(raw_text, words):
    lvl = sum(1 for w in words if w in _COMPOSITE_CUES)
    # brand names in USDA are upper-case runs
    if re.search(r"\b[A-Z]{3,}\b", raw_text):
        lvl += 1
    return min(lvl, 3)


def judging_function(ingredient, usda_match):
    try:
        raw_i = str(ingredient or "")
        raw_u = str(usda_match or "")
        ing = re.sub(r"\([^)]*\)", " ", raw_i.lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in raw_u.lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        uw = [w for f in fields for w in f]
        # "Sauce, pesto" / "Cheese, cottage": the qualifier is the specific food,
        # so it is placed LAST and wins the head-final lookup
        u_order = (fields[0] + fields[1]) if len(fields) > 1 and len(fields[0]) == 1 else fields[0]
        pi = _profile(iw)
        pu = _profile(u_order) or _profile(uw)
        if pi is not None and pu is not None:
            pi, pu = _fry_adjust(pi, iw), _fry_adjust(pu, uw)
        if pi is None or pu is None:
            same = _sing(iw[-1]) in {_sing(w) for w in u_order}
            base = 60.0 if same else 25.0
        else:
            rank = _concordance(pi[0], pu[0])
            top_same = 1.0 if pi[0][0] == pu[0][0] else 0.0
            tier = max(0.0, 1.0 - abs(pi[1] - pu[1]) / 3.0)
            base = 100.0 * (0.30 * rank + 0.30 * top_same + 0.40 * tier)
        # lower-fat USDA variant of a full-fat food lowers the fat rank / tier slightly
        if set(uw) & {"lowfat", "nonfat", "skim"} or ("low" in uw and "fat" in uw):
            if not set(iw) & {"lowfat", "nonfat", "skim", "low", "light"}:
                base -= 8.0
        ci = _composite_level(raw_i, iw)
        cu = _composite_level(raw_u, uw[len(fields[0]):] if len(fields) > 1 else [])
        base -= 9.0 * abs(ci - cu)
        return round(max(0.0, min(100.0, base)), 2)
    except Exception:
        return 0.0
