import re
import math

# Culinary Role Interchangeability, variant 5: dish-usage context profiles.
# Two items are interchangeable in a recipe when they are USED in the same
# kinds of dishes in the same way. Each food class is given a usage profile
# over dish contexts (saute base, roast/main, salad, soup/stew, baking,
# dessert, breakfast, dressing/marinade, garnish/topping, beverage/smoothie,
# snack, sandwich/spread). Form words reshape the profile (juice -> beverage,
# ground spice -> seasoning in baking/soup, sauce -> dressing/marinade,
# frozen dessert -> dessert). Profiles are compared by cosine similarity,
# and a usage-specific penalty applies when the dominant contexts differ.

_CTX = ("saute", "main", "salad", "soup", "baking", "dessert", "breakfast", "dressing",
        "garnish", "beverage", "snack", "spread")
_PROFILES = {
    "aromatic":   {"saute": 1.0, "soup": 0.8, "main": 0.5, "dressing": 0.4},
    "veg":        {"salad": 0.8, "soup": 0.8, "saute": 0.6, "main": 0.5},
    "fruit":      {"dessert": 0.7, "breakfast": 0.8, "snack": 0.8, "salad": 0.4, "baking": 0.5, "beverage": 0.3},
    "protein":    {"main": 1.0, "saute": 0.5, "soup": 0.4, "salad": 0.3, "sandwich": 0.0},
    "processed_protein": {"main": 0.6, "spread": 0.3, "snack": 0.5, "breakfast": 0.3},
    "starch":     {"main": 0.9, "soup": 0.4, "salad": 0.3, "breakfast": 0.2},
    "cereal":     {"breakfast": 1.0, "snack": 0.6, "baking": 0.3},
    "oil":        {"saute": 1.0, "dressing": 0.8, "baking": 0.4},
    "solid_fat":  {"baking": 1.0, "saute": 0.6, "spread": 0.6},
    "sweetener":  {"baking": 1.0, "dessert": 0.8, "beverage": 0.4, "breakfast": 0.4},
    "dairy_soft": {"breakfast": 0.7, "dessert": 0.4, "spread": 0.4, "dressing": 0.3, "baking": 0.4},
    "cheese":     {"main": 0.5, "garnish": 0.7, "snack": 0.6, "spread": 0.4, "baking": 0.3},
    "frozen_dessert": {"dessert": 1.0, "snack": 0.4},
    "spice":      {"baking": 0.6, "soup": 0.7, "main": 0.6, "saute": 0.4},
    "herb_fresh": {"garnish": 1.0, "salad": 0.6, "saute": 0.3, "dressing": 0.4},
    "nut_seed":   {"garnish": 0.8, "baking": 0.7, "snack": 0.8, "breakfast": 0.6, "salad": 0.4},
    "sauce":      {"dressing": 1.0, "main": 0.4, "spread": 0.4, "garnish": 0.3},
    "liquid":     {"soup": 1.0, "beverage": 0.6, "main": 0.3},
    "juice":      {"beverage": 1.0, "dressing": 0.3, "breakfast": 0.3},
    "binder":     {"baking": 1.0, "breakfast": 0.5},
}
_WORD_CLASS = {}
for _c, _ws in {
    "aromatic": "garlic onion shallot leek ginger scallion", "veg": "tomato carrot broccoli spinach kale cabbage pepper zucchini squash celery mushroom corn eggplant pea bean lentil cucumber lettuce",
    "fruit": "fruit apple banana berry blueberry strawberry orange mango peach pear grape guava ugli",
    "protein": "chicken turkey beef pork lamb fish swordfish salmon tuna cod shrimp tofu steak",
    "processed_protein": "patty sausage ham bacon nugget frankfurter salami",
    "starch": "rice pasta noodle gnocchi potato quinoa couscous bread", "cereal": "cereal granola oat",
    "oil": "oil", "solid_fat": "butter lard margarine shortening ghee", "sweetener": "sugar honey syrup molasses jam",
    "dairy_soft": "yogurt cottage ricotta cream milk", "cheese": "cheese cheddar parmesan mozzarella",
    "spice": "spice cinnamon cumin paprika nutmeg turmeric salt seasoning", "herb_fresh": "basil parsley cilantro dill mint chive",
    "nut_seed": "nut almond walnut peanut cashew pecan seed chia flaxseed sesame", "sauce": "sauce dressing ketchup mustard mayonnaise pesto gravy salsa paste",
    "liquid": "broth stock soup water", "juice": "juice", "binder": "egg",
}.items():
    for _w in _ws.split():
        _WORD_CLASS[_w] = _c
_FORM_NOUNS = {"paste", "juice", "sauce", "seed", "oil"}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _profile(words):
    cls, base = None, None
    for i, w in enumerate(words):
        s = _sing(w)
        if s not in _WORD_CLASS:
            continue
        if s in _FORM_NOUNS and cls is not None and s != "juice":
            # a form noun after a food keeps the food's class but reshapes usage
            if s in ("paste", "sauce"):
                cls = "sauce"
            continue
        cls, base = _WORD_CLASS[s], s
        if s == "cheese" and i > 0 and words[i - 1] == "cottage":
            cls = "dairy_soft"
    if cls is None:
        return None
    ws = set(words)
    if "juice" in ws and cls in ("fruit", "veg"):
        cls = "juice"
    if ws & {"ground", "powder", "spices", "dried"} and cls in ("aromatic", "herb_fresh"):
        cls = "spice"
    if "frozen" in ws and ("yogurt" in ws or "cream" in ws):
        cls = "frozen_dessert"
    if ws & {"ice"} and "cream" in ws:
        cls = "frozen_dessert"
    vec = dict.fromkeys(_CTX, 0.0)
    for k, v in _PROFILES[cls].items():
        if k in vec:
            vec[k] = v
    return vec


def _cos(a, b):
    dot = sum(a[k] * b[k] for k in _CTX)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing.split(",")[0])
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        order = fields[0] + (fields[1] if len(fields[0]) == 1 and len(fields) > 1 else [])
        extra = [w for f in fields for w in f if w not in order]
        pi = _profile(iw)
        pu = _profile(order + extra)
        if fields[0] in (["spices"], ["spice"]):
            pu = dict.fromkeys(_CTX, 0.0)
            pu.update(_PROFILES["spice"])
        if pi is None or pu is None:
            same = _sing(iw[-1]) in {_sing(w) for w in order}
            return 65.0 if same else 25.0
        c = _cos(pi, pu)
        top_i = max(pi, key=pi.get)
        top_u = max(pu, key=pu.get)
        score = 100.0 * c
        if top_i != top_u and pu[top_i] < 0.5:
            score *= 0.8
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
