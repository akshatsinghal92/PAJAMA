import re

_COMPOSITE = ['with', 'and', 'in sauce', 'stuffed', 'salad', 'soup', 'casserole',
              'sandwich', 'mix', 'blend', 'dinner', 'prepared', 'stew', 'pie',
              'pizza', 'burrito', 'taco', 'entree', 'meal', 'combination', 'dish']
_STOP = set(['g', 'of', 'the', 'a', 'an', 'or', 'raw', 'fresh', 'cooked', 'sliced',
             'diced', 'chopped', 'minced', 'shredded', 'grated', 'ground', 'whole',
             'small', 'large', 'medium', 'frozen', 'dried', 'drained', 'thawed',
             'cubed', 'peeled', 'for', 'to', 'in', 'from', 'style'])


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b', ' ', s)
    return s


def _composite_hits(s):
    toks = set(re.findall(r'[a-z]+', s))
    low = ' ' + re.sub(r'[^a-z ]', ' ', s) + ' '
    n = 0
    for c in _COMPOSITE:
        if ' ' in c:
            if (' ' + c + ' ') in low:
                n += 1
        elif c in toks:
            n += 1
    return n


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = (usda_match or '').lower()
        ing_c = _composite_hits(ing)
        usda_c = _composite_hits(usda)
        # commas in USDA entry indicate descriptors, not composite; count only keyword hits
        ing_comp = ing_c > 0
        usda_comp = usda_c > 0

        score = 5.0
        if ing_comp == usda_comp:
            score += 2.0
            if ing_comp:
                score += 1.0
        else:
            score -= 2.5 + 0.5 * min(abs(ing_c - usda_c), 3)

        # head-noun agreement
        ing_words = [_stem(w) for w in re.findall(r'[a-z]+', re.sub(r'\([^)]*\)', ' ', ing.split(',')[0])) if w not in _STOP]
        usda_primary = re.sub(r'\([^)]*\)', ' ', usda.split(',')[0])
        usda_all = set(_stem(w) for w in re.findall(r'[a-z]+', usda))
        usda_prim_words = set(_stem(w) for w in re.findall(r'[a-z]+', usda_primary))
        if ing_words:
            head = ing_words[-1]
            if head in usda_prim_words:
                score += 2.0
            elif head in usda_all:
                score += 0.8
            cov = sum(1 for w in ing_words if w in usda_all) / float(len(ing_words))
            score += 1.5 * cov
            if cov == 0:
                score -= 2.0
        # excess descriptors in USDA entry (many commas) are a mild penalty
        score -= 0.25 * max(0, usda.count(',') - 2)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
