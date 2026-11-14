import re
import math

# approximate per-100g (kcal/10, protein, carbs, fat) by food class keyword
_PROFILES = [
    (("oil", "lard", "shortening", "tallow", "margarine", "butter"), (80, 0, 0, 90)),
    (("sugar", "syrup", "honey", "molasses", "candy", "sweetener"), (38, 0, 98, 0)),
    (("spice", "spices", "seasoning", "herb", "herbs", "sage", "thyme", "oregano", "basil", "paprika", "cinnamon", "pepper", "cumin", "ginger", "garlic powder", "powder"), (28, 12, 55, 6)),
    (("sauce", "gravy", "dressing", "marinara", "ketchup", "salsa", "paste", "condiment", "mayonnaise"), (10, 2, 12, 4)),
    (("beef", "pork", "lamb", "veal", "turkey", "chicken", "duck", "goose", "sausage", "ham", "bacon", "steak", "chop", "giblets", "kidney", "kidneys", "liver", "meat", "poultry", "game", "venison", "bison"), (20, 21, 0, 12)),
    (("fish", "cod", "salmon", "tuna", "shrimp", "crab", "lobster", "tilapia", "trout", "shellfish", "clam", "oyster", "squid", "anchovy", "sardine", "mollusks", "crustaceans"), (11, 20, 0, 3)),
    (("egg", "eggs"), (15, 13, 1, 10)),
    (("cheese", "cheddar", "mozzarella", "parmesan", "cream", "cottage"), (30, 18, 3, 24)),
    (("yogurt", "milk", "kefir", "buttermilk"), (6, 4, 6, 2)),
    (("bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "peas", "tofu", "soy", "legumes"), (12, 9, 20, 3)),
    (("nut", "nuts", "almond", "almonds", "walnut", "pecan", "peanut", "seed", "seeds", "coconut", "cashew", "pistachio"), (60, 18, 22, 50)),
    (("rice", "pasta", "noodle", "noodles", "bread", "flour", "cereal", "cereals", "oat", "oats", "wheat", "bran", "corn", "grain", "cracker", "tortilla", "macaroni", "spaghetti", "barley", "quinoa"), (35, 10, 72, 3)),
    (("lettuce", "romaine", "spinach", "kale", "cabbage", "broccoli", "greens", "chard", "arugula", "celery", "cucumber", "zucchini", "mushroom", "mushrooms", "tomato", "tomatoes", "onion", "onions", "pepper", "carrot", "carrots", "cauliflower", "vegetable", "vegetables", "asparagus", "eggplant", "squash", "radish", "beet"), (3, 2, 6, 0)),
    (("potato", "potatoes", "yam", "cassava", "plantain", "sweet potato"), (8, 2, 18, 0)),
    (("fruit", "apple", "banana", "berry", "berries", "blackberry", "orange", "grape", "pomegranate", "lemon", "lime", "peach", "pear", "plum", "mango", "melon", "cherry", "cherries", "pineapple", "ugli", "raisin", "date", "dates", "fig", "juice"), (5, 1, 14, 0)),
    (("water", "broth", "stock", "soup", "tea", "coffee", "beverage", "drink", "vinegar", "wine", "beer"), (1, 1, 2, 0)),
    (("chocolate", "cocoa", "cookie", "cake", "pie", "candies", "dessert", "pudding", "ice"), (45, 5, 60, 20)),
]
_STATE_WORDS = {"raw", "cooked", "dried", "canned", "frozen", "fresh", "ground", "boiled", "roasted", "baked",
                "dry", "salted", "unsalted", "sweetened", "unsweetened", "whole", "fried", "simmered", "drained"}
_STOP = {"g", "of", "and", "with", "the", "a", "for", "or", "in", "to", "from", "style", "nfs", "only", "meat",
         "optional", "serving", "cup", "tbsp", "tsp", "chopped", "sliced", "diced", "minced", "crude"}


def _toks(s):
    return re.findall(r"[a-z]+", s.lower())


def _clean_ing(s):
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0] if len(s.split(",")[0].strip()) > 3 else s
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", s.lower())
    return s


def _profile(tokens, primary_tokens):
    # weighted blend of class profiles by keyword hits; primary-food words count double
    acc = [0.0, 0.0, 0.0, 0.0]
    wsum = 0.0
    for kws, prof in _PROFILES:
        w = 0.0
        for t in tokens:
            if t in kws:
                w += 2.0 if t in primary_tokens else 1.0
        if w > 0:
            wsum += w
            for i in range(4):
                acc[i] += w * prof[i]
    if wsum == 0:
        return None
    return [a / wsum for a in acc]


def _macro_dist(p, q):
    if p is None or q is None:
        return None
    scale = (60.0, 20.0, 50.0, 40.0)
    d = sum(((p[i] - q[i]) / scale[i]) ** 2 for i in range(4))
    return math.sqrt(d / 4.0)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ing(str(ingredient or ""))
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        usda_nop = re.sub(r"\([^)]*\)", " ", usda)
        usda_parts = usda_nop.split(",")
        it = [t for t in _toks(ing)]
        ut = _toks(usda_nop)
        u_primary = set(_toks(usda_parts[0]))
        i_primary = set(it)
        pi = _profile(it, i_primary)
        pu = _profile(ut, u_primary)
        dist = _macro_dist(pi, pu)

        # macro-class score: 0..6
        if dist is None:
            macro = 2.5
        else:
            macro = 6.0 * math.exp(-3.0 * dist)

        # content-word overlap on stemmed tokens (macro-neutral identity evidence)
        def stem(t):
            for suf in ("ies", "es", "s"):
                if t.endswith(suf) and len(t) > 4:
                    return t[: -len(suf)] if suf != "ies" else t[:-3] + "y"
            return t
        ic = {stem(t) for t in it if t not in _STOP and t not in _STATE_WORDS and len(t) > 1}
        uc = {stem(t) for t in ut if t not in _STOP and t not in _STATE_WORDS and len(t) > 1}
        if ic:
            cov = len(ic & uc) / len(ic)
        else:
            cov = 0.0
        extra = len(uc - ic)
        extra_pen = min(1.0, extra / 8.0)
        ident = 3.5 * cov - 1.0 * extra_pen

        # state mismatch: processing changes macros / texture
        istate = {t for t in it if t in _STATE_WORDS}
        ustate = {t for t in ut if t in _STATE_WORDS}
        clash = 0.0
        for a, b in (("raw", "cooked"), ("fresh", "canned"), ("fresh", "dried"), ("fresh", "frozen"),
                     ("canned", "raw"), ("dried", "raw"), ("fresh", "salted"), ("raw", "frozen")):
            if (a in istate and b in ustate and a not in ustate) or (b in istate and a in ustate and b not in ustate):
                clash += 0.6
        if ustate & {"dried", "salted"} and not (istate & {"dried", "salted"}):
            clash += 0.4
        if ("ground" in ustate and "spices" in ut) and "ground" not in istate:
            clash += 0.5
        clash = min(clash, 1.8)

        # brand-name / product-specific entries are poor generic stand-ins
        brand = 0.5 if re.search(r"[A-Z]{4,}", usda_nop) else 0.0

        score = macro + ident - clash - brand
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
