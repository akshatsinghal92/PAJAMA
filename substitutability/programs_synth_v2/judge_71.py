import re

# Culinary Role Interchangeability, variant 7: fuzzy-rule inference.
# Three crisp inputs are estimated from the texts:
#   F = function agreement (same role class 1.0, sibling roles 0.5, else 0)
#   S = shape/texture agreement (same physical form 1.0, cuttable 0.8, ...)
#   M = moisture agreement (1 - |moisture difference|)
# They are fuzzified with triangular membership functions (low/med/high),
# a small Mamdani rule base combines them (min for AND, max for OR), and the
# output (poor / fair / good / excellent on 0..10) is defuzzified by the
# centroid of the clipped output sets.

_ROLE = {
    "aromatic": "garlic onion shallot leek ginger scallion chili",
    "bulkveg": "tomato carrot broccoli spinach kale cabbage pepper zucchini squash celery mushroom corn eggplant pea cucumber lettuce",
    "fruit": "fruit apple banana berry blueberry strawberry orange mango peach pear grape guava ugli",
    "protein": "chicken turkey beef pork lamb fish swordfish salmon tuna cod shrimp tofu steak patty",
    "starch": "rice pasta noodle gnocchi potato quinoa couscous bread cereal oat",
    "fat": "oil butter lard margarine ghee shortening",
    "sweetener": "sugar honey syrup molasses jam",
    "binder": "egg chia flaxseed flax",
    "thickener": "flour cornstarch starch arrowroot",
    "creamy": "yogurt cottage ricotta cream milk cheese",
    "seasoning": "spice cinnamon cumin paprika nutmeg turmeric salt seasoning oregano",
    "crunch": "nut almond walnut peanut cashew pecan",
    "sauce": "sauce dressing ketchup mustard mayonnaise pesto gravy salsa",
    "liquid": "broth stock soup water juice",
}
_W2R = {w: r for r, ws in _ROLE.items() for w in ws.split()}
_SIBLINGS = [{"aromatic", "seasoning"}, {"bulkveg", "fruit"}, {"binder", "thickener"},
             {"creamy", "fat"}, {"sauce", "liquid"}, {"starch", "bulkveg"}, {"sauce", "seasoning"}]
_FORM_NOUNS = {"paste", "juice", "sauce", "seed", "powder"}
_MOISTURE = {"liquid": 0.95, "sauce": 0.7, "paste": 0.5, "ground": 0.05, "whole": 0.75,
             "pieces": 0.75, "gel": 0.6, "fat": 0.0, "formed": 0.6}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _role(words):
    r = None
    for w in words:
        s = _sing(w)
        if s in _FORM_NOUNS and r is not None:
            continue
        if s in _W2R:
            r = _W2R[s]
    return r


def _form(words):
    ws = set(words)
    if ws & {"juice", "broth", "stock", "milk", "water"}:
        return "liquid"
    if ws & {"sauce", "dressing", "gravy", "pesto"}:
        return "sauce"
    if ws & {"paste", "puree", "mashed", "creamed", "jam"}:
        return "paste"
    if ws & {"oil", "butter", "lard", "margarine"}:
        return "fat"
    if ws & {"ground", "powder", "flour", "spices"} and not ws & {"beef", "turkey", "pork", "chicken"}:
        return "ground"
    if "chia" in ws:
        return "gel"
    if ws & {"patty", "patties", "nuggets", "breaded", "battered", "loaf"}:
        return "formed"
    if ws & {"chopped", "diced", "sliced", "minced", "cubed", "shredded", "segmented"}:
        return "pieces"
    return "whole"


def _tri(x, a, b, c):
    if x <= a or x >= c:
        return 1.0 if (x == b == a or x == b == c) else 0.0
    return (x - a) / (b - a) if x < b else (c - x) / (c - b)


def _fuzz(x):
    return {"low": _tri(x, -0.01, 0.0, 0.5), "med": _tri(x, 0.2, 0.5, 0.8), "high": _tri(x, 0.5, 1.0, 1.01)}


_OUT = {"poor": (0.0, 1.5, 3.5), "fair": (2.5, 4.5, 6.5), "good": (5.5, 7.0, 8.5), "excellent": (7.5, 9.5, 10.0)}


def _defuzz(strengths):
    num = den = 0.0
    for i in range(101):
        x = i / 10.0
        mu = 0.0
        for name, (a, b, c) in _OUT.items():
            if strengths.get(name, 0.0) <= 0:
                continue
            m = _tri(x, a, b, c) if not (name == "excellent" and x >= b) else 1.0
            mu = max(mu, min(m, strengths[name]))
        num += x * mu
        den += mu
    return num / den if den else 0.0


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
        uw = [w for f in fields for w in f]
        ri, ru = _role(iw), _role(order)
        if fields[0] in (["spices"], ["spice"]):
            ru = "seasoning"
        if ru in ("fruit", "bulkveg") and "juice" in uw:
            ru = "liquid"
        if ri is None or ru is None:
            same = _sing(iw[-1]) in {_sing(w) for w in order}
            F = 0.8 if same else 0.15
        elif ri == ru:
            F = 1.0
        elif any({ri, ru} <= s for s in _SIBLINGS):
            F = 0.5
        else:
            F = 0.0
        fi, fu = _form(iw), _form(uw)
        if fi == fu:
            S = 1.0
        elif fi == "pieces" and fu == "whole":
            S = 1.0          # the cook cuts a whole item: shape is recoverable
        elif {fi, fu} == {"whole", "pieces"}:
            S = 0.7          # already cut when the recipe needs it whole
        elif "formed" in (fi, fu) and {fi, fu} <= {"formed", "whole", "pieces"}:
            S = 0.3          # formed/processed product vs intact food
        elif {fi, fu} <= {"paste", "sauce", "liquid"} or {fi, fu} == {"ground", "gel"}:
            S = 0.5
        else:
            S = 0.15
        M = 1.0 - abs(_MOISTURE[fi] - _MOISTURE[fu])
        f, s, m = _fuzz(F), _fuzz(S), _fuzz(M)
        rules = {
            "excellent": min(f["high"], s["high"], max(m["high"], m["med"])),
            "good": max(min(f["high"], s["med"]), min(f["high"], s["high"], m["low"]), min(f["med"], s["high"])),
            "fair": max(min(f["high"], s["low"]), min(f["med"], s["med"]), min(f["med"], s["low"])),
            "poor": f["low"],
        }
        return round(_defuzz(rules), 3)
    except Exception:
        return 0.0
