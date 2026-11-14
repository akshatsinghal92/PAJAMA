import re
import math

# Nutritional Profile Proximity, variant 1: approximate macro lookup table.
# Each side is mapped to an estimated per-100g (kcal, protein, carb, fat)
# vector from an embedded keyword table, adjusted by modifier words that
# shift macros (low fat, fried, dried, sweetened, juice, light meat, skin).
# The score is based on a scaled distance between the two vectors.

_MACROS = {
    # keyword: (kcal, protein, carb, fat)
    "oil": (884, 0, 0, 100), "butter": (717, 1, 0, 81), "margarine": (717, 0, 1, 80),
    "mayonnaise": (680, 1, 1, 75), "lard": (900, 0, 0, 100),
    "chicken": (165, 31, 0, 4), "turkey": (150, 29, 0, 3), "beef": (250, 26, 0, 15),
    "pork": (242, 27, 0, 14), "lamb": (282, 25, 0, 20), "ham": (145, 21, 1, 6),
    "bacon": (540, 37, 1, 42), "sausage": (300, 12, 2, 27), "patty": (240, 15, 8, 16),
    "fish": (130, 22, 0, 4), "swordfish": (144, 20, 0, 7), "salmon": (208, 20, 0, 13),
    "tuna": (130, 28, 0, 1), "shrimp": (99, 24, 0, 0.3), "egg": (143, 13, 1, 10),
    "tofu": (76, 8, 2, 5), "cheese": (400, 25, 1, 33), "cottage": (98, 11, 3, 4),
    "yogurt": (61, 3.5, 5, 3), "milk": (61, 3, 5, 3), "cream": (340, 2, 3, 36),
    "ice": (207, 3.5, 24, 11), "frozen yogurt": (159, 4, 24, 6),
    "rice": (130, 2.7, 28, 0.3), "pasta": (158, 6, 31, 1), "noodle": (138, 4.5, 25, 2),
    "bread": (265, 9, 49, 3), "flour": (364, 10, 76, 1), "oat": (389, 17, 66, 7),
    "cereal": (380, 8, 82, 3), "gnocchi": (133, 3, 30, 0.3), "potato": (93, 2.5, 21, 0.1),
    "corn": (86, 3, 19, 1.2), "bean": (127, 9, 23, 0.5), "lentil": (116, 9, 20, 0.4),
    "pea": (81, 5, 14, 0.4), "spinach": (23, 3, 4, 0.4), "lettuce": (15, 1.4, 3, 0.2),
    "kale": (49, 4, 9, 1), "tomato": (18, 1, 4, 0.2), "onion": (40, 1, 9, 0.1),
    "garlic": (149, 6, 33, 0.5), "carrot": (41, 1, 10, 0.2), "broccoli": (34, 3, 7, 0.4),
    "pepper": (31, 1, 6, 0.3), "mushroom": (22, 3, 3, 0.3), "fruit": (55, 0.7, 14, 0.2),
    "apple": (52, 0.3, 14, 0.2), "banana": (89, 1, 23, 0.3), "berry": (57, 0.7, 14, 0.3),
    "blueberry": (57, 0.7, 14, 0.3), "orange": (47, 1, 12, 0.1), "juice": (45, 0.5, 11, 0.1),
    "guava": (68, 2.6, 14, 1), "avocado": (160, 2, 9, 15),
    "nut": (607, 20, 21, 54), "almond": (579, 21, 22, 50), "peanut": (567, 26, 16, 49),
    "seed": (550, 20, 25, 45), "chia": (486, 17, 42, 31), "flaxseed": (534, 18, 29, 42),
    "sugar": (387, 0, 100, 0), "honey": (304, 0.3, 82, 0), "syrup": (260, 0, 67, 0),
    "chocolate": (546, 5, 61, 31), "candy": (400, 2, 90, 5), "cake": (370, 5, 55, 15),
    "cookie": (480, 5, 65, 22), "chip": (536, 7, 53, 35),
    "dressing": (300, 1, 10, 28), "sauce": (80, 2, 12, 2), "ketchup": (101, 1, 27, 0.1),
    "pesto": (420, 5, 6, 40), "hummus": (166, 8, 14, 10), "gravy": (50, 1, 5, 2),
    "soup": (40, 2, 6, 1), "broth": (7, 1, 0.5, 0.2), "paste": (100, 4, 20, 1),
    "spice": (300, 10, 60, 6), "spices": (300, 10, 60, 6), "ginger": (80, 2, 18, 0.8),
    "vinegar": (20, 0, 1, 0), "water": (0, 0, 0, 0), "coffee": (2, 0.1, 0, 0),
}
_MODS = {
    "fried": (1.35, 1.0, 1.1, 2.2), "breaded": (1.4, 0.9, 1.6, 2.0),
    "dried": (3.5, 3.5, 3.5, 3.5), "dehydrated": (3.5, 3.5, 3.5, 3.5),
    "low": (0.8, 1.05, 1.05, 0.45), "lowfat": (0.75, 1.1, 1.05, 0.4),
    "nonfat": (0.6, 1.15, 1.05, 0.05), "light": (0.85, 1.0, 1.0, 0.6),
    "sweetened": (1.25, 1.0, 1.45, 1.0), "skin": (1.25, 0.95, 1.0, 2.2),
    "reduced": (0.7, 1.0, 1.0, 0.5), "lean": (0.85, 1.05, 1.0, 0.6),
    "cooked": (1.2, 1.2, 1.0, 1.1), "roasted": (1.2, 1.2, 1.0, 1.1),
}


def _estimate(words):
    text = " ".join(words)
    vec = None
    if "frozen yogurt" in text:
        vec = list(_MACROS["frozen yogurt"])
    elif "cottage" in words:
        vec = list(_MACROS["cottage"])
    elif "ice" in words and "cream" in words:
        vec = list(_MACROS["ice"])
    else:
        # take the LAST known food keyword (head-final)
        for w in words:
            key = None
            for cand in (w, w[:-1], w[:-2], w[:-3] + "y" if w.endswith("ies") else ""):
                if len(cand) >= 3 and cand in _MACROS:
                    key = cand
                    break
            if key:
                # "garlic paste": a paste/puree keeps the macros of its source food
                if key == "paste" and vec is not None:
                    continue
                vec = list(_MACROS[key])
    if vec is None:
        return None
    for w in words:
        if w in _MODS:
            m = _MODS[w]
            vec = [v * f for v, f in zip(vec, m)]
    if "not" in words and "skin" in words:
        vec[3] /= 2.2
    return vec


def _distance(a, b):
    # scale each macro to comparable units
    scale = (300.0, 15.0, 30.0, 20.0)
    return math.sqrt(sum(((x - y) / s) ** 2 for x, y, s in zip(a, b, scale)) / 4.0)


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        iw = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", str(usda_match or "").lower())
        if not iw or not uw:
            return 0.0
        # for USDA: primary field first, but head noun inside primary is often first word
        u_fields = [re.findall(r"[a-z]+", f) for f in str(usda_match).lower().split(",")]
        u_order = (u_fields[1] if len(u_fields) > 1 else []) + u_fields[0] + [w for f in u_fields[2:] for w in f]
        vi = _estimate(iw)
        vu = _estimate(u_order) or _estimate(uw)
        if vi is None or vu is None:
            # unknown profile: same named food implies same macros
            shared = set(w.rstrip("s") for w in iw) & set(w.rstrip("s") for w in uw)
            return 7.5 if iw[-1].rstrip("s") in shared else (4.0 if shared else 2.0)
        d = _distance(vi, vu)
        score = 10.0 * math.exp(-1.3 * d)
        # the very same food named in the USDA primary field carries the same
        # macro class even when the keyword table misses its modifiers
        def _sing(w):
            if w.endswith("ies"):
                return w[:-3] + "y"
            if w.endswith("oes") or w.endswith("ches"):
                return w[:-2]
            return w[:-1] if w.endswith("s") and not w.endswith("ss") else w
        forms = {"paste", "sauce", "powder", "fresh", "frozen", "diced", "chopped", "raw"}
        prim = set(_sing(w) for w in u_fields[0]) | set(
            _sing(w) for w in (u_fields[1] if len(u_fields) > 1 else []))
        prim -= forms
        content = [_sing(w) for w in iw if len(w) > 2 and w not in forms]
        if content and content[-1] in prim:
            score = max(score, 6.5) + 1.0
        elif not (set(content) & prim):
            score -= 1.5
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
