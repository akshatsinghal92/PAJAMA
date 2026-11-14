import re

# Culinary Role Interchangeability, variant 8: role-conditioned requirement
# checking (asymmetric).
# Step 1: infer the ingredient's role in the dish.
# Step 2: look up the REQUIREMENTS that matter for that role only, e.g.
#   fat        -> can be heated / melts, physical phase (liquid oil vs solid),
#                 neutral vs strong flavour
#   aromatic   -> fresh pungent form (not dried powder), same aromatic family
#   bulk_veg   -> holds shape (not puree/sauce/juice), similar moisture
#   sweetener  -> same phase (dry crystals vs liquid), sweetness present
#   binder     -> forms gel / binds, hydration behaviour
#   protein    -> intact muscle vs formed product, similar cooking state
#   starch     -> same starch family, uncooked vs cooked state
#   dairy      -> same body (liquid / soft / firm), similar fat level
# Step 3: test each requirement on the USDA entry; weighted share satisfied.
# The USDA entry must first be capable of the role at all (role gate).

_ROLE_WORDS = {
    "fat": r"\b(oil|butter|lard|margarine|ghee|shortening)\b",
    "aromatic": r"\b(garlic|onions?|shallots?|ginger|leeks?|scallions?)\b",
    "bulk_veg": r"\b(tomato(es)?|carrots?|broccoli|spinach|kale|cabbage|peppers?|zucchini|squash|celery|mushrooms?|corn|peas|eggplant|cucumbers?|fruits?|apples?|bananas?|berr(y|ies)|blueberries|oranges?|mangos?|peach(es)?|pears?|grapes?|guavas?|ugli)\b",
    "sweetener": r"\b(sugar|honey|syrup|molasses|agave)\b",
    "binder": r"\b(eggs?|chia|flax\w*|gelatin)\b",
    "protein": r"\b(chicken|turkey|beef|pork|lamb|fish|swordfish|salmon|tuna|cod|shrimp|tofu|steak|patty)\b",
    "starch": r"\b(rice|pasta|noodles?|spaghetti|gnocchi|bread|oats?|cereals?|quinoa|couscous|potato(es)?)\b",
    "dairy": r"\b(milk|cream|yog(h)?urt|cheese|cottage|ricotta)\b",
    "seasoning": r"\b(salt|spices?|cinnamon|cumin|paprika|nutmeg|turmeric|oregano|thyme|seasoning)\b",
    "sauce": r"\b(sauce|dressing|ketchup|mustard|mayonnaise|pesto|gravy|salsa)\b",
}


def _has(rx, t):
    return re.search(rx, t) is not None


def _role(text):
    best, pos = None, -1
    for r, rx in _ROLE_WORDS.items():
        for m in re.finditer(rx, text):
            if m.start() >= pos:
                best, pos = r, m.start()
    return best


_NOT_SHAPE = r"\b(juice|puree|sauce|paste|creamed|cream style|mashed|powder|soup)\b"
_COOKED = r"\b(cooked|baked|roasted|fried|boiled|grilled|broiled|heat|steamed|stewed)\b"
_REQS = {
    "fat": [
        (2.0, lambda i, u: _has(r"\boil\b", i) == _has(r"\boil\b", u)),
        (1.0, lambda i, u: _has(r"\bbutter\b", i) == _has(r"\bbutter\b", u)),
        (1.0, lambda i, u: not _has(r"\b(spray|whipped|spread)\b", u) or _has(r"\b(spray|whipped|spread)\b", i)),
    ],
    "aromatic": [
        (2.0, lambda i, u: not _has(r"\b(ground|powder|dried|spices)\b", u) or _has(r"\b(ground|powder|dried)\b", i)),
        (2.0, lambda i, u: bool(set(re.findall(_ROLE_WORDS["aromatic"], i)) & set(re.findall(_ROLE_WORDS["aromatic"], u)))),
        (1.0, lambda i, u: not _has(r"\bsauce\b", u)),
    ],
    "bulk_veg": [
        (2.0, lambda i, u: not _has(_NOT_SHAPE, u) or _has(_NOT_SHAPE, i)),
        (1.0, lambda i, u: _has(r"\bcanned\b", i) == _has(r"\bcanned\b", u) or _has(r"\bcreamed\b", i)),
        (1.0, lambda i, u: not _has(r"\b(fried|breaded|sweetened|syrup)\b", u)),
    ],
    "sweetener": [
        (2.0, lambda i, u: _has(r"\bsugar\b", i) == _has(r"\bsugar\b", u)),
        (1.0, lambda i, u: not _has(r"\b(sugar free|substitute|artificial)\b", u)),
    ],
    "binder": [
        (2.0, lambda i, u: _has(r"\bchia\b", i) == _has(r"\bchia\b", u)),
        (1.5, lambda i, u: _has(r"\begg", i) == _has(r"\begg", u)),
        (1.0, lambda i, u: _has(r"\bground\b|\bmeal\b", i) == _has(r"\bground\b|\bmeal\b", u)),
    ],
    "protein": [
        (2.0, lambda i, u: not _has(r"\b(patty|patties|nuggets|breaded|loaf|sticks)\b", u) or _has(r"\b(patty|nuggets|breaded)\b", i)),
        (1.5, lambda i, u: not (_has(r"\b(raw|fresh|uncooked)\b", i) and _has(_COOKED, u))),
        (1.0, lambda i, u: not _has(r"\b(fried|breaded)\b", u) or _has(r"\bfried\b", i)),
    ],
    "starch": [
        (2.0, lambda i, u: bool(set(re.findall(_ROLE_WORDS["starch"], i)) & set(re.findall(_ROLE_WORDS["starch"], u)))),
        (1.0, lambda i, u: not (_has(r"\b(uncooked|dry)\b", i) and _has(_COOKED, u))),
    ],
    "dairy": [
        (2.0, lambda i, u: _has(r"\b(cheese|cottage)\b", i) == _has(r"\b(cheese|cottage)\b", u)),
        (1.5, lambda i, u: not _has(r"\bfrozen\b", u) or _has(r"\bfrozen\b", i)),
        (1.0, lambda i, u: _has(r"\b(low ?fat|lowfat|nonfat|skim|light)\b", i) == _has(r"\b(low ?fat|lowfat|nonfat|skim|light)\b", u)),
    ],
    "seasoning": [
        (2.0, lambda i, u: not _has(r"\b(and pepper|blend|mix)\b", u) or _has(r"\b(and pepper|blend|mix)\b", i)),
        (1.0, lambda i, u: _has(r"\bground\b|\bpowder\b|\bspices\b", u) or not _has(r"\bground\b|\bpowder\b", i)),
    ],
    "sauce": [
        (2.0, lambda i, u: _has(_ROLE_WORDS["sauce"], u)),
        (1.0, lambda i, u: _has(r"\breduced calorie\b|\blight\b", i) == _has(r"\breduced calorie\b|\blight\b", u)),
    ],
}
_GATE = {  # which USDA roles can stand in for the ingredient role
    "aromatic": {"aromatic": 1.0, "seasoning": 0.5, "bulk_veg": 0.4},
    "bulk_veg": {"bulk_veg": 1.0, "starch": 0.3},
    "binder": {"binder": 1.0, "starch": 0.2},
    "dairy": {"dairy": 1.0, "fat": 0.3},
    "fat": {"fat": 1.0, "dairy": 0.3},
    "seasoning": {"seasoning": 1.0, "aromatic": 0.5, "sauce": 0.3},
    "sauce": {"sauce": 1.0, "seasoning": 0.3},
}


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", str(ingredient or "").lower())
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0].strip()
        usda = str(usda_match or "").lower()
        fields = [f.strip() for f in usda.split(",") if f.strip()]
        if not ing or not fields:
            return 0.0
        zone = " ".join(fields[:2]) if len(fields[0].split()) == 1 and len(fields) > 1 else fields[0]
        ri = _role(ing)
        ru = "seasoning" if fields[0] in ("spices", "spice") else _role(zone)
        if ri is None:
            head = ing.split()[-1] if ing.split() else ""
            return 6.0 if head and head.rstrip("s") in zone else 2.0
        gate = _GATE.get(ri, {ri: 1.0}).get(ru, 0.0) if ru else 0.15
        reqs = _REQS.get(ri, [])
        tot = sum(w for w, _ in reqs) or 1.0
        ok = 0.0
        for w, test in reqs:
            try:
                if test(ing, usda):
                    ok += w
            except Exception:
                pass
        share = ok / tot
        return round(10.0 * gate * (0.35 + 0.65 * share), 3)
    except Exception:
        return 0.0
