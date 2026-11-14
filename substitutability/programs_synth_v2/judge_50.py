import re

# Food Category Consistency, variant 2: soft category distributions over a
# category TREE, compared by expected tree similarity.
# Every food word votes for a leaf category; votes are weighted by position
# (the head noun of the ingredient and the primary field of the USDA entry
# vote strongest), producing a probability distribution per text.
# Leaf categories sit in a 3-level tree:
#   food > {animal, plant, processed}
#        > animal: {flesh, dairy_egg}; plant: {produce, staple, aromatic};
#          processed: {fat_sweet, sauce_drink}
# Similarity of two leaves = depth of their lowest common ancestor / 3.
# Score = 10 * sum_a sum_b p(a) q(b) sim(a, b).

_TREE = {
    # leaf: (level-1, level-2)
    "meat": ("animal", "flesh"), "poultry": ("animal", "flesh"), "seafood": ("animal", "flesh"),
    "dairy": ("animal", "dairy_egg"), "egg": ("animal", "dairy_egg"),
    "vegetable": ("plant", "produce"), "fruit": ("plant", "produce"),
    "grain": ("plant", "staple"), "legume": ("plant", "staple"), "nutseed": ("plant", "staple"),
    "spice": ("plant", "aromatic"), "herb": ("plant", "aromatic"),
    "fat": ("processed", "fat_sweet"), "sweet": ("processed", "fat_sweet"),
    "sauce": ("processed", "sauce_drink"), "drink": ("processed", "sauce_drink"),
}
_PATTERNS = [
    ("seafood", r"fish|salmon|tuna|cod|shrimp|prawn|crab|lobster|scallop|clam|oyster|tilapia|trout|anchov|sardine"),
    ("poultry", r"chicken|turkey|duck|goose|poultry"),
    ("meat", r"beef|pork|lamb|veal|ham|bacon|sausage|steak|salami|venison"),
    ("dairy", r"milk|cheese|yogh?urt|cream|butter(?!nut)|kefir|ricotta|cottage|whey"),
    ("egg", r"^eggs?$|yolk"),
    ("fruit", r"fruit|apple|banana|orange|lemon|lime|berr|grape|mango|peach|pear|plum|cherr|pineapple|melon|guava|ugli|kiwi|fig|raisin|date"),
    ("vegetable", r"tomato|onion|garlic|carrot|broccoli|spinach|lettuce|kale|cabbage|pepper|zucchini|squash|potato|corn|celery|cucumber|mushroom|eggplant|^peas?$|asparagus|beet|leek|shallot|vegetable"),
    ("grain", r"rice|pasta|noodle|spaghetti|macaroni|bread|flour|oat|cereal|barley|quinoa|couscous|wheat|cracker|tortilla|gnocchi|grain|bagel"),
    ("legume", r"bean|lentil|chickpea|tofu|soy|edamame|hummus"),
    ("nutseed", r"nut$|nuts$|almond|walnut|pecan|cashew|peanut|pistachio|hazelnut|seed|chia|flax|sesame|tahini"),
    ("spice", r"spice|cinnamon|cumin|paprika|nutmeg|turmeric|clove|cardamom|ginger|seasoning|allspice"),
    ("herb", r"basil|thyme|rosemary|parsley|cilantro|dill|sage|oregano|mint|chive|tarragon"),
    ("fat", r"^oil$|lard|shortening|margarine|ghee"),
    ("sweet", r"sugar|honey|syrup|molasses|cand|chocolate|jam|jelly|sweetener"),
    ("sauce", r"sauce|dressing|ketchup|mustard|mayonnaise|vinegar|salsa|relish|pesto|gravy|paste|dip"),
    ("drink", r"juice|beverage|drink|soda|tea|coffee|nectar|smoothie|soup|broth|stock"),
]


def _leaf(word):
    for leaf, rx in _PATTERNS:
        if re.search(rx, word):
            return leaf
    return None


def _distribution(weighted_words):
    dist = {}
    for w, wt in weighted_words:
        leaf = _leaf(w)
        if leaf:
            dist[leaf] = dist.get(leaf, 0.0) + wt
    tot = sum(dist.values())
    return {k: v / tot for k, v in dist.items()} if tot else {}


def _sim(a, b):
    if a == b:
        return 1.0
    ta, tb = _TREE[a], _TREE[b]
    if ta[1] == tb[1]:
        return 2.0 / 3.0 * 0.85
    if ta[0] == tb[0]:
        return 1.0 / 3.0 * 0.8
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        if not iw:
            return 0.0
        n = len(iw)
        # head-final: weights rise toward the last word
        i_weighted = [(w, 1.0 + 3.0 * (k == n - 1) + 0.5 * k / max(1, n - 1)) for k, w in enumerate(iw)]
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not fields:
            return 0.0
        u_weighted = []
        for fi, f in enumerate(fields):
            fw = 3.0 if fi == 0 else (1.5 if fi == 1 else 0.3)
            for k, w in enumerate(f):
                u_weighted.append((w, fw * (1.3 if k == len(f) - 1 else 1.0)))
        p = _distribution(i_weighted)
        q = _distribution(u_weighted)
        if not p or not q:
            return 4.0
        exp_sim = sum(pa * qb * _sim(a, b) for a, pa in p.items() for b, qb in q.items())
        return round(10.0 * exp_sim, 3)
    except Exception:
        return 0.0
