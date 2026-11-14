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

        # head-food anchor: stem prefix match of usda head noun against ingredient
        head = usda.split(',')[0]
        htoks = [t for t in re.findall(r'[a-z]+', head) if t not in _STOP and len(t) > 2]
        itext = ing
        anchor = 0.0
        if htoks:
            hits = 0
            for t in htoks:
                stem = t[:max(4, len(t) - 2)]
                if stem in itext:
                    hits += 1
            anchor = hits / float(len(htoks))
        # state-word mismatches (symmetric difference of processing markers)
        marks = ['dried', 'frozen', 'canned', 'juice', 'powder', 'ground', 'sauce', 'oil',
                 'butter', 'milk', 'low', 'nonfat', 'fat', 'sweetened', 'pickled', 'sodium']
        mism = 0
        for w in marks:
            a = re.search(r'(?<![a-z])' + w, ing) is not None
            b = re.search(r'(?<![a-z])' + w, usda) is not None
            if a != b:
                mism += 1
        allt = [t for t in re.findall(r'[a-z]+', usda) if t not in _STOP and len(t) > 2]
        itoks = [t for t in re.findall(r'[a-z]+', ing) if t not in _STOP and len(t) > 2]
        ah = 0
        for t in itoks:
            st = t[:max(4, len(t) - 2)]
            if any(st in u for u in allt):
                ah += 1
        back = ah / float(len(itoks)) if itoks else 0.0
        anchor = 0.5 * anchor + 0.5 * back
        score = 0.45 * method + 5.5 * anchor - 0.6 * mism
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
