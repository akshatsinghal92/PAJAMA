import re
import math

_CLASSES = {
    'muscle': 'breast thigh wing drumstick leg loin shoulder shank rib belly brisket tenderloin sirloin steak chop roast fillet patty frankfurter sausage'.split(),
    'organ': 'liver kidney heart giblet tongue tripe gizzard brain'.split(),
    'egg': 'yolk white'.split(),
    'plantpart': 'leave leaf green root stem stalk seed kernel flower peel zest rind skin bud sprout shoot'.split(),
    'processed': 'oil juice flour meal powder paste extract sauce butter syrup starch'.split(),
}
_LOOKUP = {}
for _c, _ws in _CLASSES.items():
    for _w in _ws:
        _LOOKUP[_w] = _c
_STOP = set('a an the of and or with without in for to from raw cooked fresh frozen sliced chopped diced '
            'minced cubed thawed dried canned whole large small lean only nfs salt low fat reduced '
            'imported ready serve plain style optional garnish boiled baked fried roasted toasted'.split())


def _prep(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s+', '', s)
    return s


def _stem(w):
    if w.endswith('ies') and len(w) > 5:
        return w[:-3] + 'y'
    if w.endswith('es') and len(w) > 4 and w[-3] in 'sxzh':
        return w[:-2]
    if w.endswith('s') and not w.endswith('ss') and len(w) > 3:
        return w[:-1]
    return w


def _toks(s):
    return [_stem(w) for w in re.findall(r'[a-z]+', s)]


def _grams(w):
    w = '^' + w + '$'
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _soft(a, b):
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def judging_function(ingredient, usda_match):
    try:
        ing = _prep(ingredient)
        usd = _prep(usda_match)
        ing_main = ing.split(',')[0]
        it = [w for w in _toks(ing_main) if w not in _STOP]
        ut_all = [w for w in _toks(usd) if w not in _STOP]
        uhead = [w for w in _toks(re.sub(r'\bor\b.*', '', usd.split(',')[0])) if w not in _STOP]
        if not it or not ut_all:
            return 0.0

        # (a) soft alignment: each ingredient word finds its best USDA word (trigram Dice),
        # weighted by length so that main nouns count more than tiny words
        num = den = 0.0
        for w in it:
            best = max(_soft(w, u) for u in ut_all)
            wt = math.log(1 + len(w))
            num += wt * best
            den += wt
        align = num / den

        # (b) reverse alignment on USDA head words only
        if uhead:
            r = sum(max(_soft(u, w) for w in it + _toks(ing)) for u in uhead) / len(uhead)
        else:
            r = 0.5

        # (c) anatomical class agreement
        ic = {_LOOKUP[w] for w in _toks(ing_main) if w in _LOOKUP}
        uc = {_LOOKUP[w] for w in ut_all if w in _LOOKUP}
        iw = {w for w in _toks(ing_main) if w in _LOOKUP}
        uw = {w for w in ut_all if w in _LOOKUP}
        part = 0.0
        if iw:
            if iw & uw:
                part += 1.0
            elif uw:
                part -= 1.2 if (ic & uc) else 1.6
            else:
                part -= 0.3
        else:
            part -= 0.9 * len(uc - {'muscle'}) + 0.3 * len(uw & set(_CLASSES['muscle']))

        # (d) structure cues
        lead = usd.split(',')[0]
        mix = 0.0
        if re.search(r'\b(and|with|made|mix)\b', lead) and not re.search(r'\b(and|with|mix|made)\b', ing_main):
            mix -= 0.8
        if re.search(r'\b(mix|blend|and)\b', ing_main) and not re.search(r'\b(and|mix)\b', lead):
            mix -= 0.5

        score = 6.0 * align + 3.0 * r + 2.0 * part + mix
        # (e) exact word set bonus
        if set(it) == set(uhead):
            score += 1.5
        return round(score, 4)
    except Exception:
        return 0.0
