import re

# Processing and Additive Difference, variant 2: component-count complexity.
# A product's "complexity" is the number of distinct food COMPONENTS it
# contains plus the number of compound-product nouns (sauce, dressing,
# blend, mix, soup, salad, casserole) and processing operations that bring
# extra ingredients (breaded, glazed, marinated, seasoned, sweetened).
# The ingredient's complexity is computed the same way. Extra complexity on
# the USDA side means added components the diner tastes; the score is a
# hyperbolic decay of that excess (with a smaller cost for a USDA entry that
# is simpler than a compound ingredient).

_FOODS = set("""salt pepper sugar honey syrup oil butter garlic onion ginger tomato cheese
cream milk egg flour bread crumbs rice beans chicken beef pork turkey fish shrimp
lemon lime vinegar mustard soy herbs spices chili paprika cinnamon vanilla chocolate
peanut almond nuts raisins apple potato corn carrot celery mushroom spinach bacon ham
sesame coconut caramel fruit yogurt mayonnaise ketchup wine broth parmesan basil
oregano thyme parsley cilantro dill cumin curry jalapeno pesto olive olives bean""".split())
_COMPOUND_NOUNS = {"sauce", "dressing", "blend", "mix", "soup", "salad", "casserole",
                   "stew", "gravy", "dip", "spread", "marinade", "seasoning", "pie",
                   "sandwich", "pizza", "burrito", "entree", "dinner", "patty", "nuggets"}
_ADDING_OPS = {"breaded": 1.0, "battered": 1.0, "glazed": 1.0, "marinated": 1.0,
               "seasoned": 1.0, "sweetened": 1.0, "salted": 0.7, "candied": 1.0,
               "frosted": 1.0, "buttered": 1.0, "creamed": 1.0, "fried": 0.7,
               "smoked": 0.6, "cured": 0.7, "flavored": 1.0, "stuffed": 1.2,
               "coated": 1.0, "fortified": 0.2, "enriched": 0.2, "prepared": 0.5}
_NEGATORS = {"without", "unsalted", "unsweetened", "no", "plain", "free"}


def _complexity(text, is_usda):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    words = re.findall(r"[a-z]+", t)
    comps = set()
    neg_next = False
    for i, w in enumerate(words):
        if w in _NEGATORS:
            neg_next = True
            continue
        if w in _FOODS and not neg_next:
            comps.add(w[:-1] if w.endswith("s") and w[:-1] in _FOODS else w)
        neg_next = False
    compound = sum(1 for w in words if w in _COMPOUND_NOUNS)
    ops = 0.0
    for i, w in enumerate(words):
        if w in _ADDING_OPS:
            prev = words[i - 1] if i else ""
            if prev not in _NEGATORS:
                ops += _ADDING_OPS[w]
    # "with X" / "and X" phrases signal extra components
    joins = len(re.findall(r"\b(with|and|&)\s+(?!skin|bone|liquids|solids|peel|not)\w+", t))
    if is_usda:
        # USDA's "oil" as the primary food name is the food, not an added oil
        pass
    return comps, compound, ops, joins


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing, flags=re.I).split(",")[0]
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ci, ki, oi, ji = _complexity(ing, False)
        cu, ku, ou, ju = _complexity(usda, True)
        extra_comps = len(cu - ci)
        # the ingredient's head food appearing as the USDA food is not "extra"
        excess = 0.9 * extra_comps + 1.0 * max(0, ku - ki) + 0.8 * max(0.0, ou - oi) + 0.5 * max(0, ju - ji)
        deficit = 0.4 * len(ci - cu) + 0.5 * max(0, ki - ku) + 0.3 * max(0.0, oi - ou)
        # the identity component (e.g. "garlic") legitimately appears on both sides
        if ci and cu and not (ci & cu) and extra_comps:
            excess += 0.5
        score = 100.0 / (1.0 + 0.7 * excess + 0.45 * deficit)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
