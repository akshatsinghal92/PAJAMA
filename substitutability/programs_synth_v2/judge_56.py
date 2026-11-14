import re

# Food Category Consistency, variant 8: ordered decision list.
# A prioritised list of rules is evaluated top-down; the first rule that
# fires decides an ordinal verdict (5 = same category ... 1 = clearly
# different category that changes the dish). Rules encode the typical
# category traps: a dried spice standing in for a fresh vegetable/aromatic,
# a sauce/paste/dressing standing in for a whole food or seed, juice for
# whole fruit, a sweet for a savoury staple, a fat for a dairy food, etc.
# Category membership is tested with compact regexes over the head region.

_RX = {
    "spice": r"\bspices?\b|\bground (ginger|cinnamon|cumin|nutmeg|cloves?|pepper)\b|\bseasoning\b|\bpowder\b",
    "veg": r"\b(tomato(es)?|onions?|garlic|carrots?|broccoli|spinach|lettuce|kale|cabbage|peppers?|zucchini|squash|celery|cucumbers?|mushrooms?|corn|potato(es)?|eggplant|peas|ginger root|vegetables?)\b",
    "fruit": r"\b(fruits?|apples?|bananas?|oranges?|lemons?|limes?|berr(y|ies)|grapes?|mangos?|peach(es)?|pears?|cherr(y|ies)|pineapple|melon|guavas?|ugli|avocados?)\b",
    "sauce": r"\b(sauce|dressing|ketchup|mustard|mayonnaise|salsa|relish|pesto|gravy|paste|dip|spread)\b",
    "juice": r"\b(juice|nectar|drink|beverages?|smoothie)\b",
    "seed": r"\b(seeds?|nuts?|almonds?|walnuts?|pecans?|cashews?|peanuts?|chia|flaxseed|sesame|pistachios?)\b",
    "meat": r"\b(chicken|turkey|beef|pork|lamb|veal|ham|bacon|sausage|steak|duck|meat|patty|fish|swordfish|salmon|tuna|cod|shrimp|crab|lobster)\b",
    "dairy": r"\b(milk|cheese|yog(h)?urt|cream|cottage|ricotta|kefir)\b",
    "grain": r"\b(rice|pasta|noodles?|spaghetti|macaroni|bread|flour|oats?|cereals?|barley|quinoa|couscous|wheat|crackers?|tortillas?|gnocchi|granola)\b",
    "legume": r"\b(beans?|lentils?|chickpeas?|tofu|soy\w*|edamame|hummus)\b",
    "fat": r"\b(oil|lard|shortening|margarine|ghee|butter)\b",
    "sweet": r"\b(sugar|honey|syrup|molasses|cand(y|ies)|chocolate|jam|jelly|frozen yogurt|ice cream)\b",
}
_SCORE = {5: 10.0, 4: 7.5, 3: 5.0, 2: 2.5, 1: 0.3}


def _is(cat, text):
    return re.search(_RX[cat], text) is not None


def _cats(text):
    return {c for c in _RX if _is(c, text)}


def _head_word(text):
    words = [w for w in re.findall(r"[a-z]+", text) if w not in (
        "fresh", "frozen", "canned", "raw", "chopped", "diced", "minced", "sliced", "cooked",
        "uncooked", "large", "small", "whole", "organic")]
    return words[-1] if words else ""


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).strip()
        usda = str(usda_match or "").lower()
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        if not ing or not fields:
            return 0.0
        zone = " ".join(fields[:2])          # identity zone of the USDA entry
        head = _head_word(ing)
        ci, cu = _cats(ing), _cats(zone)
        head_shared = bool(head) and re.search(r"\b" + re.escape(head.rstrip("s")) + r"(e?s)?\b", zone)

        level = None
        # Rule 1: spice entry for a fresh vegetable / aromatic ingredient
        if _is("spice", zone) and not _is("spice", ing) and (ci & {"veg", "fruit"}):
            level = 2
        # Rule 2: sauce/paste/dressing entry for a whole food or seed
        elif _is("sauce", fields[0]) and not _is("sauce", ing) and (ci & {"seed", "veg", "fruit", "meat", "grain"}):
            level = 1
        # Rule 3: juice/beverage for whole fruit or vegetable
        elif _is("juice", fields[0]) and not _is("juice", ing) and (ci & {"fruit", "veg"}):
            level = 1
        # Rule 4: sweet / frozen dessert for a dairy or savoury food
        elif _is("sweet", fields[0]) and not _is("sweet", ing) and ci & {"dairy", "grain", "veg", "meat"}:
            level = 2
        # Rule 5: same head food named
        elif head_shared:
            level = 5
        # Rule 6: same category set (intersection on the head categories)
        elif ci and cu and ci & cu:
            level = 5 if ci == cu else 4
        # Rule 7: related categories
        elif ci and cu and (({"veg", "fruit"} >= (ci | cu)) or ({"grain", "legume"} >= (ci | cu))
                            or ({"fat", "dairy"} >= (ci | cu)) or ({"legume", "seed"} >= (ci | cu))):
            level = 3
        # Rule 8: no category evidence on one side
        elif not ci or not cu:
            level = 3 if not ci and not cu else 2
        else:
            level = 1
        return _SCORE[level]
    except Exception:
        return 0.0
