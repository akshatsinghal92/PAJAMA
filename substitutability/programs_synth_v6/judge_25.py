import re

# category -> subcategory -> keywords
_TAX = {
    "meat": {"beef": "beef buffalo ox veal brisket sirloin chuck steak", "pork": "pork ham bacon sausage cervelat salami thuringer", "lamb": "lamb mutton goat", "poultry": "chicken turkey duck poultry goose", "offal": "liver kidney tongue heart giblet gizzard innard"},
    "seafood": {"fish": "fish salmon tuna cod swordfish herring pollock bass whitefish lox trout tilapia haddock", "shellfish": "shrimp crab lobster crayfish crustacean oyster clam mussel scallop squid"},
    "dairy": {"cheese": "cheese cheddar brie camembert mozzarella parmesan asadero queso", "cultured": "yogurt kefir", "milk": "milk cream buttermilk half", "butter": "butter ghee"},
    "egg": {"egg": "egg"},
    "grain": {"flour": "flour", "cereal": "cereal oat oatmeal granola farina bran cornmeal", "bread": "bread cracker tortilla cornbread bun roll", "pasta": "pasta noodle spaghetti macaroni", "rice": "rice quinoa amaranth barley millet wheat"},
    "legume": {"bean": "bean lentil pea chickpea broadbean", "soy": "tofu soy tempeh sufu"},
    "nutseed": {"nut": "nut almond walnut pecan hazelnut pistachio cashew peanut brazil pine macadamia", "seed": "seed flaxseed sesame chia sunflower"},
    "vegetable": {"leafy": "lettuce spinach kale chard romaine escarole cabbage greens chrysanthemum arugula", "root": "potato yam carrot beet radish turnip parsnip cassava", "allium": "onion garlic leek shallot scallion", "fruitveg": "tomato pepper cucumber zucchini squash eggplant pumpkin olive", "other": "broccoli cauliflower asparagus celery mushroom artichoke okra corn"},
    "fruit": {"citrus": "orange tangerine lemon lime grapefruit", "berry": "berry blueberry strawberry raspberry blackberry cranberry grape cherry", "tree": "apple pear peach plum apricot fig date", "tropical": "mango papaya pineapple banana pomegranate coconut kiwi guava tamarind durian jamun melon watermelon"},
    "herbspice": {"herb": "parsley basil cilantro coriander mint sage thyme oregano rosemary dill", "spice": "cinnamon cumin paprika ginger turmeric pepper nutmeg clove cocoa"},
    "fatoil": {"oil": "oil shortening lard", "mayo": "mayonnaise"},
    "sweetener": {"sugar": "sugar honey molasses", "syrup": "syrup"},
    "condiment": {"sauce": "sauce ketchup salsa mustard dressing marinara", "vinegar": "vinegar"},
    "beverage": {"tea": "tea coffee", "juice": "juice nectar", "alcohol": "wine beer", "other": "beverage drink"},
}
_IDX = {}
for _c, _subs in _TAX.items():
    for _s, _kws in _subs.items():
        for _k in _kws.split():
            _IDX.setdefault(_k, (_c, _s))

_NEAR = {frozenset(a) for a in [("meat", "seafood"), ("vegetable", "fruit"), ("legume", "grain"), ("nutseed", "legume"), ("herbspice", "vegetable"), ("condiment", "fatoil"), ("sweetener", "fruit")]}
_FILL = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot raw cooked dried canned frozen toasted whole lean ground drained of and or the a with in for from nfs regular plain type separable trimmed choice select grade only mature variety flavor other than not eaten without salt added".split())
_FORM = set("oil juice syrup sauce soup pudding cookie cake candy jerky flour snack taco sandwich entree stew nectar spice".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out

def _classify(tokens):
    # prefer the last-token match for the ingredient (head noun) but form words dominate
    for t in tokens:
        if t in ("oil", "juice", "syrup", "vinegar", "sauce", "mayonnaise", "tea"):
            return _IDX.get(t)
    for t in reversed(tokens):
        if t in _IDX:
            return _IDX[t]
    return None

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _w(ing.split(",")[0])
        ut_first = _w(u.split(",")[0])
        ut = _w(u)
        if not it or not ut:
            return 0.0
        ci = _classify(it)
        cu = _classify(ut_first) or _classify(ut)
        score = 0.0
        if ci and cu:
            if ci[0] == cu[0]:
                score += 3.0
                score += 2.5 if ci[1] == cu[1] else 0.0
            elif frozenset((ci[0], cu[0])) in _NEAR:
                score += 0.8
            else:
                score -= 2.5
        elif ci or cu:
            score += 0.5
        core = [t for t in it if t not in _FILL]
        uset = set(ut)
        if core:
            cov = sum(1 for t in core if t in uset) / float(len(core))
            score += 3.5 * cov
            if core[-1] in uset:
                score += 1.5
        # form swap within the same category (hazelnut vs hazelnut oil)
        if (set(ut_first) & _FORM) - set(it):
            score -= 2.5
        if (set(it) & _FORM) - set(ut):
            score -= 1.5
        # state conflicts
        cook = set("cooked boiled baked braised fried simmered broiled roasted steamed toasted".split())
        ic, uc = bool(set(it + _w(ing)) & cook), bool(uset & cook) and "raw" not in uset
        if ic != uc:
            score -= 1.2
        if bool(set(_w(ing)) & {"dried", "dehydrated"}) != bool(uset & {"dried", "dehydrated"}):
            score -= 1.5
        mods = set("lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated".split())
        score -= 0.8 * len((uset & mods) - set(it))
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
