import re

# Culinary Role Interchangeability, variant 3: behavioural property profile
# compared with a weighted Gower distance.
# Whether two foods can play the same role depends on how they BEHAVE in the
# pan or bowl. Each food is profiled on mixed-type properties:
#   moisture (0-1), fat (0-1), sugar (0-1), structure (holds shape 0-1),
#   melts (bool), gels (bool), binds (bool), aroma (0-1 volatile flavour),
#   particle (ordinal: 0 liquid, 1 paste, 2 ground, 3 pieces, 4 whole)
# Base profiles come from food classes; form words modify them. Gower
# distance averages per-property normalised differences (numeric: |a-b|/
# range, bool/ordinal: mismatch), with weights reflecting how strongly each
# property drives a recipe change. Score = 10 * (1 - distance).

_PROPS = ("moisture", "fat", "sugar", "structure", "melts", "gels", "binds", "aroma", "particle")
_WEIGHT = {"moisture": 1.0, "fat": 1.2, "sugar": 1.0, "structure": 1.2, "melts": 0.8,
           "gels": 0.9, "binds": 1.0, "aroma": 1.1, "particle": 1.3}
_RANGE = {"particle": 4.0}

_CLASS = {
    "aromatic":  dict(moisture=0.7, fat=0.0, sugar=0.1, structure=0.4, melts=0, gels=0, binds=0, aroma=1.0, particle=4),
    "vegetable": dict(moisture=0.9, fat=0.0, sugar=0.15, structure=0.7, melts=0, gels=0, binds=0, aroma=0.3, particle=4),
    "fruit":     dict(moisture=0.85, fat=0.0, sugar=0.6, structure=0.5, melts=0, gels=0, binds=0, aroma=0.5, particle=4),
    "starchy":   dict(moisture=0.6, fat=0.0, sugar=0.05, structure=0.8, melts=0, gels=0, binds=0, aroma=0.1, particle=4),
    "meat":      dict(moisture=0.7, fat=0.25, sugar=0.0, structure=0.9, melts=0, gels=0, binds=0, aroma=0.3, particle=4),
    "liquidfat": dict(moisture=0.0, fat=1.0, sugar=0.0, structure=0.0, melts=1, gels=0, binds=0, aroma=0.2, particle=0),
    "solidfat":  dict(moisture=0.15, fat=0.85, sugar=0.0, structure=0.3, melts=1, gels=0, binds=0, aroma=0.3, particle=4),
    "sweet":     dict(moisture=0.1, fat=0.0, sugar=1.0, structure=0.0, melts=1, gels=0, binds=0, aroma=0.2, particle=2),
    "seedgel":   dict(moisture=0.05, fat=0.35, sugar=0.0, structure=0.6, melts=0, gels=1, binds=1, aroma=0.1, particle=4),
    "seedmeal":  dict(moisture=0.05, fat=0.4, sugar=0.0, structure=0.2, melts=0, gels=0, binds=1, aroma=0.2, particle=2),
    "nut":       dict(moisture=0.05, fat=0.55, sugar=0.05, structure=0.9, melts=0, gels=0, binds=0, aroma=0.3, particle=4),
    "dairysoft": dict(moisture=0.75, fat=0.2, sugar=0.05, structure=0.2, melts=1, gels=0, binds=0, aroma=0.2, particle=1),
    "cheese":    dict(moisture=0.4, fat=0.35, sugar=0.0, structure=0.6, melts=1, gels=0, binds=1, aroma=0.4, particle=4),
    "egg":       dict(moisture=0.75, fat=0.1, sugar=0.0, structure=0.1, melts=0, gels=1, binds=1, aroma=0.1, particle=0),
    "spice":     dict(moisture=0.05, fat=0.05, sugar=0.05, structure=0.0, melts=0, gels=0, binds=0, aroma=0.9, particle=2),
    "liquid":    dict(moisture=0.95, fat=0.02, sugar=0.1, structure=0.0, melts=0, gels=0, binds=0, aroma=0.2, particle=0),
    "sauce":     dict(moisture=0.7, fat=0.2, sugar=0.15, structure=0.0, melts=0, gels=0, binds=0, aroma=0.6, particle=1),
    "flour":     dict(moisture=0.1, fat=0.02, sugar=0.0, structure=0.0, melts=0, gels=1, binds=1, aroma=0.0, particle=2),
}
_FOOD2CLASS = {}
for _cls, _words in {
    "aromatic": "garlic onion shallot leek ginger scallion chili",
    "vegetable": "tomato carrot broccoli spinach kale cabbage pepper zucchini squash celery mushroom corn eggplant pea cucumber lettuce",
    "fruit": "fruit apple banana berry blueberry strawberry orange mango peach pear grape guava ugli lemon lime",
    "starchy": "potato rice pasta noodle gnocchi bread oat cereal quinoa couscous bean lentil",
    "meat": "chicken turkey beef pork lamb fish swordfish salmon tuna cod shrimp tofu ham sausage bacon patty",
    "liquidfat": "oil", "solidfat": "butter lard margarine ghee shortening",
    "sweet": "sugar honey syrup molasses jam jelly candy",
    "seedgel": "chia", "seedmeal": "flaxseed flax", "nut": "nut almond walnut peanut cashew pecan seed",
    "dairysoft": "yogurt cream cottage ricotta", "cheese": "cheese cheddar mozzarella parmesan",
    "egg": "egg", "spice": "spice cinnamon cumin paprika nutmeg turmeric oregano thyme basil salt seasoning",
    "liquid": "milk broth stock water juice soup", "sauce": "sauce dressing ketchup mustard mayonnaise pesto gravy paste salsa",
    "flour": "flour cornstarch starch",
}.items():
    for _w in _words.split():
        _FOOD2CLASS[_w] = _cls
_FORMLIKE = {"paste", "juice", "powder", "sauce", "seed", "oil", "soup"}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _profile(words):
    base = None
    for i, w in enumerate(words):
        s = _sing(w)
        if s in _FOOD2CLASS:
            if s in _FORMLIKE and base is not None:
                continue
            base = s
            if s == "cheese" and i > 0 and words[i - 1] == "cottage":
                base = "cottage"
    if base is None:
        return None
    p = dict(_CLASS[_FOOD2CLASS[base]])
    ws = set(words)
    if ws & {"paste", "puree", "mashed", "creamed"}:
        p["particle"], p["structure"] = 1, 0.1
    if ws & {"juice"} and base != "juice":
        p.update(particle=0, structure=0.0, moisture=0.95)
    if ws & {"ground", "powder", "spices"} and _FOOD2CLASS[base] not in ("meat",):
        p.update(particle=2, structure=0.0, moisture=0.05)
        if base in ("flaxseed", "flax"):
            p["binds"] = 1
    if ws & {"chopped", "diced", "sliced", "minced", "shredded", "cubed"}:
        p["particle"] = min(p["particle"], 3)
    if ws & {"dried", "dehydrated"}:
        p["moisture"] = 0.1
    if ws & {"fried", "breaded"}:
        p["fat"] = min(1.0, p["fat"] + 0.25)
    if "frozen" in ws and base in ("yogurt", "cream"):
        p.update(sugar=0.5, structure=0.5, particle=4)
    if ws & {"sweetened", "syrup"}:
        p["sugar"] = min(1.0, p["sugar"] + 0.3)
    return p


def _gower(a, b):
    num = den = 0.0
    for k in _PROPS:
        w = _WEIGHT[k]
        if k in ("melts", "gels", "binds"):
            d = 0.0 if a[k] == b[k] else 1.0
        else:
            d = abs(a[k] - b[k]) / _RANGE.get(k, 1.0)
        num += w * d
        den += w
    return num / den


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
        rest = [w for f in fields for w in f if w not in order]
        pi = _profile(iw)
        pu = _profile(order + rest) if _profile(order) is not None else _profile(order + rest)
        if pi is None or pu is None:
            same = _sing(iw[-1]) in {_sing(w) for w in order}
            return 6.5 if same else 2.5
        # squared to spread the scale: small behavioural gaps stay near 10,
        # several mismatching properties drop quickly
        return round(10.0 * (1.0 - _gower(pi, pu)) ** 2, 3)
    except Exception:
        return 0.0
