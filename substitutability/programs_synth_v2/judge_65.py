import re

# Culinary Role Interchangeability, variant 1: functional-role vectors with
# Ruzicka (weighted Jaccard) similarity.
# Each food is described by the FUNCTIONS it can serve in a dish with a
# strength 0..1: binder, sauteing fat, baking fat, bulk vegetable, aromatic,
# sweetener, thickener, acid, leavening, main protein, starch base,
# cooking liquid, creamy body, crunch/topping, seasoning, gelling.
# Form words modulate the functions (ground flax binds, whole chia gels,
# juice loses bulk, dried spice keeps seasoning but loses aromatic bulk).
# Similarity = sum(min) / sum(max) over the function vectors.

_F = ("binder", "saute_fat", "bake_fat", "bulk_veg", "aromatic", "sweetener", "thickener",
      "acid", "leaven", "protein", "starch", "liquid", "creamy", "crunch", "season", "gel")
_FOOD = {
    "egg": {"binder": 1.0, "leaven": 0.4, "protein": 0.6},
    "oil": {"saute_fat": 1.0, "bake_fat": 0.6},
    "butter": {"saute_fat": 0.8, "bake_fat": 1.0, "creamy": 0.4},
    "margarine": {"saute_fat": 0.7, "bake_fat": 0.9},
    "lard": {"saute_fat": 0.9, "bake_fat": 0.9},
    "garlic": {"aromatic": 1.0, "season": 0.5}, "onion": {"aromatic": 0.9, "bulk_veg": 0.5},
    "shallot": {"aromatic": 1.0}, "ginger": {"aromatic": 0.9, "season": 0.6},
    "tomato": {"bulk_veg": 0.8, "acid": 0.5, "liquid": 0.3}, "carrot": {"bulk_veg": 1.0},
    "corn": {"bulk_veg": 0.8, "starch": 0.4, "sweetener": 0.2}, "potato": {"starch": 0.9, "bulk_veg": 0.6, "thickener": 0.3},
    "spinach": {"bulk_veg": 1.0}, "broccoli": {"bulk_veg": 1.0}, "pepper": {"bulk_veg": 0.8, "aromatic": 0.3},
    "mushroom": {"bulk_veg": 0.9}, "celery": {"bulk_veg": 0.7, "aromatic": 0.5}, "zucchini": {"bulk_veg": 1.0},
    "sugar": {"sweetener": 1.0}, "honey": {"sweetener": 1.0, "liquid": 0.3},
    "syrup": {"sweetener": 1.0, "liquid": 0.4}, "jam": {"sweetener": 0.8, "gel": 0.5},
    "flour": {"thickener": 0.8, "starch": 0.6, "binder": 0.4},
    "cornstarch": {"thickener": 1.0}, "starch": {"thickener": 1.0},
    "chia": {"gel": 1.0, "binder": 0.6, "crunch": 0.4}, "flaxseed": {"binder": 0.9, "gel": 0.5},
    "flax": {"binder": 0.9, "gel": 0.5}, "seed": {"crunch": 0.8}, "nut": {"crunch": 1.0},
    "almond": {"crunch": 1.0}, "walnut": {"crunch": 1.0}, "peanut": {"crunch": 0.9},
    "lemon": {"acid": 1.0, "aromatic": 0.3}, "lime": {"acid": 1.0}, "vinegar": {"acid": 1.0},
    "baking": {"leaven": 1.0}, "yeast": {"leaven": 1.0},
    "chicken": {"protein": 1.0}, "turkey": {"protein": 1.0}, "beef": {"protein": 1.0},
    "pork": {"protein": 1.0}, "fish": {"protein": 1.0}, "swordfish": {"protein": 1.0},
    "salmon": {"protein": 1.0}, "shrimp": {"protein": 1.0}, "tofu": {"protein": 0.9},
    "bean": {"protein": 0.5, "starch": 0.5, "bulk_veg": 0.4}, "lentil": {"protein": 0.5, "starch": 0.5},
    "rice": {"starch": 1.0}, "pasta": {"starch": 1.0}, "noodle": {"starch": 1.0}, "gnocchi": {"starch": 1.0},
    "bread": {"starch": 0.8, "binder": 0.3}, "oat": {"starch": 0.6, "binder": 0.5, "thickener": 0.3},
    "cereal": {"starch": 0.5, "crunch": 0.8},
    "milk": {"liquid": 1.0, "creamy": 0.4}, "cream": {"creamy": 1.0, "liquid": 0.5, "bake_fat": 0.3},
    "yogurt": {"creamy": 0.8, "acid": 0.4}, "cheese": {"creamy": 0.6, "protein": 0.4, "season": 0.3},
    "cottage": {"creamy": 0.7, "protein": 0.5}, "broth": {"liquid": 1.0, "season": 0.3},
    "stock": {"liquid": 1.0, "season": 0.3}, "water": {"liquid": 1.0}, "juice": {"liquid": 0.8, "sweetener": 0.4, "acid": 0.3},
    "fruit": {"sweetener": 0.4, "bulk_veg": 0.6}, "banana": {"sweetener": 0.5, "binder": 0.5, "bulk_veg": 0.4},
    "apple": {"bulk_veg": 0.6, "sweetener": 0.4}, "berry": {"bulk_veg": 0.5, "sweetener": 0.4},
    "guava": {"bulk_veg": 0.5, "sweetener": 0.5},
    "spice": {"season": 1.0}, "salt": {"season": 1.0}, "cinnamon": {"season": 1.0}, "cumin": {"season": 1.0},
    "paprika": {"season": 1.0}, "herb": {"season": 0.8, "aromatic": 0.3},
    "sauce": {"liquid": 0.6, "season": 0.6, "creamy": 0.3}, "dressing": {"acid": 0.5, "saute_fat": 0.2, "season": 0.6},
    "paste": {"season": 0.6, "thickener": 0.3}, "pesto": {"season": 0.8, "saute_fat": 0.3},
}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _vector(words):
    v = dict.fromkeys(_F, 0.0)
    base = None
    for w in words:
        s = _sing(w)
        if s in _FOOD:
            base = s
    if base is None:
        return None, None
    for k, x in _FOOD[base].items():
        v[k] = x
    ws = set(words)
    # form modulation
    if ws & {"ground", "powder", "dried", "spices"} and base not in ("beef", "pork", "turkey", "chicken"):
        v["season"] = max(v["season"], 0.8)
        v["aromatic"] *= 0.5
        v["bulk_veg"] *= 0.2
        if base in ("flaxseed", "flax"):
            v["binder"] = 1.0
    if "juice" in ws and base != "juice":
        v["bulk_veg"] *= 0.1
        v["liquid"] = max(v["liquid"], 0.9)
    if ws & {"paste", "puree"} and base not in ("paste",):
        v["bulk_veg"] *= 0.3
        v["season"] = max(v["season"], 0.6)
    if ws & {"sauce", "dressing"} and base not in ("sauce", "dressing"):
        v["bulk_veg"] *= 0.2
        v["liquid"] = max(v["liquid"], 0.5)
    if ws & {"fried", "breaded"}:
        v["crunch"] = max(v["crunch"], 0.5)
    if ws & {"frozen"} and ws & {"yogurt", "cream"}:
        v["creamy"] *= 0.5
        v["sweetener"] = max(v["sweetener"], 0.7)
    return v, base


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        # USDA: qualifier after a 1-word header names the specific food
        order = fields[0] + (fields[1] if len(fields[0]) == 1 and len(fields) > 1 else [])
        all_u = [w for f in fields for w in f]
        vi, bi = _vector(iw)
        vu, bu = _vector(order)
        if vu is not None:
            vu2, _ = _vector(order + [w for w in all_u if w not in order])
            vu = vu2 or vu
        if vi is None or vu is None:
            head = _sing(iw[-1])
            return 6.5 if head in {_sing(w) for w in order} else 3.0
        num = sum(min(vi[k], vu[k]) for k in _F)
        den = sum(max(vi[k], vu[k]) for k in _F)
        sim = num / den if den else 0.0
        return round(10.0 * sim, 3)
    except Exception:
        return 0.0
