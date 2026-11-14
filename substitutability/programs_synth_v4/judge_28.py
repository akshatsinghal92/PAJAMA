import re
import math

# Two-level taxonomy: fine subcategory -> (coarse category, keyword weights)
_TAXONOMY = {
    "red_meat":      ("meat", {"beef": 3, "lamb": 3, "pork": 3, "veal": 3, "mutton": 3, "venison": 3,
                               "steak": 2, "chuck": 2, "sirloin": 2, "roast": 1, "brisket": 2, "loin": 1,
                               "rib": 1, "goat": 2, "bison": 3}),
    "poultry":       ("meat", {"chicken": 3, "turkey": 3, "duck": 3, "goose": 3, "quail": 3,
                               "poultry": 3, "breast": 1, "thigh": 1, "drumstick": 2, "wing": 1}),
    "organ":         ("meat", {"liver": 3, "giblets": 3, "kidney": 3, "heart": 2, "tongue": 2,
                               "tripe": 3, "variety": 1, "offal": 3, "gizzard": 3}),
    "cured_meat":    ("meat", {"sausage": 3, "ham": 3, "bacon": 3, "salami": 3, "cervelat": 3,
                               "bologna": 3, "pepperoni": 3, "luncheon": 2, "deli": 2, "frankfurter": 3,
                               "chorizo": 3, "prosciutto": 3, "hot dog": 3}),
    "fish":          ("seafood", {"fish": 3, "herring": 3, "salmon": 3, "tuna": 3, "cod": 3,
                                  "pollock": 3, "trout": 3, "sardine": 3, "anchovy": 3, "halibut": 3,
                                  "tilapia": 3, "mackerel": 3, "fillet": 1, "fillets": 1, "haddock": 3}),
    "shellfish":     ("seafood", {"lobster": 3, "crab": 3, "shrimp": 3, "crayfish": 3, "prawn": 3,
                                  "clam": 3, "mussel": 3, "oyster": 3, "scallop": 3, "squid": 3}),
    "cheese":        ("dairy", {"cheese": 3, "queso": 3, "cheddar": 3, "mozzarella": 3, "parmesan": 3,
                                "asadero": 3, "feta": 3, "ricotta": 3, "brie": 3}),
    "milk_cream":    ("dairy", {"milk": 3, "cream": 2, "yogurt": 3, "kefir": 3, "buttermilk": 3,
                                "dairy": 2, "half and half": 3}),
    "leafy_veg":     ("produce", {"escarole": 3, "lettuce": 3, "spinach": 3, "kale": 3, "chard": 3,
                                  "arugula": 3, "cabbage": 3, "endive": 3, "greens": 2, "collards": 3}),
    "veg":           ("produce", {"squash": 3, "asparagus": 3, "beans snap": 3, "carrot": 3, "onion": 3,
                                  "potato": 3, "tomato": 3, "pepper": 2, "broccoli": 3, "zucchini": 3,
                                  "celery": 3, "cucumber": 3, "eggplant": 3, "vegetable": 2, "snap": 2,
                                  "pumpkin": 3, "mushroom": 3, "corn": 2, "pea": 1, "peas": 2}),
    "fruit":         ("produce", {"apple": 3, "banana": 3, "berry": 3, "berries": 3, "orange": 3,
                                  "lemon": 3, "lime": 3, "grape": 3, "peach": 3, "pear": 3, "mango": 3,
                                  "fruit": 2, "cherry": 3, "cherries": 3, "plum": 3}),
    "flour_starch":  ("grain", {"flour": 3, "starch": 3, "meal": 1, "cornstarch": 3, "semolina": 3}),
    "bread_baked":   ("grain", {"bread": 3, "toast": 2, "crackers": 3, "cracker": 3, "bun": 3,
                                "roll": 1, "bagel": 3, "tortilla": 3, "muffin": 3, "biscuit": 3}),
    "grain_whole":   ("grain", {"rice": 3, "oats": 3, "barley": 3, "quinoa": 3, "amaranth": 2,
                                "wheat": 2, "millet": 3, "bulgur": 3, "grain": 2}),
    "pasta":         ("grain", {"pasta": 3, "spaghetti": 2, "noodle": 3, "noodles": 3, "macaroni": 3,
                                "penne": 3, "linguine": 3}),
    "legume":        ("legume", {"lentil": 3, "lentils": 3, "chickpea": 3, "chickpeas": 3,
                                 "beans": 2, "bean": 2, "soy": 2, "tofu": 3, "peanut": 1, "garbanzo": 3}),
    "nut_seed":      ("nut_seed", {"pecan": 3, "pecans": 3, "almond": 3, "walnut": 3, "cashew": 3,
                                   "flaxseed": 3, "flaxseeds": 3, "seed": 2, "seeds": 2, "sesame": 3,
                                   "chia": 3, "pistachio": 3, "hazelnut": 3, "nut": 2, "nuts": 2}),
    "spice_herb":    ("spice_herb", {"spice": 3, "spices": 3, "ginger": 2, "cinnamon": 3, "cumin": 3,
                                     "paprika": 3, "oregano": 3, "basil": 3, "thyme": 3, "garlic": 2,
                                     "pepper black": 3, "nutmeg": 3, "herb": 3, "herbs": 3, "ground": 0.5}),
    "oil_fat":       ("oil_fat", {"oil": 3, "butter": 2, "lard": 3, "shortening": 3, "margarine": 3,
                                  "ghee": 3, "fat": 1, "tallow": 3}),
    "sweetener":     ("sweetener", {"sugar": 3, "honey": 3, "syrup": 3, "molasses": 3, "agave": 3,
                                    "sweetener": 3, "chocolate": 1, "cocoa": 1}),
    "sauce_cond":    ("condiment", {"sauce": 3, "dressing": 3, "ketchup": 3, "mustard": 3,
                                    "mayonnaise": 3, "vinegar": 3, "salsa": 3, "relish": 3, "paste": 1,
                                    "gravy": 3}),
    "soup_dish":     ("prepared", {"soup": 3, "entree": 3, "dinner": 2, "casserole": 3, "stew": 1,
                                   "pizza": 3, "sandwich": 3, "with": 0.5, "frozen entree": 3}),
    "beverage":      ("beverage", {"tea": 3, "coffee": 3, "juice": 2, "drink": 3, "beverage": 3,
                                   "brewed": 2, "soda": 3, "hot chocolate": 3, "mix": 1}),
    "egg":           ("egg", {"egg": 3, "eggs": 3, "yolk": 3, "whites": 2}),
}

# Coarse-level affinity: plausibly interchangeable coarse pairs
_COARSE_AFFINITY = {
    frozenset(["meat", "seafood"]): 0.15,
    frozenset(["legume", "nut_seed"]): 0.25,
    frozenset(["produce", "legume"]): 0.15,
    frozenset(["sweetener", "beverage"]): 0.05,
    frozenset(["condiment", "prepared"]): 0.10,
    frozenset(["oil_fat", "dairy"]): 0.15,
}

# Form markers: physical state changing texture/appearance even in same category
_FORM_GROUPS = {
    "ground_powder": {"ground", "powder", "powdered", "flour", "meal", "dry mix"},
    "whole": {"whole"},
    "butter_paste": {"butter", "paste", "spread"},
    "cooked": {"cooked", "broiled", "roasted", "baked", "fried", "grilled", "toasted", "boiled", "steamed"},
    "raw": {"raw", "uncooked", "fresh"},
}

_PREP_NOISE = {"chopped", "diced", "sliced", "minced", "shredded", "grated", "trimmed", "divided",
               "optional", "thawed", "of", "visible", "the", "and", "or", "a", "to", "for", "strong",
               "lean", "fresh", "large", "small", "medium", "nfs", "ns", "as", "major", "separable",
               "choice", "prepackaged", "reduced", "sodium", "calorie", "by", "products"}


def _normalize(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)\b", " ", t)
    t = re.sub(r"\d+(?:\.\d+)?\s*%", " ", t)
    t = re.sub(r"[^a-z,/ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _token_set(text):
    toks = re.findall(r"[a-z]+", text)
    out = set(toks)
    for i in range(len(toks) - 1):
        out.add(toks[i] + " " + toks[i + 1])
    return out


def _category_distribution(text, head_weight_tokens):
    """Return dict fine_cat -> probability, using keyword voting with
    extra weight for tokens appearing in the head (primary) phrase."""
    toks = _token_set(text)
    votes = {}
    for fine, (_coarse, kws) in _TAXONOMY.items():
        s = 0.0
        for kw, w in kws.items():
            if kw in toks or (" " in kw and kw in text):
                boost = 2.0 if kw in head_weight_tokens else 1.0
                s += w * boost
        if s > 0:
            votes[fine] = s
    total = sum(votes.values())
    if total <= 0:
        return {}
    # Sharpen distribution (softmax-like on log votes)
    sharp = {k: v ** 1.5 for k, v in votes.items()}
    z = sum(sharp.values())
    return {k: v / z for k, v in sharp.items()}


def _coarse_of(dist):
    out = {}
    for fine, p in dist.items():
        c = _TAXONOMY[fine][0]
        out[c] = out.get(c, 0.0) + p
    return out


def _bhattacharyya(p, q):
    keys = set(p) | set(q)
    return sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in keys)


def _coarse_affinity(pc, qc):
    s = 0.0
    for a, pa in pc.items():
        for b, qb in qc.items():
            if a == b:
                s += pa * qb
            else:
                s += pa * qb * _COARSE_AFFINITY.get(frozenset([a, b]), 0.0)
    return s


def _forms(text):
    toks = _token_set(text)
    found = set()
    for g, words in _FORM_GROUPS.items():
        for w in words:
            if w in toks or (" " in w and w in text):
                found.add(g)
    return found


def _content_tokens(text):
    return {t for t in re.findall(r"[a-z]+", text) if len(t) > 2 and t not in _PREP_NOISE}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = _normalize(ingredient)
        usda = _normalize(usda_match)
        if not ing or not usda:
            return 0.0

        ing_main = ing.split(",")[0].strip()
        usda_head = usda.split(",")[0].strip()
        ing_head_toks = _token_set(ing_main)
        usda_head_toks = _token_set(usda_head)

        p = _category_distribution(ing, ing_head_toks)
        q = _category_distribution(usda, usda_head_toks)

        # 1) Category consistency (core signal)
        if p and q:
            fine_sim = _bhattacharyya(p, q)
            coarse_sim = _coarse_affinity(_coarse_of(p), _coarse_of(q))
            cat_score = 0.55 * fine_sim + 0.45 * min(1.0, coarse_sim)
        elif p or q:
            cat_score = 0.3  # one side unknown
        else:
            cat_score = 0.35

        # Hard penalty: USDA is a prepared dish/soup while ingredient is not
        usda_prepared = any(_TAXONOMY[f][0] == "prepared" for f in q if q[f] > 0.25)
        ing_prepared = any(_TAXONOMY[f][0] == "prepared" for f in p if p[f] > 0.25)
        dish_pen = 0.35 if (usda_prepared and not ing_prepared) else 0.0

        # 2) Identity anchor: does the specific food name carry over (stemmed overlap)
        ic = {_stem(t) for t in _content_tokens(ing)}
        uc = {_stem(t) for t in _content_tokens(usda)}
        ic_main = {_stem(t) for t in _content_tokens(ing_main)}
        inter = ic & uc
        anchor = len(ic_main & uc) / max(1, len(ic_main))
        jacc = len(inter) / max(1, len(ic | uc))

        # 3) Form consistency within category (whole vs ground, butter vs nut, raw vs cooked)
        fi, fu = _forms(ing), _forms(usda)
        form_pen = 0.0
        conflicts = [("ground_powder", "whole"), ("butter_paste", None), ("cooked", "raw")]
        if ("whole" in fi and "ground_powder" in fu) or ("ground_powder" in fi and "whole" in fu):
            form_pen += 0.25
        if ("butter_paste" in fi) != ("butter_paste" in fu):
            form_pen += 0.2
        if ("cooked" in fi and "raw" in fu) or ("raw" in fi and "cooked" in fu):
            form_pen += 0.2
        if "cooked" in fi and "cooked" not in fu and "raw" not in fu and "toasted" in ing:
            form_pen += 0.15

        # Extra unmatched USDA descriptors that likely alter the item
        extra = uc - ic
        extra_pen = min(0.2, 0.04 * len(extra))

        raw = (
            0.50 * cat_score
            + 0.30 * anchor
            + 0.20 * jacc
            - dish_pen
            - form_pen
            - extra_pen
        )
        # Cross-category gating: if category similarity is very low, cap the score
        if p and q and cat_score < 0.15:
            raw = min(raw, 0.1)

        score = 10.0 / (1.0 + math.exp(-6.0 * (raw - 0.35)))
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
