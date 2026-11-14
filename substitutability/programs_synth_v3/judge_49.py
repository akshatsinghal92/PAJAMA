import re

_CATEGORY_LEXICON = {
    "dairy": ["milk", "cheese", "yogurt", "yoghurt", "cream", "butter", "kefir", "whey",
              "curd", "ricotta", "mozzarella", "cheddar", "parmesan", "feta", "ghee",
              "buttermilk", "custard", "ice cream", "brie", "gouda", "mascarpone"],
    "red_meat": ["beef", "pork", "lamb", "veal", "mutton", "goat", "venison", "bison",
                 "ham", "bacon", "steak", "brisket", "shank", "loin", "rib", "chuck"],
    "poultry": ["chicken", "turkey", "duck", "goose", "quail", "hen", "capon", "pheasant"],
    "processed_meat": ["sausage", "salami", "cervelat", "thuringer", "bologna", "frankfurter",
                       "hot dog", "pepperoni", "chorizo", "kielbasa", "bratwurst", "pastrami",
                       "luncheon", "mortadella", "liverwurst"],
    "seafood": ["fish", "salmon", "tuna", "cod", "shrimp", "prawn", "crab", "lobster",
                "clam", "mussel", "oyster", "scallop", "sardine", "anchovy", "trout",
                "tilapia", "halibut", "mackerel", "squid", "octopus"],
    "egg": ["egg", "eggs", "yolk"],
    "fruit": ["apple", "banana", "papaya", "mango", "orange", "lemon", "lime", "berry",
              "berries", "strawberry", "blueberry", "raspberry", "grape", "pear", "peach",
              "plum", "cherry", "pineapple", "melon", "watermelon", "kiwi", "apricot",
              "fig", "date", "dates", "coconut", "avocado", "pomegranate", "grapefruit"],
    "vegetable": ["onion", "carrot", "potato", "tomato", "pepper", "spinach", "lettuce",
                  "cabbage", "broccoli", "cauliflower", "celery", "cucumber", "zucchini",
                  "squash", "pumpkin", "eggplant", "kale", "mushroom", "beet", "radish",
                  "leek", "asparagus", "artichoke", "corn", "peas", "okra", "shallot",
                  "turnip", "parsnip", "sweet potato", "yam", "chard", "arugula"],
    "grain": ["rice", "wheat", "flour", "bread", "pasta", "noodle", "noodles", "oat",
              "oats", "barley", "rye", "quinoa", "couscous", "bulgur", "cornmeal",
              "tortilla", "tortillas", "bran", "cereal", "cracker", "crackers", "bagel",
              "roll", "bun", "spaghetti", "macaroni", "millet", "semolina", "paper",
              "pita", "muffin", "biscuit"],
    "legume": ["bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "soy",
               "soybean", "tofu", "tempeh", "edamame", "pea", "garbanzo", "hummus"],
    "nut_seed": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "peanut",
                 "seed", "seeds", "sesame", "chia", "flax", "flaxseed", "sunflower",
                 "pumpkin seed", "pine nut", "macadamia", "tahini", "nut", "nuts"],
    "spice_herb": ["spice", "spices", "cinnamon", "ginger", "cumin", "paprika", "turmeric",
                   "oregano", "basil", "thyme", "rosemary", "parsley", "cilantro", "dill",
                   "nutmeg", "clove", "cloves", "garlic", "pepper black", "cardamom",
                   "coriander", "sage", "mint", "bay", "allspice", "saffron", "vanilla",
                   "chili powder", "curry"],
    "oil_fat": ["oil", "lard", "shortening", "margarine", "tallow", "suet", "fat"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener", "stevia",
                  "candy", "chocolate", "jam", "jelly", "marmalade", "carob"],
    "condiment": ["sauce", "ketchup", "mustard", "mayonnaise", "vinegar", "dressing",
                  "salsa", "relish", "soy sauce", "paste", "pesto", "gravy", "chutney"],
    "beverage": ["juice", "coffee", "tea", "wine", "beer", "soda", "water", "drink"],
}

# Related categories: partial credit rather than full penalty
_RELATED = {
    frozenset(["red_meat", "processed_meat"]): 0.45,
    frozenset(["poultry", "processed_meat"]): 0.35,
    frozenset(["red_meat", "poultry"]): 0.15,
    frozenset(["vegetable", "legume"]): 0.3,
    frozenset(["dairy", "oil_fat"]): 0.3,
    frozenset(["fruit", "vegetable"]): 0.2,
    frozenset(["sweetener", "condiment"]): 0.2,
    frozenset(["fruit", "beverage"]): 0.25,
    frozenset(["grain", "legume"]): 0.15,
    frozenset(["spice_herb", "condiment"]): 0.25,
    frozenset(["nut_seed", "legume"]): 0.3,
}

_PREP_WORDS = set("""fresh frozen thawed chopped diced minced sliced cubed ripe cooked raw
grated shredded peeled crushed ground whole large small medium finely roughly pan fried
pan-fried baked boiled steamed roasted grilled broiled lean only drained rinsed soft hard
toasted melted softened beaten optional to taste and or of the a for with from""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|cups?|tbsp|tsp)?\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?\s*%", " ", t)
    t = re.sub(r"[^a-z\s,\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _category_profile(text, positional_weights):
    """Return dict category->weight. positional_weights is a list of (segment, weight)."""
    profile = {}
    for seg, w in positional_weights:
        padded = " " + seg.replace("-", " ") + " "
        for cat, words in _CATEGORY_LEXICON.items():
            hits = 0
            for kw in words:
                if (" " + kw + " ") in padded:
                    hits += 1 + kw.count(" ")
            if hits:
                profile[cat] = profile.get(cat, 0.0) + w * hits
    return profile


def _ingredient_segments(text):
    t = _clean(text)
    main = t.split(",")[0]
    words = [w for w in main.split() if w not in _PREP_WORDS]
    if not words:
        return [(main, 1.0)], set()
    # last noun (head) is most informative in English noun phrases
    head = words[-1]
    mods = " ".join(words[:-1])
    segs = [(head, 3.0)]
    if mods:
        segs.append((mods, 1.0))
    segs.append((" ".join(words[-2:]), 1.5))
    return segs, set(words)


def _usda_segments(text):
    t = _clean(text)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    segs = []
    tokens = set()
    for i, p in enumerate(parts):
        w = 3.0 if i == 0 else (1.2 if i == 1 else 0.6)
        segs.append((p, w))
        tokens.update(x for x in p.split() if x not in _PREP_WORDS)
    return segs, tokens, (parts[0] if parts else "")


def _dominant(profile):
    if not profile:
        return None, 0.0
    total = sum(profile.values())
    cat = max(profile, key=profile.get)
    return cat, profile[cat] / total if total else 0.0


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_segs, ing_tokens = _ingredient_segments(ingredient)
        usda_segs, usda_tokens, usda_primary = _usda_segments(usda_match)

        p_ing = _category_profile(ingredient, ing_segs)
        p_usda = _category_profile(usda_match, usda_segs)

        cat_i, conf_i = _dominant(p_ing)
        cat_u, conf_u = _dominant(p_usda)

        # --- category consistency component (0..6) ---
        if cat_i is None or cat_u is None:
            cat_score = 2.0  # unknown category: neutral-low
        elif cat_i == cat_u:
            cat_score = 4.5 + 1.5 * min(conf_i, conf_u)
        else:
            rel = _RELATED.get(frozenset([cat_i, cat_u]), 0.0)
            # overlap of full distributions (soft agreement)
            ti = sum(p_ing.values()) or 1.0
            tu = sum(p_usda.values()) or 1.0
            overlap = sum(min(p_ing.get(c, 0) / ti, p_usda.get(c, 0) / tu)
                          for c in set(p_ing) | set(p_usda))
            cat_score = 6.0 * max(rel, 0.6 * overlap) * 0.8

        # --- identity anchor within category (0..4) ---
        si = {_stem(w) for w in ing_tokens if len(w) > 2}
        su = {_stem(w) for w in usda_tokens if len(w) > 2}
        prim = {_stem(w) for w in usda_primary.split() if len(w) > 2 and w not in _PREP_WORDS}
        anchor = 0.0
        if prim and si:
            if prim & si:
                anchor += 2.0
            elif any(a in b or b in a for a in prim for b in si if len(a) > 3 and len(b) > 3):
                anchor += 1.0
        if si:
            coverage = len(si & su) / float(len(si))
            anchor += 2.0 * coverage
            # penalize USDA descriptors that are extra specific foods (different identity)
            extra_food = 0
            for w in su - si:
                for cat, words in _CATEGORY_LEXICON.items():
                    if w in words and cat != cat_i:
                        extra_food += 1
                        break
            anchor -= 0.5 * min(extra_food, 3)

        # cross-category with no anchor: strong penalty
        score = cat_score + max(anchor, -1.5)
        if cat_i and cat_u and cat_i != cat_u and anchor < 1.0:
            score *= 0.6
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
