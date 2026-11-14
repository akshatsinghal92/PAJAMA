import re

PARTS = {
    'breast', 'thigh', 'wing', 'drumstick', 'leg', 'loin', 'shoulder', 'rib', 'ribs',
    'tenderloin', 'sirloin', 'brisket', 'shank', 'heart', 'liver', 'kidney', 'kidneys',
    'tongue', 'tail', 'neck', 'belly', 'ground', 'fillet', 'steak', 'yolk', 'white',
    'whites', 'yolks', 'zest', 'peel', 'skin', 'leaves', 'greens', 'root', 'stem',
    'stems', 'seed', 'seeds', 'flower', 'bulb', 'shoots', 'stalk', 'stalks', 'juice',
    'oil', 'butter', 'powder', 'flour', 'milk', 'cream', 'crumbs', 'chips', 'cookies',
    'sauce', 'entree', 'patty', 'sausage', 'bone', 'bones', 'meat', 'lean', 'fat',
    'chuck', 'round', 'flank', 'ham', 'bacon', 'gizzard', 'giblets', 'organ',
}
STOP = {'raw', 'fresh', 'dried', 'dry', 'cooked', 'frozen', 'the', 'and', 'of', 'with',
        'without', 'salt', 'g', 'for', 'or', 'in', 'a', 'all', 'nfs', 'optional',
        'chopped', 'sliced', 'diced', 'cubed', 'shredded', 'ripe', 'large', 'small'}
SYN = {'kidneys': 'kidney', 'whites': 'white', 'yolks': 'yolk', 'ribs': 'rib',
       'stems': 'stem', 'seeds': 'seed', 'stalks': 'stalk', 'bones': 'bone'}


def _norm(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|oz|ml|lb|lbs)?\b', ' ', s)
    toks = re.findall(r'[a-z]+', s)
    out = []
    for t in toks:
        t = SYN.get(t, t)
        if len(t) > 3 and t.endswith('s') and t not in PARTS:
            t = t[:-1]
        out.append(t)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient.split(',')[0] if ingredient else '')
        usd = _norm(usda_match)
        if not ing or not usd:
            return 0.0
        ing_c = [t for t in ing if t not in STOP]
        usd_c = [t for t in usd if t not in STOP]
        if not ing_c or not usd_c:
            return 0.0
        iset, uset = set(ing_c), set(usd_c)
        # coverage of ingredient content words in USDA text
        cover = len(iset & uset) / len(iset)
        # primary food (first USDA segment) coverage
        prim = set(_norm((usda_match or '').split(',')[0])) - STOP
        pcover = len(iset & prim) / len(iset) if prim else 0.0
        # part-word agreement
        ip = iset & PARTS
        up = uset & PARTS
        score = 6.0 * cover + 2.0 * pcover
        if ip:
            if ip <= up:
                score += 2.0
            elif ip & up:
                score += 0.5
            else:
                score -= 2.5
        # USDA introduces part/form words ingredient lacks
        extra = (up - ip) - iset
        score -= 0.8 * len(extra & {'patty', 'sausage', 'entree', 'cookies', 'chips', 'sauce',
                                     'crumbs', 'flour', 'powder', 'oil', 'butter', 'juice'})
        score -= 0.4 * len(extra - {'patty', 'sausage', 'entree', 'cookies', 'chips', 'sauce',
                                     'crumbs', 'flour', 'powder', 'oil', 'butter', 'juice'})
        # brand-like noise penalty: huge USDA description with low coverage
        if len(usd_c) > 3 * len(ing_c) + 3 and cover < 0.7:
            score -= 1.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
