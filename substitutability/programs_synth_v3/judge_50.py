import re
import math

_CATEGORY_LEXICON = {
    "dairy": ["milk", "cheese", "cream", "butter", "yogurt", "yoghurt", "kefir", "whey",
              "ghee", "curd", "ricotta", "mozzarella", "cheddar", "parmesan", "feta",
              "buttermilk", "custard", "ice cream", "sour cream", "paneer", "brie"],
    "produce_veg": ["onion", "garlic", "tomato", "potato", "carrot", "celery", "pepper",
                    "lettuce", "spinach", "kale", "cabbage", "broccoli", "cauliflower",
                    "zucchini", "squash", "pumpkin", "eggplant", "cucumber", "yam",
                    "mushroom", "leek", "beet", "radish", "turnip", "asparagus", "okra",
                    "artichoke", "corn", "pea", "sprout", "chard", "shallot", "vegetable"],
    "produce_fruit": ["apple", "banana", "orange", "lemon", "lime", "grape", "berry",
                      "berries", "strawberry", "blueberry", "raspberry", "cherry", "peach",
                      "pear", "plum", "mango", "pineapple", "melon", "kiwi", "fig", "date",
                      "apricot", "papaya", "guava", "coconut", "ugli", "grapefruit",
                      "pomegranate", "fruit", "raisin", "tangerine", "avocado"],
    "meat_poultry": ["chicken", "turkey", "beef", "pork", "lamb", "veal", "duck", "goose",
                     "bacon", "ham", "sausage", "merguez", "salami", "venison", "mutton",
                     "steak", "mince", "patty", "skin", "neck", "liver", "meat", "chorizo",
                     "pepperoni", "prosciutto", "goat", "rabbit", "breast", "thigh", "wing"],
    "fish_seafood": ["fish", "salmon", "tuna", "cod", "shrimp", "prawn", "crab", "lobster",
                     "clam", "mussel", "oyster", "scallop", "anchovy", "sardine", "tilapia",
                     "trout", "halibut", "squid", "octopus", "mackerel", "haddock"],
    "grain": ["flour", "rice", "wheat", "oat", "oats", "barley", "bread", "pasta",
              "noodle", "tortilla", "tortillas", "cornmeal", "quinoa", "amaranth",
              "couscous", "bulgur", "millet", "rye", "cereal", "cracker", "bun", "roll",
              "spaghetti", "macaroni", "semolina", "polenta", "bagel", "pita"],
    "legume": ["bean", "beans", "lentil", "chickpea", "garbanzo", "soy", "tofu", "tempeh",
               "edamame", "peanut", "lima", "kidney", "pinto", "hummus", "dal"],
    "nut_seed": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "seed",
                 "seeds", "sesame", "chia", "flax", "sunflower", "pine nut", "macadamia",
                 "tahini", "nut", "nuts"],
    "spice_herb": ["spice", "spices", "cinnamon", "cumin", "paprika", "turmeric", "ginger",
                   "nutmeg", "clove", "oregano", "basil", "thyme", "rosemary", "parsley",
                   "cilantro", "coriander", "dill", "sage", "mint", "pepper, black",
                   "cardamom", "saffron", "bay", "chili powder", "curry", "allspice",
                   "fennel", "tarragon", "ground", "dried herb"],
    "oil_fat": ["oil", "lard", "shortening", "margarine", "tallow", "fat", "drippings"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener", "stevia",
                  "jaggery", "treacle", "candy", "chocolate", "caramel"],
    "condiment": ["sauce", "ketchup", "mustard", "mayonnaise", "mayo", "vinegar", "salsa",
                  "dressing", "relish", "paste", "soy sauce", "chutney", "pesto", "gravy",
                  "jam", "jelly", "marinade", "dip", "spread"],
    "egg": ["egg", "eggs", "yolk", "albumen"],
    "beverage": ["juice", "coffee", "tea", "wine", "beer", "soda", "water", "broth",
                 "stock", "drink"],
}

_NOISE = set("""g kg mg ml l oz lb lbs tsp tbsp cup cups fresh frozen thawed chopped diced
sliced minced toasted cooked raw canned sweetened unsweetened soft hard large small
medium whole of and or the a an with from tube to taste finely roughly peeled
buttered grated shredded drained rinsed""".split())

# Categories that are culinarily "near" each other (partial credit).
_NEIGHBORS = {
    frozenset(["produce_veg", "legume"]): 0.45,
    frozenset(["produce_veg", "produce_fruit"]): 0.3,
    frozenset(["meat_poultry", "fish_seafood"]): 0.35,
    frozenset(["nut_seed", "legume"]): 0.35,
    frozenset(["oil_fat", "dairy"]): 0.3,
    frozenset(["spice_herb", "condiment"]): 0.25,
    frozenset(["sweetener", "condiment"]): 0.2,
    frozenset(["grain", "legume"]): 0.2,
    frozenset(["produce_fruit", "nut_seed"]): 0.2,
    frozenset(["produce_veg", "spice_herb"]): 0.1,
}


def _clean_ingredient(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb|lbs)?\b", " ", t)
    t = re.sub(r"[^a-z\s\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _usda_segments(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    segs = [re.sub(r"[^a-z\s\-]", " ", s).strip() for s in t.split(",")]
    return [re.sub(r"\s+", " ", s) for s in segs if s.strip()]


def _term_hits(phrase, term):
    if " " in term or "," in term:
        return term.replace(",", "") in phrase
    words = phrase.split()
    for w in words:
        if w == term or (len(term) > 3 and w.rstrip("s") == term.rstrip("s")):
            return True
    return False


def _profile(weighted_phrases):
    """Return a normalized probability distribution over categories."""
    mass = {}
    for phrase, weight in weighted_phrases:
        if not phrase:
            continue
        for cat, terms in _CATEGORY_LEXICON.items():
            for term in terms:
                if _term_hits(phrase, term):
                    # longer, more specific terms carry more evidence
                    bonus = 1.0 + 0.15 * min(len(term), 10) / 10.0
                    mass[cat] = mass.get(cat, 0.0) + weight * bonus
    total = sum(mass.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in mass.items()}


def _ingredient_profile(ingredient):
    core = _clean_ingredient(ingredient)
    words = [w for w in core.split() if w not in _NOISE]
    if not words:
        return {}, core
    phrases = []
    n = len(words)
    # positional weighting: the head noun (last word) dominates in English noun phrases
    for i, w in enumerate(words):
        weight = 0.5 + 1.5 * ((i + 1) / n) ** 2
        phrases.append((w, weight))
    # bigrams for multi-word terms
    for i in range(n - 1):
        phrases.append((words[i] + " " + words[i + 1], 1.2))
    return _profile(phrases), " ".join(words)


def _usda_profile(usda):
    segs = _usda_segments(usda)
    if not segs:
        return {}, ""
    phrases = []
    for idx, seg in enumerate(segs):
        # primary food (first segment) dominates; descriptors decay geometrically
        weight = 2.5 * (0.45 ** idx)
        phrases.append((seg, weight))
    return _profile(phrases), segs[0]


def _bhattacharyya(p, q):
    return sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in set(p) | set(q))


def _neighbor_affinity(p, q):
    score = 0.0
    for a, pa in p.items():
        for b, qb in q.items():
            if a == b:
                continue
            w = _NEIGHBORS.get(frozenset([a, b]), 0.0)
            score += w * math.sqrt(pa * qb)
    return score


def _argmax(d):
    return max(d.items(), key=lambda kv: kv[1])[0] if d else None


def judging_function(ingredient, usda_match):
    try:
        if not str(ingredient or "").strip() or not str(usda_match or "").strip():
            return 0.0

        p_ing, ing_core = _ingredient_profile(ingredient)
        p_usda, usda_head = _usda_profile(usda_match)

        if not p_ing and not p_usda:
            # no category evidence at all: fall back to weak lexical overlap
            a = set(ing_core.split())
            b = set(re.sub(r"[^a-z\s]", " ", str(usda_match).lower()).split())
            if not a or not b:
                return 2.0
            return round(2.0 + 4.0 * len(a & b) / len(a | b), 3)

        if not p_ing or not p_usda:
            # one side unclassifiable: uncertain, middle-low score
            return 3.5

        bc = _bhattacharyya(p_ing, p_usda)          # 0..1 distribution overlap
        near = _neighbor_affinity(p_ing, p_usda)    # partial credit for related categories
        top_i, top_u = _argmax(p_ing), _argmax(p_usda)

        score = 6.0 * bc + 2.0 * min(near, 1.0)
        if top_i == top_u:
            score += 2.0
        else:
            pair_w = _NEIGHBORS.get(frozenset([top_i, top_u]), 0.0)
            score -= 2.5 * (1.0 - pair_w)

        # entropy penalty: mixed-category USDA entries (e.g. "fruit mixture") are vaguer
        ent = -sum(v * math.log(v) for v in p_usda.values() if v > 0)
        score -= 0.6 * ent

        # small bonus if the USDA primary food word literally appears in the ingredient
        head_words = [w for w in usda_head.split() if w not in _NOISE]
        if head_words and any(w.rstrip("s") in ing_core for w in head_words):
            score += 1.0

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
