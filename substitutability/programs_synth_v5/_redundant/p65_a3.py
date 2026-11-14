import re

_METHODS = {
    'raw': ['raw', 'fresh', 'uncooked', 'unprepared'],
    'boiled': ['boiled', 'boil', 'poached', 'simmered', 'stewed', 'blanched'],
    'steamed': ['steamed', 'steam'],
    'baked': ['baked', 'bake'],
    'roasted': ['roasted', 'roast', 'oven-roasted'],
    'grilled': ['grilled', 'grill', 'charbroiled', 'barbecued', 'bbq'],
    'fried': ['fried', 'fry', 'pan-fried', 'panfried', 'pan-broiled', 'stir-fried'],
    'deepfried': ['deep-fried', 'deep fried'],
    'sauteed': ['sauteed', 'sautéed', 'saute'],
    'broiled': ['broiled', 'broil'],
    'microwaved': ['microwaved', 'microwave'],
    'smoked': ['smoked'],
    'toasted': ['toasted', 'toast'],
    'cooked': ['cooked', 'cook', 'prepared'],
    'dried': ['dried', 'dehydrated', 'dry'],
    'frozen': ['frozen'],
    'canned': ['canned'],
}
_FAMILY = {
    'raw': 'raw', 'boiled': 'wet', 'steamed': 'wet', 'baked': 'dry', 'roasted': 'dry',
    'grilled': 'dry', 'fried': 'fat', 'deepfried': 'fat', 'sauteed': 'fat',
    'broiled': 'dry', 'microwaved': 'wet', 'smoked': 'smoke', 'toasted': 'toast',
    'cooked': 'any', 'dried': 'dried', 'frozen': 'raw', 'canned': 'wet',
}
_STOP = set('a an the and or of with without in for from to fresh into g kg ml oz lb cup cups tbsp tsp small large medium chopped sliced diced minced shredded grated cubed crumbled thawed cold hot warm whole raw cooked boiled baked roasted fried NFS regular type added no salt'.split())


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\s+', '', s)
    return s


def _methods(text):
    found = set()
    for k, words in _METHODS.items():
        for w in words:
            if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text):
                found.add(k)
                break
    return found


def _heads(text):
    text = re.sub(r'\(.*?\)', ' ', text)
    toks = re.findall(r'[a-z]+', text)
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
        ing = _clean(ingredient)
        usda = (usda_match or '').lower()
        im, um = _methods(ing), _methods(usda)
        ih = _heads(ing)
        parts = usda.split(',')
        uh_all = _heads(usda)
        uh_prim = _heads(parts[0])

        # Food identity (gate)
        def _m(a, bs):
            for b in bs:
                if a == b or (len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a))):
                    return True
            return False
        generic = set(['cheese', 'oil', 'bean', 'meat', 'sauce', 'milk', 'fruit', 'juice', 'bread', 'nut', 'seed', 'flour', 'sugar', 'spice', 'beef', 'pork', 'chicken', 'fish', 'cream', 'butter', 'rice', 'salad', 'soup', 'mix', 'pasta', 'leave', 'leaf'])
        def _w(t):
            return 0.35 if t in generic else 1.0
        tot = sum(_w(a) for a in ih)
        hit = sum(_w(a) for a in ih if _m(a, uh_all))
        cov = hit / tot if tot else 0.0
        ph = [t for t in uh_prim]
        ptot = sum(_w(t) for t in ph)
        phit = sum(_w(t) for t in ph if _m(t, ih))
        precision = phit / ptot if ptot else 0.0
        identity = (0.65 * cov + 0.35 * precision) ** 2

        # Cooking-method agreement
        # implicit method: unstated ingredient method is compatible with raw/generic
        if not im and not um:
            meth = 0.85
        elif not im:
            if um <= {'raw', 'frozen'}:
                meth = 1.0
            elif 'cooked' in um or um & {'boiled', 'steamed'}:
                meth = 0.6
            else:
                meth = 0.45
        elif not um:
            meth = 0.7
        else:
            if im & um:
                meth = 1.0
            else:
                fi = set(_FAMILY[m] for m in im)
                fu = set(_FAMILY[m] for m in um)
                if fi & fu:
                    meth = 0.75
                elif 'any' in fi or 'any' in fu:
                    meth = 0.65
                else:
                    meth = 0.2
                    if fi <= {'raw'} and fu & {'fat', 'dry', 'smoke', 'toast'}:
                        meth = 0.1
                if ('toasted' in um) != ('toasted' in im):
                    meth -= 0.15
                if ('dried' in um) != ('dried' in im):
                    meth -= 0.15
        if ('toasted' in im) != ('toasted' in um):
            meth -= 0.15
        if ('dried' in im) != ('dried' in um) and (im or um):
            meth -= 0.1
        meth = max(0.0, min(1.0, meth))

        return round(100.0 * identity * (0.35 + 0.65 * meth), 2)
    except Exception:
        return 0.0
