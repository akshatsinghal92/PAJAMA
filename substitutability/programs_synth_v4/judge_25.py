import re
from collections import defaultdict

# Hierarchical taxonomy: category -> subcategory -> keywords
_TAXONOMY = {
    "dairy": {
        "cheese": ["cheese", "queso", "asadero", "cheddar", "mozzarella", "parmesan", "feta", "ricotta", "brie", "gouda", "paneer"],
        "yogurt": ["yogurt", "yoghurt", "kefir"],
        "cream": ["cream", "half and half", "creamer", "sour cream"],
        "milk": ["milk", "buttermilk"],
        "butter": ["butter", "ghee"],
    },
    "meat": {
        "beef": ["beef", "steak", "veal", "brisket", "sirloin"],
        "pork": ["pork", "ham", "bacon", "prosciutto", "pancetta"],
        "lamb": ["lamb", "mutton", "goat"],
        "poultry": ["chicken", "turkey", "duck", "goose", "quail", "hen"],
        "sausage": ["sausage", "salami", "chorizo", "pepperoni", "hot dog", "frankfurter"],
    },
    "seafood": {
        "fish": ["fish", "salmon", "tuna", "swordfish", "cod", "tilapia", "halibut", "trout", "anchovy", "sardine", "mackerel"],
        "shellfish": ["crayfish", "crustaceans", "shrimp", "prawn", "crab", "lobster", "mussel", "clam", "oyster", "scallop", "squid"],
    },
    "produce_fruit": {
        "fruit": ["apple", "banana", "pineapple", "pomegranate", "durian", "mango", "berry", "blackberry", "blueberry",
                  "strawberry", "raspberry", "grape", "orange", "lemon", "lime", "peach", "pear", "plum", "cherry",
                  "melon", "kiwi", "papaya", "fig", "date", "apricot", "coconut", "avocado"],
    },
    "produce_veg": {
        "vegetable": ["chard", "spinach", "kale", "lettuce", "cabbage", "pepper", "peppers", "tomato", "onion", "carrot",
                      "celery", "broccoli", "cauliflower", "zucchini", "squash", "eggplant", "cucumber", "potato",
                      "mushroom", "leek", "beet", "radish", "asparagus", "okra", "corn"],
    },
    "grain": {
        "bread": ["bread", "toast", "bun", "roll", "bagel", "pita", "tortilla", "croissant"],
        "pasta": ["pasta", "gnocchi", "noodle", "spaghetti", "macaroni", "lasagna"],
        "cereal": ["cereal", "flakes", "oats", "oatmeal", "granola", "muesli"],
        "grain": ["rice", "flour", "wheat", "barley", "quinoa", "couscous", "bulgur", "millet"],
        "snack": ["chips", "crackers", "pretzel", "popcorn"],
    },
    "legume": {
        "soy": ["tofu", "sufu", "fuyu", "tempeh", "soy", "edamame"],
        "bean": ["bean", "beans", "lentil", "chickpea", "pea", "peas"],
    },
    "nut_seed": {
        "nut": ["nut", "nuts", "hazelnut", "hazelnuts", "almond", "walnut", "pecan", "cashew", "pistachio", "peanut", "macadamia"],
        "seed": ["seed", "seeds", "flaxseed", "flaxseeds", "chia", "sesame", "sunflower", "pumpkin seed"],
    },
    "spice_herb": {
        "spice": ["spices", "spice", "cinnamon", "cumin", "paprika", "ginger", "turmeric", "nutmeg", "clove", "pepper, black"],
        "herb": ["basil", "oregano", "thyme", "parsley", "cilantro", "rosemary", "dill", "mint", "sage"],
    },
    "oil_fat": {
        "oil": ["oil", "shortening", "lard", "margarine"],
    },
    "sweetener": {
        "sugar": ["sugar", "honey", "syrup", "molasses", "sweetener", "agave", "stevia"],
    },
    "condiment": {
        "sauce": ["sauce", "ketchup", "salsa", "gravy", "dressing", "pesto"],
        "mayo": ["mayonnaise", "mayo", "aioli"],
        "vinegar": ["vinegar"],
        "mustard": ["mustard", "relish"],
    },
}

_RELATED = {
    frozenset(["meat", "seafood"]): 0.25,
    frozenset(["produce_fruit", "produce_veg"]): 0.3,
    frozenset(["nut_seed", "legume"]): 0.3,
    frozenset(["oil_fat", "dairy"]): 0.2,
    frozenset(["condiment", "spice_herb"]): 0.15,
}

_PREP = set("fresh frozen thawed chopped diced sliced minced crushed shelled toasted boneless skinless "
            "grated shredded cooked raw ground whole large small medium optional for serving to taste "
            "and of the a plus extra peeled".split())


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _profile(text, head_text=None):
    """Return dict of (cat, sub) -> weight. Head text gets extra weight."""
    prof = defaultdict(float)
    padded = " " + re.sub(r"[^a-z, ]", " ", text) + " "
    head = " " + re.sub(r"[^a-z ]", " ", head_text or "") + " "
    for cat, subs in _TAXONOMY.items():
        for sub, kws in subs.items():
            for kw in kws:
                pat = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
                if re.search(pat, padded):
                    w = 1.0
                    if head_text and re.search(pat, head):
                        w = 2.0
                    prof[(cat, sub)] = max(prof[(cat, sub)], w)
    return prof


def _dominant(prof):
    if not prof:
        return None, None
    cat_w = defaultdict(float)
    for (c, s), w in prof.items():
        cat_w[c] += w
    cat = max(cat_w, key=cat_w.get)
    subs = {s: w for (c, s), w in prof.items() if c == cat}
    sub = max(subs, key=subs.get)
    return cat, sub


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ingredient(str(ingredient or ""))
        usda = str(usda_match or "").lower().strip()
        if not ing or not usda:
            return 0.0
        usda_head = usda.split(",")[0]

        ing_prof = _profile(ing)
        usda_prof = _profile(usda, usda_head)
        ic, isub = _dominant(ing_prof)
        uc, usub = _dominant(usda_prof)

        # Category consistency component (0..60)
        if ic is None and uc is None:
            cat_score = 25.0
        elif ic is None or uc is None:
            cat_score = 20.0
        elif ic == uc:
            cat_score = 45.0 + (15.0 if isub == usub else 0.0)
        else:
            rel = _RELATED.get(frozenset([ic, uc]), 0.0)
            cat_score = 60.0 * rel

        # Ingredient's primary category must be present in the USDA head (primary food)
        head_bonus = 0.0
        if ic is not None:
            head_prof = _profile(usda_head)
            head_cats = {c for (c, s) in head_prof}
            head_subs = {(c, s) for (c, s) in head_prof}
            if (ic, isub) in head_subs:
                head_bonus = 15.0
            elif ic in head_cats:
                head_bonus = 8.0
            elif head_cats:
                head_bonus = -10.0

        # Cross-category contamination: USDA head in a different category than ingredient's
        # strongest one (e.g. oil made from seeds) is penalized.
        contamination = 0.0
        if ic and uc and ic != uc:
            contamination = -10.0

        # Lexical anchor of content words (0..25)
        ing_words = [w for w in re.findall(r"[a-z]+", ing) if w not in _PREP and len(w) > 2]
        usda_words = set(re.findall(r"[a-z]+", usda))
        def stem(w):
            return w[:-1] if w.endswith("s") and len(w) > 3 else w
        usda_stems = {stem(w) for w in usda_words}
        if ing_words:
            hits = sum(1 for w in ing_words if stem(w) in usda_stems)
            lex = 25.0 * hits / len(ing_words)
        else:
            lex = 5.0

        score = cat_score + head_bonus + contamination + lex
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
