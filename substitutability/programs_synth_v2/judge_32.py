import re

# Nutritional Profile Proximity, variant 8: macro-swing checklist.
# A dietitian's checklist of the situations that swing per-100g macros the
# most. Each check is a predicate over (ingredient, usda) and has an estimated
# severity (approximate % of the macro profile that changes). The score starts
# at 100 and loses the severity of every triggered check (diminishing so the
# score never goes negative). A base-food check compares macro groups.

_GROUPS = {
    "purefat": r"\b(oil|lard|ghee|shortening|butter|margarine)\b",
    "nutseed": r"\b(nuts?|almonds?|walnuts?|pecans?|cashews?|peanuts?|seeds?|chia|flaxseed|sesame|tahini)\b",
    "meat": r"\b(chicken|turkey|beef|pork|lamb|veal|fish|swordfish|salmon|tuna|cod|shrimp|crab|meat|patty|steak|ham)\b",
    "dairy": r"\b(cheese|milk|yogurt|cream|cottage|ricotta|kefir)\b",
    "starch": r"\b(rice|pasta|noodles?|gnocchi|potato(es)?|bread|cereals?|flour|oats?|corn|tortillas?|quinoa|couscous)\b",
    "legume": r"\b(beans?|lentils?|chickpeas?|peas)\b",
    "veg": r"\b(tomato(es)?|onions?|spinach|lettuce|kale|carrots?|broccoli|peppers?|garlic|celery|zucchini|mushrooms?|cabbage)\b",
    "fruit": r"\b(fruit|apples?|bananas?|berr(y|ies)|blueberries|oranges?|guava|mango|grapes?|peach(es)?|pears?|melon|ugli)\b",
    "sugar": r"\b(sugar|honey|syrup|molasses|jam|jelly|candy|candies|chocolate)\b",
    "spice": r"\b(spices?|cinnamon|cumin|paprika|nutmeg|turmeric|ginger|oregano|thyme|pepper)\b",
}
_GROUP_DIST = {
    frozenset(["purefat", "nutseed"]): 25, frozenset(["meat", "dairy"]): 35,
    frozenset(["starch", "legume"]): 25, frozenset(["veg", "fruit"]): 20,
    frozenset(["fruit", "sugar"]): 45, frozenset(["starch", "sugar"]): 40,
    frozenset(["veg", "legume"]): 35, frozenset(["starch", "veg"]): 40,
    frozenset(["spice", "veg"]): 45, frozenset(["meat", "legume"]): 45,
}


def _has(rx, text):
    return re.search(rx, text) is not None


def _group(text):
    best, pos = None, -1
    for g, rx in _GROUPS.items():
        for m in re.finditer(rx, text):
            if m.start() > pos:
                best, pos = g, m.start()
    return best


_CHECKS = [
    # name, severity, predicate(ing, usda)
    ("fried_vs_not", 30, lambda i, u: _has(r"\b(fried|breaded|battered)\b", u) != _has(r"\b(fried|breaded|battered|crispy)\b", i)),
    ("fat_reduced", 22, lambda i, u: _has(r"\b(low ?fat|lowfat|nonfat|fat free|skim|reduced fat|light)\b", u) != _has(r"\b(low ?fat|lowfat|nonfat|fat free|skim|reduced fat|light)\b", i)),
    ("calorie_reduced", 30, lambda i, u: _has(r"\breduced calorie|\blow calorie|\bdiet\b", u) != _has(r"\breduced calorie|\blow calorie|\bdiet\b|\blight\b", i)),
    ("juice_vs_whole", 40, lambda i, u: _has(r"\bjuice\b", u) != _has(r"\bjuice\b", i)),
    ("dried_vs_fresh", 45, lambda i, u: _has(r"\b(dried|dehydrated|powder)\b", u) != _has(r"\b(dried|dehydrated|powder)\b", i)),
    ("skin", 18, lambda i, u: (_has(r"\bskin\b", i) and _has(r"skin not eaten|without skin|skinless", u)) or (_has(r"skinless", i) and _has(r"skin eaten|with skin", u))),
    ("sweetened", 20, lambda i, u: _has(r"\b(sweetened|syrup|candied|frosted|glazed)\b", u) != _has(r"\b(sweet(ened)?|syrup|candied|frosted|glazed|honey)\b", i)),
    ("frozen_dessert", 35, lambda i, u: _has(r"frozen yogurt|ice cream", u) != _has(r"frozen yogurt|ice cream", i)),
    ("sauce_vs_plain", 35, lambda i, u: _has(r"\b(sauce|dressing|gravy|pesto|dip)\b", u) != _has(r"\b(sauce|dressing|gravy|pesto|dip)\b", i)),
    ("blend_vs_pure", 25, lambda i, u: _has(r"\b(blend|mix|seasoning)\b", u) != _has(r"\b(blend|mix|seasoning)\b", i)),
    ("broth_vs_soup", 30, lambda i, u: (_has(r"\bbroth|\bstock\b", i) and _has(r"\bsoup\b", u)) or (_has(r"\bsoup\b", i) and _has(r"\bbroth\b", u))),
    ("condensed", 25, lambda i, u: _has(r"\bcondensed\b", u) != _has(r"\bcondensed\b", i)),
    ("oil_packed", 20, lambda i, u: _has(r"\bin oil\b|oil[- ]packed", u) != _has(r"\bin oil\b|oil[- ]packed", i)),
]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing_main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0].strip()
        if not ing_main or not usda.strip():
            return 0.0
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        # specific qualifier last so head-final group detection sees it
        u_head = " ".join(fields[:2]) if len(fields) > 1 and len(fields[0].split()) == 1 else fields[0]

        remaining = 1.0
        for _name, sev, pred in _CHECKS:
            try:
                if pred(ing_main, usda):
                    remaining *= (1.0 - sev / 100.0)
            except Exception:
                continue

        gi, gu = _group(ing_main), _group(u_head) or _group(usda)
        if gi is None or gu is None:
            base = 0.8
        elif gi == gu:
            base = 1.0
        else:
            base = 1.0 - _GROUP_DIST.get(frozenset([gi, gu]), 70) / 100.0
        # same named head food: base macros are identical by construction
        head = re.findall(r"[a-z]+", ing_main)
        if head and re.search(r"\b" + re.escape(head[-1].rstrip("s")) + r"(e?s)?\b", u_head):
            base = 1.0
        return round(100.0 * base * remaining, 2)
    except Exception:
        return 0.0
