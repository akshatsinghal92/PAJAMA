import re

# Culinary Role Interchangeability, variant 4: count of forced recipe changes.
# We simulate putting the USDA item into the recipe slot and count how many
# ADJUSTMENTS a cook would have to make. Each adjustment type is a test:
#   shape     - whole/pieces vs ground/puree/paste/juice (shape matters)
#   fat_phase - liquid oil vs solid fat (sauteing vs baking/creaming)
#   sweet_phase - dry sugar vs liquid sweetener (moisture balance)
#   aroma     - fresh aromatic vs dried/ground form (amount and timing)
#   bind      - chia gel vs ground flax vs egg (hydration step)
#   structure - whole muscle vs formed/processed meat (patty, nuggets)
#   cooked    - raw component vs pre-cooked component (timing)
#   function  - different primary function class altogether
# Each failed test multiplies the score by its retention factor; the
# function test is the harshest.

_FUNC = {
    "fat": r"\b(oil|butter|lard|margarine|ghee|shortening)\b",
    "sweet": r"\b(sugar|honey|syrup|molasses|agave)\b",
    "aromatic": r"\b(garlic|onions?|shallots?|ginger|leeks?|scallions?|chil(i|e)s?)\b",
    "binder": r"\b(eggs?|chia|flax\w*|gelatin)\b",
    "thickener": r"\b(flour|cornstarch|starch|arrowroot)\b",
    "protein": r"\b(chicken|turkey|beef|pork|lamb|fish|swordfish|salmon|tuna|cod|shrimp|tofu|steak|patty)\b",
    "starch": r"\b(rice|pasta|noodles?|spaghetti|gnocchi|bread|oats?|cereals?|quinoa|couscous|potato(es)?)\b",
    "bulk": r"\b(tomato(es)?|carrots?|broccoli|spinach|kale|cabbage|peppers?|zucchini|squash|celery|mushrooms?|corn|peas|beans|lentils|eggplant)\b",
    "fruit": r"\b(fruits?|apples?|bananas?|berr(y|ies)|blueberries|oranges?|mangos?|peach(es)?|pears?|grapes?|guavas?|ugli)\b",
    "dairy": r"\b(milk|cream|yog(h)?urt|cheese|cottage|ricotta)\b",
    "seasoning": r"\b(salt|spices?|cinnamon|cumin|paprika|nutmeg|turmeric|oregano|thyme|basil|seasoning)\b",
    "crunch": r"\b(nuts?|almonds?|walnuts?|peanuts?|cashews?|pecans?|seeds?)\b",
    "sauce": r"\b(sauce|dressing|ketchup|mustard|mayonnaise|pesto|gravy|salsa)\b",
    "liquid": r"\b(broth|stock|juice|water|soup)\b",
}
_RELATED = {frozenset(["aromatic", "seasoning"]), frozenset(["bulk", "fruit"]),
            frozenset(["binder", "thickener"]), frozenset(["dairy", "fat"]),
            frozenset(["sauce", "seasoning"]), frozenset(["liquid", "sauce"]),
            frozenset(["starch", "bulk"]), frozenset(["crunch", "binder"])}
_RETAIN = {"shape": 0.65, "fat_phase": 0.7, "sweet_phase": 0.75, "aroma": 0.7, "bind": 0.65,
           "structure": 0.6, "cooked": 0.8, "function_related": 0.5, "function": 0.15}


def _func(text):
    best, pos = None, -1
    for f, rx in _FUNC.items():
        for m in re.finditer(rx, text):
            # form nouns like "paste"/"juice" don't move the head; last food wins
            if m.start() >= pos:
                best, pos = f, m.start()
    return best


def _shape(text):
    if re.search(r"\b(juice|broth|stock|milk|syrup)\b", text):
        return "liquid"
    if re.search(r"\b(paste|puree|pureed|mashed|creamed|sauce|pesto)\b", text):
        return "paste"
    if re.search(r"\b(ground|powder\w*|flour|meal)\b", text) and not re.search(r"\bground (beef|turkey|pork|chicken|lamb)\b|\b(beef|turkey|pork|chicken|lamb), ground\b", text):
        return "ground"
    return "solid"


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", str(ingredient or "").lower())
        ing_main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower()
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        if not ing_main.strip() or not fields:
            return 0.0
        zone = fields[0] if len(fields[0].split()) > 1 or len(fields) == 1 else fields[0] + " " + fields[1]
        fi, fu = _func(ing_main), _func(zone) or _func(usda)
        if fields[0] in ("spices", "spice"):
            fu = "seasoning"
        tests = []
        if fi and fu and fi != fu:
            tests.append("function_related" if frozenset([fi, fu]) in _RELATED else "function")
        elif fi is None or fu is None:
            tests.append("function_related")
        si, su = _shape(ing_main), _shape(usda)
        if si != su:
            tests.append("shape")
        if fi == "fat" and fu == "fat":
            liquid_i = bool(re.search(r"\boil\b", ing_main))
            liquid_u = bool(re.search(r"\boil\b", usda))
            if liquid_i != liquid_u:
                tests.append("fat_phase")
        if fi == "sweet" and fu == "sweet":
            if bool(re.search(r"\bsugar\b", ing_main)) != bool(re.search(r"\bsugar\b", usda)):
                tests.append("sweet_phase")
        if fi == "aromatic" and re.search(r"\b(ground|powder|dried|spices)\b", usda) and not re.search(r"\b(ground|powder|dried)\b", ing_main):
            tests.append("aroma")
        if fi == "binder" and fu == "binder":
            if bool(re.search(r"\bchia\b", ing_main)) != bool(re.search(r"\bchia\b", usda)):
                tests.append("bind")
        if fi == "protein" and re.search(r"\b(patty|patties|nuggets|sticks|loaf|breaded)\b", usda) and not re.search(r"\b(patty|nuggets|breaded)\b", ing_main):
            tests.append("structure")
        raw_i = bool(re.search(r"\b(raw|fresh|uncooked)\b", ing_main))
        cooked_u = bool(re.search(r"\b(cooked|baked|roasted|fried|boiled|grilled|broiled|heat)\b", usda))
        if raw_i and cooked_u:
            tests.append("cooked")
        score = 10.0
        for t in tests:
            score *= _RETAIN[t]
        return round(score, 3)
    except Exception:
        return 0.0
