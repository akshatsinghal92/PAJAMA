import re

# Food Category Consistency, variant 5: USDA SR food-group codes.
# USDA SR-style descriptions start with headers that map closely onto the
# official SR food groups (0100 Dairy and Egg, 0200 Spices and Herbs,
# 0400 Fats and Oils, 0500 Poultry, 0600 Soups/Sauces/Gravies, 0700 Sausages,
# 0800 Breakfast Cereals, 0900 Fruits, 1000 Pork, 1100 Vegetables, 1200 Nuts
# and Seeds, 1300 Beef, 1400 Beverages, 1500 Finfish and Shellfish,
# 1600 Legumes, 1700 Lamb/Veal/Game, 1800 Baked Products, 1900 Sweets,
# 2000 Cereal Grains and Pasta, 2100 Fast Foods, 2200 Meals/Entrees,
# 2500 Snacks). The USDA entry is coded from its header (then its food
# words), the ingredient from its words; codes are compared exactly and via
# super-groups (animal protein, plant produce, starches, flavourings).

_HEADER_CODE = [
    (r"^(milk|cheese|yogurt|cream|butter|egg|eggs|whey|kefir)\b", 100),
    (r"^(spices?|herbs?|seasoning|salt|ginger|cinnamon|cumin|paprika|nutmeg|turmeric|oregano|"
     r"basil|thyme|rosemary|parsley|cilantro|dill|sage|cloves?|cardamom|pepper, black|allspice)\b", 200),
    (r"^(oil|fat|margarine|shortening|lard|salad dressing|mayonnaise)\b", 400),
    (r"^(chicken|turkey|duck|goose|poultry)\b", 500),
    (r"^(soup|sauce|gravy|gravies)\b", 600),
    (r"^(sausage|frankfurter|bologna|salami|pepperoni|luncheon)\b", 700),
    (r"^(cereals ready-to-eat|cereals|cereal)\b", 800),
    (r"^(fruit|apples?|bananas?|blueberries|oranges?|grapes?|peaches|pears|guavas?|mangos?|strawberries|cherries|lemons?|limes?|raisins)\b", 900),
    (r"^(pork|ham|bacon)\b", 1000),
    (r"^(vegetables?|tomato(es)?|onions?|corn|potato(es)?|carrots?|broccoli|spinach|lettuce|peppers?|garlic|mushrooms?|cabbage|kale|celery|squash|peas)\b", 1100),
    (r"^(nuts?|seeds?|almonds?|walnuts?|peanuts?|cashews?|flaxseed|chia)\b", 1200),
    (r"^(beef)\b", 1300),
    (r"^(beverages?|juice|fruit juice|coffee|tea|soda|water)\b", 1400),
    (r"^(fish|crustaceans|mollusks|shrimp|crab|salmon|tuna|swordfish)\b", 1500),
    (r"^(beans?|lentils?|chickpeas?|tofu|soy\w*|hummus|peanut butter)\b", 1600),
    (r"^(lamb|veal|game|venison|bison)\b", 1700),
    (r"^(bread|rolls?|crackers?|cake|cookies?|muffins?|pie|pastry|bagels?|tortillas?)\b", 1800),
    (r"^(sugars?|candies|candy|honey|syrups?|jams?|jellies|chocolate|frozen yogurt|ice cream|gelatin)\b", 1900),
    (r"^(rice|pasta|noodles?|spaghetti|macaroni|flour|oats?|barley|quinoa|couscous|wheat|gnocchi)\b", 2000),
    (r"^(fast foods?|restaurant)\b", 2100),
    (r"^(snacks?|chips?|popcorn|pretzels?)\b", 2500),
]
_SUPER = {
    100: "dairy", 200: "flavour", 400: "fat", 500: "animal", 600: "flavour", 700: "animal",
    800: "starch", 900: "produce", 1000: "animal", 1100: "produce", 1200: "plantprotein",
    1300: "animal", 1400: "drink", 1500: "animal", 1600: "plantprotein", 1700: "animal",
    1800: "starch", 1900: "sweet", 2000: "starch", 2100: "prepared", 2500: "prepared",
}


def _code_phrase(phrase):
    p = phrase.strip()
    for rx, code in _HEADER_CODE:
        if re.search(rx, p):
            return code
    return None


def _code_ingredient(words):
    # try progressively shorter suffixes of the head-final phrase: "olive oil" -> "oil"
    # but also whole phrase first (e.g. "frozen yogurt", "peanut butter")
    for start in range(len(words)):
        c = _code_phrase(" ".join(words[start:]))
        if c is not None:
            # "peanut butter": phrase match at start beats the generic suffix "butter"
            return c
    for w in reversed(words):
        c = _code_phrase(w)
        if c is not None:
            return c
    return None


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\b(fresh|frozen|canned|raw|cooked|uncooked|chopped|diced|minced|sliced|large|small|whole|organic)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [f.strip() for f in str(usda_match or "").lower().split(",") if f.strip()]
        if not iw or not fields:
            return 0.0
        cu = _code_phrase(fields[0])
        if cu is None:
            words0 = re.findall(r"[a-z]+", fields[0])
            cu = _code_ingredient(words0)
        if cu is None and len(fields) > 1:
            cu = _code_phrase(fields[1])
        ci = _code_ingredient(iw)
        # the same head food named on both sides is the same category by definition
        u_words = set(re.findall(r"[a-z]+", " ".join(fields[:2])))
        head = iw[-1]
        if head in u_words or head.rstrip("s") in {w.rstrip("s") for w in u_words}:
            if ci is None or cu is None or _SUPER.get(ci) == _SUPER.get(cu):
                return 100.0
        if ci is None or cu is None:
            return 40.0 if ci is None and cu is None else 30.0
        if ci == cu:
            return 100.0
        si, su = _SUPER[ci], _SUPER[cu]
        if si == su:
            return 60.0
        softer = {frozenset(["dairy", "fat"]), frozenset(["plantprotein", "starch"]),
                  frozenset(["produce", "drink"]), frozenset(["sweet", "dairy"]),
                  frozenset(["prepared", "animal"]), frozenset(["prepared", "starch"])}
        if frozenset([si, su]) in softer:
            return 30.0
        return 5.0
    except Exception:
        return 0.0
