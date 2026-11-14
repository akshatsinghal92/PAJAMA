import re
import math

# Approximate per-100g macro prototypes: (kcal, protein, carb, fat)
_PROTOTYPES = {
    "sugar": (387, 0, 100, 0), "honey": (304, 0.3, 82, 0), "syrup": (260, 0, 67, 0),
    "substitute": (330, 0, 85, 0), "sweetener": (330, 0, 85, 0), "stevia": (0, 0, 0, 0),
    "flour": (364, 10, 76, 1), "bread": (265, 9, 49, 3), "cornbread": (330, 7, 50, 11),
    "rice": (130, 2.7, 28, 0.3), "pasta": (158, 6, 31, 1), "noodle": (138, 4.5, 25, 2),
    "oat": (389, 17, 66, 7), "cereal": (380, 7, 84, 2), "cracker": (430, 9, 70, 13),
    "oil": (884, 0, 0, 100), "butter": (717, 1, 0, 81), "lard": (902, 0, 0, 100),
    "margarine": (717, 0, 1, 80), "shortening": (884, 0, 0, 100), "mayonnaise": (680, 1, 1, 75),
    "cheese": (380, 23, 2, 31), "ricotta": (174, 11, 3, 13), "cottage": (98, 11, 3.4, 4.3),
    "cream": (340, 2, 3, 36), "milk": (61, 3.2, 4.8, 3.3), "yogurt": (61, 3.5, 4.7, 3.3),
    "egg": (143, 12.6, 0.7, 9.5), "tofu": (76, 8, 1.9, 4.8), "fuyu": (116, 8, 5, 8), "sufu": (116, 8, 5, 8),
    "chicken": (165, 31, 0, 3.6), "turkey": (170, 27, 0, 7), "beef": (250, 26, 0, 15),
    "pork": (242, 27, 0, 14), "lamb": (294, 25, 0, 21), "bacon": (541, 37, 1.4, 42),
    "sausage": (300, 12, 2, 27), "ham": (145, 21, 1.5, 6), "patty": (250, 17, 6, 18),
    "fish": (140, 22, 0, 5), "salmon": (208, 20, 0, 13), "swordfish": (144, 20, 0, 6.7),
    "tuna": (130, 29, 0, 1), "cod": (82, 18, 0, 0.7), "shrimp": (99, 24, 0.2, 0.3),
    "crab": (97, 19, 0, 1.5), "tilapia": (96, 20, 0, 1.7),
    "nut": (607, 20, 21, 54), "pine": (673, 14, 13, 68), "pinyon": (629, 12, 19, 61),
    "kernel": (600, 14, 18, 55), "almond": (579, 21, 22, 50), "walnut": (654, 15, 14, 65),
    "peanut": (567, 26, 16, 49), "seed": (560, 20, 20, 48),
    "bean": (127, 9, 23, 0.5), "lentil": (116, 9, 20, 0.4), "chickpea": (164, 9, 27, 2.6),
    "orange": (47, 0.9, 12, 0.1), "apple": (52, 0.3, 14, 0.2), "banana": (89, 1.1, 23, 0.3),
    "berry": (50, 0.8, 12, 0.4), "fruit": (55, 0.8, 14, 0.2), "lemon": (29, 1.1, 9, 0.3),
    "juice": (45, 0.6, 10, 0.2), "raisin": (299, 3, 79, 0.5), "dried": (280, 3, 70, 1),
    "lettuce": (15, 1.4, 2.9, 0.2), "spinach": (23, 2.9, 3.6, 0.4), "kale": (49, 4.3, 9, 0.9),
    "cabbage": (25, 1.3, 6, 0.1), "greens": (25, 2.5, 4, 0.4), "tomato": (18, 0.9, 3.9, 0.2),
    "onion": (40, 1.1, 9, 0.1), "garlic": (149, 6.4, 33, 0.5), "carrot": (41, 0.9, 10, 0.2),
    "potato": (77, 2, 17, 0.1), "pepper": (31, 1, 6, 0.3), "mushroom": (22, 3.1, 3.3, 0.3),
    "vegetable": (35, 1.5, 7, 0.2), "corn": (86, 3.2, 19, 1.2), "pea": (81, 5.4, 14, 0.4),
    "spice": (300, 10, 60, 6), "spices": (300, 10, 60, 6), "ground": (300, 10, 60, 6),
    "ginger": (80, 1.8, 18, 0.8), "cinnamon": (247, 4, 81, 1.2), "salt": (0, 0, 0, 0),
    "seasoning": (250, 8, 45, 4), "sauce": (90, 2, 15, 2), "paste": (120, 4, 20, 3),
    "ketchup": (101, 1, 27, 0.1), "vinegar": (18, 0, 0.04, 0), "broth": (7, 1, 0.5, 0.2),
    "soup": (50, 2.5, 7, 1.5), "chocolate": (546, 5, 61, 31), "cocoa": (228, 20, 58, 14),
    "cake": (370, 4, 55, 15), "cookie": (480, 5, 65, 22), "candy": (400, 2, 90, 5),
    "wine": (85, 0.1, 2.6, 0), "beer": (43, 0.5, 3.6, 0), "water": (0, 0, 0, 0),
}

# Modifiers that scale macros: (kcal_mult, protein_mult, carb_mult, fat_mult)
_MODIFIERS = {
    "lean": (0.85, 1.05, 1.0, 0.6), "fried": (1.35, 0.95, 1.2, 2.0), "breaded": (1.3, 0.9, 2.5, 1.6),
    "dried": (2.5, 2.5, 3.0, 2.0), "dehydrated": (2.8, 2.8, 3.2, 2.0), "powder": (3.0, 2.5, 3.0, 1.5),
    "light": (0.7, 1.0, 0.9, 0.5), "lite": (0.7, 1.0, 0.9, 0.5), "reduced": (0.75, 1.0, 1.0, 0.55),
    "nonfat": (0.5, 1.1, 1.1, 0.05), "skim": (0.55, 1.1, 1.05, 0.05), "fat-free": (0.5, 1.1, 1.1, 0.05),
    "sweetened": (1.3, 1.0, 1.6, 1.0), "canned": (0.95, 1.0, 1.05, 1.0), "toasted": (1.12, 1.1, 1.1, 1.05),
    "roasted": (1.15, 1.1, 1.05, 1.1), "cooked": (1.1, 1.2, 1.0, 1.1), "broiled": (1.15, 1.25, 1.0, 1.0),
    "boiled": (0.95, 1.0, 1.0, 0.95), "raw": (1.0, 1.0, 1.0, 1.0), "whole": (1.1, 1.0, 1.0, 1.25),
    "farmed": (1.1, 1.0, 1.0, 1.3), "mix": (1.05, 0.9, 1.1, 1.05), "patties": (1.1, 0.9, 1.2, 1.2),
    "substitute": (0.6, 1.0, 0.85, 0.5),
}

_STOP = {"g", "gram", "grams", "of", "and", "or", "the", "a", "with", "nfs", "ns", "from",
         "fresh", "frozen", "thawed", "chopped", "sliced", "diced", "minced", "large", "small",
         "medium", "for", "to", "in", "all", "commercial", "varieties", "uncooked", "prepared",
         "tube", "steak", "steaks", "kernels"}


def _tokens(text):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", text)
    text = re.sub(r"^\s*\d+(\.\d+)?\s*(g|grams?|ml|kg|oz)\b", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*%", " ", text)
    raw = re.findall(r"[a-z][a-z\-]*", text)
    out = []
    for t in raw:
        if t.endswith("ies") and len(t) > 4:
            out.append(t[:-3] + "y")
        elif t.endswith("es") and t[:-2] in _PROTOTYPES:
            out.append(t[:-2])
        elif t.endswith("s") and not t.endswith("ss") and t[:-1] in _PROTOTYPES:
            out.append(t[:-1])
        else:
            out.append(t)
    return out


def _estimate(tokens, primary_weight):
    """Weighted blend of matched prototypes; earlier/primary tokens weigh more."""
    acc = [0.0, 0.0, 0.0, 0.0]
    total_w = 0.0
    hits = []
    n = len(tokens)
    for i, t in enumerate(tokens):
        proto = _PROTOTYPES.get(t)
        if proto is None:
            continue
        w = 1.0 + primary_weight(i, n)
        hits.append(t)
        for k in range(4):
            acc[k] += w * proto[k]
        total_w += w
    if total_w == 0:
        return None, hits
    vec = [a / total_w for a in acc]
    for t in tokens:
        mod = _MODIFIERS.get(t)
        if mod:
            vec = [v * m for v, m in zip(vec, mod)]
    vec[0] = min(vec[0], 902.0)
    return vec, hits


def _ing_weight(i, n):
    # Ingredient: the head noun tends to be at the end of the pre-comma phrase
    return 1.5 * (i + 1) / max(n, 1)


def _usda_weight(i, n):
    # USDA: primary food is first
    return 2.0 if i == 0 else 1.0 / (i + 1)


def _macro_distance(a, b):
    # Compare on energy-normalised, log-compressed axes
    da = [math.log1p(max(a[0], 0)) - math.log1p(max(b[0], 0))]
    for k in range(1, 4):
        da.append(math.log1p(max(a[k], 0)) - math.log1p(max(b[k], 0)))
    weights = (1.2, 1.0, 0.9, 1.1)
    d = math.sqrt(sum(w * x * x for w, x in zip(weights, da)))
    # composition shares (fraction of energy from p/c/f)
    def shares(v):
        e = 4 * v[1] + 4 * v[2] + 9 * v[3]
        if e <= 0:
            return (0.0, 0.0, 0.0)
        return (4 * v[1] / e, 4 * v[2] / e, 9 * v[3] / e)
    sa, sb = shares(a), shares(b)
    comp = sum(abs(x - y) for x, y in zip(sa, sb)) / 2.0
    return d, comp


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_head = ing.split(",")[0]
        it = [t for t in _tokens(ing_head) if t not in _STOP or t in _MODIFIERS]
        ut_all = _tokens(usda)
        ut = [t for t in ut_all if t not in _STOP or t in _MODIFIERS]
        # Include post-comma state words of the ingredient only as modifiers
        post = [t for t in _tokens(",".join(ing.split(",")[1:])) if t in _MODIFIERS]

        va, hits_a = _estimate(it + post, _ing_weight)
        vb, hits_b = _estimate(ut, _usda_weight)

        ing_set = set(t for t in it if t not in _MODIFIERS)
        usda_set = set(t for t in ut if t not in _MODIFIERS)
        overlap = len(ing_set & usda_set) / max(1, len(ing_set | usda_set))

        if va is None or vb is None:
            # Fall back on lexical overlap only; uncertain macro profile
            return round(1.0 + 8.0 * overlap, 3)

        d, comp = _macro_distance(va, vb)
        # Similarity from distance (d ~0 identical, ~3+ very different)
        macro_sim = math.exp(-0.9 * d)
        comp_sim = 1.0 - comp
        score = 10.0 * (0.40 * macro_sim + 0.20 * comp_sim + 0.40 * overlap)

        # Penalise class swings: a substitute/blend vs a pure food
        if ("substitute" in usda_set) != ("substitute" in ing_set):
            score *= 0.7
        # Shared primary prototype hit is a strong signal of same macro class
        if hits_a and hits_b and hits_a[-1] == hits_b[0]:
            score += 0.5
        # Disjoint vocabularies rarely denote the same food
        if overlap == 0.0:
            score -= 1.5
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
