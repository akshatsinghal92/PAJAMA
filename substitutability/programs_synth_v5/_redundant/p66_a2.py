import re

_METHODS = {
    'raw': ['raw', 'fresh', 'uncooked', 'unroasted', 'unprepared'],
    'boiled': ['boiled', 'boil', 'poached', 'simmered', 'stewed', 'blanched'],
    'steamed': ['steamed', 'steam'],
    'baked': ['baked', 'bake'],
    'roasted': ['roasted', 'roast', 'oven-roasted'],
    'grilled': ['grilled', 'grill', 'charbroiled', 'barbecued', 'bbq', 'pan-broiled', 'broiled'],
    'fried': ['fried', 'pan-fried', 'stir-fried', 'sauteed', 'sautéed', 'saute'],
    'deepfried': ['deep-fried', 'deep fried'],
    'microwaved': ['microwaved', 'microwave'],
    'smoked': ['smoked', 'smoke'],
    'toasted': ['toasted', 'toast'],
    'cooked': ['cooked', 'cooking'],
    'dried': ['dried', 'dehydrated', 'dry'],
    'canned': ['canned', 'pickled', 'preserved'],
    'frozen': ['frozen'],
}

# Distance classes between method groups (0 = identical, higher = worse)
_FAMILY = {
    'raw': 'raw', 'boiled': 'wet', 'steamed': 'wet', 'microwaved': 'wet',
    'baked': 'dry', 'roasted': 'dry', 'toasted': 'dry', 'grilled': 'dry',
    'fried': 'fat', 'deepfried': 'fat', 'smoked': 'smoke', 'cooked': 'gen',
    'dried': 'dried', 'canned': 'canned', 'frozen': 'raw',
}

_STOP = set('the a an of and with in for from or to fresh style type nfs ns as'.split())


def _clean(s):
    s = s.lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|gm|grams?|kg|oz|ml|lb|lbs)\b', ' ', s)
    return s


def _methods(text):
    found = set()
    for m, words in _METHODS.items():
        for w in words:
            if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text):
                found.add(m)
                break
    if 'deepfried' in found:
        found.discard('fried')
    return found


def _pair_cost(a, b):
    if a == b:
        return 0.0
    fa, fb = _FAMILY[a], _FAMILY[b]
    if 'gen' in (fa, fb):
        return 0.5
    if fa == fb:
        return 1.0
    if {fa, fb} == {'dry', 'fat'}:
        return 2.5
    if 'raw' in (fa, fb):
        return 3.5
    if 'dried' in (fa, fb) or 'canned' in (fa, fb):
        return 3.0
    if 'smoke' in (fa, fb):
        return 3.0
    return 2.0


def _tokens(s):
    toks = re.findall(r'[a-z]+', s)
    out = set()
    for t in toks:
        if t in _STOP or len(t) < 3:
            continue
        if t.endswith('ies') and len(t) > 4:
            t = t[:-3] + 'y'
        elif t.endswith('s') and not t.endswith('ss') and len(t) > 3:
            t = t[:-1]
        out.add(t)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ''))
        usda = _clean(str(usda_match or ''))
        if not ing.strip() or not usda.strip():
            return 0.0

        im = _methods(ing)
        um = _methods(usda)

        # method agreement score in [0, 10]
        if not im and not um:
            method = 8.0
        elif not im or not um:
            # unstated is compatible with raw / generic; mild penalty for strong method
            present = im or um
            if present <= {'raw', 'cooked', 'frozen'}:
                method = 8.5
            elif present & {'fried', 'deepfried', 'smoked', 'toasted', 'roasted', 'dried', 'canned'}:
                method = 5.5
            else:
                method = 7.0
        else:
            # best alignment: each ingredient method matched to nearest usda method
            costs = []
            for a in im:
                costs.append(min(_pair_cost(a, b) for b in um))
            for b in um:
                costs.append(min(_pair_cost(a, b) for a in im))
            avg = sum(costs) / len(costs)
            method = max(0.0, 10.0 - 2.8 * avg)

        # food-identity guard: method agreement is meaningless if foods differ
        it = _tokens(ing) - set(sum(_METHODS.values(), []))
        ut = _tokens(usda) - set(sum(_METHODS.values(), []))
        if it and ut:
            inter = len(it & ut)
            cover = inter / len(it)
            first_usda = _tokens(usda.split(',')[0])
            head_hit = 1.0 if (first_usda & it) else 0.0
            identity = 0.5 * cover + 0.5 * head_hit
            if it <= ut or ut <= it:
                identity = min(1.0, identity + 0.25)
        else:
            identity = 0.2

        # extra descriptors in usda that signal processing change
        penalty = 0.0
        for w in ('pickled', 'canned', 'juice', 'powder', 'low sodium', 'lactose'):
            if w in usda and w not in ing:
                penalty += 1.0

        score = method * (0.1 + 0.9 * identity * identity) - penalty
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
