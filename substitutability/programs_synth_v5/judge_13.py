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


def _vec(p):
    e = (p[1] * 4.0, p[2] * 4.0, p[3] * 9.0)
    t = sum(e) or 1.0
    return [x / t for x in e], p[0]


def _best(tokens, head_tokens):
    # class from the primary food (USDA head / ingredient first noun group) gets priority
    hc, hp, hs = _profile(head_tokens) if head_tokens else (None, None, {})
    ac, ap, as_ = _profile(tokens)
    if hp is not None:
        return hc, hp
    return ac, ap


def judging_function(ingredient, usda_match):
    try:
        ing = (ingredient or "").lower()
        ing_main = ing.split(",")[0]
        ti = _tokens(ing_main)
        tu_all = _tokens(usda_match)
        um = (usda_match or "").split(",")
        tu_head = _tokens(um[0])
        ci, pi = _best(ti, ti[-3:] if len(ti) > 3 else ti)
        cu, pu = _best(tu_all, tu_head)
        if pi is None or pu is None:
            return 4.0 if (pi is None and pu is None) else 3.0
        pi = _adjust(pi, _tokens(ing))
        pu = _adjust(pu, tu_all)
        vi, ki = _vec(pi)
        vu, ku = _vec(pu)
        dot = sum(a * b for a, b in zip(vi, vu))
        ni = math.sqrt(sum(a * a for a in vi)) or 1.0
        nu = math.sqrt(sum(a * a for a in vu)) or 1.0
        cos = dot / (ni * nu)
        kr = abs(math.log((ki + 20.0) / (ku + 20.0)))
        score = 3.0 + 5.0 * cos * cos - 2.5 * min(kr, 1.6)
        if ci == cu:
            score += 3.0
        if (cu == "fastfood") != (ci == "fastfood"):
            score -= 3.0
        if bool(set(ti) & DRY) != bool(set(tu_all) & DRY):
            score -= 1.0
        if "oil" in set(tu_all) and "oil" not in set(_tokens(ing)):
            score -= 3.0
        # macro-density state: cooked/dried/canned/raw shift water content, so states must agree
        def state(ts):
            ts = set(ts)
            if ts & DRY: return "dry"
            if ts & {"cooked", "boiled", "baked", "simmered", "grilled", "roasted", "fried", "steamed", "braised"}: return "cooked"
            if ts & {"canned", "drained"}: return "canned"
            if ts & {"frozen"}: return "frozen"
            return "raw"
        si_, su_ = state(_tokens(ing)), state(tu_all)
        if si_ != su_:
            score -= 1.5 if "raw" in (si_, su_) and "frozen" in (si_, su_) else 3.0
        # specificity: USDA qualifiers naming a different variety/subtype than the ingredient
        ig = set(w[:5] for w in _tokens(ing) if len(w) > 3)
        ug = [w[:5] for w in tu_all if len(w) > 3 and w not in WET and w not in FATTY_HINT]
        if ug:
            hit = sum(1 for w in ug if w in ig) / float(len(ug))
            score += 2.5 * hit - 1.0
        return max(0.0, min(14.0, score))
    except Exception:
        return 0.0
