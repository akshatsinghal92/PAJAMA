import re
import math

_ADDITIVE = {
    'sauce': 3.0, 'pie': 3.0, 'filling': 3.0, 'mix': 2.0, 'mixture': 2.5, 'chips': 3.0,
    'frozen': 1.5, 'entree': 3.5, 'breaded': 3.0, 'battered': 3.0, 'fried': 2.0,
    'sweetened': 2.5, 'flavored': 2.5, 'seasoned': 2.5, 'seasoning': 2.5, 'candied': 3.0,
    'glazed': 2.5, 'canned': 1.5, 'syrup': 2.5, 'sugar': 1.5, 'salt': 1.2, 'pepper': 1.0,
    'oil': 1.2, 'butter': 1.2, 'cream': 1.5, 'cheese': 1.0, 'pickled': 2.5, 'smoked': 1.5,
    'cured': 2.0, 'prepared': 1.8, 'restaurant': 2.5, 'fast': 2.0, 'foods': 1.0,
    'bar': 2.5, 'patty': 1.2, 'patties': 1.2, 'frankfurter': 3.0, 'sausage': 2.0,
    'nfs': 1.0, 'dressing': 3.0, 'soup': 3.0, 'jam': 3.0, 'jelly': 3.0, 'juice': 2.0,
    'dried': 1.2, 'enriched': 1.0, 'added': 1.5, 'with': 1.5, 'and': 1.0, 'stuffed': 3.0,
    'dessert': 3.0, 'cookie': 3.0, 'cake': 3.0, 'bread': 1.5, 'snack': 3.0, 'infant': 3.0,
    'imitation': 3.0, 'substitute': 3.0, 'flour': 1.0, 'starch': 1.0, 'mashed': 1.5,
}
_PLAIN = {'raw': 1.0, 'plain': 1.5, 'unsalted': 1.2, 'unsweetened': 1.2, 'fresh': 1.0,
          'without': 0.6, 'whole': 0.5, 'unroasted': 0.8, 'unenriched': 0.4}
_STOP = {'g', 'kg', 'oz', 'ml', 'of', 'the', 'a', 'an', 'fresh', 'optional', 'garnish',
         'chopped', 'sliced', 'diced', 'minced', 'cubed', 'thawed', 'trimmed', 'ground',
         'cooked', 'raw', 'large', 'small', 'medium', 'to', 'taste', 'for', 'or', 'from',
         'tube', 'slices', 'segments', 'visible', 'fat', 'all', 'types', 'whole'}


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _toks(s):
    s = re.sub(r'\([^)]*\)', ' ', s.lower())
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)?\b', ' ', s)
    return [_stem(t) for t in re.findall(r'[a-z]+', s)]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_all = set(_toks(ing))
        usda_parts = [p for p in usda.split(',')]
        usda_all = _toks(usda)
        usda_set = set(usda_all)
        ing_core = set(t for t in ing_all if t not in _STOP and len(t) > 1)
        if not ing_core:
            ing_core = set(ing_all)
        # coverage of ingredient core words by usda
        cov = sum(1 for t in ing_core if t in usda_set) / float(len(ing_core) or 1)
        # primary food coverage: how much of usda's head is explained by ingredient
        head = set(_toks(usda_parts[0])) if usda_parts else set()
        head_ex = (sum(1 for t in head if t in ing_all) / float(len(head))) if head else 0.0
        # additive penalty: additive words in usda that ingredient lacks
        pen = 0.0
        for t in usda_set:
            w = _ADDITIVE.get(t)
            if w is None and t.endswith('ed') and t[:-2] in _ADDITIVE:
                w = _ADDITIVE[t[:-2]]
            if w and t not in ing_all:
                pen += w
        # extra descriptors beyond ingredient
        extra = len([t for t in usda_set if t not in ing_all and t not in _PLAIN])
        bonus = sum(_PLAIN.get(t, 0) for t in usda_set)
        score = 4.0 * cov + 2.5 * head_ex + 0.5 * bonus
        score -= 0.9 * pen
        score -= 0.25 * math.log1p(extra)
        # compound-ingredient hint: "X with Y", "X and Y" absent in ingredient
        if re.search(r'\b(with|and)\b', usda.lower()) and not re.search(r'\b(with|and)\b', ing.lower()):
            score -= 1.0
        return float(score)
    except Exception:
        return 0.0
