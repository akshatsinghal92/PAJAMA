import re
import math

# Nutritional Profile Proximity, variant 5: morphology + USDA category
# headers placed on a 2-D ternary macro map.
# Food words are located on a ternary diagram of energy shares
# (protein / carbohydrate / fat) using SUFFIX and STEM rules
# (-fish, -berry, -seed, -meal, -nut ...) and the conventional USDA category
# headers ("Spices", "Beverages", "Candies", "Cereals", "Snacks", "Soup").
# Ternary points are projected to 2-D cartesian coordinates; the score
# decays with planar distance, and energy density (light / dense) is a
# third, smaller axis.

_SUFFIX_RULES = [
    # (regex on a word, (protein share, carb share, fat share), density 0..1)
    (r".*oil$", (0.0, 0.0, 1.0), 1.0),
    (r".*(butter|lard|ghee|margarine)$", (0.01, 0.0, 0.99), 0.9),
    (r".*fish$|^(salmon|tuna|cod|tilapia|trout|halibut)$", (0.75, 0.0, 0.25), 0.2),
    (r"^(shrimp|prawn|crab|lobster|scallop|clam|mussel)s?$", (0.85, 0.05, 0.10), 0.12),
    (r"^(chicken|turkey|breast|poultry)$", (0.75, 0.0, 0.25), 0.2),
    (r"^(beef|pork|lamb|veal|steak|ham|venison)$", (0.50, 0.0, 0.50), 0.3),
    (r"^(bacon|sausage|salami|pepperoni|patty|hotdog)s?$", (0.25, 0.03, 0.72), 0.45),
    (r".*berr(y|ies)$|.*fruit$|^(apple|banana|guava|mango|orange|grape|pear|peach|melon)s?$", (0.05, 0.92, 0.03), 0.07),
    (r".*seeds?$|^(chia|flax|sesame|tahini)$|.*nuts?$|^(almond|walnut|pecan|cashew|pistachio)s?$", (0.13, 0.17, 0.70), 0.65),
    (r".*meal$|.*flour$|^(cereal|cereals|oats|granola|cracker|crackers|muesli)$", (0.12, 0.78, 0.10), 0.42),
    (r"^(rice|pasta|noodles?|spaghetti|macaroni|gnocchi|couscous|quinoa|potato(es)?|bread|tortilla|corn)$", (0.10, 0.85, 0.05), 0.17),
    (r"^(bean|beans|lentils?|chickpeas?|peas?|hummus)$", (0.27, 0.68, 0.05), 0.15),
    (r"^(spinach|lettuce|kale|arugula|chard|cabbage|greens|broccoli|celery|cucumber|zucchini)$", (0.32, 0.58, 0.10), 0.03),
    (r"^(tomato(es)?|onions?|carrots?|peppers?|mushrooms?|squash|eggplant|garlic)$", (0.13, 0.80, 0.07), 0.05),
    (r"^(cheese|cheddar|parmesan|mozzarella|brie|gouda)$", (0.27, 0.03, 0.70), 0.45),
    (r"^(cottage|ricotta|skyr|quark)$", (0.48, 0.15, 0.37), 0.1),
    (r"^(yogurt|yoghurt|kefir|milk)$", (0.22, 0.30, 0.48), 0.07),
    (r"^(cream)$", (0.03, 0.04, 0.93), 0.4),
    (r"^(egg|eggs)$", (0.35, 0.03, 0.62), 0.16),
    (r"^(sugar|honey|syrup|molasses|jam|jelly|candy|candies)$", (0.0, 1.0, 0.0), 0.45),
    (r"^(chocolate|cookie|cookies|cake|brownie|pastry|doughnut)s?$", (0.05, 0.50, 0.45), 0.55),
    (r"^(dressing|vinaigrette|mayonnaise|pesto|aioli)$", (0.02, 0.10, 0.88), 0.45),
    (r"^(sauce|ketchup|salsa|gravy|paste)$", (0.10, 0.75, 0.15), 0.1),
    (r"^(juice|nectar|soda|lemonade|beverages?|drink)$", (0.03, 0.95, 0.02), 0.05),
    (r"^(broth|stock|bouillon|consomme)$", (0.55, 0.30, 0.15), 0.01),
    (r"^(soup|chowder|stew)$", (0.20, 0.50, 0.30), 0.05),
    (r"^(spices?|cinnamon|cumin|paprika|nutmeg|turmeric|ginger|oregano|seasoning)$", (0.13, 0.67, 0.20), 0.33),
]
_CATEGORY_HEADERS = {
    "spices": "spices", "beverages": "juice", "candies": "candy", "cereals": "cereal",
    "snacks": "chocolate", "soup": "soup", "fish": "fish", "cheese": "cheese",
}


def _locate(word):
    for rx, tern, dens in _SUFFIX_RULES:
        if re.match(rx + r"\Z" if not rx.endswith("$") else rx, word):
            return tern, dens
    return None


def _xy(tern):
    p, c, f = tern
    # equilateral triangle: protein (0,0), carb (1,0), fat (0.5, 0.866)
    return (c + 0.5 * f, 0.866 * f)


def _profile(words):
    loc = None
    for w in words:
        r = _locate(w)
        if r:
            loc = r            # head-final: keep last located word
    return loc


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        header = fields[0][0] if fields[0] else ""
        if len(fields[0]) == 1 and header in _CATEGORY_HEADERS and len(fields) > 1:
            pu = _profile(fields[1]) or _locate(_CATEGORY_HEADERS[header])
        else:
            pu = _profile(fields[0]) or (_profile(fields[1]) if len(fields) > 1 else None)
        pi = _profile(iw)
        if pi is None or pu is None:
            u_all = {w.rstrip("s") for f in fields for w in f}
            return 6.0 if iw[-1].rstrip("s") in u_all else 2.5
        (x1, y1), (x2, y2) = _xy(pi[0]), _xy(pu[0])
        planar = math.hypot(x1 - x2, y1 - y2)
        dens = abs(pi[1] - pu[1])
        u_words = set(w for f in fields for w in f)
        # fat-lowering descriptors move the USDA point toward the protein/carb edge
        if u_words & {"lowfat", "nonfat", "skim", "low", "light", "reduced"}:
            planar += 0.08
        if u_words & {"fried", "breaded"} and not set(iw) & {"fried", "breaded"}:
            planar += 0.15
            dens += 0.15
        d = math.sqrt(planar ** 2 + (0.8 * dens) ** 2)
        score = 10.0 * math.exp(-4.0 * d)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
