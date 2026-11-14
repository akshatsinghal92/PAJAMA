import re
import math

# Approximate per-100g macro prototypes: (kcal, protein, carb, fat)
_PROTOTYPES = {
    # pure fats
    "oil": (884, 0, 0, 100), "butter": (717, 1, 0, 81), "lard": (902, 0, 0, 100),
    "ghee": (876, 0, 0, 99), "shortening": (884, 0, 0, 100), "margarine": (717, 0, 1, 80),
    "mayonnaise": (680, 1, 1, 75), "aioli": (650, 1, 3, 70),
    # nuts / seeds
    "nut": (650, 16, 14, 60), "nuts": (650, 16, 14, 60), "almond": (579, 21, 22, 50),
    "seed": (550, 20, 25, 45), "seeds": (550, 20, 25, 45), "flaxseed": (534, 18, 29, 42),
    "linseed": (534, 18, 29, 42), "linseeds": (534, 18, 29, 42), "peanut": (567, 26, 16, 49),
    # meats
    "beef": (250, 26, 0, 15), "pork": (240, 27, 0, 14), "lamb": (280, 25, 0, 20),
    "chicken": (190, 27, 0, 8), "turkey": (170, 28, 0, 6), "bison": (145, 28, 0, 3),
    "buffalo": (145, 28, 0, 3), "ham": (145, 20, 2, 6), "sausage": (300, 13, 2, 27),
    "bacon": (540, 37, 1, 42), "heart": (180, 26, 0, 7), "liver": (165, 26, 4, 5),
    "steak": (230, 27, 0, 13), "ground": (260, 25, 0, 17), "feet": (215, 19, 0, 15),
    "wings": (250, 23, 0, 17), "patty": (260, 16, 10, 18),
    # fish / seafood
    "fish": (150, 22, 0, 6), "salmon": (208, 20, 0, 13), "swordfish": (144, 20, 0, 7),
    "tuna": (130, 29, 0, 1), "cod": (82, 18, 0, 1), "shrimp": (99, 24, 0, 0.3),
    # dairy
    "yogurt": (80, 8, 9, 1), "milk": (60, 3, 5, 3), "cheese": (380, 24, 2, 31),
    "cream": (340, 2, 3, 36), "egg": (143, 13, 1, 10), "eggs": (143, 13, 1, 10),
    # grains / starches
    "cereal": (380, 8, 82, 4), "cereals": (380, 8, 82, 4), "oat": (389, 17, 66, 7),
    "wheat": (340, 11, 75, 2), "rice": (130, 3, 28, 0.3), "bran": (316, 13, 50, 21),
    "flour": (364, 10, 76, 1), "bread": (265, 9, 49, 3), "pasta": (158, 6, 31, 1),
    "corn": (365, 9, 74, 5), "flakes": (357, 7, 84, 0.4), "chips": (520, 6, 60, 28),
    "paper": (330, 6, 80, 0.5), "potato": (77, 2, 17, 0.1), "yam": (118, 1.5, 28, 0.2),
    "beans": (130, 8, 23, 0.5), "lentils": (116, 9, 20, 0.4),
    # sugars / syrups
    "syrup": (280, 0, 76, 0), "syrups": (280, 0, 76, 0), "sugar": (387, 0, 100, 0),
    "honey": (304, 0, 82, 0), "jam": (250, 0, 65, 0), "filling": (100, 0, 26, 0.1),
    "pie": (250, 2, 35, 12),
    # vegetables / fruit
    "radish": (16, 0.7, 3.4, 0.1), "escarole": (17, 1.3, 3.4, 0.2), "lettuce": (15, 1.4, 3, 0.2),
    "spinach": (23, 2.9, 3.6, 0.4), "kale": (49, 4, 9, 0.9), "onion": (40, 1, 9, 0.1),
    "carrot": (41, 1, 10, 0.2), "tomato": (18, 0.9, 3.9, 0.2), "apple": (52, 0.3, 14, 0.2),
    "pomegranate": (83, 1.7, 19, 1.2), "plum": (46, 0.7, 11, 0.3), "peach": (39, 0.9, 10, 0.3),
    "strawberry": (32, 0.7, 8, 0.3), "berry": (50, 0.7, 12, 0.3), "carissa": (62, 0.5, 14, 1.3),
    "banana": (89, 1, 23, 0.3), "garlic": (149, 6, 33, 0.5), "ginger": (80, 1.8, 18, 0.8),
    # sauces / spices
    "sauce": (150, 1, 30, 2), "spices": (300, 10, 60, 5), "paste": (120, 3, 20, 3),
}

# Processing state multipliers on (kcal, protein, carb, fat)
_STATE = {
    "dried": (4.5, 4.5, 4.5, 4.5), "dehydrated": (4.5, 4.5, 4.5, 4.5),
    "fried": (1.4, 1.0, 1.0, 2.5), "toasted": (1.05, 1.03, 1.03, 1.05),
    "roasted": (1.05, 1.05, 1.05, 1.05), "cooked": (0.9, 1.0, 0.9, 1.0),
    "boiled": (0.85, 0.95, 0.85, 0.95), "braised": (1.2, 1.3, 1.0, 1.1),
    "nonfat": (0.7, 1.1, 1.0, 0.05), "lean": (0.75, 1.1, 1.0, 0.45),
    "light": (0.7, 1.0, 1.0, 0.5), "sweetened": (1.3, 1.0, 1.6, 1.0),
    "frozen": (1.0, 1.0, 1.0, 1.0), "raw": (1.0, 1.0, 1.0, 1.0),
}

_FORM_GROUPS = {
    "whole": {"steak", "breast", "fillet", "chop", "whole", "slices", "cubed"},
    "minced": {"ground", "minced", "crushed", "mince"},
}


def _tokens(text):
    text = str(text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", text)
    text = re.sub(r"[^a-z\s,%-]", " ", text)
    return [t for t in re.split(r"[\s,\-]+", text) if t]


def _stem(t):
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("es") and len(t) > 4 and t[-3] in "sxh":
        return t[:-2]
    if t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
        return t[:-1]
    return t


def _macro_vector(tokens):
    vecs = []
    weights = []
    n = len(tokens)
    for i, t in enumerate(tokens):
        proto = _PROTOTYPES.get(t) or _PROTOTYPES.get(_stem(t))
        if proto:
            # earlier tokens (primary food) weigh more for USDA; later for recipe heads
            w = 1.0 + 0.3 * (1.0 - i / max(1, n))
            vecs.append(proto)
            weights.append(w)
    if not vecs:
        return None
    tot = sum(weights)
    v = [sum(vec[k] * w for vec, w in zip(vecs, weights)) / tot for k in range(4)]
    for t in tokens:
        m = _STATE.get(t)
        if m:
            v = [v[k] * m[k] for k in range(4)]
    # clamp to physical range
    v[0] = min(v[0], 900.0)
    for k in range(1, 4):
        v[k] = min(v[k], 100.0)
    return v


def _macro_similarity(a, b):
    # energy proximity on log scale
    e = abs(math.log((a[0] + 5.0) / (b[0] + 5.0)))
    energy_sim = math.exp(-1.3 * e)
    # composition proximity: share of energy from P/C/F
    def shares(v):
        p, c, f = v[1] * 4, v[2] * 4, v[3] * 9
        s = p + c + f
        if s <= 0:
            return (1 / 3.0, 1 / 3.0, 1 / 3.0)
        return (p / s, c / s, f / s)
    sa, sb = shares(a), shares(b)
    l1 = sum(abs(x - y) for x, y in zip(sa, sb)) / 2.0  # 0..1
    comp_sim = 1.0 - l1
    return 0.5 * energy_sim + 0.5 * comp_sim


def judging_function(ingredient, usda_match):
    try:
        ing = _tokens(ingredient)
        usd = _tokens(usda_match)
        if not ing or not usd:
            return 0.0

        ing_set = set(_stem(t) for t in ing)
        usd_set = set(_stem(t) for t in usd)

        va = _macro_vector(ing)
        vb = _macro_vector(usd)
        if va is not None and vb is not None:
            macro = _macro_similarity(va, vb)
        else:
            macro = 0.4  # unknown profile: neutral-low

        # identity anchor: does a known-food token in the ingredient appear in USDA?
        food_ing = {_stem(t) for t in ing if (t in _PROTOTYPES or _stem(t) in _PROTOTYPES)}
        food_usd = {_stem(t) for t in usd if (t in _PROTOTYPES or _stem(t) in _PROTOTYPES)}
        if food_ing:
            anchor = len(food_ing & food_usd) / float(len(food_ing))
        else:
            common = ing_set & usd_set
            anchor = len(common) / float(max(1, len(ing_set)))

        # state mismatch penalty: processing words present on one side only
        state_words = {"dried", "dehydrated", "fried", "toasted", "roasted", "cooked",
                       "boiled", "braised", "frozen", "nonfat", "lean", "sweetened"}
        si = {t for t in ing if t in state_words}
        su = {t for t in usd if t in state_words}
        penalty = 0.0
        heavy = {"dried", "dehydrated", "fried", "toasted", "nonfat", "lean"}
        for t in si ^ su:
            penalty += 0.12 if t in heavy else 0.06
        if ("cooked" in su or "boiled" in su) and "frozen" in si:
            penalty += 0.08

        # form mismatch (ground vs steak etc.)
        fi = {g for g, ws in _FORM_GROUPS.items() if ws & set(ing)}
        fu = {g for g, ws in _FORM_GROUPS.items() if ws & set(usd)}
        if fi and fu and fi != fu:
            penalty += 0.15

        score = 0.55 * macro + 0.45 * anchor - penalty
        score = max(0.0, min(1.0, score))
        return round(score * 100.0, 3)
    except Exception:
        return 0.0
