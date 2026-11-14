import re
import math

# Nutritional Profile Proximity, variant 2: macro-class assignment and
# energy-fraction similarity between class centroids.
# Each food is assigned a macro class (lean protein, fatty protein, pure fat,
# starch, sugar, leafy green, non-starchy veg, fruit, full-fat dairy,
# lean dairy, legume, nut/seed, dried spice, condiment, beverage).
# A class centroid is described by the share of energy from protein / carb /
# fat plus its energy density. Similarity = cosine of energy shares times a
# density agreement term. Modifier words (low fat, fried, sweetened, juice)
# can move a food into a neighbouring class before comparison.

_CENTROIDS = {
    # (protein%, carb%, fat%, kcal per 100 g)
    "lean_protein": (0.80, 0.0, 0.20, 130), "fatty_protein": (0.40, 0.02, 0.58, 280),
    "fat": (0.0, 0.0, 1.0, 850), "starch": (0.12, 0.83, 0.05, 150),
    "grain_dry": (0.12, 0.80, 0.08, 370), "sugar": (0.0, 0.98, 0.02, 380),
    "leafy": (0.35, 0.55, 0.10, 22), "veg": (0.15, 0.78, 0.07, 40),
    "fruit": (0.05, 0.92, 0.03, 55), "dairy_full": (0.25, 0.05, 0.70, 380),
    "dairy_lean": (0.45, 0.25, 0.30, 80), "legume": (0.28, 0.68, 0.04, 120),
    "nutseed": (0.13, 0.15, 0.72, 580), "spice": (0.12, 0.70, 0.18, 300),
    "condiment": (0.03, 0.30, 0.67, 250), "beverage": (0.03, 0.95, 0.02, 45),
    "dessert": (0.07, 0.60, 0.33, 300), "broth": (0.6, 0.3, 0.1, 8),
}
_CLASS_WORDS = [
    ("fat", ["oil", "butter", "lard", "ghee", "shortening", "margarine", "mayonnaise"]),
    ("spice", ["spices", "spice", "cinnamon", "cumin", "paprika", "nutmeg", "oregano",
               "turmeric", "seasoning", "pepper", "ginger", "clove"]),
    ("condiment", ["dressing", "sauce", "pesto", "gravy", "dip", "aioli"]),
    ("broth", ["broth", "stock", "bouillon", "consomme"]),
    ("beverage", ["juice", "soda", "drink", "beverage", "nectar", "lemonade", "tea"]),
    ("dessert", ["ice", "frozen yogurt", "cake", "cookie", "pie", "pudding", "brownie",
                 "doughnut", "pastry"]),
    ("sugar", ["sugar", "honey", "syrup", "candy", "candies", "jam", "jelly", "molasses"]),
    ("nutseed", ["almond", "walnut", "pecan", "cashew", "peanut", "nut", "nuts", "seed",
                 "seeds", "chia", "flaxseed", "sesame", "tahini", "pistachio"]),
    ("dairy_lean", ["cottage", "yogurt", "milk", "kefir", "skim", "ricotta"]),
    ("dairy_full", ["cheese", "cheddar", "parmesan", "mozzarella", "cream"]),
    ("fatty_protein", ["bacon", "sausage", "salami", "pork", "lamb", "duck", "patty",
                       "beef", "salmon", "skin", "hot dog", "pepperoni"]),
    ("lean_protein", ["chicken", "turkey", "fish", "swordfish", "tuna", "cod", "shrimp",
                      "egg", "tofu", "breast", "tilapia", "crab"]),
    ("legume", ["bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "pea", "peas",
                "hummus"]),
    ("grain_dry", ["flour", "cereal", "cereals", "oats", "granola", "cracker", "crackers"]),
    ("starch", ["rice", "pasta", "noodle", "noodles", "potato", "potatoes", "gnocchi",
                "bread", "corn", "tortilla", "couscous", "quinoa"]),
    ("leafy", ["spinach", "lettuce", "kale", "arugula", "chard", "greens", "cabbage"]),
    ("fruit", ["apple", "banana", "berries", "berry", "orange", "fruit", "grape", "mango",
               "guava", "peach", "pear", "melon", "pineapple", "cherries", "blueberries"]),
    ("veg", ["tomato", "tomatoes", "onion", "carrot", "broccoli", "pepper", "zucchini",
             "garlic", "celery", "cucumber", "mushroom", "mushrooms", "squash"]),
]


def _classify(text):
    t = " " + text + " "
    best, best_pos = None, -1
    for cls, words in _CLASS_WORDS:
        for w in words:
            for m in re.finditer(r"\b" + re.escape(w) + r"\b", t):
                # later position in an English phrase -> head; keep latest
                if m.start() > best_pos:
                    best, best_pos = cls, m.start()
    return best


def _adjust(cls, words):
    ws = set(words)
    if cls == "dairy_full" and ws & {"low", "lowfat", "nonfat", "skim", "light", "reduced"}:
        return "dairy_lean"
    if cls in ("lean_protein", "starch", "veg") and ws & {"fried", "breaded", "battered"}:
        return "fatty_protein" if cls == "lean_protein" else "dessert"
    if cls == "fruit" and "juice" in ws:
        return "beverage"
    if cls in ("fruit", "veg") and ws & {"dried", "dehydrated"}:
        return "sugar"
    if cls == "dairy_lean" and "frozen" in ws:
        return "dessert"
    return cls


def _sim(c1, c2):
    a, b = _CENTROIDS[c1], _CENTROIDS[c2]
    dot = sum(x * y for x, y in zip(a[:3], b[:3]))
    na = math.sqrt(sum(x * x for x in a[:3]))
    nb = math.sqrt(sum(x * x for x in b[:3]))
    cos = dot / (na * nb) if na and nb else 0.0
    dens = math.exp(-abs(math.log((a[3] + 5) / (b[3] + 5))))
    return cos * (0.4 + 0.6 * dens)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        usda = str(usda_match or "").lower()
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        if not ing.strip() or not fields:
            return 0.0
        # reorder "Cheese, cottage" -> "cottage cheese" style for head detection
        u_text = (fields[1] + " " + fields[0]) if len(fields) > 1 and len(fields[0].split()) == 1 else fields[0]
        u_all = re.findall(r"[a-z]+", usda)
        i_words = re.findall(r"[a-z]+", ing)
        ci = _classify(ing)
        cu = _classify(u_text) or _classify(usda)
        if ci is None or cu is None:
            same = bool(i_words) and i_words[-1] in u_all
            return 70.0 if same else 30.0
        ci = _adjust(ci, i_words)
        cu = _adjust(cu, u_all)
        score = 100.0 * _sim(ci, cu)
        if ci == cu:
            score = max(score, 90.0)
            # same class AND same named food -> nearly identical macros
            if i_words and i_words[-1].rstrip("s") in [w.rstrip("s") for w in u_all]:
                score = 100.0
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
