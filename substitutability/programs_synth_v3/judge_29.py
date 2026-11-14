import re
import math

# Approximate per-100g macro vectors: (kcal, protein g, carbs g, fat g)
_MACROS = {
    # pure fats
    "oil": (884, 0, 0, 100), "lard": (902, 0, 0, 100), "shortening": (884, 0, 0, 100),
    "butter": (717, 1, 0, 81), "ghee": (876, 0, 0, 99), "margarine": (717, 0, 1, 80),
    "mayonnaise": (680, 1, 1, 75), "tallow": (902, 0, 0, 100),
    # lean / fatty proteins
    "chicken": (165, 31, 0, 4), "turkey": (135, 30, 0, 1), "breast": (120, 23, 0, 2),
    "wing": (203, 30, 0, 8), "wings": (203, 30, 0, 8), "feet": (215, 19, 0, 15),
    "thigh": (209, 26, 0, 11), "beef": (250, 26, 0, 15), "steak": (271, 25, 0, 19),
    "flank": (192, 27, 0, 8), "chuck": (230, 26, 0, 14), "roast": (230, 26, 0, 13),
    "pork": (242, 27, 0, 14), "lamb": (294, 25, 0, 21), "veal": (172, 24, 0, 8),
    "sausage": (300, 13, 2, 27), "bacon": (541, 37, 1, 42), "ham": (145, 21, 1, 6),
    "fish": (130, 22, 0, 4), "swordfish": (144, 20, 0, 7), "salmon": (208, 20, 0, 13),
    "tuna": (132, 28, 0, 1), "cod": (82, 18, 0, 1), "shrimp": (99, 24, 0, 0.3),
    "egg": (143, 13, 1, 10), "eggs": (143, 13, 1, 10), "tofu": (76, 8, 2, 5),
    "patty": (250, 15, 8, 18),
    # dairy
    "milk": (61, 3, 5, 3), "cheese": (400, 25, 1, 33), "cottage": (98, 11, 3, 4),
    "yogurt": (61, 3.5, 5, 3), "cream": (340, 2, 3, 36), "ricotta": (174, 11, 3, 13),
    # grains / starches
    "rice": (130, 2.7, 28, 0.3), "flour": (364, 10, 76, 1), "pasta": (158, 6, 31, 1),
    "bread": (265, 9, 49, 3), "oats": (389, 17, 66, 7), "potato": (77, 2, 17, 0.1),
    "potatoes": (77, 2, 17, 0.1), "noodles": (138, 5, 25, 2), "corn": (86, 3, 19, 1),
    "sugar": (387, 0, 100, 0), "honey": (304, 0, 82, 0), "syrup": (260, 0, 67, 0),
    # vegetables
    "greens": (30, 2, 5, 0.3), "spinach": (23, 3, 4, 0.4), "lettuce": (15, 1, 3, 0.2),
    "kale": (49, 4, 9, 1), "turnip": (28, 1, 6, 0.1), "turnips": (28, 1, 6, 0.1),
    "onion": (40, 1, 9, 0.1), "onions": (40, 1, 9, 0.1), "garlic": (149, 6, 33, 0.5),
    "tomato": (18, 1, 4, 0.2), "tomatoes": (18, 1, 4, 0.2), "carrot": (41, 1, 10, 0.2),
    "carrots": (41, 1, 10, 0.2), "pepper": (31, 1, 6, 0.3), "peppers": (31, 1, 6, 0.3),
    "cabbage": (25, 1, 6, 0.1), "broccoli": (34, 3, 7, 0.4), "mushroom": (22, 3, 3, 0.3),
    "mushrooms": (22, 3, 3, 0.3), "celery": (16, 1, 3, 0.2), "beans": (127, 9, 23, 0.5),
    "olive": (115, 1, 6, 11), "olives": (115, 1, 6, 11), "tapenade": (230, 2, 6, 23),
    "ginger": (80, 2, 18, 1),
    # fruits
    "apple": (52, 0.3, 14, 0.2), "banana": (89, 1, 23, 0.3), "lemon": (29, 1, 9, 0.3),
    # nuts / seeds
    "sesame": (573, 18, 23, 50), "seeds": (560, 20, 20, 48), "almond": (579, 21, 22, 50),
    "almonds": (579, 21, 22, 50), "peanut": (567, 26, 16, 49), "nuts": (607, 20, 21, 54),
    "walnuts": (654, 15, 14, 65),
    # seasonings / condiments
    "salt": (0, 0, 0, 0), "spices": (300, 10, 60, 5), "spice": (300, 10, 60, 5),
    "paste": (120, 3, 20, 3), "sauce": (80, 2, 12, 2), "vinegar": (18, 0, 1, 0),
    "ketchup": (101, 1, 27, 0.1), "mustard": (60, 4, 6, 3), "water": (0, 0, 0, 0),
    "broth": (5, 1, 0.5, 0.2), "stock": (5, 1, 0.5, 0.2), "seasoning": (250, 8, 50, 4),
}

# Modifiers that scale the four macros (kcal, protein, carbs, fat)
_MODIFIERS = {
    "lowfat": (0.75, 1.05, 1.0, 0.4), "low-fat": (0.75, 1.05, 1.0, 0.4),
    "nonfat": (0.6, 1.1, 1.05, 0.05), "fat-free": (0.6, 1.1, 1.05, 0.05),
    "skim": (0.6, 1.1, 1.05, 0.05),
    "reduced": (0.85, 1.0, 0.95, 0.8), "light": (0.8, 1.0, 1.0, 0.6),
    "dried": (2.8, 2.8, 2.8, 2.8), "dehydrated": (2.8, 2.8, 2.8, 2.8),
    "powder": (2.5, 2.5, 2.5, 2.5), "fried": (1.4, 1.0, 1.1, 2.2),
    "breaded": (1.3, 0.9, 3.0, 1.4), "sweetened": (1.3, 1.0, 1.6, 1.0),
    "kernel": (1.0, 1.0, 1.0, 1.0),
}

_STOP = {"and", "or", "with", "of", "the", "a", "to", "taste", "for", "from", "in",
         "raw", "fresh", "frozen", "sliced", "chopped", "diced", "minced", "thawed",
         "trimmed", "visible", "fat", "boneless", "choice", "select", "uncooked",
         "unprepared", "cooked", "boiled", "no", "added", "table", "refined",
         "separable", "tube", "spread", "large", "small", "medium"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b", " ", t)
    t = re.sub(r"\d+/\d+\"?", " ", t)
    return t


def _tokens(text):
    return re.findall(r"[a-z][a-z\-]*", text)


def _component_vector(tokens):
    """Average macro vector over recognized food tokens, then apply modifiers."""
    hits = [_MACROS[t] for t in tokens if t in _MACROS]
    if not hits:
        return None
    vec = [sum(h[i] for h in hits) / len(hits) for i in range(4)]
    for t in tokens:
        if t in _MODIFIERS:
            m = _MODIFIERS[t]
            vec = [vec[i] * m[i] for i in range(4)]
    return vec


def _profile(text, split_compounds):
    """Return (macro_vector, n_components, coverage)."""
    t = _clean(text)
    # parenthetical content counts as weaker info: keep it, but separately
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    main = re.sub(r"\([^)]*\)", " ", t)
    if split_compounds:
        main_core = main.split(",")[0]
        parts = [p for p in re.split(r"\band\b|&|\bwith\b|\bplus\b", main_core) if p.strip()]
    else:
        parts = [main]
    comps = []
    covered = 0
    total = 0
    for p in parts:
        toks = _tokens(p)
        total += len([x for x in toks if x not in _STOP])
        covered += len([x for x in toks if x in _MACROS])
        v = _component_vector(toks)
        if v is not None:
            comps.append(v)
    if not comps and paren:
        v = _component_vector(_tokens(paren))
        if v is not None:
            comps.append(v)
    if not comps:
        return None, 0, 0.0
    vec = [sum(c[i] for c in comps) / len(comps) for i in range(4)]
    cov = covered / total if total else 0.0
    return vec, len(comps), cov


def _macro_distance(a, b):
    """Scaled distance between two macro vectors, in roughly [0, ~3]."""
    # scale: kcal by 900, protein by 35, carbs by 100, fat by 100
    scales = (900.0, 35.0, 100.0, 100.0)
    weights = (1.0, 1.2, 1.0, 1.3)
    d = 0.0
    for i in range(4):
        diff = (a[i] - b[i]) / scales[i]
        d += weights[i] * diff * diff
    abs_d = math.sqrt(d)
    # relative component: compare energy share proportions
    def shares(v):
        p, c, f = v[1] * 4, v[2] * 4, v[3] * 9
        s = p + c + f
        if s <= 0:
            return (0.0, 0.0, 0.0)
        return (p / s, c / s, f / s)
    sa, sb = shares(a), shares(b)
    rel = sum(abs(sa[i] - sb[i]) for i in range(3)) / 2.0
    return abs_d + 0.8 * rel


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0

        ing_vec, ing_n, ing_cov = _profile(ing, split_compounds=True)
        usda_vec, usda_n, usda_cov = _profile(usda, split_compounds=False)

        ing_toks = set(_tokens(_clean(re.sub(r"\([^)]*\)", " ", ing)))) - _STOP
        usda_toks = set(_tokens(_clean(usda))) - _STOP
        # crude singular folding
        fold = lambda s: {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in s}
        fi, fu = fold(ing_toks), fold(usda_toks)
        overlap = len(fi & fu) / max(1, len(fi))

        # head noun of the ingredient (last content word before any comma) found in USDA
        core0 = re.sub(r"\([^)]*\)", " ", _clean(ing).split(",")[0])
        head_toks = [w for w in _tokens(core0) if w not in _STOP]
        head = fold({head_toks[-1]}) if head_toks else set()
        primary_hit = 1.0 if (head and head & fu) else 0.0

        if ing_vec is None or usda_vec is None:
            # unknown macro class: lexical estimate of same-food-ness
            score = 10.0 + 45.0 * overlap + 25.0 * primary_hit
        else:
            dist = _macro_distance(ing_vec, usda_vec)
            macro_sim = math.exp(-2.2 * dist)  # 1 when identical
            score = 50.0 * macro_sim + 25.0 * overlap + 15.0 * primary_hit

        # compound ingredient whose components are not all reflected in the USDA entry
        core = re.sub(r"\([^)]*\)", " ", _clean(ing).split(",")[0])
        parts = [p for p in re.split(r"\band\b|&|\bwith\b|\bplus\b", core) if p.strip()]
        if len(parts) > 1:
            missing = 0
            for p in parts:
                pt = fold(set(_tokens(p)) - _STOP)
                if pt and not (pt & fu):
                    missing += 1
            score -= 12.0 * missing

        # fat-level qualifier present on only one side shifts fat/protein balance
        fat_q = {"lowfat", "low-fat", "nonfat", "fat-free", "skim", "reduced", "light", "lactose"}
        if (usda_toks & fat_q) and not (ing_toks & fat_q):
            score -= 10.0
        if (ing_toks & fat_q) and not (usda_toks & fat_q):
            score -= 6.0

        # source-variety tokens that change fatty-acid profile (e.g. palm vs palm kernel)
        variety = {"kernel", "germ", "bran", "hull"}
        if (usda_toks & variety) and not (ing_toks & variety):
            score -= 25.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
