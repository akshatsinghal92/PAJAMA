import re

_PARTS = {
    'breast': 'breast', 'thigh': 'thigh', 'wing': 'wing', 'drumstick': 'drumstick', 'leg': 'leg',
    'loin': 'loin', 'shoulder': 'shoulder', 'shank': 'shank', 'rib': 'rib', 'ribs': 'rib',
    'belly': 'belly', 'tenderloin': 'loin', 'sirloin': 'loin', 'brisket': 'brisket',
    'liver': 'organ', 'kidney': 'organ', 'heart': 'organ', 'giblets': 'organ', 'tongue': 'organ',
    'tripe': 'organ', 'gizzard': 'organ', 'yolk': 'yolk', 'yolks': 'yolk', 'white': 'white',
    'whites': 'white', 'leaves': 'leaf', 'leaf': 'leaf', 'greens': 'leaf', 'root': 'root',
    'stem': 'stem', 'stalk': 'stem', 'stalks': 'stem', 'seed': 'seed', 'seeds': 'seed',
    'kernels': 'seed', 'kernel': 'seed', 'flower': 'flower', 'flowers': 'flower',
    'peel': 'peel', 'zest': 'peel', 'skin': 'skin', 'rind': 'peel', 'flesh': 'flesh',
    'fillet': 'fillet', 'fillets': 'fillet', 'ground': 'ground', 'bone': 'bone', 'bones': 'bone',
    'neck': 'neck', 'tail': 'tail', 'feet': 'feet', 'head': 'head', 'oil': 'oil', 'juice': 'juice',
    'flour': 'flour', 'meal': 'flour', 'butter': 'butter', 'milk': 'milk',
}
_NOISE = set('fresh frozen raw cooked boiled drained without with salt sliced chopped diced minced '
             'cubed thawed dried canned whole large small medium lean only the of and or in for a an '
             'to from nfs imported separable fat low nonfat reduced style plain ready serve '
             'toasted baked fried roasted pan simmered stewed grilled ground optional garnish'.split())


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b', ' ', s)
    return s


def _stem(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('es') and w[-3] in 'sxz':
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _tags(s):
    out = set()
    for w in re.findall(r'[a-z]+', s):
        if w in _PARTS:
            out.add(_PARTS[w])
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        ing_pre = ing.split(',')[0]
        usd_toks = re.findall(r'[a-z]+', usd)
        ing_toks = re.findall(r'[a-z]+', ing_pre)
        if not ing_toks or not usd_toks:
            return 0.0
        score = 5.0

        # part tags
        ti = _tags(ing_pre)
        tu = _tags(usd)
        if ti:
            if ti & tu:
                score += 2.5
            elif tu:
                score -= 3.0
            else:
                score -= 1.0
        else:
            # unspecified part in ingredient: fine unless usda picks a special part
            special = tu & {'organ', 'yolk', 'white', 'peel', 'skin', 'bone', 'seed', 'leaf', 'root', 'flower', 'stem', 'oil', 'flour', 'juice', 'butter'}
            if special:
                score -= 1.5 * len(special)
        if ti and tu and (ti - tu) and (tu - ti):
            score -= 1.0

        # primary food head match (first usda token vs ingredient content words)
        ing_c = [_stem(w) for w in ing_toks if w not in _NOISE]
        usd_c = [_stem(w) for w in usd_toks if w not in _NOISE]
        usd_first = [_stem(w) for w in re.findall(r'[a-z]+', usd.split(',')[0]) if w not in _NOISE]
        if ing_c and usd_c:
            si, su = set(ing_c), set(usd_c)
            cover = len(si & su) / float(len(si))
            back = len(si & su) / float(len(su))
            score += 4.0 * cover + 2.0 * back
            if ing_c[-1] in usd_first:
                score += 1.5
            elif ing_c[-1] not in su:
                score -= 2.0
            # words in usda primary food that are absent from the ingredient
            extra = [w for w in usd_first if w not in si]
            score -= 0.8 * len(extra)
            # unmatched ingredient words that are modifiers
            miss = [w for w in ing_c if w not in su]
            score -= 0.5 * len(miss)

        # mixture/prepared-dish mismatch
        if re.search(r'\b(and|with|mix|made)\b', usd.split(',')[0]) and not re.search(r'\b(and|with|mix|made)\b', ing_pre):
            score -= 1.5
        if re.search(r'\bbeans?\b', usd) and not re.search(r'\bbeans?\b', ing_pre):
            score -= 1.5
        return max(-10.0, min(15.0, score))
    except Exception:
        return 0.0
