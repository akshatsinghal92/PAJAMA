import re

_CATS = {
    "dairy": "milk cheese yogurt yoghurt cream butter ricotta camembert brie cheddar mozzarella parmesan kefir whey curd buttermilk",
    "meat": "beef pork lamb veal turkey chicken duck bacon ham sausage steak liver meat venison goose rabbit patties",
    "fish": "fish salmon tuna swordfish cod trout shrimp prawn crab lobster oyster clam squid anchovy sardine mackerel tilapia scallop",
    "grain": "rice wheat flour bread cornbread oat oats barley rye pasta noodle noodles cereal bran corn cornmeal quinoa couscous cracker tortilla bulgur",
    "legume": "bean beans lentil lentils chickpea peas pea soybean tofu tempeh hummus edamame sufu fuyu",
    "nut": "nut nuts almond walnut pecan peanut cashew pistachio hazelnut pine pinyon seed seeds flaxseed flax linseed sesame sunflower pumpkin chia coconut",
    "spice": "spice spices ginger cinnamon pepper paprika cumin turmeric oregano basil thyme rosemary parsley cilantro dill mint sage clove nutmeg cardamom herb herbs vanilla extract",
    "oil": "oil oils lard shortening margarine fat tallow ghee",
    "sweet": "sugar honey syrup molasses sweetener stevia agave candy",
    "condiment": "sauce ketchup mustard mayonnaise vinegar dressing paste salsa relish soy pickle marinade",
    "fruit": "apple orange lemon lime banana berry berries grape peach pear plum mango pineapple melon cherry apricot fig date raisin applesauce fruit strawberry blueberry cranberry",
    "veg": "radish carrot onion garlic potato tomato lettuce spinach cabbage broccoli cauliflower celery cucumber squash zucchini pumpkin mushroom borage kale beet pepper eggplant seaweed kombu laver",
    "drink": "tea coffee juice soda beer wine water drink",
}
_W2C = {}
for _c, _ws in _CATS.items():
    for _w in _ws.split():
        _W2C.setdefault(_w, []).append(_c)

_MODS = {"dried", "powder", "powdered", "dry", "mix", "substitute", "oil", "extract", "juice", "canned",
         "frozen", "cooked", "fried", "roasted", "toasted", "smoked", "pickled", "fermented", "prepared",
         "butter", "paste", "sauce", "flavored", "imitation", "pudding", "puddings"}
_STOP = {"raw", "fresh", "whole", "of", "and", "or", "with", "the", "a", "in", "for", "from", "nfs", "regular",
         "all", "commercial", "varieties", "g", "sliced", "chopped", "diced", "ground", "large", "small", "medium"}


def _norm(t):
    t = str(t or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb|mg)?\b", " ", t)
    return t


def _stem(w):
    for s in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(s):
            return w[: -len(s)] + ("y" if s == "ies" else "")
    return w


def _cats(tokens):
    sc = {}
    n = len(tokens)
    for i, w in enumerate(tokens):
        for key in (w, _stem(w)):
            if key in _W2C:
                for c in _W2C[key]:
                    sc[c] = max(sc.get(c, 0), 1.0 + 0.2 * (i == 0 or i == n - 1))
                break
    return sc


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda_full = str(usda_match or "").lower()
        ing_main = ing.split(",")[0]
        usda_main = _norm(usda_full).split(",")[0]
        it = re.findall(r"[a-z]+", ing_main)
        ut_all = re.findall(r"[a-z]+", _norm(usda_full))
        ut = re.findall(r"[a-z]+", usda_main)
        if not it or not ut_all:
            return 0.0
        ic = _cats(it)
        uc = _cats(ut if ut else ut_all)
        uc_all = _cats(ut_all)
        score = 5.0
        if ic and uc:
            shared = set(ic) & set(uc)
            if shared:
                score += 3.0
            elif set(ic) & set(uc_all):
                score += 1.0
            else:
                score -= 3.5
        elif ic and uc_all:
            score += 1.5 if set(ic) & set(uc_all) else -1.5
        # content-word overlap
        iset = {_stem(w) for w in it if w not in _STOP and w not in _MODS}
        uset = {_stem(w) for w in ut_all if w not in _STOP and w not in _MODS}
        if iset:
            ov = len(iset & uset) / float(len(iset))
            score += 2.5 * ov
            if ov == 0:
                score -= 1.0
        # form-changing modifiers present on one side only
        im = {_stem(w) for w in re.findall(r"[a-z]+", ing) if w in _MODS}
        um = {_stem(w) for w in ut_all if w in _MODS}
        diff = im ^ um
        score -= 0.8 * min(len(diff), 3)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
