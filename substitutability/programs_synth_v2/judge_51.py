import re

# Food Category Consistency, variant 3: culinary-ROLE categories.
# Cooks think of categories by the role a food plays in a dish, which is
# what determines whether a swap "changes the dish":
#   protein_main, starch_base, vegetable, fruit, aromatic (garlic/onion/
#   ginger root), seasoning (dried spices, salt), fat_medium, sweetener,
#   liquid (juice, broth, milk), sauce_condiment, dairy_rich (cheese, cream,
#   yogurt), crunchy_seed (nuts, seeds).
# Role detection uses both the food noun and FORM cues: "ginger" fresh is an
# aromatic, but "Spices, ginger, ground" is a seasoning; "orange" is a fruit,
# but "orange juice" is a liquid. A role-swap cost matrix gives the score.

_ROLE_NOUNS = {
    "protein_main": "chicken turkey beef pork lamb veal fish swordfish salmon tuna cod shrimp crab lobster tofu egg eggs steak patty ham sausage bacon meat duck tilapia",
    "starch_base": "rice pasta noodle noodles spaghetti macaroni bread flour oat oats cereal cereals quinoa couscous potato potatoes gnocchi tortilla barley cracker crackers corn",
    "vegetable": "tomato tomatoes carrot carrots broccoli spinach lettuce kale cabbage pepper peppers zucchini squash celery cucumber mushroom mushrooms eggplant peas asparagus beet beets beans lentils chickpeas",
    "fruit": "fruit apple apples banana bananas orange lemon lime berries berry blueberries strawberries grape grapes mango peach pear cherries pineapple melon guava ugli avocado",
    "aromatic": "garlic onion onions shallot shallots ginger leek scallion scallions chili chile",
    "seasoning": "spice spices cinnamon cumin paprika nutmeg turmeric clove cloves cardamom oregano thyme basil rosemary parsley cilantro dill sage salt seasoning allspice",
    "fat_medium": "oil lard shortening margarine ghee butter",
    "sweetener": "sugar honey syrup molasses candy candies chocolate jam jelly",
    "liquid": "juice broth stock milk water beverage beverages drink soda nectar soup",
    "sauce_condiment": "sauce dressing ketchup mustard mayonnaise vinegar salsa relish pesto gravy paste dip",
    "dairy_rich": "cheese cream yogurt yoghurt cottage ricotta mozzarella cheddar parmesan",
    "crunchy_seed": "nut nuts almond almonds walnut walnuts pecan pecans cashew cashews peanut peanuts seed seeds chia flaxseed sesame pistachio",
}
_N2R = {w: r for r, ws in _ROLE_NOUNS.items() for w in ws.split()}

# cost of swapping role A for role B (symmetric), 0 = same role
_COST = {
    frozenset(["aromatic", "vegetable"]): 0.45, frozenset(["aromatic", "seasoning"]): 0.5,
    frozenset(["vegetable", "fruit"]): 0.55, frozenset(["fruit", "liquid"]): 0.75,
    frozenset(["dairy_rich", "liquid"]): 0.6, frozenset(["dairy_rich", "fat_medium"]): 0.6,
    frozenset(["sauce_condiment", "seasoning"]): 0.65, frozenset(["sweetener", "fruit"]): 0.7,
    frozenset(["starch_base", "vegetable"]): 0.6, frozenset(["protein_main", "dairy_rich"]): 0.7,
    frozenset(["crunchy_seed", "starch_base"]): 0.8, frozenset(["liquid", "sauce_condiment"]): 0.6,
}
_DEFAULT_COST = 0.95


def _role(words, form_words):
    role = None
    for w in words:
        if w in _N2R:
            role = _N2R[w]
    if role is None:
        return None
    fw = set(form_words)
    # form cues override the noun's default role
    if role in ("aromatic", "vegetable", "fruit") and fw & {"ground", "powder", "dried", "spices"}:
        if role == "aromatic" or "spices" in fw or "powder" in fw:
            return "seasoning"
    if role == "fruit" and "juice" in fw:
        return "liquid"
    if role in ("vegetable", "fruit", "aromatic") and fw & {"sauce", "paste", "dressing", "puree"}:
        return "sauce_condiment"
    if role == "fat_medium" and "butter" in words and fw & set(_ROLE_NOUNS["crunchy_seed"].split()):
        return "crunchy_seed"
    return role


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        uw_all = [w for f in fields for w in f]
        # USDA: role from primary field; if header is a category, from the next field
        ru = _role(fields[0], uw_all)
        if ru is None and len(fields) > 1:
            ru = _role(fields[1], uw_all)
        if fields[0] == ["spices"] or fields[0] == ["spice"]:
            ru = "seasoning"
        ri = _role(iw, iw)
        if ri is None or ru is None:
            return 45.0 if (ri is None and ru is None) else 35.0
        if ri == ru:
            return 100.0
        cost = _COST.get(frozenset([ri, ru]), _DEFAULT_COST)
        return round(100.0 * (1.0 - cost), 2)
    except Exception:
        return 0.0
