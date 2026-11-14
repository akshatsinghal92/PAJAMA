import re

_ALIASES = [
    ("garbanzo beans", "chickpea"), ("garbanzo", "chickpea"), ("chickpeas", "chickpea"),
    ("aubergine", "eggplant"), ("courgette", "zucchini"), ("squash zucchini", "zucchini"),
    ("scallions", "scallion"), ("spring onions", "scallion"), ("spring onion", "scallion"),
    ("green onions", "scallion"), ("green onion", "scallion"),
    ("linseeds", "flaxseed"), ("linseed", "flaxseed"), ("flax seeds", "flaxseed"), ("flax", "flaxseed"),
    ("maize", "corn"), ("corn flakes", "corn flake"), ("cornflakes", "corn flake"),
    ("pinyon", "pine nut"), ("pine nuts", "pine nut"), ("pinenuts", "pine nut"),
    ("coriander leaves", "cilantro"), ("coriander", "cilantro"),
    ("rocket", "arugula"), ("capsicum", "bell pepper"), ("sweet pepper", "bell pepper"),
    ("prawns", "shrimp"), ("prawn", "shrimp"), ("swede", "rutabaga"), ("beetroot", "beet"),
    ("icing sugar", "powdered sugar"), ("confectioners sugar", "powdered sugar"),
    ("caster sugar", "sugar granulated"), ("castor sugar", "sugar granulated"),
    ("double cream", "heavy cream"), ("heavy whipping cream", "heavy cream"),
    ("cornstarch", "corn starch"), ("cornflour", "corn starch"),
    ("lox", "smoked salmon"), ("mince", "ground"), ("minced meat", "ground meat"),
    ("aubergines", "eggplant"), ("garbanzos", "chickpea"), ("french fries", "fries"),
    ("chips", "fries"), ("biscuits", "cookie"), ("yoghurt", "yogurt"), ("yogurts", "yogurt"),
    ("cilantro leaves", "cilantro"), ("bicarbonate of soda", "baking soda"),
    ("sodium bicarbonate", "baking soda"), ("potatoes", "potato"), ("tomatoes", "tomato"),
    ("peanuts", "peanut"), ("hazelnuts", "hazelnut"), ("filberts", "hazelnut"), ("filbert", "hazelnut"),
    ("grapes", "grape"), ("radishes", "radish"), ("onions", "onion"), ("almonds", "almond"),
    ("walnuts", "walnut"), ("cashews", "cashew"), ("pecans", "pecan"), ("beans", "bean"),
]
_STOP = set("""a an the of and or with without in on for to from fresh raw cooked fried baked boiled
dried dry frozen canned chopped sliced diced minced grated shredded crushed ground whole large small
medium optional garnish thawed peeled toasted roasted plain regular unsalted salted lean fat separable
choice made type style prepared ready serve serving pieces piece slices slice cut finely roughly
g kg ml oz lb cup cups tbsp tsp or more taste about each""".split())
_STATE = set("raw cooked fried baked boiled dried dry frozen canned toasted roasted smoked braised steamed pickled powder powdered ground".split())
_CONFLICT = [
    {"balsamic", "red", "white", "rice", "cider", "malt", "wine"},
    {"brown", "white", "coconut", "powdered", "granulated", "cane", "maple"},
    {"decaffeinated", "caffeinated"},
    {"soymilk", "soy", "almond", "coconut", "oat", "rice", "milk", "cow"},
]
_DIFFERENT_FOODS = ["oil", "cheese", "yogurt", "milk", "butter", "sugar", "vinegar", "bread", "flour",
                    "tea", "soymilk", "cereal", "seaweed", "beef", "pork", "chicken", "lamb", "turkey",
                    "fish", "salmon", "cream", "sauce", "dressing", "juice", "nut", "seed", "bean",
                    "egg", "rice", "pasta", "cookie", "cake", "soup", "wine", "beer", "souffle", "ball"]


def _canon(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb|l)\b", " ", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = " " + re.sub(r"\s+", " ", t).strip() + " "
    for a, b in sorted(_ALIASES, key=lambda x: -len(x[0])):
        t = t.replace(" " + a + " ", " " + b + " ")
    return t.split()


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _content(tokens):
    return [_stem(w) for w in tokens if w not in _STOP and len(w) > 1]


def judging_function(ingredient, usda_match):
    try:
        ingredient = str(ingredient or "")
        usda_match = str(usda_match or "")
        if not ingredient.strip() or not usda_match.strip():
            return 0.0
        ing_main = ingredient.split(",")[0]
        ing_all = _canon(ingredient)
        ing_t = _content(_canon(ing_main))
        parts = usda_match.split(",")
        usda_primary = _content(_canon(parts[0]))
        usda_all = _content(_canon(usda_match))
        if not ing_t or not usda_all:
            return 0.0
        iset, uset = set(ing_t), set(usda_all)
        pset = set(usda_primary)
        # 1. coverage of ingredient concepts by USDA entry
        cover = len(iset & uset) / float(len(iset))
        # 2. head-noun resolution: last content word of ingredient (head), also first of USDA
        head = ing_t[-1]
        head_hit = 1.0 if head in uset else 0.0
        # primary food of USDA must appear in ingredient (same food resolved)
        prim_hit = 0.0
        if pset:
            prim_hit = len(pset & iset) / float(len(pset))
        # USDA extra descriptors not in ingredient: mild penalty (excluding states)
        extra = [w for w in usda_all if w not in iset and w not in _STATE]
        extra_pen = min(len(extra), 6) * 0.04
        # Different-food conflict: USDA primary names a food class not present in ingredient
        conflict = 0.0
        for w in pset:
            if w in _DIFFERENT_FOODS and w not in iset:
                conflict += 0.35
        # ingredient food class not in usda
        for w in iset:
            if w in _DIFFERENT_FOODS and w not in uset:
                conflict += 0.25
        for grp in _CONFLICT:
            a = iset & grp
            b = uset & grp
            if a and b and not (a & b):
                conflict += 0.3
            elif a and not b and len(a) >= 1 and (a - {"white", "red", "milk"}):
                conflict += 0.15
        # state agreement
        istate = set(ing_all) & _STATE
        ustate = set(usda_all) & _STATE
        state = 0.0
        if istate and ustate:
            state = 0.1 if istate & ustate else -0.1
        elif ustate - {"raw"} and not istate:
            state = -0.05
        score = 0.45 * cover + 0.25 * head_hit + 0.3 * prim_hit + state - extra_pen - conflict
        # exact alias-resolved equality bonus
        if iset == uset or (iset <= uset and pset <= iset):
            score += 0.2
        return round(max(-1.0, min(1.5, score)) * 10, 3)
    except Exception:
        return 0.0
