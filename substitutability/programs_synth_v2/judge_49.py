import re

# Food Category Consistency, variant 1: lexicon classification with a
# category-affinity matrix.
# Both texts are classified into one of: dairy, produce_veg, produce_fruit,
# meat, poultry, seafood, egg, grain, legume, nut_seed, spice_herb, oil_fat,
# sweetener, condiment, beverage, prepared. The USDA description is
# classified from its primary field first (USDA uses category-like headers:
# "Spices, ...", "Fish, ...", "Beverages, ..."), the ingredient from its head
# noun (last matching keyword wins). Same category = 10; related categories
# (meat/poultry, veg/fruit, grain/legume ...) get partial credit.

_CATS = {
    "dairy": "milk cheese yogurt yoghurt cream butter buttermilk kefir ricotta cottage mozzarella cheddar parmesan feta whey ghee",
    "produce_veg": "tomato onion garlic carrot broccoli spinach lettuce kale cabbage pepper zucchini squash potato corn celery cucumber mushroom eggplant pea asparagus beet radish leek shallot vegetable vegetables",
    "produce_fruit": "fruit apple banana orange lemon lime berry blueberry strawberry raspberry grape mango peach pear plum cherry pineapple melon guava ugli grapefruit kiwi avocado date fig raisin",
    "meat": "beef pork lamb veal ham bacon sausage steak venison goat salami pepperoni",
    "poultry": "chicken turkey duck goose poultry hen",
    "seafood": "fish swordfish salmon tuna cod tilapia shrimp prawn crab lobster scallop clam mussel oyster anchovy sardine trout halibut",
    "egg": "egg eggs yolk",
    "grain": "rice pasta noodle spaghetti macaroni bread flour oat oats cereal cereals barley quinoa couscous wheat cracker tortilla gnocchi bagel granola",
    "legume": "bean beans lentil lentils chickpea chickpeas tofu soy soybean edamame hummus",
    "nut_seed": "nut nuts almond walnut pecan cashew peanut pistachio hazelnut seed seeds chia flaxseed sesame sunflower tahini",
    "spice_herb": "spice spices cinnamon cumin paprika nutmeg turmeric oregano basil thyme rosemary parsley cilantro dill sage ginger clove cardamom seasoning",
    "oil_fat": "oil lard shortening margarine",
    "sweetener": "sugar honey syrup molasses candy candies chocolate jam jelly sweetener",
    "condiment": "sauce dressing ketchup mustard mayonnaise vinegar salsa relish pesto gravy paste dip",
    "beverage": "juice beverage beverages drink soda tea coffee water nectar smoothie",
    "prepared": "soup stew casserole pizza sandwich burrito salad patty nuggets dinner entree",
}
_WORD2CAT = {}
for _c, _ws in _CATS.items():
    for _w in _ws.split():
        _WORD2CAT[_w] = _c

_RELATED = {
    frozenset(["meat", "poultry"]): 5.0, frozenset(["poultry", "seafood"]): 3.5,
    frozenset(["meat", "seafood"]): 3.0, frozenset(["produce_veg", "produce_fruit"]): 4.5,
    frozenset(["grain", "legume"]): 3.5, frozenset(["legume", "nut_seed"]): 3.5,
    frozenset(["oil_fat", "dairy"]): 3.0, frozenset(["condiment", "spice_herb"]): 3.0,
    frozenset(["sweetener", "condiment"]): 2.5, frozenset(["beverage", "produce_fruit"]): 2.5,
    frozenset(["prepared", "meat"]): 3.0, frozenset(["prepared", "poultry"]): 3.0,
    frozenset(["prepared", "grain"]): 2.5, frozenset(["dairy", "egg"]): 2.5,
    frozenset(["produce_veg", "spice_herb"]): 2.0, frozenset(["produce_veg", "legume"]): 3.5,
}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _cat_of_words(words, last_wins=True):
    found = None
    for w in words:
        c = _WORD2CAT.get(w) or _WORD2CAT.get(_sing(w))
        if c:
            found = c
            if not last_wins:
                return c
    return found


def _cat_ingredient(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    words = re.findall(r"[a-z]+", t)
    # olive oil -> oil_fat; peanut butter -> nut_seed; garlic paste -> condiment? keep head
    if "butter" in words and words.index("butter") > 0 and _WORD2CAT.get(words[words.index("butter") - 1]) == "nut_seed":
        return "nut_seed"
    return _cat_of_words(words, last_wins=True)


def _cat_usda(text):
    fields = [re.findall(r"[a-z]+", f) for f in text.lower().split(",")]
    fields = [f for f in fields if f]
    if not fields:
        return None
    first = fields[0]
    # USDA style: primary field names the category / food. Prefer its head.
    c = _cat_of_words(first, last_wins=True)
    if c == "condiment" and len(fields) > 1 and first[-1] in ("paste", "sauce"):
        c2 = _cat_of_words(fields[1])
        if c2 == "nut_seed":
            return c2
    if c is None and len(fields) > 1:
        c = _cat_of_words(fields[1])
    return c


def judging_function(ingredient, usda_match):
    try:
        ci = _cat_ingredient(str(ingredient or ""))
        cu = _cat_usda(str(usda_match or ""))
        if ci is None and cu is None:
            return 5.0
        if ci is None or cu is None:
            return 4.0
        if ci == cu:
            return 10.0
        return _RELATED.get(frozenset([ci, cu]), 0.5)
    except Exception:
        return 0.0
