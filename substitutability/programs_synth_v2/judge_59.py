import re

# Processing and Additive Difference, variant 3: NOVA-style processing level.
# Each side is placed in a NOVA-like group:
#   1 unprocessed / minimally processed (raw, frozen, plain dried, plain
#     cooked meat, milk, plain yogurt)
#   2 processed culinary ingredient (oil, butter, sugar, salt, flour, honey)
#   3 processed food (canned in brine/syrup, salted, cured, smoked, cheese,
#     simple breads, sweetened variants)
#   4 ultra-processed / compound (breaded, sauces, dressings, seasoning
#     blends, flavoured products, branded RTE items, patties, mixes)
# The GROUP the recipe ingredient implies is compared with the USDA group.
# Moving to a higher group than the ingredient implies costs much more than
# moving lower. Within-group differences in salt / sugar flags add a small cost.

_G2 = r"\b(oil|butter|lard|ghee|margarine|sugar|salt|honey|maple syrup|flour|vinegar|starch)\b"
_G3 = (r"\b(canned|in brine|in syrup|salted|cured|smoked|pickled|cheese|bread|sweetened|"
       r"jam|jelly|bacon|ham|dried fruit|roasted nuts|tofu|paste|condensed)\b")
_G4 = (r"\b(breaded|battered|sauce|dressing|gravy|seasoning|blend|mix|flavou?red|"
       r"patty|patties|nuggets|frozen yogurt|ice cream|candy|candies|cereals? ready-to-eat|"
       r"ready-to-eat|snacks?|chips|crackers|cookies?|cake|pastry|frankfurter|sausage|"
       r"salami|bologna|nfs|fast foods?|restaurant|imitation|substitute|spread|dip|soup)\b")
_PLAIN = r"\b(without salt|unsalted|unsweetened|no sugar|plain|raw|fresh)\b"
_SALT = r"\b(salted|with salt|salt added|brine|soy sauce)\b"
_SUGAR = r"\b(sweetened|sugar(ed)?|syrup|honey|candied|glazed|frosted)\b"


def _group(text, raw_case):
    g = 1
    if re.search(_G2, text):
        g = 2
    if re.search(_G3, text):
        g = 3
    if re.search(_G4, text) or re.search(r"\b[A-Z]{3,}\b", raw_case):
        g = 4
    # "Cheese, cottage" / plain yogurt / milk are minimally processed dairy
    if g == 3 and re.search(r"\bcottage\b|\bricotta\b", text) and not re.search(r"\bsalted\b|\bflavou?red\b", text):
        g = 2
    return g


def judging_function(ingredient, usda_match):
    try:
        raw_i = re.sub(r"\([^)]*\)", " ", str(ingredient or ""))
        raw_i = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", raw_i, flags=re.I).split(",")[0]
        raw_u = re.sub(r"\([^)]*\)", " ", str(usda_match or ""))
        ing, usda = raw_i.lower(), raw_u.lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        gi = _group(ing, raw_i)
        gu = _group(usda, raw_u)
        diff = gu - gi
        if diff > 0:
            score = 10.0 - 2.8 * diff
        else:
            score = 10.0 + 1.2 * diff           # USDA simpler: cook can add, mild cost
        # within-group seasoning flags
        si, su = bool(re.search(_SALT, ing)), bool(re.search(_SALT, usda))
        ti, tu = bool(re.search(_SUGAR, ing)), bool(re.search(_SUGAR, usda))
        if su and not si:
            score -= 1.0
        if tu and not ti:
            score -= 1.3
        if re.search(_PLAIN, usda) and gi == 1:
            score += 0.5
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
