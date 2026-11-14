import re
import math

# Soft category distributions: each lexicon stem contributes weighted evidence
# to one or more food categories. Scores compare category probability
# distributions via the Bhattacharyya coefficient, weighting head nouns more.
_LEX = {
    "dairy": {"milk": 1.0, "cheese": 1.0, "brie": 1.0, "cheddar": 1.0, "mozzarella": 1.0,
              "parmesan": 1.0, "feta": 1.0, "yogurt": 1.0, "yoghurt": 1.0, "cream": 0.8,
              "butter": 0.7, "ricotta": 1.0, "kefir": 1.0, "whey": 0.9, "ghee": 0.5,
              "buttermilk": 1.0, "custard": 0.6, "gouda": 1.0, "swiss": 0.3, "camembert": 1.0},
    "produce": {"apple": 1.0, "pineapple": 1.0, "grape": 1.0, "olive": 0.9, "chard": 1.0,
                "spinach": 1.0, "lettuce": 1.0, "kale": 1.0, "tomato": 1.0, "onion": 1.0,
                "carrot": 1.0, "potato": 1.0, "pepper": 0.5, "berry": 1.0, "berries": 1.0,
                "banana": 1.0, "lemon": 1.0, "lime": 1.0, "orange": 1.0, "cabbage": 1.0,
                "celery": 1.0, "cucumber": 1.0, "squash": 1.0, "zucchini": 1.0, "mushroom": 1.0,
                "leaves": 0.6, "leaf": 0.6, "fruit": 1.0, "vegetable": 1.0, "melon": 1.0,
                "peach": 1.0, "pear": 1.0, "plum": 1.0, "cherry": 1.0, "cherries": 1.0,
                "mango": 1.0, "broccoli": 1.0, "cauliflower": 1.0, "corn": 0.5, "garlic": 0.6,
                "avocado": 1.0, "beet": 1.0, "radish": 1.0, "raw": 0.2},
    "meat": {"chicken": 1.0, "beef": 1.0, "pork": 1.0, "lamb": 1.0, "turkey": 1.0,
             "frankfurter": 1.0, "hot dog": 1.0, "sausage": 1.0, "bacon": 1.0, "ham": 1.0,
             "fish": 1.0, "salmon": 1.0, "tuna": 1.0, "shrimp": 1.0, "cod": 1.0, "crab": 1.0,
             "veal": 1.0, "duck": 1.0, "patty": 0.6, "breast": 0.5, "thigh": 0.6, "steak": 1.0,
             "anchovy": 1.0, "salami": 1.0, "egg": 0.5},
    "grain": {"rice": 0.9, "bran": 1.0, "oat": 1.0, "oats": 1.0, "wheat": 1.0, "flour": 1.0,
              "bread": 1.0, "cereal": 1.0, "cereals": 1.0, "cracker": 1.0, "crackers": 1.0,
              "pasta": 1.0, "noodle": 1.0, "barley": 1.0, "quinoa": 1.0, "cornmeal": 1.0,
              "tortilla": 0.9, "cheerios": 1.0, "paper": 0.4, "biscuit": 0.8, "couscous": 1.0,
              "rye": 1.0, "granola": 1.0},
    "legume": {"bean": 1.0, "beans": 1.0, "pinto": 0.8, "lentil": 1.0, "chickpea": 1.0,
               "garbanzo": 1.0, "pea": 0.7, "peas": 0.7, "soy": 0.9, "tofu": 1.0, "peanut": 0.8,
               "edamame": 1.0, "hummus": 0.8},
    "nut_seed": {"nut": 1.0, "nuts": 1.0, "almond": 1.0, "walnut": 1.0, "pecan": 1.0,
                 "cashew": 1.0, "brazil": 0.8, "para": 0.6, "hazelnut": 1.0, "pistachio": 1.0,
                 "seed": 1.0, "seeds": 1.0, "sesame": 1.0, "flax": 1.0, "chia": 1.0,
                 "sunflower": 0.8, "pumpkin seed": 1.0, "macadamia": 1.0},
    "spice_herb": {"spice": 1.0, "spices": 1.0, "ground": 0.3, "cinnamon": 1.0, "ginger": 0.8,
                   "cumin": 1.0, "paprika": 1.0, "oregano": 1.0, "basil": 1.0, "thyme": 1.0,
                   "parsley": 1.0, "cilantro": 1.0, "nutmeg": 1.0, "clove": 0.8, "turmeric": 1.0,
                   "dried": 0.2, "rosemary": 1.0, "sage": 1.0, "dill": 1.0, "salt": 0.7,
                   "herb": 1.0, "herbs": 1.0, "chili powder": 1.0, "vanilla": 0.7},
    "oil_fat": {"oil": 1.0, "lard": 1.0, "shortening": 1.0, "margarine": 1.0, "butter": 0.4,
                "ghee": 0.6, "fat": 0.6, "tallow": 1.0},
    "sweetener": {"sugar": 1.0, "honey": 1.0, "syrup": 1.0, "molasses": 1.0, "agave": 1.0,
                  "sweetener": 1.0, "candy": 0.7, "chocolate": 0.6, "jam": 0.6},
    "condiment": {"sauce": 1.0, "ketchup": 1.0, "mustard": 1.0, "mayonnaise": 1.0,
                  "vinegar": 1.0, "dressing": 1.0, "salsa": 1.0, "relish": 1.0, "sauerkraut": 0.9,
                  "paste": 0.4, "pickle": 0.8, "soy sauce": 1.0, "gravy": 1.0},
    "beverage": {"juice": 1.0, "coffee": 1.0, "tea": 1.0, "wine": 1.0, "beer": 1.0, "soda": 1.0,
                 "beverage": 1.0, "water": 0.6},
}

_CATS = list(_LEX.keys())
_NOISE = {"g", "kg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "sliced", "chopped",
          "diced", "minced", "fresh", "frozen", "thawed", "drained", "canned", "toasted",
          "for", "garnish", "the", "and", "or", "of", "with", "from", "tube", "large", "small",
          "uncooked", "cooked", "all", "varieties", "type", "solids", "to", "a", "in", "round"}


def _norm(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb)?\b", " ", t)
    return t


def _ingredient_segments(text):
    t = _norm(text)
    main = t.split(",")[0]
    words = [w for w in re.findall(r"[a-z]+", main) if w not in _NOISE]
    if not words:
        return []
    # head noun (last word) gets highest weight; earlier modifiers less
    segs = []
    n = len(words)
    for i, w in enumerate(words):
        segs.append((w, 0.5 + 1.5 * (i + 1) / n))
    for i in range(n - 1):
        segs.append((words[i] + " " + words[i + 1], 2.0))
    return segs


def _usda_segments(text):
    t = _norm(text)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    segs = []
    for idx, part in enumerate(parts):
        weight = 2.2 if idx == 0 else 1.0 / (idx + 0.5)
        words = [w for w in re.findall(r"[a-z]+", part) if w not in _NOISE]
        for w in words:
            segs.append((w, weight))
        for i in range(len(words) - 1):
            segs.append((words[i] + " " + words[i + 1], weight * 1.1))
    return segs


def _lookup(term):
    hits = {}
    for cat, lex in _LEX.items():
        if term in lex:
            hits[cat] = lex[term]
        elif len(term) > 3 and term.endswith("s") and term[:-1] in lex:
            hits[cat] = lex[term[:-1]]
        elif len(term) > 4 and term.endswith("es") and term[:-2] in lex:
            hits[cat] = lex[term[:-2]]
    return hits


def _distribution(segs):
    mass = {c: 0.0 for c in _CATS}
    for term, w in segs:
        for cat, v in _lookup(term).items():
            mass[cat] += w * v
    total = sum(mass.values())
    if total <= 0:
        return None, 0.0
    return {c: m / total for c, m in mass.items()}, total


def _token_set(segs):
    out = set()
    for term, _ in segs:
        if " " in term:
            continue
        s = term[:-1] if len(term) > 3 and term.endswith("s") else term
        out.add(s[:5])
    return out


def judging_function(ingredient, usda_match):
    try:
        if not str(ingredient or "").strip() or not str(usda_match or "").strip():
            return 0.0
        iseg = _ingredient_segments(ingredient)
        useg = _usda_segments(usda_match)
        if not iseg or not useg:
            return 1.0

        pi, mi = _distribution(iseg)
        pu, mu = _distribution(useg)

        ti, tu = _token_set(iseg), _token_set(useg)
        overlap = len(ti & tu) / max(1, min(len(ti), len(tu)))

        if pi is None or pu is None:
            # no category evidence on one side: fall back to lexical cue only
            return round(3.0 + 4.0 * overlap, 3)

        bc = sum(math.sqrt(pi[c] * pu[c]) for c in _CATS)  # 0..1
        top_i = max(pi, key=pi.get)
        top_u = max(pu, key=pu.get)
        dominant_agree = 1.0 if top_i == top_u else 0.0

        # confidence: how sure we are about the category of each side
        conf = (1 - math.exp(-mi / 2.0)) * (1 - math.exp(-mu / 2.0))

        score = 10.0 * (0.55 * bc + 0.25 * dominant_agree + 0.20 * overlap)
        # cross-category penalty scaled by confidence
        if dominant_agree == 0.0 and bc < 0.35:
            score -= 3.0 * conf
        # blend toward a neutral mid-value when confidence is low
        score = conf * score + (1 - conf) * (3.5 + 3.0 * overlap)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
