import re

_ROLE_LEXICON = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "sweetener": ["sugar", "sugars", "honey", "syrup", "molasses", "agave", "sweetener", "nectar"],
    "acid": ["vinegar", "lemon juice", "lime juice", "verjuice"],
    "liquid": ["milk", "juice", "broth", "stock", "water", "wine", "beer", "cream", "drink", "beverage"],
    "protein": ["chicken", "beef", "pork", "lamb", "turkey", "fish", "steak", "bison", "buffalo",
                "sausage", "egg", "tofu", "herring", "bass", "salmon", "tuna", "shrimp", "veal", "duck"],
    "grain": ["rice", "flour", "oat", "oats", "wheat", "barley", "amaranth", "quinoa", "bran",
              "pasta", "spaghetti", "noodle", "bread", "corn", "millet"],
    "legume": ["bean", "beans", "lentil", "lentils", "pea", "peas", "chickpea", "chickpeas"],
    "nut": ["nut", "nuts", "hazelnut", "hazelnuts", "walnut", "pecan", "almond", "peanut",
            "cashew", "pistachio", "kernels", "seed", "seeds"],
    "aromatic": ["garlic", "onion", "ginger", "shallot", "spice", "spices", "herb", "pepper",
                 "cumin", "cinnamon", "basil", "oregano"],
    "dairy": ["yogurt", "cheese", "kefir", "sour cream"],
    "sauce": ["sauce", "paste", "ketchup", "dressing", "salsa", "gravy", "puree"],
    "fruit": ["papaya", "durian", "grape", "grapes", "apple", "banana", "berry", "berries",
              "pomegranate", "mango", "peach", "pear", "orange", "melon", "cherry"],
    "vegetable": ["radish", "turnip", "greens", "cucumber", "carrot", "cabbage", "spinach",
                  "potato", "tomato", "lettuce", "kale", "squash", "celery", "broccoli"],
}

_FORM_GROUPS = {
    "dried": {"dried", "dehydrated", "dry"},
    "juice": {"juice"},
    "spread": {"butter", "spread"},
    "milk": {"milk"},
    "ground": {"ground", "powder", "powdered", "meal"},
    "pickled": {"pickled", "brined"},
    "smoked": {"smoked"},
    "paste": {"paste", "puree"},
    "deli": {"deli", "luncheon"},
}

_DISH_MARKERS = {"salad", "entree", "sandwich", "casserole", "soup", "dinner", "meal", "with",
                 "made", "frozen entree", "stew", "pie", "burrito", "pizza"}

_PREP_NOISE = {"sliced", "chopped", "diced", "cubed", "minced", "ripe", "fresh", "thawed",
               "frozen", "baked", "cooked", "raw", "soaked", "overnight", "for", "garnish",
               "the", "a", "of", "to", "and", "or", "from", "tube", "large", "small", "medium",
               "whole", "fillets", "fillet", "boneless", "uncooked", "unprepared"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    return t


def _words(text):
    return re.findall(r"[a-z]+", text)


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _roles(text):
    found = {}
    padded = " " + " ".join(_words(text)) + " "
    for role, keys in _ROLE_LEXICON.items():
        for k in keys:
            pos = padded.find(" " + k + " ")
            if pos >= 0:
                if role not in found or pos < found[role]:
                    found[role] = pos
    return found


def _forms(words):
    ws = set(words)
    return {f for f, keys in _FORM_GROUPS.items() if ws & keys}


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = _clean(usda_match)
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        ing_main = ing_raw.split(",")[0]
        usda_parts = [p.strip() for p in usda_raw.split(",") if p.strip()]
        usda_head = usda_parts[0] if usda_parts else usda_raw

        ing_words = _words(ing_main)
        usda_words = _words(usda_raw)
        ing_core = [_stem(w) for w in ing_words if w not in _PREP_NOISE]
        usda_core = [_stem(w) for w in usda_words if w not in _PREP_NOISE]
        usda_head_core = [_stem(w) for w in _words(usda_head) if w not in _PREP_NOISE]

        score = 50.0

        # 1. Culinary role agreement (dominant role = earliest-positioned role)
        ing_roles = _roles(ing_main)
        usda_roles = _roles(usda_head)
        if not usda_roles:
            usda_roles = _roles(usda_raw)
        if ing_roles and usda_roles:
            ing_dom = min(ing_roles, key=ing_roles.get)
            usda_dom = min(usda_roles, key=usda_roles.get)
            shared = set(ing_roles) & set(usda_roles)
            if ing_dom == usda_dom:
                score += 12
            elif shared:
                score += 3
            else:
                score -= 18

        # 2. Identity of the key item: the last core word in the ingredient is
        #    usually the item noun; modifiers come before it.
        ing_set = set(ing_core)
        usda_set = set(usda_core)
        head_set = set(usda_head_core)
        if ing_core:
            item = ing_core[-1]
            if item in head_set:
                score += 14
            elif item in usda_set:
                score += 6
            else:
                score -= 10
            modifiers = [w for w in ing_core[:-1]]
            if modifiers:
                hit = sum(1 for m in modifiers if m in usda_set)
                miss = len(modifiers) - hit
                score += 6 * hit - 7 * miss
        coverage = len(ing_set & usda_set) / float(len(ing_set) or 1)
        score += 12 * coverage

        # 3. Form / texture behavior mismatch
        ing_forms = _forms(ing_words)
        usda_forms = _forms(usda_words)
        diff = ing_forms ^ usda_forms
        for f in diff:
            if f in ("juice", "milk", "spread"):
                score -= 14
            elif f in ("dried", "pickled", "smoked", "deli"):
                score -= 11
            else:
                score -= 7
        if "from dried" in usda_raw and "dried" in ing_forms:
            score -= 8  # prepared/cooked from dried vs. dry pulses: different handling

        # 4. Composite dish: a prepared dish cannot play a single-ingredient role
        usda_ws = set(usda_words)
        dish_hits = len(usda_ws & _DISH_MARKERS)
        ing_dish = len(set(ing_words) & _DISH_MARKERS)
        if dish_hits > ing_dish:
            score -= 16 * (dish_hits - ing_dish)
        if " and " in (" " + ing_main + " ") and " and " not in (" " + usda_raw + " "):
            score -= 12  # ingredient is a combination; single item misses part of the role

        # 5. Brand or extra specialty qualifiers mostly harmless; long tails slightly risky
        extra = len(usda_set - ing_set)
        score -= min(extra, 8) * 1.2

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
