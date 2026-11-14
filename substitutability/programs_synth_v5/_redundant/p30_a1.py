import re

ADDITIVES = {
    'salt': 2.0, 'salted': 2.0, 'sugar': 2.0, 'sweetened': 2.5, 'sauce': 3.0,
    'breaded': 3.0, 'battered': 3.0, 'breading': 3.0, 'seasoned': 2.5,
    'seasoning': 2.5, 'flavored': 1.5, 'flavor': 1.5, 'glazed': 2.5,
    'marinated': 2.5, 'pickled': 2.0, 'smoked': 1.5, 'candied': 3.0,
    'syrup': 2.5, 'honey': 1.5, 'cured': 2.0, 'fried': 2.0, 'canned': 1.0,
    'mix': 2.5, 'blend': 2.5, 'dressing': 3.0, 'frosting': 3.0, 'coating': 2.5,
    'filled': 2.5, 'stuffed': 2.5, 'creamed': 2.0, 'cheese': 1.0, 'butter': 1.0,
    'oil': 1.0, 'pepper': 1.0, 'garlic': 1.0, 'vanilla': 1.0, 'chocolate': 1.5,
    'frozen': 0.5, 'dessert': 3.0, 'prepared': 2.0, 'instant': 1.5,
    'sweetener': 2.5, 'powder': 1.0, 'dehydrated': 1.0, 'dried': 0.5,
    'roasted': 0.5, 'cooked': 0.3, 'enriched': 1.0, 'fortified': 1.5,
}
PLAIN = {'raw', 'plain', 'fresh', 'unsweetened', 'unsalted', 'without', 'whole', 'nfs', 'ns'}
STOP = {'the', 'a', 'an', 'of', 'and', 'or', 'with', 'in', 'for', 'from', 'to', 'on',
        'g', 'fresh', 'sliced', 'diced', 'chopped', 'minced', 'cubed', 'drained',
        'thawed', 'trimmed', 'sifted', 'skin', 'bagged', 'type', 'style'}


def _toks(s):
    s = s.lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r"'", '', s)
    return re.findall(r'[a-z]+', s)


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _additive_load(tokens, skip):
    load = 0.0
    for t in set(tokens):
        if t in skip:
            continue
        load += ADDITIVES.get(t, 0.0)
    return load


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_raw = _toks(re.sub(r'^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s*', '', ing.lower()))
        usda_t = _toks(usda)
        if not usda_t:
            return 0.0
        ing_s = set(_stem(t) for t in ing_raw)
        usda_s = [_stem(t) for t in usda_t]
        ing_all = set(ing_raw) | ing_s

        # additive load that the USDA entry has beyond what the ingredient mentions
        skip = set(ing_all)
        extra = _additive_load([_stem(t) for t in usda_t] + usda_t, skip)
        # additive load the ingredient has that USDA lacks (lost processing)
        usda_all = set(usda_t) | set(usda_s)
        missing = _additive_load(ing_raw + list(ing_s), usda_all)

        # primary food head (first comma segment) overlap
        head = [_stem(t) for t in _toks(usda.split(',')[0])]
        head = [t for t in head if t not in STOP]
        content = [t for t in ing_s if t not in STOP and t not in ADDITIVES]
        head_hit = sum(1 for t in head if t in ing_s or t in ing_all)
        head_frac = head_hit / float(len(head)) if head else 0.0
        all_hit = sum(1 for t in content if t in usda_all)
        cov = all_hit / float(len(content)) if content else 0.0

        plain_bonus = 0.5 * sum(1 for t in set(usda_t) if t in PLAIN)
        plain_bonus = min(plain_bonus, 1.5)

        # descriptor-count penalty: many extra comma segments imply compound product
        segs = len([x for x in usda.split(',') if x.strip()])
        seg_pen = 0.2 * max(0, segs - 3)

        score = 10.0 * (0.55 * cov + 0.45 * head_frac)
        score -= 1.1 * extra
        score -= 0.7 * missing
        score += plain_bonus
        score -= seg_pen
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
