import re

# Lexicon of compound food names: (modifier tuple, head). The modifier changes the food.
_COMPOUNDS = [
    ("sweet", "potato"), ("coconut", "milk"), ("coconut", "cream"), ("coconut", "sugar"),
    ("coconut", "oil"), ("coconut", "water"), ("almond", "milk"), ("soy", "milk"),
    ("oat", "milk"), ("rice", "milk"), ("peanut", "butter"), ("almond", "butter"),
    ("pecan", "butter"), ("cashew", "butter"), ("apple", "butter"), ("cocoa", "butter"),
    ("green", "tea"), ("black", "tea"), ("sea", "bass"), ("striped", "bass"),
    ("kidney", "beans"), ("green", "beans"), ("black", "beans"), ("pinto", "beans"),
    ("navy", "beans"), ("lima", "beans"), ("pine", "nuts"), ("brown", "sugar"),
    ("powdered", "sugar"), ("corn", "bread"), ("corn", "starch"), ("corn", "syrup"),
    ("corn", "flour"), ("rice", "flour"), ("rice", "vinegar"), ("cream", "cheese"),
    ("cottage", "cheese"), ("ice", "cream"), ("sour", "cream"), ("whipped", "cream"),
    ("half", "half"), ("plum", "sauce"), ("barbecue", "sauce"), ("soy", "sauce"),
    ("fish", "sauce"), ("hot", "sauce"), ("tomato", "sauce"), ("hot", "dog"),
    ("stew", "meat"), ("swiss", "chard"), ("bell", "pepper"), ("chili", "pepper"),
    ("black", "pepper"), ("sweet", "corn"), ("pop", "corn"), ("egg", "plant"),
    ("butter", "milk"), ("butter", "nut"), ("water", "chestnut"), ("water", "melon"),
    ("star", "fruit"), ("passion", "fruit"), ("grape", "fruit"), ("bread", "fruit"),
    ("jack", "fruit"), ("pork", "chop"), ("lamb", "chop"), ("beef", "shank"),
    ("lamb", "shank"), ("lamb", "liver"), ("beef", "liver"), ("chicken", "liver"),
    ("beef", "kidney"), ("lamb", "heart"), ("chicken", "breast"), ("turkey", "breast"),
    ("chicken", "frankfurter"), ("turkey", "frankfurter"), ("beef", "frankfurter"),
    ("chicken", "sausage"), ("turkey", "bacon"), ("indian", "date"), ("split", "peas"),
    ("snow", "peas"), ("chick", "peas"), ("green", "onion"), ("spring", "onion"),
    ("red", "onion"), ("sea", "salt"), ("garlic", "salt"), ("celery", "salt"),
    ("evaporated", "milk"), ("condensed", "milk"), ("powdered", "milk"), ("dry", "milk"),
    ("goat", "cheese"), ("goat", "milk"), ("brown", "rice"), ("wild", "rice"),
    ("baking", "soda"), ("baking", "powder"), ("tea", "leaves"), ("collard", "greens"),
    ("mustard", "greens"), ("turnip", "greens"), ("sesame", "oil"), ("olive", "oil"),
    ("maple", "syrup"), ("rice", "cake"), ("fish", "cake"), ("crab", "cake"),
    ("sunflower", "seeds"), ("pumpkin", "seeds"), ("bean", "sprouts"),
]

_ALIASES = {
    "cornbread": "corn bread", "eggplant": "egg plant", "buttermilk": "butter milk",
    "popcorn": "pop corn", "watermelon": "water melon", "grapefruit": "grape fruit",
    "breadfruit": "bread fruit", "jackfruit": "jack fruit", "starfruit": "star fruit",
    "butternut": "butter nut", "cornstarch": "corn starch", "chickpeas": "chick peas",
    "chickpea": "chick peas", "hotdog": "hot dog", "frank": "frankfurter",
    "franks": "frankfurter", "bbq": "barbecue", "scallion": "green onion",
    "scallions": "green onion", "pinyon": "pine", "tamarind": "indian date",
    "tamarinds": "indian date", "chops": "chop", "garbanzo": "chick peas",
}

_STOP = {
    "g", "kg", "mg", "ml", "oz", "lb", "and", "or", "with", "of", "the", "a", "an",
    "in", "for", "from", "to", "fresh", "raw", "cooked", "chopped", "sliced", "diced",
    "minced", "store", "bought", "nfs", "ns", "all", "varieties", "made", "home",
    "recipe", "ready", "serve", "unheated", "frozen", "thawed", "boneless", "lean",
    "only", "quick", "cooking", "dried", "dry", "separable", "fat", "uncooked",
    "large", "small", "medium", "mixed", "equal", "parts", "including", "assorted",
    "brands", "enriched", "inch", "whole", "mature", "variety", "meats", "products",
    "by", "soft", "reduced", "simmered", "grilled", "roasted", "imported", "center",
}


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _normalize(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb|lbs)\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = t.replace("-", " ").replace("/", " ")
    words = re.findall(r"[a-z]+", t)
    out = []
    for w in words:
        rep = _ALIASES.get(w)
        if rep is None:
            rep = _ALIASES.get(_singular(w), w)
        out.extend(rep.split())
    return [_singular(w) for w in out]


_COMP = [(_singular(m), _singular(h)) for m, h in _COMPOUNDS]


def _find_compounds(tokens, adjacent):
    found = set()
    tset = set(tokens)
    for m, h in _COMP:
        if adjacent:
            for i in range(len(tokens) - 1):
                if tokens[i] == m and tokens[i + 1] == h:
                    found.add((m, h))
                    break
            # "half and half"
            if m == h == "half" and tokens.count("half") >= 2:
                found.add((m, h))
        else:
            if m in tset and h in tset:
                if m == h and tokens.count(m) < 2:
                    continue
                found.add((m, h))
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = _normalize(ingredient)
        usda = _normalize(usda_match)
        if not ing or not usda:
            return 0.0

        ing_set = set(ing)
        usda_set = set(usda)

        # Ingredient compounds are read in natural (adjacent) order.
        ing_comp = _find_compounds(ing, adjacent=True)
        # USDA descriptions are inverted ("Beans, kidney"), so look for both parts anywhere.
        usda_comp_loose = _find_compounds(usda, adjacent=False)
        usda_comp_tight = _find_compounds(usda, adjacent=True)

        score = 50.0

        # 1. Ingredient compounds must survive intact.
        for m, h in ing_comp:
            if (m, h) in usda_comp_tight:
                score += 22
            elif (m, h) in usda_comp_loose:
                score += 16
            elif h in usda_set and m not in usda_set:
                # Kept only the head: "pecan butter" -> "peanut butter"
                score -= 28
            elif m in usda_set and h not in usda_set:
                # Kept only the modifier: "beef kidney" -> "kidney beans" style
                score -= 18
            else:
                score -= 10

        # 2. USDA forms a compound around a word that is bare (not compounded) in the ingredient.
        ing_heads_modifiers = set()
        for m, h in ing_comp:
            ing_heads_modifiers.add(m)
            ing_heads_modifiers.add(h)
        for m, h in usda_comp_tight | usda_comp_loose:
            if (m, h) in ing_comp:
                continue
            if m in ing_set and h in ing_set:
                continue
            if (h in ing_set or m in ing_set):
                # e.g. ingredient "kidney" (beef) vs USDA "kidney beans";
                # ingredient "sugar" (coconut) vs USDA "brown sugar".
                score -= 20

        # 3. General content overlap anchored on the primary (first comma segment) of USDA.
        ing_content = [w for w in ing if w not in _STOP]
        usda_content = [w for w in usda if w not in _STOP]
        ic = set(ing_content)
        uc = set(usda_content)
        if ic and uc:
            inter = ic & uc
            recall = len(inter) / len(ic)
            precision = len(inter) / len(uc)
            score += 25 * recall + 8 * precision
            if not inter:
                score -= 30

        primary = _normalize(str(usda_match).split(",")[0])
        prim = [w for w in primary if w not in _STOP]
        if prim:
            if any(w in ic for w in prim):
                score += 8
            else:
                score -= 8

        # 4. Last content word of ingredient is typically the head noun; it should appear.
        if ing_content:
            head = ing_content[-1]
            if head in uc:
                score += 6
            else:
                score -= 6

        return float(max(0.0, min(100.0, score)))
    except Exception:
        return 0.0
