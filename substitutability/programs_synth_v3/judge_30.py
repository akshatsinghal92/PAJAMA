import re
import math

# Approximate per-100g macro estimates: (kcal, protein, carbs, fat, water%)
_MACRO_LEXICON = {
    # pure fats / oils
    "oil": (884, 0, 0, 100, 0), "butter": (717, 1, 0, 81, 16), "lard": (902, 0, 0, 100, 0),
    "shortening": (884, 0, 0, 100, 0), "ghee": (900, 0, 0, 100, 0), "margarine": (717, 0, 1, 80, 16),
    "mayonnaise": (680, 1, 1, 75, 20),
    # lean / fatty proteins
    "chicken": (165, 31, 0, 4, 65), "turkey": (150, 29, 0, 3, 68), "beef": (200, 26, 0, 11, 62),
    "pork": (200, 26, 0, 10, 63), "lamb": (250, 25, 0, 17, 58), "veal": (170, 30, 0, 5, 65),
    "fish": (130, 22, 0, 4, 72), "salmon": (200, 22, 0, 13, 65), "tuna": (130, 28, 0, 1, 70),
    "shrimp": (100, 24, 0, 1, 75), "egg": (143, 13, 1, 10, 76), "tofu": (80, 8, 2, 5, 84),
    "sirloin": (180, 27, 0, 8, 65), "chuck": (230, 25, 0, 14, 60), "loin": (190, 27, 0, 9, 64),
    "steak": (200, 26, 0, 11, 62), "roast": (220, 25, 0, 13, 60), "chop": (200, 26, 0, 10, 63),
    "breast": (165, 31, 0, 4, 65), "bacon": (540, 37, 1, 42, 12), "sausage": (300, 14, 2, 26, 50),
    "ham": (145, 21, 1, 6, 68), "patty": (250, 16, 8, 17, 55),
    # dairy
    "milk": (60, 3, 5, 3, 88), "cream": (340, 2, 3, 36, 58), "yogurt": (70, 6, 8, 2, 82),
    "greek": (90, 9, 6, 2, 80), "cheese": (380, 24, 2, 31, 38), "ricotta": (174, 11, 3, 13, 72),
    "cottage": (98, 11, 3, 4, 80), "parmesan": (430, 38, 4, 29, 30), "mozzarella": (300, 22, 2, 22, 50),
    "frozen yogurt": (160, 4, 25, 5, 63), "ice cream": (210, 4, 24, 11, 60),
    # starches / grains
    "rice": (130, 3, 28, 0, 68), "pasta": (370, 13, 75, 2, 10), "bread": (265, 9, 49, 3, 36),
    "flour": (364, 10, 76, 1, 12), "oat": (380, 13, 68, 7, 10), "cereal": (380, 9, 80, 4, 3),
    "cereals": (380, 9, 80, 4, 3), "cheerios": (370, 12, 73, 7, 3), "popcorn": (500, 8, 55, 28, 3),
    "potato": (77, 2, 17, 0, 79), "corn": (86, 3, 19, 1, 76), "noodle": (370, 13, 75, 2, 10),
    "cracker": (430, 9, 70, 12, 4), "chips": (540, 7, 53, 34, 2), "tortilla": (300, 8, 50, 7, 30),
    # legumes / nuts
    "bean": (130, 9, 23, 1, 63), "beans": (130, 9, 23, 1, 63), "lentil": (116, 9, 20, 0, 70),
    "chickpea": (164, 9, 27, 3, 60), "peanut": (567, 26, 16, 49, 6), "almond": (579, 21, 22, 50, 4),
    "nut": (600, 18, 20, 54, 4), "nuts": (600, 18, 20, 54, 4), "seed": (560, 20, 20, 48, 5),
    # vegetables
    "green beans": (31, 2, 7, 0, 90), "spinach": (23, 3, 4, 0, 91), "lettuce": (15, 1, 3, 0, 95),
    "kale": (49, 4, 9, 1, 84), "cabbage": (25, 1, 6, 0, 92), "broccoli": (34, 3, 7, 0, 89),
    "carrot": (41, 1, 10, 0, 88), "onion": (40, 1, 9, 0, 89), "tomato": (18, 1, 4, 0, 94),
    "pepper": (26, 1, 6, 0, 92), "garlic": (149, 6, 33, 1, 59), "mushroom": (22, 3, 3, 0, 92),
    "celery": (16, 1, 3, 0, 95), "cucumber": (15, 1, 4, 0, 95), "squash": (20, 1, 4, 0, 94),
    "zucchini": (17, 1, 3, 0, 95), "vegetable": (30, 2, 6, 0, 90),
    # fruits
    "papaya": (43, 0, 11, 0, 88), "apple": (52, 0, 14, 0, 86), "banana": (89, 1, 23, 0, 75),
    "berry": (50, 1, 12, 0, 85), "orange": (47, 1, 12, 0, 87), "lemon": (29, 1, 9, 0, 89),
    "mango": (60, 1, 15, 0, 83), "grape": (69, 1, 18, 0, 81), "fruit": (55, 1, 14, 0, 85),
    "raisin": (299, 3, 79, 0, 15), "dried": (280, 3, 70, 1, 18),
    # sweets / cocoa / sugar
    "sugar": (387, 0, 100, 0, 0), "honey": (304, 0, 82, 0, 17), "syrup": (260, 0, 67, 0, 32),
    "chocolate": (546, 5, 61, 31, 1), "cocoa": (228, 20, 58, 14, 3), "cocoa butter": (884, 0, 0, 100, 0),
    "candy": (390, 2, 90, 3, 5), "cookie": (480, 5, 65, 22, 4), "cake": (370, 5, 55, 15, 25),
    "jam": (250, 0, 65, 0, 33),
    # spices / condiments / sauces
    "spices": (300, 10, 60, 6, 8), "spice": (300, 10, 60, 6, 8), "ginger": (335, 9, 72, 4, 9),
    "cinnamon": (247, 4, 81, 1, 10), "cumin": (375, 18, 44, 22, 8), "paprika": (282, 14, 54, 13, 11),
    "seasoning": (250, 8, 50, 4, 8), "salt": (0, 0, 0, 0, 0), "sauce": (80, 2, 12, 2, 80),
    "ketchup": (101, 1, 27, 0, 69), "mustard": (60, 4, 6, 3, 83), "vinegar": (20, 0, 1, 0, 94),
    "broth": (5, 1, 0, 0, 97), "stock": (5, 1, 0, 0, 97), "soup": (50, 2, 7, 1, 87),
    "paste": (120, 4, 20, 3, 70), "dressing": (400, 1, 10, 40, 45), "juice": (45, 0, 11, 0, 88),
    "water": (0, 0, 0, 0, 100), "wine": (85, 0, 3, 0, 87), "beer": (43, 0, 4, 0, 92),
    "vanilla": (290, 0, 13, 0, 53),
}

# Modifiers that scale an estimated macro vector (kcal, prot, carb, fat, water multipliers)
_MODIFIERS = {
    "lowfat": (0.8, 1.05, 1.05, 0.4, 1.02), "low-fat": (0.8, 1.05, 1.05, 0.4, 1.02),
    "nonfat": (0.65, 1.1, 1.1, 0.05, 1.04), "fat-free": (0.65, 1.1, 1.1, 0.05, 1.04),
    "skim": (0.6, 1.1, 1.1, 0.05, 1.04), "lean": (0.85, 1.05, 1.0, 0.6, 1.02),
    "dry": (2.5, 2.5, 2.5, 2.5, 0.05), "powder": (2.8, 2.5, 2.8, 1.0, 0.05),
    "dehydrated": (3.0, 3.0, 3.0, 3.0, 0.1), "fried": (1.5, 1.0, 1.2, 2.5, 0.7),
    "sweetened": (1.3, 1.0, 1.6, 1.0, 0.85), "candied": (2.0, 0.6, 2.5, 1.0, 0.3),
    "breaded": (1.3, 0.9, 3.0, 1.4, 0.85), "canned": (1.0, 0.95, 1.05, 1.0, 1.05),
    "cooked": (1.1, 1.15, 1.0, 1.1, 0.9), "roasted": (1.15, 1.15, 1.05, 1.1, 0.85),
    "light": (0.75, 1.0, 1.0, 0.6, 1.05), "reduced": (0.8, 1.0, 1.0, 0.6, 1.03),
    "unsweetened": (0.9, 1.0, 0.8, 1.0, 1.0), "whole": (1.05, 1.0, 1.0, 1.15, 0.98),
}

_PHRASE_KEYS = sorted([k for k in _MACRO_LEXICON if " " in k], key=len, reverse=True)

_STOP = {"g", "the", "a", "an", "of", "and", "or", "for", "with", "from", "in", "to", "made",
         "raw", "fresh", "frozen", "thawed", "drained", "trimmed", "visible", "bagged",
         "regular", "flavor", "flavored", "choice", "select", "boneless", "separable",
         "chopped", "sliced", "diced", "minced", "large", "small", "medium", "tube", "microwave"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|grams?|kg|ml|oz)\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?\s*/\s*\d+\"?", " ", t)
    t = re.sub(r"[^a-z\-\s,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _estimate(text, is_usda):
    """Return (macro vector, confidence) for a food text."""
    t = _clean(text)
    if not t:
        return None, 0.0
    # Position weights: for USDA, the primary food (first comma segment) dominates.
    segments = [s.strip() for s in t.split(",") if s.strip()]
    if not is_usda:
        # recipe text: the head before comma is the food, post-comma is state
        segments = segments[:1] if segments else [t]
    hits = []  # (vector, weight)
    for idx, seg in enumerate(segments):
        seg_w = 1.0 / (1.0 + 0.6 * idx) if is_usda else 1.0
        work = " " + seg + " "
        for ph in _PHRASE_KEYS:
            if " " + ph + " " in work:
                hits.append((_MACRO_LEXICON[ph], seg_w * 3.0))
                work = work.replace(" " + ph + " ", " ")
        tokens = [w for w in work.split() if w not in _STOP]
        n = len(tokens)
        for j, tok in enumerate(tokens):
            base = tok
            if base not in _MACRO_LEXICON and base.endswith("s") and base[:-1] in _MACRO_LEXICON:
                base = base[:-1]
            if base in _MACRO_LEXICON:
                # in recipe text, later nouns are usually the head noun
                pos_w = (0.6 + 0.8 * (j + 1) / n) if not is_usda else 1.0
                hits.append((_MACRO_LEXICON[base], seg_w * pos_w))
    if not hits:
        return None, 0.0
    total = sum(w for _, w in hits)
    vec = [sum(v[i] * w for v, w in hits) / total for i in range(5)]
    # apply modifiers from the full text
    words = set(re.split(r"[\s,]+", t))
    for mod, mult in _MODIFIERS.items():
        if mod in words:
            vec = [vec[i] * mult[i] for i in range(5)]
    vec[4] = min(vec[4], 100.0)
    conf = min(1.0, total / 2.0)
    return vec, conf


def _macro_class(vec):
    kcal, p, c, f, w = vec
    energy = p * 4 + c * 4 + f * 9 + 1e-6
    if f * 9 / energy > 0.8 and kcal > 500:
        return "fat"
    if p * 4 / energy > 0.5:
        return "protein"
    if kcal < 70 and w > 80:
        return "watery-produce"
    if c * 4 / energy > 0.6 and w < 30:
        return "dry-carb"
    if c * 4 / energy > 0.6:
        return "moist-carb"
    return "mixed"


def _same_food(ingredient, usda_match):
    ta = set(_clean(ingredient).replace(",", " ").split()) - _STOP
    tb_all = set(_clean(usda_match).replace(",", " ").split()) - _STOP
    tb = set(_clean(usda_match).split(",")[0].split()) - _STOP
    if not ta or not tb_all:
        return 0.0
    norm = lambda s: set(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in s)
    ta, tb, tb_all = norm(ta), norm(tb), norm(tb_all)
    head_hit = len(ta & tb) / float(len(tb)) if tb else 0.0
    all_hit = len(ta & tb_all) / float(len(ta))
    return 0.5 * head_hit + 0.5 * all_hit


def _macro_similarity(a, b):
    # 1. Log-ratio distance on energy density
    e_diff = abs(math.log((a[0] + 20.0) / (b[0] + 20.0)))
    energy_score = math.exp(-1.6 * e_diff)

    # 2. Energy-share composition distance (protein/carb/fat fractions)
    def shares(v):
        tot = v[1] * 4 + v[2] * 4 + v[3] * 9
        if tot <= 0:
            return (0.0, 0.0, 0.0)
        return (v[1] * 4 / tot, v[2] * 4 / tot, v[3] * 9 / tot)
    sa, sb = shares(a), shares(b)
    comp_score = 1.0 - sum(abs(x - y) for x, y in zip(sa, sb)) / 2.0

    # 3. Absolute gram-level deviation per macro (Gower-like)
    ranges = (40.0, 100.0, 100.0)
    gower = sum(min(1.0, abs(a[i] - b[i]) / ranges[i - 1]) for i in (1, 2, 3)) / 3.0
    gram_score = 1.0 - gower

    # 4. Moisture proximity (fresh vs dry forms)
    water_score = 1.0 - min(1.0, abs(a[4] - b[4]) / 60.0)

    # 5. Macro-class agreement
    class_bonus = 1.0 if _macro_class(a) == _macro_class(b) else 0.0

    raw = (0.27 * energy_score + 0.25 * comp_score + 0.20 * gram_score
           + 0.13 * water_score + 0.15 * class_bonus)
    if energy_score < 0.4 and comp_score < 0.6:
        raw *= 0.6
    return raw


def judging_function(ingredient, usda_match):
    try:
        if not str(ingredient or "").strip() or not str(usda_match or "").strip():
            return 0.0
        a, _ = _estimate(ingredient, False)
        b, _ = _estimate(usda_match, True)
        same = _same_food(ingredient, usda_match)
        if a is None or b is None:
            macro = 0.45  # unknown profile: neutral prior
        else:
            macro = _macro_similarity(a, b)
        # identical food names imply identical macro profiles
        score = 100.0 * (0.6 * macro + 0.4 * same)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
