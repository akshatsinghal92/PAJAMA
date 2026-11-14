import re

COMPOSITE_WORDS = {
    'with', 'and', 'stuffed', 'salad', 'soup', 'casserole', 'sandwich', 'mix',
    'blend', 'dinner', 'prepared', 'sauce', 'pie', 'stew', 'combo', 'topping',
    'filled', 'mixture', 'medley', 'entree', 'burrito', 'pizza', 'dressing',
}
STOP = {'g', 'of', 'the', 'a', 'an', 'in', 'for', 'to', 'or', 'from', 'style',
        'fresh', 'raw', 'cooked', 'sliced', 'chopped', 'diced', 'minced',
        'frozen', 'dried', 'ground', 'whole', 'small', 'large', 'nfs'}


def _clean(s):
    s = str(s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|gram|grams|kg|oz|ml)?\b', ' ', s)
    return s


def _tokens(s):
    return re.findall(r"[a-z]+", s)


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _composite_count(s):
    toks = [_stem(t) if t not in ('and', 'with') else t for t in _tokens(s)]
    return sum(1 for t in toks if t in COMPOSITE_WORDS or _stem(t) in COMPOSITE_WORDS)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        # ingredient main part: before post-comma state
        ing_main = ing.split(',')[0]
        usda_parts = [p.strip() for p in usda.split(',')]
        usda_head = usda_parts[0]

        ic = _composite_count(ing_main)
        # in USDA, 'with' in comma descriptors like "with skin" is minor; count head only fully
        uc_head = _composite_count(usda_head)
        uc_all = _composite_count(usda)
        uc = uc_head + 0.4 * max(0, uc_all - uc_head)

        i_comp = ic > 0
        u_comp = uc_head > 0 or uc >= 1.2

        score = 5.0
        # composite agreement
        if i_comp == u_comp:
            score += 1.5
            if i_comp:
                # dish for dish: need shared content tokens
                pass
        else:
            score -= 3.5
        score -= 0.8 * abs(ic - uc)

        # content token overlap (sets)
        it = {_stem(t) for t in _tokens(ing_main) if t not in STOP and t not in COMPOSITE_WORDS}
        ut_head = {_stem(t) for t in _tokens(usda_head) if t not in STOP and t not in COMPOSITE_WORDS}
        ut_all = {_stem(t) for t in _tokens(usda) if t not in STOP and t not in COMPOSITE_WORDS}
        if it:
            cover = len(it & ut_all) / len(it)
            head_cover = len(it & ut_head) / len(it)
        else:
            cover = head_cover = 0.0
        extra = len(ut_head - it)
        score += 3.0 * cover + 1.0 * head_cover
        score -= 0.5 * min(extra, 4)

        # product-form mismatch: derived forms listed on one side only
        forms = ['juice', 'oil', 'paste', 'pate', 'powder', 'sugar', 'flour', 'butter', 'sauce', 'extract']
        for f in forms:
            if (f in it) != (f in ut_head | ut_all):
                score -= 1.5
        # ingredient head noun should appear in USDA head
        ing_words = [_stem(t) for t in _tokens(ing_main) if t not in STOP]
        if ing_words and ing_words[-1] not in ut_all:
            score -= 1.5
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
