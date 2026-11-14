import re

# Food Category Consistency, variant 6: attribute-vector category matching.
# Instead of a single label, each food is described by binary category
# ATTRIBUTES (animal-origin, plant-origin, muscle-protein, dairy, produce,
# grain-starch, legume, nut/seed, seasoning, fat, sweet, sauce, liquid).
# Attributes are switched on by lexicon hits and by morphological suffix
# cues for unknown words (-fish, -berry/-berries, -seed, -nut, -meal,
# -flour, -oil). Two items are compared with a weighted Jaccard over the
# attribute sets, where "core" attributes (the defining category) weigh
# more than generic ones (plant-origin, animal-origin).

_LEX = {
    "muscle": "chicken turkey beef pork lamb veal ham bacon sausage steak duck meat patty breast thigh fish swordfish salmon tuna cod shrimp crab lobster scallop tilapia",
    "dairy": "milk cheese yogurt yoghurt cream butter cottage ricotta kefir whey cheddar mozzarella parmesan",
    "egg": "egg eggs yolk",
    "produce": "tomato tomatoes onion onions garlic carrot carrots broccoli spinach lettuce kale cabbage pepper peppers zucchini squash celery cucumber mushroom mushrooms corn potato potatoes eggplant fruit apple apples banana bananas orange oranges lemon lime grape grapes mango peach pear cherries pineapple melon guava ugli avocado",
    "grain": "rice pasta noodle noodles spaghetti macaroni bread flour oat oats cereal cereals barley quinoa couscous wheat cracker crackers tortilla gnocchi granola grains grain",
    "legume": "bean beans lentil lentils chickpea chickpeas tofu soy soybean edamame hummus peas",
    "nutseed": "nut nuts almond almonds walnut walnuts pecan cashew peanut peanuts pistachio hazelnut seed seeds chia flaxseed sesame sunflower tahini",
    "seasoning": "spice spices cinnamon cumin paprika nutmeg turmeric oregano basil thyme rosemary parsley cilantro dill sage ginger clove cloves cardamom seasoning salt",
    "fat": "oil lard shortening margarine ghee",
    "sweet": "sugar honey syrup molasses candy candies chocolate jam jelly",
    "sauce": "sauce dressing ketchup mustard mayonnaise vinegar salsa relish pesto gravy paste dip",
    "liquid": "juice beverage beverages drink soda tea coffee water nectar broth stock soup",
}
_W2A = {}
for _a, _ws in _LEX.items():
    for _w in _ws.split():
        _W2A.setdefault(_w, set()).add(_a)
_SUFFIX = [("fish", "muscle"), ("berry", "produce"), ("berries", "produce"), ("seed", "nutseed"),
           ("seeds", "nutseed"), ("nut", "nutseed"), ("nuts", "nutseed"), ("meal", "grain"),
           ("flour", "grain"), ("oil", "fat"), ("bread", "grain"), ("fruit", "produce")]
_ORIGIN = {"muscle": "animal", "dairy": "animal", "egg": "animal", "produce": "plant",
           "grain": "plant", "legume": "plant", "nutseed": "plant", "seasoning": "plant"}
_CORE_W = 3.0
_GENERIC_W = 0.7


def _attrs_of_word(w):
    a = set(_W2A.get(w, set()))
    if not a:
        for suf, attr in _SUFFIX:
            if w.endswith(suf) and len(w) > len(suf):
                a.add(attr)
                break
    return a


def _attrs(words):
    """Head-final: the last word that yields attributes defines the core set;
    form words (paste, juice, oil, spices) after a food also join the core."""
    core = set()
    for w in words:
        a = _attrs_of_word(w)
        if a:
            core = a if not (a & {"sauce", "liquid", "fat", "seasoning"} and core) else core | a
    full = set(core)
    for c in core:
        if c in _ORIGIN:
            full.add(_ORIGIN[c])
    return core, full


def _wjaccard(ci, fi, cu, fu):
    def w(a, core):
        return _CORE_W if a in core else _GENERIC_W
    inter = fi & fu
    union = fi | fu
    num = sum(max(w(a, ci), w(a, cu)) for a in inter)
    den = sum(max(w(a, ci), w(a, cu)) for a in union)
    return num / den if den else 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        # USDA: category header first then the specific food: read header + qualifier
        u_words = fields[0] + (fields[1] if len(fields[0]) == 1 and len(fields) > 1 else [])
        ci, fi = _attrs(iw)
        cu, fu = _attrs(u_words)
        if "spices" in fields[0] or "spice" in fields[0]:
            cu, fu = {"seasoning"}, {"seasoning", "plant"}
        if not fi or not fu:
            return 4.0 if not fi and not fu else 3.0
        return round(10.0 * _wjaccard(ci, fi, cu, fu), 3)
    except Exception:
        return 0.0
