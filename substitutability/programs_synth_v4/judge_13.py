import re
import math

# Approximate per-100g macro vectors: (kcal, protein, carb, fat, water-ish share)
_MACRO_LEXICON = {
    # lean proteins / seafood
    "crayfish": (77, 16, 0, 1), "shrimp": (85, 20, 0, 1), "crab": (85, 18, 0, 1),
    "lobster": (90, 19, 0, 1), "pollock": (92, 19, 0, 1), "cod": (82, 18, 0, 1),
    "fish": (110, 20, 0, 3), "salmon": (180, 20, 0, 11), "tuna": (130, 28, 0, 1),
    "chicken": (165, 25, 0, 6), "turkey": (150, 25, 0, 5), "breast": (150, 27, 0, 3),
    "liver": (135, 20, 4, 5), "giblets": (150, 22, 2, 6), "kidney": (100, 17, 1, 3),
    "beef": (220, 26, 0, 13), "steak": (200, 27, 0, 10), "lamb": (250, 24, 0, 17),
    "pork": (240, 25, 0, 15), "duck": (330, 19, 0, 28), "veal": (170, 24, 0, 7),
    "egg": (150, 13, 1, 10), "tofu": (120, 10, 4, 7), "fuyu": (115, 8, 5, 8),
    "sufu": (115, 8, 5, 8),
    # processed meats
    "frankfurter": (290, 11, 3, 26), "sausage": (300, 13, 2, 27), "bacon": (450, 13, 1, 42),
    "patty": (250, 15, 8, 17), "salami": (380, 22, 2, 31),
    # dairy
    "milk": (60, 3, 5, 3), "yogurt": (85, 5, 13, 1), "cheese": (380, 24, 2, 31),
    "cottage": (90, 11, 4, 3), "butter": (717, 1, 0, 81), "cream": (340, 2, 3, 36),
    # fats / oils
    "oil": (884, 0, 0, 100), "lard": (900, 0, 0, 100), "margarine": (717, 0, 1, 80),
    # sugars / sweet
    "sugar": (387, 0, 100, 0), "honey": (304, 0, 82, 0), "syrup": (260, 0, 67, 0),
    "chocolate": (546, 5, 61, 31), "candy": (400, 2, 90, 5),
    # grains / starches
    "cereal": (380, 8, 80, 4), "cereals": (380, 8, 80, 4), "flour": (364, 10, 76, 1),
    "rice": (130, 3, 28, 0), "pasta": (370, 13, 75, 2), "bread": (265, 9, 49, 3),
    "oats": (389, 17, 66, 7), "taco": (220, 10, 22, 10), "tortilla": (300, 8, 50, 7),
    "potato": (77, 2, 17, 0),
    # legumes / nuts
    "beans": (340, 21, 60, 1), "broadbeans": (340, 26, 58, 2), "favas": (340, 26, 58, 2),
    "fava": (340, 26, 58, 2), "lentils": (350, 25, 60, 1), "chickpeas": (360, 19, 61, 6),
    "nuts": (650, 15, 15, 60), "nut": (650, 15, 15, 60), "hazelnut": (628, 15, 17, 61),
    "hazelnuts": (628, 15, 17, 61), "brazil": (659, 14, 12, 67), "almond": (579, 21, 22, 50),
    "almonds": (579, 21, 22, 50), "walnut": (654, 15, 14, 65), "peanut": (567, 26, 16, 49),
    # vegetables
    "squash": (40, 1, 10, 0), "chard": (19, 2, 4, 0), "spinach": (23, 3, 4, 0),
    "radish": (16, 1, 3, 0), "tomato": (18, 1, 4, 0), "carrot": (41, 1, 10, 0),
    "onion": (40, 1, 9, 0), "snap": (31, 2, 7, 0), "green": (30, 2, 6, 0),
    "lettuce": (15, 1, 3, 0), "cabbage": (25, 1, 6, 0), "olives": (115, 1, 6, 11),
    "olive": (115, 1, 6, 11), "pepper": (30, 1, 6, 0), "garlic": (149, 6, 33, 0),
    "juice": (45, 1, 10, 0),
    # fruits
    "raspberries": (52, 1, 12, 1), "berries": (55, 1, 13, 0), "banana": (89, 1, 23, 0),
    "apple": (52, 0, 14, 0), "tangerines": (53, 1, 13, 0), "clementine": (47, 1, 12, 0),
    "mandarin": (53, 1, 13, 0), "orange": (47, 1, 12, 0), "oranges": (47, 1, 12, 0),
    # sauces / spices
    "sauce": (70, 2, 10, 2), "marinara": (60, 2, 9, 2), "ketchup": (100, 1, 26, 0),
    "spices": (300, 10, 60, 5), "ginger": (335, 9, 72, 4), "salt": (0, 0, 0, 0),
}

_STATE_MODIFIERS = {
    # multiplier on energy density (kcal, protein, carb, fat)
    "dried": 3.5, "dehydrated": 3.5, "dry": 3.0, "powder": 3.5, "ground": 1.0,
    "canned": 1.0, "fried": 1.4, "lowfat": 0.7, "light": 0.75, "nonfat": 0.55,
    "skim": 0.6, "reduced": 0.8, "sweetened": 1.2, "unsweetened": 0.95,
}

_UNIT_RE = re.compile(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b\.?\s*", re.I)
_TOKEN_RE = re.compile(r"[a-z]+")


def _clean(text):
    text = str(text or "").lower()
    text = _UNIT_RE.sub("", text)
    text = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", text)
    return text


def _stem(tok):
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("es") and not tok.endswith("ses"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _macro_vector(tokens):
    """Weighted blend of known macro vectors; earlier/primary foods weigh more."""
    acc = [0.0, 0.0, 0.0, 0.0]
    total_w = 0.0
    hits = 0
    for i, tok in enumerate(tokens):
        vec = _MACRO_LEXICON.get(tok) or _MACRO_LEXICON.get(_stem(tok))
        if vec is None:
            continue
        w = 1.0 / (1.0 + 0.35 * i)
        hits += 1
        total_w += w
        for k in range(4):
            acc[k] += w * vec[k]
    if total_w == 0:
        return None, 0
    vec = [a / total_w for a in acc]
    mult = 1.0
    for tok in tokens:
        if tok in _STATE_MODIFIERS:
            mult *= _STATE_MODIFIERS[tok]
    mult = max(0.4, min(mult, 4.0))
    # density multiplier affects energy/macros; fat tweaks for lowfat
    vec = [vec[0] * mult, vec[1] * mult, vec[2] * mult, vec[3] * (mult if mult >= 1 else mult * mult)]
    return vec, hits


def _macro_distance(a, b):
    # normalize: kcal by 900, macros by 100; compute shares too
    da = [a[0] / 900.0, a[1] / 100.0, a[2] / 100.0, a[3] / 100.0]
    db = [b[0] / 900.0, b[1] / 100.0, b[2] / 100.0, b[3] / 100.0]
    absd = math.sqrt(sum((x - y) ** 2 for x, y in zip(da, db)))
    # compositional (share) distance
    sa = sum(a[1:]) or 1.0
    sb = sum(b[1:]) or 1.0
    shares = math.sqrt(sum((x / sa - y / sb) ** 2 for x, y in zip(a[1:], b[1:])))
    # log ratio of energy density
    er = abs(math.log((a[0] + 10.0) / (b[0] + 10.0)))
    return absd, shares, er


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_tokens = _TOKEN_RE.findall(ing)
        usda_tokens = _TOKEN_RE.findall(usda)
        if not ing_tokens or not usda_tokens:
            return 0.0

        # Primary USDA food: first comma segment carries most weight; reorder so
        # USDA primary tokens appear first, then descriptors.
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_ordered = []
        for part in usda_parts:
            usda_ordered.extend(_TOKEN_RE.findall(part))

        # For ingredient, the head noun tends to be last in the pre-comma part.
        ing_main = ing.split(",")[0]
        ing_main_tokens = _TOKEN_RE.findall(ing_main)
        ing_ordered = list(reversed(ing_main_tokens)) + _TOKEN_RE.findall(",".join(ing.split(",")[1:]))

        va, ha = _macro_vector(ing_ordered)
        vb, hb = _macro_vector(usda_ordered)

        # Lexical identity signal (shared stems) used as a fallback/support
        sa = set(_stem(t) for t in ing_tokens if len(t) > 2)
        sb = set(_stem(t) for t in usda_tokens if len(t) > 2)
        overlap = len(sa & sb) / float(max(1, min(len(sa), len(sb))))

        if va is None or vb is None:
            # No macro knowledge: lean on identity overlap only, centered
            return round(max(0.0, min(10.0, 2.0 + 6.0 * overlap)), 3)

        absd, shares, er = _macro_distance(va, vb)
        proximity = math.exp(-(1.6 * absd + 1.1 * shares + 0.9 * er))  # 0..1

        # Class-swing penalties: oil vs whole food, sauce vs raw veg, mixed dish
        penalty = 0.0
        ing_set, usda_set = set(ing_tokens), set(usda_tokens)
        if "oil" in usda_set and "oil" not in ing_set:
            penalty += 2.5
        if ("sauce" in usda_set) != ("sauce" in ing_set or "marinara" in ing_set):
            penalty += 1.0
        if usda_match and re.match(r"^\s*[A-Z][A-Z ']{3,}", str(usda_match)):
            penalty += 1.5  # branded restaurant/mixed dish
        if ("dried" in ing_set) != ("dried" in usda_set or "dry" in usda_set or "mature" in usda_set):
            penalty += 0.8
        cooked_words = {"cooked", "baked", "boiled", "roasted", "simmered", "grilled", "fried"}
        if (ing_set & cooked_words) and not (usda_set & cooked_words):
            penalty += 0.4
        if (usda_set & cooked_words) and not (ing_set & cooked_words):
            penalty += 0.9

        score = 10.0 * (0.65 * proximity + 0.35 * overlap) - penalty
        confidence = min(1.0, (ha + hb) / 3.0)
        score = confidence * score + (1 - confidence) * (2.0 + 6.0 * overlap)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
