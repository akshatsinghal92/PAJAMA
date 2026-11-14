import re

# part classes: words in same class are the same anatomical region; different classes conflict
CLASSES = {
    'breast': 'breast', 'thigh': 'leg', 'drumstick': 'leg', 'leg': 'leg', 'wing': 'wing',
    'loin': 'loin', 'tenderloin': 'loin', 'sirloin': 'loin', 'shoulder': 'shoulder',
    'chuck': 'shoulder', 'brisket': 'brisket', 'rib': 'rib', 'belly': 'belly',
    'bacon': 'belly', 'heart': 'organ_h', 'liver': 'organ_l', 'kidney': 'organ_k',
    'tongue': 'organ_t', 'tail': 'tail', 'yolk': 'yolk', 'white': 'eggwhite',
    'zest': 'peel', 'peel': 'peel', 'rind': 'peel', 'skin': 'peel',
    'leaf': 'leaf', 'leaves': 'leaf', 'greens': 'leaf', 'root': 'root', 'tuber': 'root',
    'stem': 'stem', 'stalk': 'stem', 'seed': 'seed', 'flower': 'flower', 'bud': 'flower',
    'ground': 'ground', 'mince': 'ground', 'fillet': 'fillet', 'steak': 'fillet',
    'bone': 'bone', 'bones': 'bone', 'shank': 'shank', 'neck': 'neck',
}
# products derived from a part (not the plain part)
DERIVED = {'oil', 'butter', 'flour', 'powder', 'juice', 'sauce', 'cookies', 'chips', 'crumbs',
           'patty', 'sausage', 'entree', 'soup', 'cake', 'bar', 'snack', 'candy', 'extract',
           'paste', 'syrup', 'dessert', 'mix', 'drink', 'cereal', 'bread', 'pie', 'candies'}
NOISE = {'raw', 'fresh', 'dried', 'dry', 'cooked', 'frozen', 'and', 'the', 'of', 'with', 'for',
         'without', 'salt', 'nfs', 'optional', 'g', 'in', 'or', 'all', 'a', 'ripe', 'whole',
         'large', 'small', 'chopped', 'sliced', 'diced', 'cubed', 'shredded', 'minced'}


def _tokens(s, first_only=False):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    if first_only:
        s = s.split(',')[0]
    s = re.sub(r'\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b', ' ', s)
    out = []
    for t in re.findall(r"[a-z]+", s):
        if len(t) > 3 and t.endswith('ies'):
            t = t[:-3] + 'y'
        elif len(t) > 3 and t.endswith('s') and not t.endswith('ss'):
            t = t[:-1]
        out.append(t)
    return out


def _lcs_suffix(a, b):
    n = 0
    while n < len(a) and n < len(b) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_all = _tokens(ingredient.split(',')[0])
        ing = [t for t in ing_all if t not in NOISE]
        full = [t for t in _tokens(usda_match) if t not in NOISE]
        head_u = [t for t in _tokens(usda_match, True) if t not in NOISE]
        if not ing or not full:
            return 0.0
        # 1. head noun: last ingredient word must appear in USDA text
        head = ing[-1]
        head_hit = 1.0 if head in full else 0.0
        head_in_primary = 1.0 if head in head_u else 0.0
        # 2. bigram adjacency of ingredient phrase inside USDA tokens
        bi_i = set(zip(ing, ing[1:]))
        bi_u = set(zip(full, full[1:])) | set(zip(full, full[2:]))
        bi = (len(bi_i & bi_u) / len(bi_i)) if bi_i else head_hit
        # 3. part conflict check
        ci = {CLASSES[t] for t in ing if t in CLASSES}
        cu = {CLASSES[t] for t in full if t in CLASSES}
        mult = 1.0
        if ci and cu:
            mult *= 1.0 if ci & cu else 0.35
        elif ci and not cu:
            mult *= 0.8
        elif cu and not ci:
            mult *= 0.8 if 'ground' not in cu else 0.7
        # derived-product mismatch
        di = {t for t in ing if t in DERIVED}
        du = {t for t in full if t in DERIVED}
        if du - di:
            mult *= 0.4
        if di - du:
            mult *= 0.5
        # unmatched ingredient tokens
        miss = [t for t in ing if t not in full]
        miss_frac = len(miss) / len(ing)
        base = 4.0 * head_hit + 2.0 * head_in_primary + 2.0 * (1 - miss_frac) + 2.0 * bi
        # length sanity: huge USDA descriptions (brands) dilute
        if len(full) > 4 * len(ing) + 4:
            mult *= 0.7
        return round(base * mult, 3)
    except Exception:
        return 0.0
