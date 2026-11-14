import re

_ADDITIVE = {
    'salt', 'salted', 'sugar', 'sweetened', 'sweetener', 'syrup', 'honey', 'oil', 'butter',
    'sauce', 'gravy', 'seasoned', 'seasoning', 'breaded', 'battered', 'breading', 'coated',
    'flavored', 'flavor', 'flavoured', 'spiced', 'marinated', 'glazed', 'candied', 'frosted',
    'blend', 'mix', 'mixture', 'dressing', 'filled', 'stuffed', 'canned', 'pickled', 'smoked',
    'cured', 'sandwich', 'cookies', 'cookie', 'cake', 'pie', 'souffle', 'pudding', 'chocolate',
    'vanilla', 'cheese', 'cream', 'fortified', 'enriched', 'added', 'preserved', 'pepper',
    'prepackaged', 'luncheon', 'imitation', 'substitute', 'dessert', 'snack', 'bar', 'cereal',
}
_PROCESS = {'frozen', 'dried', 'dehydrated', 'cooked', 'boiled', 'fried', 'roasted', 'baked',
            'raw', 'fresh', 'toasted', 'ground', 'powder', 'powdered', 'paste', 'juice',
            'canned', 'drained', 'unprepared', 'steamed', 'simmered', 'grilled', 'braised'}
_STOP = {'and', 'or', 'with', 'without', 'of', 'the', 'a', 'in', 'from', 'for', 'to', 'no', 'not',
         'only', 'g', 'kg', 'oz', 'lb', 'cup', 'cups', 'tbsp', 'tsp', 'sliced', 'chopped',
         'diced', 'minced', 'shredded', 'grated', 'thawed', 'finely', 'thinly', 'large', 'small',
         'medium', 'whole', 'meat', 'type', 'all', 'varieties', 'includes'}


def _toks(s):
    s = (s or '').lower()
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|oz|lb|ml)?\b', ' ', s)
    s = re.sub(r'\(([^)]*)\)', r' \1 ', s)
    return re.findall(r'[a-z]+', s)


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = [_stem(t) for t in _toks(ingredient) if t not in _STOP]
        parts = (usda_match or '').split(',')
        usda_all = [_stem(t) for t in _toks(usda_match) if t not in _STOP]
        if not ing or not usda_all:
            return 0.0
        ing_set, usda_set = set(ing), set(usda_all)
        add = {_stem(a) for a in _ADDITIVE}
        proc = {_stem(a) for a in _PROCESS}
        # content words (not processing words)
        ing_c = {t for t in ing_set if t not in proc}
        usda_c = {t for t in usda_set if t not in proc}
        if not ing_c:
            ing_c = ing_set
        # core coverage of the ingredient's food words by the USDA entry
        cover = len(ing_c & usda_set) / float(len(ing_c))
        # primary food (first segment) match
        prim = {_stem(t) for t in _toks(parts[0]) if t not in _STOP}
        prim_hit = len(prim & ing_set) / float(len(prim)) if prim else 0.0
        # additives present in usda but not mentioned in ingredient
        extra_add = [t for t in usda_set if t in add and t not in ing_set]
        # extra compound content words
        extra_c = usda_c - ing_set
        # additives in ingredient absent from usda (ingredient has flavor, usda is plain)
        miss_add = [t for t in ing_set if t in add and t not in usda_set]
        score = 6.0 * cover + 3.0 * prim_hit
        score -= 1.8 * len(extra_add)
        score -= 0.7 * min(len(extra_c), 5)
        score -= 1.0 * len(miss_add)
        # processing-state agreement
        ip, up = ing_set & proc, usda_set & proc
        if ip and up:
            score += 1.5 if ip & up else -0.5
        if cover == 0:
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
