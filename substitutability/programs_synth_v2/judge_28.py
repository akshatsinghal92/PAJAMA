import re

# Nutritional Profile Proximity, variant 4: Atwater energy + tolerance bands.
# Each food gets (protein, carb, fat) grams per 100 g from a group table;
# energy is derived with Atwater factors (4/4/9). The two profiles are
# compared through discrete tolerance bands, like a dietitian would:
#   energy within 15% / 35% / 70%; each macro within 3 g / 8 g / 20 g;
#   same dominant energy source (protein, carb, or fat).
# Points from the bands are summed into a 0-100 score.

_GROUP_PCF = [
    (("olive", "canola", "vegetable", "sesame", "coconut", "sunflower", "oil", "lard", "ghee"), (0, 0, 100)),
    (("butter", "margarine"), (1, 0, 81)),
    (("mayonnaise", "aioli"), (1, 1, 75)),
    (("bacon", "salami", "pepperoni", "chorizo"), (30, 1, 40)),
    (("sausage", "hotdog", "frankfurter", "patty", "burger"), (14, 4, 22)),
    (("beef", "pork", "lamb", "veal", "steak", "duck"), (26, 0, 15)),
    (("chicken", "turkey", "breast", "poultry"), (29, 0, 5)),
    (("swordfish", "salmon", "trout", "mackerel", "sardine"), (21, 0, 9)),
    (("fish", "cod", "tilapia", "tuna", "shrimp", "crab", "scallop", "lobster"), (22, 0, 1.5)),
    (("egg", "eggs"), (13, 1, 10)),
    (("tofu", "tempeh"), (10, 3, 6)),
    (("cottage", "ricotta", "quark"), (11, 3.5, 4)),
    (("cheddar", "parmesan", "mozzarella", "swiss", "gouda", "cheese"), (25, 2, 32)),
    (("yogurt", "yoghurt", "kefir", "milk"), (3.5, 5, 3)),
    (("cream",), (2, 3, 35)),
    (("almond", "walnut", "pecan", "cashew", "peanut", "hazelnut", "pistachio", "nut", "nuts"), (20, 20, 52)),
    (("chia", "flaxseed", "flax", "sesame", "sunflower", "pumpkin", "seed", "seeds"), (19, 30, 40)),
    (("bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "hummus"), (8, 21, 1)),
    (("flour", "cereal", "cereals", "oats", "oatmeal", "granola", "cracker", "crackers"), (10, 72, 5)),
    (("bread", "bagel", "roll", "tortilla", "pita", "bun"), (9, 49, 3)),
    (("rice", "pasta", "noodle", "noodles", "spaghetti", "macaroni", "couscous", "gnocchi", "quinoa"), (4, 28, 1)),
    (("potato", "potatoes", "yam", "sweet potato"), (2, 20, 0.1)),
    (("corn", "peas", "pea"), (3.3, 18, 1.2)),
    (("spinach", "lettuce", "kale", "arugula", "chard", "cabbage", "greens"), (2.5, 4, 0.4)),
    (("tomato", "tomatoes", "cucumber", "zucchini", "celery", "pepper", "peppers", "broccoli",
      "cauliflower", "carrot", "carrots", "onion", "onions", "mushroom", "mushrooms", "squash"), (1.5, 7, 0.3)),
    (("garlic", "shallot"), (6, 33, 0.5)),
    (("juice", "nectar", "lemonade", "soda"), (0.5, 11, 0.1)),
    (("banana", "apple", "berries", "blueberries", "strawberries", "orange", "grape", "grapes",
      "mango", "peach", "pear", "fruit", "guava", "melon", "pineapple", "cherries"), (0.8, 14, 0.3)),
    (("avocado",), (2, 9, 15)),
    (("sugar", "honey", "syrup", "molasses", "candy", "candies", "jam", "jelly"), (0, 80, 0)),
    (("chocolate",), (5, 60, 31)),
    (("dressing", "vinaigrette"), (0.5, 10, 30)),
    (("pesto",), (5, 6, 40)),
    (("ketchup", "sauce", "salsa", "gravy", "paste"), (2, 15, 1.5)),
    (("broth", "stock", "bouillon", "consomme"), (1, 0.5, 0.3)),
    (("soup", "chowder", "stew"), (3, 7, 2)),
    (("spices", "spice", "cinnamon", "cumin", "paprika", "nutmeg", "turmeric", "ginger", "seasoning"), (10, 60, 7)),
]
_FAT_DOWN = {"low": 0.5, "lowfat": 0.4, "nonfat": 0.05, "skim": 0.05, "light": 0.6, "reduced": 0.6, "lean": 0.6}


def _lookup(words):
    found = None
    for w in words:
        for keys, pcf in _GROUP_PCF:
            if w in keys:
                found = pcf          # last match wins (head-final)
                break
    return found


def _modify(pcf, words):
    p, c, f = pcf
    for w in words:
        if w in _FAT_DOWN:
            f *= _FAT_DOWN[w]
    if set(words) & {"fried", "breaded", "battered"}:
        f += 10
        c += 6 if set(words) & {"breaded", "battered"} else 0
    if set(words) & {"dried", "dehydrated"}:
        p, c, f = p * 3.5, c * 3.5, f * 3.5
    if set(words) & {"sweetened", "candied", "frosted"}:
        c += 12
    return p, c, f


def _dominant(p, c, f):
    e = {"p": 4 * p, "c": 4 * c, "f": 9 * f}
    return max(e, key=e.get)


def _band(diff, tight, mid, wide, pts):
    if diff <= tight:
        return pts
    if diff <= mid:
        return pts * 0.6
    if diff <= wide:
        return pts * 0.25
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        usda = str(usda_match or "").lower()
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in usda.split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        uw = [w for f in fields for w in f]
        order = (fields[1] + fields[0]) if len(fields) > 1 and len(fields[0]) == 1 else fields[0]
        bi = _lookup(iw)
        bu = _lookup(order) or _lookup(uw)
        if bi is None or bu is None:
            head = iw[-1].rstrip("s")
            return 65.0 if any(w.rstrip("s") == head for w in order) else 25.0
        p1, c1, f1 = _modify(bi, iw)
        p2, c2, f2 = _modify(bu, uw)
        e1 = 4 * p1 + 4 * c1 + 9 * f1
        e2 = 4 * p2 + 4 * c2 + 9 * f2
        rel = abs(e1 - e2) / max(e1, e2, 1.0)
        score = _band(rel, 0.15, 0.35, 0.70, 30.0)
        score += _band(abs(p1 - p2), 3, 8, 20, 18.0)
        score += _band(abs(c1 - c2), 3, 8, 20, 18.0)
        score += _band(abs(f1 - f2), 3, 8, 20, 18.0)
        if _dominant(p1, c1, f1) == _dominant(p2, c2, f2):
            score += 16.0
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
