import re

_METHODS = {
    'raw': ['raw', 'fresh', 'uncooked'],
    'boil': ['boiled', 'boil', 'poached', 'simmered', 'stewed'],
    'steam': ['steamed', 'steam'],
    'bake': ['baked', 'bake'],
    'roast': ['roasted', 'roast', 'dry roasted', 'oil roasted'],
    'grill': ['grilled', 'grill', 'charbroiled', 'barbecued', 'bbq'],
    'fry': ['fried', 'pan-fried', 'panfried', 'fry'],
    'deep': ['deep-fried', 'deep fried'],
    'saute': ['sauteed', 'sautéed', 'stir-fried', 'stir fried'],
    'broil': ['broiled', 'broil'],
    'micro': ['microwaved', 'microwave'],
    'smoke': ['smoked', 'cured', 'lox'],
    'toast': ['toasted', 'toast'],
    'braise': ['braised'],
    'cooked': ['cooked', 'dry heat', 'moist heat'],
    'dried': ['dried', 'dehydrated', 'dry'],
    'canned': ['canned'],
    'frozen': ['frozen'],
}
# compatibility between method classes (0..1)
_COMPAT = {
    frozenset(['boil', 'steam']): 0.8, frozenset(['bake', 'roast']): 0.85,
    frozenset(['grill', 'broil']): 0.85, frozenset(['fry', 'saute']): 0.8,
    frozenset(['fry', 'deep']): 0.8, frozenset(['braise', 'boil']): 0.7,
    frozenset(['braise', 'roast']): 0.5, frozenset(['toast', 'roast']): 0.7,
    frozenset(['toast', 'bake']): 0.6, frozenset(['grill', 'roast']): 0.6,
    frozenset(['bake', 'grill']): 0.5, frozenset(['bake', 'broil']): 0.6,
    frozenset(['raw', 'dried']): 0.3, frozenset(['canned', 'boil']): 0.6,
    frozenset(['frozen', 'raw']): 0.7, frozenset(['canned', 'cooked']): 0.7,
}
_STOP = set('a an the of and or with without in for to from fresh raw cooked dried frozen canned ground whole sliced chopped diced minced large small medium pieces piece style type fat salt added lean trimmed select prepared'.split())


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb|mg)?\b', ' ', s)
    return s


def _methods(text):
    found = set()
    for k, ws in _METHODS.items():
        for w in ws:
            if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text):
                found.add(k)
                break
    if 'deep' in found:
        found.discard('fry')
    if 'cooked' in found and len(found - {'cooked'}) > 0:
        found.discard('cooked')
    return found


def _tokens(text):
    out = set()
    for t in re.findall(r'[a-z]+', text):
        if t in _STOP or len(t) < 3:
            continue
        if t.endswith('ies') and len(t) > 4:
            t = t[:-3] + 'y'
        elif t.endswith('es') and len(t) > 4:
            t = t[:-2]
        elif t.endswith('s') and len(t) > 3:
            t = t[:-1]
        out.add(t)
    return out


def _pair(a, b):
    if a == b:
        return 1.0
    return _COMPAT.get(frozenset([a, b]), 0.0)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        # method component
        mi = _methods(ing)
        mu = _methods(usda)
        mi_n = mi - {'raw'}
        mu_n = mu - {'raw'}
        if not mi and not mu:
            meth = 0.85
        elif not mi:
            # unstated: compatible with raw / generic; mild penalty for heavy processing
            if not mu or mu <= {'raw', 'cooked', 'canned', 'frozen', 'dried'}:
                meth = 0.8
            else:
                meth = 0.55
        elif not mu:
            meth = 0.6 if 'raw' in mi else 0.45
        else:
            best = 0.0
            for a in mi:
                for b in mu:
                    best = max(best, _pair(a, b))
            meth = best
            # penalize extra transformative methods only on one side
            extra = (mu_n ^ mi_n) - set(k for k in (mu_n | mi_n) if any(_pair(k, o) > 0.5 for o in (mu_n | mi_n) if o != k))
            meth -= 0.15 * min(len(extra), 2)
            meth = max(0.0, min(1.0, meth))
        # food identity component: head-word agreement
        ti = _tokens(ing) - set(sum(_METHODS.values(), []))
        tu = _tokens(usda) - set(sum(_METHODS.values(), []))
        if not ti or not tu:
            ident = 0.0
        else:
            inter = ti & tu
            cover = len(inter) / float(len(ti))
            prec = len(inter) / float(len(tu))
            ident = 0.7 * cover + 0.3 * prec
            # primary food of usda (first comma segment) appearing in ingredient
            head = _tokens(usda.split(',')[0])
            if head and (head & ti):
                ident = min(1.0, ident + 0.25)
            elif not inter:
                ident = 0.0
        score = 100.0 * (0.35 * meth + 0.65 * ident)
        if ident == 0.0:
            score *= 0.3
        return round(score, 3)
    except Exception:
        return 0.0
