import re

_SYN = {'cos': 'romaine', 'wrap': 'tortilla', 'frankfurters': 'frankfurter', 'fructose': 'fructose'}
_NOISE = {'and', 'or', 'of', 'the', 'a', 'with', 'in', 'from', 'to', 'for', 'g', 'kg', 'oz', 'ml', 'lb',
          'thawed', 'tube', 'raw', 'unprepared', 'nfs', 'shelled', 'fresh', 'chopped', 'sliced', 'diced'}
_PREP = {'frozen', 'dried', 'dry', 'cooked', 'canned', 'smoked', 'roasted', 'ground', 'lean', 'low', 'fat',
         'reduced', 'sweetened', 'unsweetened', 'salted', 'unsalted', 'sodium', 'powder', 'powdered',
         'pickled', 'fried', 'baked', 'boiled'}


def _stem(w):
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('es') and len(w) > 4 and w[-3] in 'sxzh':
        return w[:-2]
    if w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
        return w[:-1]
    return w


def _words(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s) if re.sub(r'\([^)]*\)', ' ', s).strip() else s
    s = re.sub(r'^\s*\d+(\.\d+)?\s*[a-z]{0,2}\b', ' ', s)
    s = re.sub(r'[^a-z,\s]', ' ', s)
    return s


def judging_function(ingredient, usda_match):
    try:
        iw = _words(ingredient)
        uw = _words(usda_match)
        # split usda into primary segment and descriptor segments
        segs = [x for x in uw.split(',') if x.strip()]
        if not segs or not iw.strip():
            return 0.0
        primary = [_SYN.get(w, _stem(w)) for w in segs[0].split() if w not in _NOISE]
        desc = []
        for sg in segs[1:]:
            desc += [_SYN.get(w, _stem(w)) for w in sg.split() if w not in _NOISE]
        itoks = [_SYN.get(w, _stem(w)) for w in re.split(r'[\s,]+', iw) if w and w not in _NOISE]
        if not itoks or not primary:
            return 0.0
        iset = set(itoks)
        pset = set(primary)
        dset = set(desc)
        allu = pset | dset

        # 1. How much of the ingredient is accounted for by the usda entry (weight later words more: head noun)
        n = len(itoks)
        wsum = 0.0
        hit = 0.0
        for k, t in enumerate(itoks):
            w = 1.0 + k / max(1, n - 1) if n > 1 else 2.0
            wsum += w
            if t in allu:
                hit += w
        accounted = hit / wsum

        # 2. Primary food of usda must be echoed by the ingredient
        prim_ok = len(pset & iset) / len(pset)

        # 3. Qualifier agreement: preparation words present on exactly one side
        pi = {t for t in iset if _stem(t) in {_stem(p) for p in _PREP}}
        pu = {t for t in allu if _stem(t) in {_stem(p) for p in _PREP}}
        mismatch = len(pi ^ pu)
        agree = len(pi & pu)

        # 4. Unexplained usda descriptors: details diner would see
        unexplained = len(dset - iset)

        # 5. Ingredient words missing from usda
        missing = len(iset - allu)

        score = 40 * accounted + 30 * prim_ok + 6 * agree
        score -= 9 * mismatch + 3 * min(unexplained, 5) + 7 * missing
        if not (iset & allu):
            score -= 15
        return float(score)
    except Exception:
        return 0.0
