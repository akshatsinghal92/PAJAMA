import re

# Food Category Consistency, variant 4: nearest-prototype classification
# with character trigrams.
# Word lists never cover every food name, so each category is described by a
# set of PROTOTYPE words and a text's head words are classified by their
# best character-trigram Dice similarity to any prototype. This generalises
# to unseen names ("blackberries" ~ "berries", "swordfish" ~ "fish",
# "flaxseed" ~ "seed", "provolone" falls back to its context word "cheese").
# The score blends category agreement with classification confidence, and
# uses a second-choice category so near-ties are judged softly.

_PROTO = {
    "dairy": ["milk", "cheese", "yogurt", "cream", "butter", "cottage", "ricotta", "kefir", "cheddar"],
    "vegetable": ["tomato", "onion", "garlic", "carrot", "broccoli", "spinach", "lettuce", "cabbage",
                  "pepper", "potato", "corn", "celery", "cucumber", "mushroom", "zucchini", "vegetable"],
    "fruit": ["fruit", "apple", "banana", "orange", "berries", "berry", "grape", "mango", "peach",
              "pear", "cherry", "melon", "guava", "lemon", "citrus"],
    "animal": ["chicken", "turkey", "beef", "pork", "lamb", "fish", "shrimp", "salmon", "tuna",
               "meat", "steak", "sausage", "bacon", "ham", "crab", "patty"],
    "grain": ["rice", "pasta", "noodle", "bread", "flour", "oats", "cereal", "wheat", "grain",
              "gnocchi", "barley", "cracker", "tortilla"],
    "legume": ["beans", "lentil", "chickpea", "tofu", "soybean", "hummus", "peas"],
    "nutseed": ["nuts", "almond", "walnut", "peanut", "cashew", "seed", "sesame", "chia", "pecan"],
    "spice": ["spices", "cinnamon", "cumin", "paprika", "nutmeg", "turmeric", "oregano", "basil",
              "thyme", "parsley", "seasoning", "ginger", "clove"],
    "fat": ["oil", "lard", "shortening", "margarine"],
    "sweet": ["sugar", "honey", "syrup", "candy", "chocolate", "jam", "jelly", "molasses"],
    "condiment": ["sauce", "dressing", "ketchup", "mustard", "mayonnaise", "vinegar", "salsa",
                  "pesto", "gravy", "paste"],
    "beverage": ["juice", "beverage", "drink", "soda", "coffee", "tea", "broth", "soup"],
}
_NEAR = {frozenset(["vegetable", "fruit"]), frozenset(["grain", "legume"]),
         frozenset(["legume", "nutseed"]), frozenset(["spice", "condiment"]),
         frozenset(["fat", "dairy"]), frozenset(["sweet", "condiment"]),
         frozenset(["beverage", "fruit"])}
_STOP = set("""g kg ml oz lb fresh frozen canned raw cooked chopped diced minced sliced
shredded grated thawed segmented peeled drained large small medium whole uncooked and
or of with the a an in nfs ns low fat reduced calorie sodium dry heat""".split())


def _grams(w):
    w = "#" + w + "#"
    return {w[i:i + 3] for i in range(len(w) - 2)}


_PROTO_GRAMS = {c: [(p, _grams(p)) for p in ps] for c, ps in _PROTO.items()}


def _dice(a, b):
    return 2.0 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def _classify_word(w):
    g = _grams(w)
    scores = []
    for c, plist in _PROTO_GRAMS.items():
        best = 0.0
        for p, pg in plist:
            if p == w:
                best = 1.0
                break
            s = _dice(g, pg)
            # a prototype contained in a compound ("swordfish" > "fish") is strong
            if len(p) >= 3 and p in w:
                s = max(s, 0.8)
            best = max(best, s)
        scores.append((best, c))
    scores.sort(reverse=True)
    return scores


def _classify_phrase(words):
    """Head-final weighting: last word dominates, earlier words assist."""
    agg = {}
    n = len(words)
    for i, w in enumerate(words):
        wt = 1.0 if i == n - 1 else 0.35
        for s, c in _classify_word(w)[:2]:
            if s >= 0.45:
                agg[c] = max(agg.get(c, 0.0), s * wt)
    ranked = sorted(((v, c) for c, v in agg.items()), reverse=True)
    return ranked


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = [w for w in re.findall(r"[a-z]+", ing) if w not in _STOP]
        fields = [[w for w in re.findall(r"[a-z]+", f) if w not in _STOP]
                  for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        uw = fields[0] if len(fields[0]) > 1 or len(fields) == 1 else fields[1] + fields[0]
        ri = _classify_phrase(iw)
        ru = _classify_phrase(uw)
        if not ri or not ru:
            return 4.0
        (si, ci), (su, cu) = ri[0], ru[0]
        conf = min(si, su)
        if ci == cu:
            score = 6.0 + 4.0 * conf
        elif frozenset([ci, cu]) in _NEAR:
            score = 3.5 * conf
        else:
            score = 0.5
            # second-choice agreement softens a near-tie misclassification
            alt_i = {c for _, c in ri[:2]}
            alt_u = {c for _, c in ru[:2]}
            if alt_i & alt_u:
                score = 3.0
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
