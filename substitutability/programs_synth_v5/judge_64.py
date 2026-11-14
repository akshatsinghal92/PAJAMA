import re
import math

_COMPOSITE = {
    'with': 2.0, 'and': 1.0, 'stuffed': 3.0, 'salad': 3.0, 'soup': 3.0,
    'casserole': 3.0, 'sandwich': 3.0, 'mix': 2.5, 'blend': 2.0, 'dinner': 3.0,
    'prepared': 2.0, 'sauce': 2.0, 'pie': 3.0, 'pizza': 3.0, 'burrito': 3.0,
    'entree': 3.0, 'stew': 3.0, 'cake': 2.0, 'cookie': 2.0, 'cookies': 2.0,
    'dressing': 2.0, 'filled': 2.0, 'topping': 1.5, 'frozen meal': 3.0,
    'restaurant': 2.5, 'fast': 1.5, 'combination': 2.5, 'mixture': 2.5,
    'seasoning': 1.5, 'drink': 1.5, 'beverage': 1.5, 'candies': 1.5, 'snacks': 1.0,
}
_STOP = {'the', 'of', 'a', 'an', 'for', 'to', 'in', 'or', 'and', 'with', 'raw',
         'fresh', 'cooked', 'g', 'all', 'type', 'style', 'regular', 'plain'}
_PREP = {'chopped', 'diced', 'sliced', 'minced', 'melted', 'crushed', 'sifted',
         'cubed', 'thawed', 'frozen', 'ground', 'grated', 'shredded', 'peeled',
         'powdered', 'whole', 'fresh', 'large', 'small', 'medium', 'cut', 'florets',
         'leaves', 'pulp'}


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb|mg)?\b', ' ', s)
    return s


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s)]


def _comp_load(text, comma_parts):
    load = 0.0
    words = set(re.findall(r"[a-z]+", text))
    for k, v in _COMPOSITE.items():
        if ' ' in k:
            if k in text:
                load += v
        elif k in words:
            load += v
    # number of comma descriptors hints at complex prepared items
    load += 0.3 * max(0, len(comma_parts) - 3)
    # multiple foods joined in primary name
    if len(comma_parts) and re.search(r'\b(and|with|&)\b|/', comma_parts[0]):
        load += 1.5
    return load


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = ing.split(',')[0]
        ing_parts = [p for p in ing.split(',') if p.strip()]
        usda_parts = [p for p in usda.split(',') if p.strip()]

        ci = _comp_load(ing_main, ing_parts[:1])
        cu = _comp_load(usda, usda_parts)

        # composite-class mismatch penalty
        gap = abs(ci - cu)
        if (ci > 0) == (cu > 0):
            class_term = 4.0 - 0.3 * min(gap, 5)
        else:
            class_term = 4.0 - 2.0 * min(gap, 2.5)

        # content overlap of primary food words
        it = set(t for t in _toks(ing_main) if t not in _STOP and t not in _PREP and len(t) > 1)
        ut_all = set(t for t in _toks(usda) if t not in _STOP and len(t) > 1)
        ut_head = set(t for t in _toks(usda_parts[0]) if t not in _STOP and len(t) > 1)
        if not it:
            overlap = 0.0
        else:
            hit_head = len(it & ut_head) / float(len(it))
            hit_all = len(it & ut_all) / float(len(it))
            overlap = 0.65 * hit_head + 0.35 * hit_all
        # penalize extra unexplained words in the usda primary food
        extra = len(ut_head - it)
        extra_pen = 0.4 * math.log1p(extra)

        score = class_term + 6.0 * overlap - extra_pen
        return float(score)
    except Exception:
        return 0.0
