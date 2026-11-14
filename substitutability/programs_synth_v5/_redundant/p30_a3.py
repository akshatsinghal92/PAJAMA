import re

NOISE = set('the a an of and or with without in for from to on g kg ml oz lb raw fresh sliced diced '
            'chopped minced cubed drained thawed trimmed sifted skin bagged type style whole separable '
            'lean fat choice grade nfs ns as to major regular made large small medium boneless '
            'ground cooked dry'.split())
PROC = set('salt salted sugar sweetened sauce breaded battered seasoned seasoning flavored glazed '
           'marinated pickled smoked candied syrup cured fried mix blend dressing frosting coating '
           'filled stuffed creamed dessert prepared instant fortified butterscotch frozen canned '
           'powder powdered dehydrated candies spices soup'.split())


def _stem(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and w.endswith('es') and w[-3] in 'sxz':
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _tokens(s):
    s = s.lower().replace("'", '')
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b', ' ', s)
    return [_stem(w) for w in re.findall(r'[a-z]+', s)]


def judging_function(ingredient, usda_match):
    try:
        ing_t = _tokens(str(ingredient or ''))
        usda_str = str(usda_match or '')
        if not ing_t or not usda_str.strip():
            return 0.0
        head_t = _tokens(usda_str.split(',')[0])
        rest_t = _tokens(','.join(usda_str.split(',')[1:]))
        ing_set = set(ing_t)
        proc_stems = set(_stem(p) for p in PROC)

        ing_core = [t for t in ing_set if t not in NOISE and t not in proc_stems]
        head_core = [t for t in head_t if t not in NOISE]
        rest_core = [t for t in rest_t if t not in NOISE]

        # core food identity: does the USDA head name the ingredient's food word?
        hits_head = sum(1 for t in head_core if t in ing_set)
        hits_rest = sum(1 for t in rest_core if t in ing_set)
        ident = 0.0
        if ing_core:
            matched = sum(1 for t in ing_core if t in head_core or t in rest_core)
            ident = matched / float(len(ing_core))
        head_ok = hits_head / float(len(head_core)) if head_core else 0.0

        # processing mismatch (symmetric difference of processing words)
        up = set(t for t in head_t + rest_t if t in proc_stems)
        ip = set(t for t in ing_set if t in proc_stems)
        added = up - ip
        dropped = ip - up

        # unexplained descriptor tokens in USDA
        unexplained = [t for t in head_core + rest_core if t not in ing_set]
        unexpl_frac = len(unexplained) / float(max(1, len(head_core) + len(rest_core)))

        score = 5.0 * ident + 3.0 * head_ok + 1.0 * hits_rest / float(max(1, len(rest_core)))
        score -= 2.0 * len(added) + 1.2 * len(dropped)
        score -= 1.5 * unexpl_frac
        if ident == 0:
            score -= 1.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
