import re
import math

# (kcal, protein, carb, fat) per 100g rough class profiles
CLASSES = [
    ("oil", ["oil", "lard", "shortening", "tallow", "ghee"], (880, 0, 0, 99)),
    ("butter", ["butter", "margarine"], (720, 1, 0, 80)),
    ("sugar", ["sugar", "syrup", "honey", "molasses", "candy", "sweetener"], (380, 0, 98, 0)),
    ("spice", ["spice", "spices", "pepper", "cinnamon", "ginger", "paprika", "cumin", "turmeric", "oregano", "basil", "thyme", "seasoning", "herb", "herbs", "salt"], (270, 11, 55, 6)),
    ("nut", ["nut", "nuts", "almond", "almonds", "walnut", "pecan", "cashew", "hazelnut", "pistachio", "peanut", "peanuts", "seed", "seeds", "sesame", "sunflower"], (600, 20, 18, 52)),
    ("cheese", ["cheese", "cheddar", "mozzarella", "parmesan", "feta", "ricotta"], (330, 22, 3, 26)),
    ("dairy", ["milk", "yogurt", "yoghurt", "cream", "kefir", "buttermilk"], (60, 3.5, 5, 3)),
    ("egg", ["egg", "eggs"], (145, 12, 1, 10)),
    ("fish", ["fish", "salmon", "tuna", "cod", "pollock", "trout", "shrimp", "crab", "crayfish", "lobster", "crustaceans", "mollusks", "clam", "oyster", "squid", "tilapia", "sardine", "anchovy", "mackerel"], (110, 21, 0, 2.5)),
    ("meat", ["beef", "pork", "chicken", "turkey", "lamb", "duck", "veal", "steak", "ham", "bacon", "sausage", "frankfurter", "liver", "giblets", "meat", "game", "venison", "goose"], (200, 20, 0, 13)),
    ("legume", ["bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "peas", "broadbeans", "favas", "fava", "legumes", "tofu", "tempeh", "soy", "soybeans"], (130, 9, 20, 3)),
    ("grain", ["rice", "pasta", "noodles", "bread", "flour", "wheat", "oats", "oat", "cereal", "cereals", "barley", "corn", "quinoa", "cracker", "crackers", "tortilla", "macaroni", "spaghetti"], (350, 11, 72, 2)),
    ("starchveg", ["potato", "potatoes", "yam", "cassava", "squash", "pumpkin", "sweet", "plantain", "taro", "parsnip", "beet", "carrot", "carrots"], (80, 2, 18, 0.2)),
    ("leafy", ["spinach", "kale", "chard", "lettuce", "cabbage", "arugula", "collards", "greens", "watercress", "endive", "radicchio", "bok"], (23, 2.5, 4, 0.3)),
    ("veg", ["tomato", "tomatoes", "onion", "onions", "pepper", "peppers", "cucumber", "celery", "broccoli", "cauliflower", "zucchini", "eggplant", "mushroom", "mushrooms", "radish", "asparagus", "garlic", "leek", "beans,snap", "vegetable", "vegetables", "olives", "olive"], (30, 1.8, 6, 0.3)),
    ("fruit", ["apple", "apples", "orange", "oranges", "banana", "bananas", "berry", "berries", "raspberries", "strawberries", "blueberries", "grape", "grapes", "peach", "pear", "plum", "mango", "pineapple", "tangerines", "clementine", "cherry", "cherries", "lemon", "lime", "melon", "fruit", "apricot", "raspberry", "tangerine", "mandarin"], (55, 0.8, 14, 0.3)),
    ("sauce", ["sauce", "ketchup", "dressing", "mayonnaise", "gravy", "salsa", "soup", "broth", "marinara", "paste", "juice"], (70, 2, 11, 2)),
    ("fastfood", ["restaurant", "mcdonalds", "burger", "taco", "pizza", "sandwich", "wendys", "kfc", "subway", "bell", "meal", "entree", "dinner"], (250, 11, 28, 11)),
]
DRY = {"dried", "dehydrated", "powder", "powdered", "flour", "ground", "dry", "freeze-dried"}
WET = {"raw", "fresh", "cooked", "boiled", "canned", "juice", "drained", "simmered", "steamed", "baked"}
FATTY_HINT = {"fried", "oil", "fat", "whole", "nonfat", "fat-free", "lowfat", "skim", "lean", "reduced"}


def _tokens(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb|mg)?\b", " ", s)
    s = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", s)
    return re.findall(r"[a-z\-]+", s)


def _profile(tokens, primary_first=True):
    # score each class by weighted keyword hits; earlier tokens weigh more
    scores = {}
    for i, t in enumerate(tokens):
        w = 1.0 / (1.0 + 0.35 * i)
        for name, kws, prof in CLASSES:
            if t in kws:
                scores[name] = scores.get(name, 0) + w
    if not scores:
        return None, None, {}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = ranked[0][0]
    prof = None
    for name, kws, p in CLASSES:
        if name == top:
            prof = p
    # blend top two when close
    if len(ranked) > 1 and ranked[1][1] >= 0.7 * ranked[0][1]:
        p2 = [p for n, k, p in CLASSES if n == ranked[1][0]][0]
        prof = tuple((a + b) / 2 for a, b in zip(prof, p2))
    return top, prof, scores


def _adjust(prof, tokens):
    k, p, c, f = prof
    ts = set(tokens)
    if ts & DRY:
        k, p, c, f = k * 1.8, p * 1.8, c * 1.8, f * 1.8
    if "oil" in ts and "olive" in ts:
        f = max(f, 90)
    return (k, p, c, f)


def _dist(a, b):
    # normalized macro distance, energy share based
    ea = (a[1] * 4, a[2] * 4, a[3] * 9)
    eb = (b[1] * 4, b[2] * 4, b[3] * 9)
    sa = sum(ea) or 1.0
    sb = sum(eb) or 1.0
    share = sum(abs(x / sa - y / sb) for x, y in zip(ea, eb)) / 2.0  # 0..1
    mag = abs(math.log((a[0] + 20) / (b[0] + 20)))  # log kcal ratio
    return share, mag


def judging_function(ingredient, usda_match):
    try:
        ti = _tokens(ingredient)
        usda_main = (usda_match or "").split(",")
        tu = _tokens(usda_match)
        ci, pi, si = _profile(ti)
        cu, pu, su = _profile(tu)
        score = 5.0
        if pi is None or pu is None:
            # unknown classes: fall back on content word overlap
            a, b = set(ti), set(tu)
            stop = {"g", "of", "and", "the", "a", "with", "or", "in"}
            a -= stop
            b -= stop
            if not a or not b:
                return 2.0
            return 10.0 * len(a & b) / len(a | b)
        pi = _adjust(pi, ti)
        pu = _adjust(pu, tu)
        share, mag = _dist(pi, pu)
        score = 10.0 - 8.0 * share - 3.0 * min(mag, 1.5)
        # same macro class bonus; a different class penalty
        if ci == cu:
            score += 1.5
        elif set(si) & set(su):
            score += 0.5
        # a processed fast food / sauce / prepared item standing in for a plain food
        if (cu == "fastfood") != (ci == "fastfood"):
            score -= 3.0
        # dry/wet state mismatch swings macro density
        if bool(set(ti) & DRY) != bool(set(tu) & DRY):
            score -= 1.5
        # primary food of USDA entry (before first comma) must appear in ingredient
        head = _tokens(usda_main[0]) if usda_main else []
        if head and not (set(head) & set(ti)):
            score -= 0.5
        # a bare oil extract of a nut/seed
        if "oil" in set(tu) and "oil" not in set(ti):
            score -= 3.0
        # lexical anchor: shared stemmed content words of the food name
        stop = {"g", "of", "and", "the", "a", "with", "or", "in", "raw", "fresh", "cooked", "canned", "dried", "ground", "whole", "sliced", "chopped", "drained", "without", "salt", "style", "frozen", "unheated"}
        def stem(w):
            for suf in ("ies", "es", "s"):
                if w.endswith(suf) and len(w) > len(suf) + 2:
                    return w[: -len(suf)] + ("y" if suf == "ies" else "")
            return w
        a = set(stem(w) for w in ti if w not in stop and len(w) > 1)
        b = set(stem(w) for w in tu if w not in stop and len(w) > 1)
        if a and b:
            ov = len(a & b) / float(len(a))
            score = 0.5 * score + 5.0 * ov
        return max(0.0, min(12.0, score))
    except Exception:
        return 0.0
