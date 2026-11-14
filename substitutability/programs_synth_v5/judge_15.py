import re
import math

# keyword -> (kcal, protein, carb, fat) per 100g, rough estimates
MACRO = [
    (("oil", "lard", "shortening", "tallow", "ghee"), (880, 0, 0, 100)),
    (("butter", "margarine"), (720, 1, 0, 80)),
    (("mayonnaise", "aioli", "mayo"), (690, 1, 3, 75)),
    (("sugar", "syrup", "honey", "molasses", "jam", "jelly"), (320, 0, 80, 0)),
    (("nut", "nuts", "almond", "walnut", "pecan", "cashew", "pistachio", "peanut", "hazelnut"), (610, 18, 18, 52)),
    (("seed", "seeds", "flaxseed", "linseed", "sesame", "chia"), (540, 20, 25, 42)),
    (("cereal", "cereals", "cheerios", "flakes", "oat", "oats", "granola"), (380, 9, 77, 5)),
    (("flour", "wheat", "rice", "corn", "pasta", "noodle", "noodles", "bread", "barley", "bran", "quinoa", "cracker", "chips"), (350, 9, 72, 3)),
    (("beef", "pork", "lamb", "bison", "buffalo", "veal", "steak", "sirloin", "ham", "bacon", "sausage", "venison"), (220, 20, 0, 15)),
    (("chicken", "turkey", "duck"), (190, 20, 0, 11)),
    (("fish", "salmon", "tuna", "swordfish", "cod", "shrimp", "tilapia", "trout", "crab", "lobster"), (140, 22, 0, 5)),
    (("egg", "eggs"), (145, 12, 1, 10)),
    (("yogurt", "yoghurt", "milk", "kefir"), (65, 5, 7, 1.5)),
    (("cheese", "cheddar", "mozzarella", "parmesan"), (350, 22, 2, 28)),
    (("cream",), (250, 2, 4, 25)),
    (("bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "pea", "peas", "tofu", "soy"), (120, 8, 20, 1)),
    (("potato", "potatoes", "yam", "cassava", "taro", "sweet"), (90, 2, 20, 0.2)),
    (("spinach", "kale", "lettuce", "escarole", "arugula", "cabbage", "chard", "greens", "celery", "cucumber", "radish", "broccoli", "cauliflower", "tomato", "pepper", "onion", "carrot", "zucchini", "mushroom", "mushrooms"), (25, 2, 5, 0.3)),
    (("apple", "pear", "peach", "plum", "grape", "berry", "berries", "strawberry", "orange", "banana", "mango", "pomegranate", "cherry", "melon", "pineapple", "fruit", "carissa", "lemon", "lime"), (55, 0.7, 14, 0.3)),
    (("sauce", "ketchup", "dressing", "salsa", "paste", "broth", "stock", "soup"), (80, 2, 12, 3)),
    (("spice", "spices", "ginger", "cinnamon", "cumin", "paprika", "turmeric", "oregano", "basil", "pepper", "seasoning", "garlic"), (280, 11, 55, 6)),
]
STATE_FLAGS = {
    "dried": 1, "dry": 1, "dehydrated": 1, "powder": 1,
    "cooked": 2, "boiled": 2, "baked": 2, "fried": 2, "roasted": 2, "braised": 2, "toasted": 2,
    "canned": 3, "pie": 4, "filling": 4, "sauce": 4, "juice": 5, "paste": 4,
    "frozen": 0, "raw": 0, "fresh": 0,
}
NOISE = set("g kg ml oz lb for with without and or of the a in to from fresh large small medium chopped diced sliced minced crushed cubed thawed grated peeled ground whole regular plain".split())


def _clean(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\s*", "", s)
    return s


def _tokens(s):
    return [t for t in re.findall(r"[a-z]+", s)]


def _vec(tokens, head_first=False):
    best = None
    scan = tokens
    for kws, v in MACRO:
        for i, t in enumerate(scan):
            if t in kws or (len(t) > 3 and t.rstrip("s") in kws):
                # prefer earliest-matching head noun for usda, last for ingredient
                pos = i if head_first else -i
                if best is None or pos < best[0]:
                    best = (pos, v)
                break
    return best[1] if best else None


def _dist(a, b):
    sc = (500.0, 25.0, 50.0, 50.0)
    return math.sqrt(sum(((x - y) / s) ** 2 for x, y, s in zip(a, b, sc)))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = ing.split(",")[0]
        usda_parts = usda.split(",")
        usda_main = usda_parts[0]
        it = _tokens(ing_main)
        ut = _tokens(usda)
        vi = _vec(it, head_first=False) or _vec(_tokens(ing), False)
        vu = _vec(_tokens(usda_main), True) or _vec(ut, True)
        score = 5.0
        if vi and vu:
            d = _dist(vi, vu)
            score += 3.0 * math.exp(-2.5 * d) * 2 - 3.0
        # content-word overlap as a food-identity proxy
        ci = set(t for t in it if t not in NOISE and len(t) > 2)
        cu = set(t for t in ut if t not in NOISE and len(t) > 2)
        norm = lambda w: w[:-1] if w.endswith("s") and len(w) > 3 else w
        ci = {norm(w) for w in ci}
        cu = {norm(w) for w in cu}
        if ci:
            cover = len(ci & cu) / float(len(ci))
            score += 3.0 * cover
            if cover == 0:
                score -= 2.0
        # state mismatch penalty (processing level)
        si = {STATE_FLAGS[t] for t in _tokens(ing) if t in STATE_FLAGS and STATE_FLAGS[t] > 0}
        su = {STATE_FLAGS[t] for t in ut if t in STATE_FLAGS and STATE_FLAGS[t] > 0}
        diff = si ^ su
        score -= 0.8 * len(diff)
        # extra USDA descriptors that swing macros
        for bad in ("pie", "filling", "juice", "sauce"):
            if bad in ut and bad not in _tokens(ing):
                score -= 1.5
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
