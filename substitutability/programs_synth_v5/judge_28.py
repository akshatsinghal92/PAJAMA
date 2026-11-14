import re

# Category gate via suffix/stem cues; scoring is multiplicative with a tiered ladder.
_GROUPS = [
    ('animal', ['chicken', 'turkey', 'duck', 'beef', 'pork', 'lamb', 'veal', 'ham', 'bacon', 'sausage', 'steak', 'liver', 'giblet', 'sirloin', 'chuck', 'meat', 'fish', 'salmon', 'tuna', 'cod', 'herring', 'pollock', 'shrimp', 'crab', 'lobster', 'crayfish', 'oyster', 'clam', 'squid', 'trout', 'sardine', 'cervelat', 'salami']),
    ('dairy', ['milk', 'cream', 'cheese', 'butter', 'yogurt', 'whey', 'queso', 'ricotta', 'custard', 'kefir', 'ghee']),
    ('plantstaple', ['rice', 'wheat', 'flour', 'bread', 'pasta', 'oat', 'barley', 'rye', 'corn', 'noodle', 'spaghetti', 'cereal', 'quinoa', 'amaranth', 'cracker', 'bagel', 'tortilla', 'starch', 'bean', 'lentil', 'chickpea', 'pea', 'soy', 'tofu']),
    ('nutseed', ['almond', 'pecan', 'walnut', 'cashew', 'peanut', 'pistachio', 'hazelnut', 'flaxseed', 'flax', 'sesame', 'sunflower', 'chia', 'seed', 'nut']),
    ('fresh', ['squash', 'tomato', 'potato', 'onion', 'carrot', 'spinach', 'lettuce', 'escarole', 'cabbage', 'broccoli', 'apple', 'banana', 'orange', 'lemon', 'berry', 'cucumber', 'celery', 'mushroom', 'garlic', 'kale', 'zucchini', 'grape', 'mango', 'fruit', 'asparagus', 'eggplant', 'pumpkin']),
    ('seasoning', ['spice', 'ginger', 'cinnamon', 'cumin', 'paprika', 'oregano', 'basil', 'thyme', 'turmeric', 'clove', 'nutmeg', 'herb', 'parsley', 'cilantro', 'dill', 'rosemary', 'sage', 'vanilla', 'salt']),
    ('fatoil', ['oil', 'lard', 'shortening', 'margarine', 'tallow']),
    ('sugar', ['sugar', 'honey', 'syrup', 'molasses', 'sweetener', 'chocolate', 'cocoa']),
    ('prepared', ['sauce', 'dressing', 'ketchup', 'mustard', 'mayonnaise', 'vinegar', 'salsa', 'gravy', 'paste', 'soup', 'entree', 'dinner', 'sandwich', 'pizza', 'burrito', 'casserole', 'stew', 'mix']),
    ('drink', ['tea', 'coffee', 'juice', 'wine', 'beer', 'soda']),
    ('egg', ['egg', 'yolk']),
]
_LOOK = {}
for _g, _ws in _GROUPS:
    for _w in _ws:
        _LOOK[_w] = _g

_STOP = set('chopped diced sliced minced shredded grated crushed fresh whole large small medium optional divided cooked raw toasted trimmed thawed drained packed finely roughly cut of and or the a with from for to into plus more lean hot strong brewed ns nfs as major prepackaged choice separable fat visible'.split())

def _stem(w):
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('es') and len(w) > 4 and w[-3] in 'sxz':
        return w[:-2]
    if w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
        return w[:-1]
    return w

def _words(s):
    return [_stem(w) for w in re.findall(r'[a-z]+', s.lower())]

def _group_of(words, from_end):
    seq = list(reversed(words)) if from_end else words
    for w in seq:
        if w in _LOOK:
            return _LOOK[w]
    return None

def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '').lower()
        usda = str(usda_match or '').lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r'\([^)]*\)', ' ', ing)
        ing = re.sub(r'^\s*[\d.]+\s*(kg|g|ml|oz|lb)?\s*', '', ing)
        parts = ing.split(',')
        ing_main = _words(parts[0])
        ing_post = _words(','.join(parts[1:]))
        u_parts = usda.split(',')
        u_head = _words(u_parts[0])
        u_rest = _words(','.join(u_parts[1:]))

        # Tier 1: category agreement (head noun of ingredient vs head word of USDA)
        gi = _group_of(ing_main, True)
        gu = _group_of(u_head, False) or _group_of(u_rest, False)
        if gi is None or gu is None:
            tier = 0.45
        elif gi == gu:
            tier = 1.0
        elif {gi, gu} <= {'animal', 'dairy'} or {gi, gu} <= {'plantstaple', 'nutseed'}:
            tier = 0.3
        else:
            tier = 0.1

        # Tier 2: does the USDA head name cover the ingredient's content words?
        ic = [w for w in ing_main if w not in _STOP]
        uc_head = [w for w in u_head if w not in _STOP]
        uc_all = set(w for w in u_head + u_rest if w not in _STOP)
        if ic:
            cover = sum(1 for w in ic if w in uc_all) / float(len(ic))
        else:
            cover = 0.0
        # USDA items with unrelated extra specifics
        surplus = [w for w in uc_head if w not in ic]
        surplus_pen = 1.0 / (1.0 + 0.4 * len(surplus))

        score = tier * (0.25 + 0.75 * cover) * surplus_pen

        # Tier 3: preparation state conflicts
        states = [('raw', 'cooked'), ('whole', 'ground'), ('fresh', 'canned'), ('fresh', 'frozen')]
        ing_all = set(ing_main + ing_post)
        u_all = set(u_head + u_rest)
        for a, b in states:
            if (a in ing_all and b in u_all) or (b in ing_all and a in u_all):
                score *= 0.6
        for m in ('ground', 'flour', 'butter', 'powder', 'dried', 'juice', 'deli', 'luncheon', 'reduced', 'dry', 'mix', 'entree', 'canned'):
            if (m in u_all) != (m in ing_all):
                score *= 0.8
        return round(10.0 * max(0.0, min(1.0, score)), 3)
    except Exception:
        return 0.0
