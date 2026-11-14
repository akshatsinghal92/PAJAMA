import re

# Canonical concept lexicon: alias phrase -> concept id.
# Longest phrases are matched first so multi-word aliases resolve before single words.
_ALIASES = {
    # vegetables
    "aubergine": "eggplant", "eggplant": "eggplant", "brinjal": "eggplant",
    "courgette": "zucchini", "zucchini": "zucchini", "baby marrow": "zucchini",
    "scallion": "scallion", "scallions": "scallion", "spring onion": "scallion",
    "spring onions": "scallion", "green onion": "scallion", "green onions": "scallion",
    "rocket": "arugula", "arugula": "arugula", "roquette": "arugula",
    "coriander leaves": "cilantro", "cilantro": "cilantro", "fresh coriander": "cilantro",
    "capsicum": "bell pepper", "bell pepper": "bell pepper", "sweet pepper": "bell pepper",
    "peppers sweet": "bell pepper",
    "swede": "rutabaga", "rutabaga": "rutabaga",
    "beetroot": "beet", "beet": "beet", "beets": "beet",
    "mangetout": "snow pea", "snow peas": "snow pea", "snow pea": "snow pea",
    "okra": "okra", "ladies fingers": "okra", "lady fingers okra": "okra",
    "chicory": "endive", "endive": "endive",
    "celeriac": "celeriac", "celery root": "celeriac",
    "pak choi": "bok choy", "bok choy": "bok choy", "pak choy": "bok choy",
    "cabbage chinese pak choi": "bok choy",
    "napa cabbage": "napa", "chinese cabbage": "napa", "pe tsai": "napa",
    "sweetcorn": "corn", "corn": "corn", "maize": "corn",
    "artichoke": "artichoke", "artichokes": "artichoke", "artichoke hearts": "artichoke",
    "cos lettuce": "romaine", "romaine": "romaine",
    "yam": "yam", "sweet potato": "sweet potato", "sweet potatoes": "sweet potato",
    "kumara": "sweet potato",
    "potato": "potato", "potatoes": "potato",
    "tomato": "tomato", "tomatoes": "tomato",
    "garlic": "garlic", "ginger": "ginger", "onion": "onion", "onions": "onion",
    "shallot": "shallot", "shallots": "shallot",
    "mushroom": "mushroom", "mushrooms": "mushroom",
    "spinach": "spinach", "carrot": "carrot", "carrots": "carrot",
    # legumes
    "garbanzo": "chickpea", "garbanzo beans": "chickpea", "chickpea": "chickpea",
    "chickpeas": "chickpea", "chick peas": "chickpea", "bengal gram": "chickpea",
    "fava": "fava", "fava beans": "fava", "broad beans": "fava", "broadbeans": "fava",
    "edamame": "edamame", "green soybeans": "edamame",
    "lima beans": "lima", "butter beans": "lima",
    "navy beans": "navy", "haricot beans": "navy",
    "kidney beans": "kidney bean", "lentil": "lentil", "lentils": "lentil",
    "green beans": "green bean", "string beans": "green bean", "snap beans": "green bean",
    "french beans": "green bean",
    # fruit
    "durian": "durian", "tamarind": "tamarind", "pecan": "pecan", "pecans": "pecan",
    "cherry": "cherry", "cherries": "cherry", "plum": "plum", "plums": "plum",
    "prunes": "prune", "dried plums": "prune",
    "sultanas": "raisin", "raisins": "raisin",
    "passion fruit": "passionfruit", "granadilla": "passionfruit",
    "kiwi": "kiwifruit", "kiwifruit": "kiwifruit", "chinese gooseberry": "kiwifruit",
    "pawpaw": "papaya", "papaya": "papaya",
    "coconut": "coconut", "cranberries": "cranberry", "cranberry": "cranberry",
    "groundnut": "peanut", "groundnuts": "peanut", "peanut": "peanut", "peanuts": "peanut",
    "filbert": "hazelnut", "filberts": "hazelnut", "hazelnut": "hazelnut", "hazelnuts": "hazelnut",
    # herbs / spices
    "sage": "sage", "coriander seed": "coriander seed", "cumin": "cumin",
    "jeera": "cumin", "allspice": "allspice", "pimento": "allspice",
    "chilli": "chili", "chili": "chili", "chile": "chili", "chillies": "chili",
    "chili pepper": "chili", "hot pepper": "chili", "peppers hot chili": "chili",
    # dairy / fats / sugar
    "double cream": "heavy cream", "heavy cream": "heavy cream",
    "heavy whipping cream": "heavy cream", "whipping cream": "heavy cream",
    "single cream": "light cream", "light cream": "light cream",
    "icing sugar": "powdered sugar", "confectioners sugar": "powdered sugar",
    "powdered sugar": "powdered sugar",
    "caster sugar": "white sugar", "granulated sugar": "white sugar",
    "white sugar": "white sugar", "sugar white": "white sugar", "sugar": "white sugar",
    "cottage cheese": "cottage cheese", "cheese cottage": "cottage cheese",
    "plain flour": "ap flour", "all purpose flour": "ap flour", "all-purpose flour": "ap flour",
    "wheat flour white all purpose": "ap flour",
    "cornflour": "cornstarch", "cornstarch": "cornstarch", "corn starch": "cornstarch",
    "bicarbonate of soda": "baking soda", "baking soda": "baking soda",
    "olive oil": "olive oil", "salt": "salt", "table salt": "salt",
    # meats
    "minced beef": "ground beef", "ground beef": "ground beef", "beef mince": "ground beef",
    "beef ground": "ground beef",
    "ground turkey": "ground turkey", "turkey ground": "ground turkey",
    "prawns": "shrimp", "prawn": "shrimp", "shrimp": "shrimp",
    "chuck": "beef chuck", "chuck roast": "beef chuck", "beef chuck": "beef chuck",
    "sirloin": "beef sirloin", "beef sirloin": "beef sirloin", "beef top sirloin": "beef sirloin",
    "tongue": "tongue", "heart": "heart", "liver": "liver",
    "frankfurter": "frankfurter", "frankfurters": "frankfurter", "hot dog": "frankfurter",
    "hot dogs": "frankfurter", "wiener": "frankfurter",
    "ham": "ham", "bacon": "bacon", "streaky bacon": "bacon",
    "pork loin": "pork loin", "pork fresh loin": "pork loin",
    "lamb shank": "lamb shank", "lamb hind-shank": "lamb shank", "lamb hind shank": "lamb shank",
    "whitefish": "whitefish", "sausage": "sausage",
    "veal": "veal", "duck": "duck", "chicken": "chicken", "turkey": "turkey",
    "beef": "beef", "pork": "pork", "lamb": "lamb",
    # misc
    "spaghetti sauce": "pasta sauce", "marinara": "pasta sauce", "pasta sauce": "pasta sauce",
    "plum sauce": "plum sauce", "sauce plum": "plum sauce",
    "tomato juice": "tomato juice", "vegetable juice": "vegetable juice",
    "aubergines": "eggplant", "courgettes": "zucchini",
}

# Concepts that indicate a distinct product form; disagreement means different food.
_FORM_WORDS = {
    "juice", "nectar", "pulp", "paste", "powder", "sauce", "spread", "salad", "chips",
    "cookies", "cookie", "entree", "soup", "dressing", "syrup", "jam", "jelly", "candy",
    "bar", "bars", "pie", "cake", "drink", "beverage", "patty", "sandwich", "pizza",
    "casserole", "dip", "cracker", "crackers", "flakes", "cereal", "milk", "cream",
}

# Attribute antonym groups: if both sides specify different members, they conflict.
_ATTR_GROUPS = [
    {"sweet", "tart", "sour"},
    {"sweetened", "unsweetened"},
    {"lean", "fat", "lowfat", "nonfat", "fat-free", "whole"},
    {"dried", "fresh", "canned", "raw"},
    {"smoked", "unsmoked"},
    {"salted", "unsalted", "low sodium"},
    {"lactose reduced"},
]

_STOP = {
    "g", "kg", "ml", "the", "a", "an", "of", "for", "to", "with", "or", "in", "and",
    "fresh", "chopped", "sliced", "diced", "minced", "large", "small", "medium",
    "optional", "garnish", "serving", "taste", "thawed", "drained", "raw", "cooked",
    "boneless", "bone-in", "skinless", "trimmed", "separable", "all", "grades",
    "includes", "foods", "usda", "s", "food", "distribution", "program", "frozen",
    "ready-to-serve", "prepared", "uncooked", "boiled", "fine", "finely", "roughly",
}


def _norm(text):
    t = str(text or "").lower()
    t = t.replace("’", "'")
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb)\b\.?", " ", t)
    t = re.sub(r"\d+(?:/\d+)?", " ", t)
    t = re.sub(r"[\"'`]", "", t)
    return t


def _parse_ingredient(ing):
    t = _norm(ing)
    parens = re.findall(r"\(([^)]*)\)", t)
    core = re.sub(r"\([^)]*\)", " ", t)
    head, _, tail = core.partition(",")
    return head.strip(), tail.strip(), " ".join(parens)


def _parse_usda(usda):
    t = _norm(usda)
    parens = re.findall(r"\(([^)]*)\)", t)
    core = re.sub(r"\([^)]*\)", " ", t)
    parts = [p.strip() for p in core.split(",") if p.strip()]
    return parts, " ".join(parens)


def _words(text):
    return [w for w in re.findall(r"[a-z][a-z\-]*", text or "")]


def _concepts(text):
    """Greedy longest-match resolution of alias phrases to concept ids."""
    words = _words(text)
    found = []
    i = 0
    while i < len(words):
        matched = False
        for n in (4, 3, 2, 1):
            if i + n > len(words):
                continue
            phrase = " ".join(words[i:i + n])
            if phrase in _ALIASES:
                found.append(_ALIASES[phrase])
                i += n
                matched = True
                break
            # crude plural stripping
            if n == 1 and phrase.endswith("s") and phrase[:-1] in _ALIASES:
                found.append(_ALIASES[phrase[:-1]])
                i += 1
                matched = True
                break
        if not matched:
            i += 1
    return found


def _attrs(text):
    t = " " + " ".join(_words(text)) + " "
    out = set()
    for grp in _ATTR_GROUPS:
        for a in grp:
            if " " + a + " " in t:
                out.add(a)
    return out


def _attr_conflicts(a, b):
    n = 0
    for grp in _ATTR_GROUPS:
        x = a & grp
        y = b & grp
        if x and y and not (x & y):
            n += 1
        elif len(grp) == 1 and (x or y) and not (x and y):
            # one-sided special attribute (e.g. lactose reduced)
            n += 0.5
    return n


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "shxo":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_head, ing_tail, ing_par = _parse_ingredient(ingredient)
        usda_parts, usda_par = _parse_usda(usda_match)
        if not ing_head or not usda_parts:
            return 0.0

        usda_primary = usda_parts[0]
        usda_full = " ".join(usda_parts)
        # Reordered USDA name: "Cheese, cottage" -> also try "cheese cottage"
        usda_lead2 = " ".join(usda_parts[:2])

        ing_concepts = _concepts(ing_head)
        usda_concepts_all = _concepts(usda_full + " " + usda_par) + _concepts(usda_lead2)
        usda_concepts_primary = _concepts(usda_primary) + _concepts(usda_lead2)

        score = 0.0

        # 1. Concept (alias-resolved) agreement
        ic = set(ing_concepts)
        uc_all = set(usda_concepts_all)
        uc_pri = set(usda_concepts_primary)
        shared = ic & uc_all
        if ic:
            # the most specific ingredient concept is usually the last one resolved
            key = ing_concepts[-1]
            if key in uc_pri:
                score += 45
            elif key in uc_all:
                score += 32
            elif shared:
                score += 18
            else:
                # resolved to known but different foods
                if uc_pri and not (uc_pri & ic):
                    score -= 15
            score += 6 * (len(shared) / max(1, len(ic)))
        # 2. Residual lexical evidence (stemmed content words), weighted lightly
        iw = {_stem(w) for w in _words(ing_head) if w not in _STOP and len(w) > 2}
        uw = {_stem(w) for w in _words(usda_full + " " + usda_par) if w not in _STOP and len(w) > 2}
        if iw:
            cover = len(iw & uw) / len(iw)
            score += 20 * cover
            if not ic and cover == 0:
                score -= 10

        # 3. Compound ingredient ("X and Y") matched to only one food
        ing_words = _words(ing_head)
        usda_words_all = set(_words(usda_full))
        if "and" in ing_words and "and" not in usda_words_all:
            score -= 22
        # USDA describes a combination dish the ingredient isn't
        if ("and" in usda_words_all or "with" in _words(usda_primary)) and "and" not in ing_words:
            score -= 15

        # 4. Product-form mismatch (juice vs pulp, spread vs ham, etc.)
        ing_forms = set(ing_words) & _FORM_WORDS
        usda_forms = set(_words(usda_full)) & _FORM_WORDS
        if usda_forms - ing_forms:
            score -= 12 * len(usda_forms - ing_forms)
        if ing_forms - usda_forms:
            score -= 8 * len(ing_forms - usda_forms)

        # 5. Attribute conflicts (sweet vs tart, lean vs regular, dried vs canned ...)
        ia = _attrs(ing_head + " " + ing_tail)
        ua = _attrs(usda_full + " " + usda_par)
        score -= 9 * _attr_conflicts(ia, ua)
        # USDA adds diet-modifying qualifiers absent from ingredient
        for q in ("low sodium", "lowfat", "nonfat", "reduced", "sweetened", "imported", "light"):
            if q in " ".join(_words(usda_full)) and q not in " ".join(ing_words):
                score -= 4
        # ingredient specifies a qualifier USDA ignores
        for q in ("lean", "smoked", "canned", "dried", "chicken"):
            if q in ing_words and q not in usda_words_all and q not in _words(usda_par):
                score -= 5

        # 6. Brand-like USDA entry (Title Case brand, primary not a food concept)
        raw_primary = str(usda_match).split(",")[0]
        caps = re.findall(r"\b[A-Z][a-z]+", raw_primary)
        if len(caps) >= 2 and not uc_pri:
            score -= 10
        if uc_pri == set() and ic and not shared:
            score -= 10

        return round(max(0.0, min(100.0, score + 20.0)), 3)
    except Exception:
        return 0.0
