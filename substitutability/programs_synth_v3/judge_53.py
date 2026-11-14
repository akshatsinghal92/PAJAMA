import re
import math

# Two-level taxonomy: coarse category -> fine subcategory -> keyword stems.
_TAXONOMY = {
    "dairy": {
        "milk": ["milk", "cream", "half and half", "buttermilk", "kefir"],
        "cheese": ["cheese", "cheddar", "mozzarella", "parmesan", "ricotta", "feta", "brie", "gouda", "paneer"],
        "yogurt": ["yogurt", "yoghurt", "skyr"],
        "butter": ["butter", "ghee"],
        "egg": ["egg", "eggs", "yolk"],
    },
    "meat": {
        "poultry": ["chicken", "turkey", "duck", "goose", "quail", "hen"],
        "red": ["beef", "pork", "lamb", "veal", "goat", "venison", "bison", "mutton"],
        "processed": ["sausage", "bacon", "ham", "salami", "merguez", "chorizo", "pepperoni", "liver cheese",
                      "hot dog", "frankfurter", "bologna", "patty", "jerky", "pate"],
        "offal": ["liver", "neck", "kidney", "heart", "gizzard", "tongue", "tripe"],
    },
    "seafood": {
        "fish": ["fish", "salmon", "tuna", "cod", "whiting", "tilapia", "trout", "sardine", "anchovy",
                 "mackerel", "halibut", "haddock", "herring", "snapper", "catfish"],
        "shellfish": ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop", "squid", "octopus"],
    },
    "produce": {
        "fruit": ["apple", "grape", "banana", "orange", "lemon", "lime", "berry", "berries", "mango", "peach",
                  "pear", "plum", "cherry", "pineapple", "melon", "tamarind", "date", "fig", "apricot",
                  "olive", "olives", "avocado", "coconut", "kiwi", "papaya", "raisin"],
        "vegetable": ["onion", "garlic", "carrot", "tomato", "potato", "pepper", "spinach", "lettuce",
                      "cabbage", "broccoli", "cauliflower", "celery", "cucumber", "zucchini", "squash",
                      "mushroom", "kale", "chrysanthemum", "leek", "eggplant", "corn", "pea", "beet",
                      "radish", "turnip", "greens", "chard", "asparagus", "artichoke"],
    },
    "grain": {
        "grain": ["rice", "wheat", "oat", "oats", "barley", "quinoa", "millet", "flour", "cornmeal",
                  "bread", "pasta", "noodle", "noodles", "spaghetti", "tortilla", "couscous", "bulgur", "cereal"],
    },
    "legume": {
        "legume": ["bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "tofu", "soybean",
                   "edamame", "tempeh", "split pea"],
    },
    "nut_seed": {
        "nut_seed": ["almond", "walnut", "pecan", "cashew", "peanut", "pistachio", "hazelnut", "seed",
                     "seeds", "sesame", "chia", "flax", "pine nut", "macadamia"],
    },
    "spice_herb": {
        "spice": ["spices", "cinnamon", "cumin", "paprika", "turmeric", "nutmeg", "clove", "ginger",
                  "cardamom", "coriander", "pepper black", "chili powder", "curry", "saffron", "allspice"],
        "herb": ["basil", "oregano", "thyme", "rosemary", "parsley", "cilantro", "dill", "mint", "sage",
                 "tarragon", "bay leaf", "chives"],
        "flavoring": ["vanilla", "extract", "salt"],
    },
    "oil_fat": {
        "oil_fat": ["oil", "lard", "shortening", "margarine", "tallow", "fat"],
    },
    "sweetener": {
        "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "stevia", "sweetener", "jaggery"],
    },
    "condiment": {
        "sauce": ["sauce", "ketchup", "mustard", "mayonnaise", "dressing", "salsa", "vinegar", "paste",
                  "chutney", "relish", "soy sauce", "pesto", "gravy"],
    },
    "beverage": {
        "beverage": ["juice", "nectar", "drink", "beverage", "soda", "tea", "coffee", "wine", "beer", "smoothie"],
    },
}

# Words in the USDA tail that imply the product has been transformed into another form
# (often pushing it toward a different category: fruit -> beverage/sweetened).
_FORM_SHIFT = {
    "nectar": "beverage", "juice": "beverage", "syrup": "sweetener", "heavy syrup": "sweetener",
    "sweetened": "sweetener", "candied": "sweetener", "jam": "sweetener", "jelly": "sweetener",
    "sauce": "condiment", "dressing": "condiment", "powder": "spice_herb", "ground": None,
}

_STATE_WORDS = {"fresh", "raw", "cooked", "boiled", "canned", "frozen", "dried", "dry", "roasted",
                "fried", "smoked", "drained", "thawed", "uncooked"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"[^a-z\s,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _contains(text, kw):
    return re.search(r"\b" + re.escape(kw) + r"s?\b", text) is not None


def _profile(text, head_weight=2.5):
    """Weighted vote over (coarse, fine) labels.  Keywords found in the 'head'
    segment (before the first comma) count more than those in the tail."""
    parts = text.split(",")
    head = parts[0].strip()
    tail = " ".join(parts[1:])
    votes = {}
    for coarse, subs in _TAXONOMY.items():
        for fine, kws in subs.items():
            for kw in kws:
                w = 0.0
                if _contains(head, kw):
                    w += head_weight * (1.0 + 0.15 * kw.count(" "))
                if tail and _contains(tail, kw):
                    w += 0.6
                if w:
                    votes[(coarse, fine)] = votes.get((coarse, fine), 0.0) + w
    return votes


def _distribution(votes, level):
    dist = {}
    for (coarse, fine), w in votes.items():
        key = coarse if level == 0 else (coarse, fine)
        dist[key] = dist.get(key, 0.0) + w
    total = sum(dist.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in dist.items()}


def _bhattacharyya(p, q):
    if not p or not q:
        return None
    keys = set(p) | set(q)
    return sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in keys)


def _dominant(dist):
    if not dist:
        return None
    return max(dist.items(), key=lambda kv: kv[1])[0]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        # Ingredient text rarely has commas meaningfully; treat the part before the
        # first comma as head (post-comma is usually state like "drained").
        v_ing = _profile(ing, head_weight=2.0)
        v_usda = _profile(usda, head_weight=3.0)

        # Form-shift words in the USDA string push its distribution toward another category.
        usda_tail = " ".join(usda.split(",")[1:]) + " " + usda.split(",")[0]
        ing_flat = ing.replace(",", " ")
        for word, target in _FORM_SHIFT.items():
            if target and _contains(usda_tail, word) and not _contains(ing_flat, word):
                key = (target, next(iter(_TAXONOMY[target])))
                v_usda[key] = v_usda.get(key, 0.0) + 2.0

        c_ing, c_usda = _distribution(v_ing, 0), _distribution(v_usda, 0)
        f_ing, f_usda = _distribution(v_ing, 1), _distribution(v_usda, 1)

        coarse_sim = _bhattacharyya(c_ing, c_usda)
        fine_sim = _bhattacharyya(f_ing, f_usda)

        if coarse_sim is None:
            # Unknown category on at least one side: fall back to head-token anchoring only.
            ing_toks = set(re.findall(r"[a-z]{3,}", ing))
            head_toks = set(re.findall(r"[a-z]{3,}", usda.split(",")[0]))
            if not ing_toks or not head_toks:
                return 2.0
            ov = len(ing_toks & head_toks) / float(len(head_toks))
            return round(2.0 + 4.0 * ov, 3)

        score = 6.0 * coarse_sim + 2.5 * (fine_sim or 0.0)

        # Hard penalty when the dominant categories disagree.
        d_ing, d_usda = _dominant(c_ing), _dominant(c_usda)
        if d_ing != d_usda:
            score -= 2.0

        # Fine-level dominant agreement (e.g. poultry vs offal both "meat").
        fd_ing, fd_usda = _dominant(f_ing), _dominant(f_usda)
        if d_ing == d_usda and fd_ing != fd_usda:
            score -= 1.0

        # Ingredient keywords that the USDA entry fails to cover hint at a different food
        # within the same category (e.g. "coconut sugar" vs "Sugar, brown").
        uncovered = [k for k in v_ing if k not in v_usda]
        score -= 0.6 * min(len(uncovered), 3)

        # State consistency: a fresh ingredient matched to a cooked/canned USDA entry
        # changes texture.
        ing_states = {w for w in _STATE_WORDS if _contains(ing_flat, w)}
        usda_states = {w for w in _STATE_WORDS if _contains(usda, w)}
        if "fresh" in ing_states and usda_states & {"cooked", "boiled", "canned"}:
            score -= 1.0
        if ing_states and usda_states and ing_states & usda_states:
            score += 0.5

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
