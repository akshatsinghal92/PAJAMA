import re
import math

# Variant 3: soft category distributions via prefix-stem voting with positional
# decay, compared by cosine similarity, plus a head-category agreement bonus and
# a branded/processed-product penalty.

_CATEGORY_STEMS = {
    "dairy": ["milk", "chees", "yogurt", "yoghurt", "cream", "butter", "kefir", "ghee",
              "curd", "ricotta", "mozzarell", "cheddar", "parmesan", "feta", "asadero",
              "brie", "gouda", "whey", "buttermilk", "custard", "paneer", "mascarpone"],
    "produce_veg": ["onion", "garlic", "tomato", "pepper", "carrot", "celery", "lettuce",
                    "spinach", "kale", "cabbage", "broccoli", "cauliflower", "potato",
                    "squash", "zucchini", "cucumber", "mushroom", "eggplant", "leek",
                    "shallot", "pea", "corn", "radish", "beet", "turnip", "seaweed",
                    "agar", "kelp", "asparagus", "artichoke", "okra", "chard", "arugula"],
    "produce_fruit": ["apple", "banana", "grape", "orange", "lemon", "lime", "berry",
                      "berries", "cherr", "peach", "pear", "plum", "mango", "pineapple",
                      "melon", "apricot", "fig", "date", "raisin", "kiwi", "papaya",
                      "coconut", "avocado", "pomegranate", "cranberr", "currant"],
    "meat": ["chicken", "beef", "pork", "lamb", "turkey", "sausage", "bacon", "ham",
             "veal", "duck", "goose", "venison", "salami", "chorizo", "pepperoni",
             "steak", "breast", "thigh", "liver", "meat", "blood", "patty", "frank",
             "bologna", "prosciutto"],
    "fish": ["fish", "salmon", "tuna", "cod", "shrimp", "crab", "lobster", "clam",
             "oyster", "mussel", "scallop", "anchov", "sardine", "tilapia", "trout",
             "halibut", "squid", "octopus", "mackerel"],
    "grain": ["flour", "rice", "wheat", "oat", "barley", "bread", "pasta", "noodle",
              "spaghetti", "macaroni", "quinoa", "cornmeal", "semolina", "bulgur",
              "couscous", "rye", "millet", "cereal", "cracker", "tortilla", "cookie",
              "cake", "biscuit", "bran"],
    "legume": ["bean", "lentil", "chickpea", "garbanzo", "soy", "tofu", "tempeh",
               "pinto", "edamame", "hummus", "peanut", "legume"],
    "nut_seed": ["nut", "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut",
                 "seed", "sesame", "flax", "chia", "pumpkin seed", "sunflower", "tahini",
                 "pine nut", "macadamia", "brazil"],
    "spice_herb": ["spice", "salt", "cumin", "cinnamon", "paprika", "oregano", "basil",
                   "thyme", "rosemary", "sage", "parsley", "cilantro", "coriander",
                   "ginger", "turmeric", "nutmeg", "clove", "cardamom", "dill", "mint",
                   "bay leaf", "chili powder", "vanilla extract", "saffron", "fennel",
                   "tarragon", "allspice", "herb", "seasoning", "carob"],
    "oil_fat": ["oil", "lard", "shortening", "margarine", "tallow", "drippings", "fat"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener",
                  "stevia", "chocolate", "cocoa", "candy", "jam", "jelly", "caramel"],
    "condiment": ["sauce", "ketchup", "mustard", "mayonnaise", "vinegar", "dressing",
                  "salsa", "relish", "paste", "gravy", "pesto", "soy sauce", "chutney",
                  "marinade", "broth", "stock", "bouillon", "soup"],
    "egg": ["egg"],
    "beverage": ["juice", "coffee", "tea", "wine", "beer", "soda", "drink", "beverage"],
}

_NOISE = {"g", "gram", "grams", "kg", "ml", "l", "oz", "lb", "cup", "cups", "tbsp",
          "tsp", "of", "and", "or", "with", "without", "the", "a", "an", "to", "for",
          "fresh", "frozen", "thawed", "chopped", "diced", "sliced", "minced", "raw",
          "cooked", "canned", "drained", "dried", "dry", "melted", "ground", "whole",
          "large", "small", "medium", "nfs", "ns", "added", "type", "from", "tube",
          "plain", "regular", "uncooked", "boiled", "roasted", "solids", "style"}

_PROCESSED_FORMS = {"sauce", "soup", "patty", "cookie", "cookies", "bar", "candy",
                    "spread", "dip", "dressing", "sandwich", "pie", "cake", "nuggets",
                    "flavored", "mix", "substitute", "imitation", "chips", "crackers"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"[^a-z,\s\-]", " ", t)
    return t


def _tokens(text):
    return [w for w in re.split(r"[\s,\-]+", text) if w and w not in _NOISE]


def _category_vector(tokens, raw_text, decay):
    vec = {c: 0.0 for c in _CATEGORY_STEMS}
    n = len(tokens)
    for idx, tok in enumerate(tokens):
        w = decay(idx, n)
        for cat, stems in _CATEGORY_STEMS.items():
            for s in stems:
                if " " in s:
                    continue
                if tok == s or (len(s) >= 4 and tok.startswith(s)) or tok == s + "s" or tok == s + "es":
                    vec[cat] += w
                    break
    for cat, stems in _CATEGORY_STEMS.items():
        for s in stems:
            if " " in s and s in raw_text:
                vec[cat] += 1.5
    return vec


def _cosine(a, b):
    dot = sum(a[k] * b[k] for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return None
    return dot / (na * nb)


def _argmax(vec):
    best = max(vec.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else None


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        ing_clean = _clean(ing_raw.split(",")[0] if "," in ing_raw else ing_raw)
        usda_clean = _clean(usda_raw)

        ing_tok = _tokens(ing_clean)
        usda_tok = _tokens(usda_clean)
        if not ing_tok or not usda_tok:
            return 10.0

        # ingredient: head noun is usually last -> weight later tokens more
        ing_vec = _category_vector(ing_tok, ing_clean,
                                   lambda i, n: 0.5 + 1.0 * (i + 1) / n)
        # USDA: primary food first -> exponential decay over comma segments
        usda_head = _tokens(usda_clean.split(",")[0])
        head_len = max(1, len(usda_head))
        usda_vec = _category_vector(usda_tok, usda_clean,
                                    lambda i, n: 2.0 if i < head_len else math.exp(-0.45 * (i - head_len + 1)))

        cos = _cosine(ing_vec, usda_vec)
        ing_cat = _argmax(ing_vec)
        usda_cat = _argmax(usda_vec)

        score = 35.0
        if cos is None:
            score = 35.0 if (ing_cat is None and usda_cat is None) else 25.0
        else:
            score = 15.0 + 50.0 * cos

        if ing_cat and usda_cat:
            if ing_cat == usda_cat:
                score += 15.0
            else:
                score -= 20.0

        # same specific food token (stem-level) shared
        ing_set = set(t.rstrip("s") for t in ing_tok)
        usda_set = set(t.rstrip("s") for t in usda_tok)
        overlap = ing_set & usda_set
        if overlap:
            score += min(15.0, 7.5 * len(overlap))
        else:
            score -= 8.0

        # processed-form penalty when the ingredient isn't itself that form
        proc_u = set(usda_tok) & _PROCESSED_FORMS
        proc_i = set(ing_tok) & _PROCESSED_FORMS
        if proc_u - proc_i:
            score -= 12.0

        # branded entry penalty: title-case words before first comma, no comma structure
        head_seg = usda_raw.split(",")[0].strip()
        words = head_seg.split()
        if len(words) >= 2 and sum(1 for w in words if w[:1].isupper()) >= 2 and "," in usda_raw:
            score -= 10.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
