import re

# Modifier and Qualifier Consistency, variant 6: food-specific qualifier
# relevance.
# Which qualifiers a diner notices depends on the food:
#   peppers -> colour, heat variety       milk/yogurt/cream -> fat level, flavour
#   chicken/turkey -> part, skin, meat colour   beef/pork -> leanness, cut
#   cheese -> variety, fat level          rice -> colour/variety (brown vs white)
#   apples/potatoes/onions -> variety/colour (moderately noticeable)
#   dressings -> style, calorie level     chocolate -> darkness
# The food family is detected first; then only its relevant qualifier
# dimensions are extracted from both texts with regexes and compared
# (agreement +, contradiction -, unspecified neutral) using family-specific
# weights. Qualifiers irrelevant to the family are ignored.

_DIMS = {
    "colour": {"red": r"\bred\b", "green": r"\bgreen\b", "yellow": r"\byellow\b", "orange": r"\borange\b",
               "white": r"\bwhite\b", "brown": r"\bbrown\b", "purple": r"\bpurple\b"},
    "heat": {"sweet": r"\bsweet\b|\bbell\b", "hot": r"\bhot\b|\bjalapeno\b|\bserrano\b|\bchili\b|\bhabanero\b"},
    "fatlvl": {"whole": r"\bwhole\b|\bfull[- ]fat\b", "reduced": r"\b2 ?%|\breduced fat\b",
               "low": r"\blow ?fat\b|\blowfat\b|\b1 ?%|\blight\b", "none": r"\bskim\b|\bnonfat\b|\bfat[- ]free\b"},
    "flavour": {"plain": r"\bplain\b", "vanilla": r"\bvanilla\b", "fruit": r"\bstrawberry\b|\bfruit\b|\bblueberry\b|\bpeach\b",
                "chocolate": r"\bchocolate\b", "honey": r"\bhoney\b"},
    "part": {"breast": r"\bbreast\b", "thigh": r"\bthigh\b", "wing": r"\bwings?\b", "leg": r"\bleg\b|\bdrumstick\b",
             "ground": r"\bground\b", "whole": r"\bwhole\b"},
    "meatcolour": {"light": r"\blight meat\b|\bwhite meat\b", "dark": r"\bdark meat\b"},
    "skin": {"with": r"\bwith skin\b|\bskin eaten\b|\bskin and\b|\band skin\b", "without": r"\bskinless\b|\bskin not eaten\b|\bwithout skin\b"},
    "lean": {"lean": r"\blean\b|\b9\d ?%", "regular": r"\b(7\d|8\d) ?%|\bregular\b|\bfat\b"},
    "variety_cheese": {"cottage": r"\bcottage\b", "cheddar": r"\bcheddar\b", "mozzarella": r"\bmozzarella\b",
                       "swiss": r"\bswiss\b", "parmesan": r"\bparmesan\b", "feta": r"\bfeta\b", "cream": r"\bcream cheese\b"},
    "style": {"italian": r"\bitalian\b", "ranch": r"\branch\b", "caesar": r"\bcaesar\b", "french": r"\bfrench\b",
              "vinaigrette": r"\bvinaigrette\b"},
    "calorie": {"reduced": r"\breduced calorie\b|\blow calorie\b|\blite\b|\blight\b|\bdiet\b", "regular": r"\bregular\b"},
    "darkness": {"dark": r"\bdark\b|\bbittersweet\b|\bsemisweet\b", "milk": r"\bmilk chocolate\b", "white": r"\bwhite\b"},
    "variety_veg": {"russet": r"\brusset\b", "red": r"\bred\b", "yukon": r"\byukon\b", "sweet": r"\bsweet\b",
                    "granny": r"\bgranny smith\b", "fuji": r"\bfuji\b", "gala": r"\bgala\b"},
}
_FAMILIES = [
    (r"\bpeppers?\b", {"colour": 2.0, "heat": 2.5}),
    (r"\b(milk|yogurt|yoghurt|cream|kefir)\b", {"fatlvl": 2.2, "flavour": 2.6}),
    (r"\b(chicken|turkey|duck)\b", {"part": 2.4, "skin": 1.4, "meatcolour": 2.2}),
    (r"\b(beef|pork|lamb)\b", {"lean": 1.6, "part": 1.4}),
    (r"\bcheese\b|\bcottage\b", {"variety_cheese": 3.0, "fatlvl": 1.6}),
    (r"\brice\b", {"colour": 2.5}),
    (r"\b(potato(es)?|apples?|onions?)\b", {"variety_veg": 1.2, "colour": 1.4}),
    (r"\bdressing\b", {"style": 2.6, "calorie": 1.8}),
    (r"\bchocolate\b", {"darkness": 2.4}),
]
_GENERIC = {"colour": 1.0, "fatlvl": 1.0, "flavour": 1.2}


def _value(dim, text):
    hits = [v for v, rx in _DIMS[dim].items() if re.search(rx, text)]
    return set(hits)


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        dims = None
        for rx, d in _FAMILIES:
            if re.search(rx, ing) or re.search(rx, usda.split(",")[0]):
                dims = d
                break
        if dims is None:
            dims = _GENERIC
        # disambiguate cheese "cream" from dairy cream; skin phrasing; "skin not eaten"
        score = 80.0
        for dim, w in dims.items():
            a, b = _value(dim, ing), _value(dim, usda)
            if dim == "skin" and "with" in b and "without" in b:
                b = {"without"}
            if a and b:
                if a & b:
                    score += 4.0 * w
                else:
                    score -= 12.0 * w
            elif a and not b:
                score -= 2.0 * w        # USDA silent on something the recipe specified
            elif b and not a:
                score -= 1.0 * w        # USDA asserts a qualifier the recipe left open
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
