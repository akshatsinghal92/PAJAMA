import re

# Processing-profile dimensions: each dimension has trigger stems.
_DIMS = {
    'thermal':   ('cook', 'bake', 'roast', 'boil', 'broil', 'grill', 'fry', 'steam', 'toast', 'braise', 'stew', 'heat'),
    'preserved': ('frozen', 'canned', 'dried', 'dehydrat', 'pickle', 'cured', 'smoked', 'brine', 'jarred', 'powder'),
    'compound':  ('sauce', 'pie', 'filling', 'mix', 'entree', 'soup', 'dressing', 'dessert', 'cake', 'cookie',
                  'snack', 'chip', 'bar', 'stuff', 'dip', 'spread', 'paste', 'gravy', 'salad', 'sandwich', 'burrito'),
    'coating':   ('bread', 'batter', 'glaz', 'candi', 'coated', 'crumb', 'frost', 'icing'),
    'sweet':     ('sweeten', 'sugar', 'syrup', 'honey', 'flavor', 'chocolate', 'vanilla', 'caramel'),
    'salty':     ('salt', 'sodium', 'brine', 'season', 'spice', 'pepper', 'herb'),
    'fatty':     ('oil', 'butter', 'cream', 'lard', 'margarine', 'fat'),
    'refined':   ('flour', 'starch', 'juice', 'puree', 'extract', 'concentrate', 'enriched', 'instant', 'prepared', 'imitation'),
}
_NEG = ('without', 'unsalted', 'unsweetened', 'plain', 'raw', 'unroasted', 'unprepared', 'fresh')


def _clean(s):
    s = s.lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)?\b', ' ', s)
    return s


def _profile(text):
    prof = {}
    for d, stems in _DIMS.items():
        c = 0
        for st in stems:
            c += len(re.findall(r'\b' + st, text))
        prof[d] = min(c, 3)
    return prof


def _head(s):
    first = s.split(',')[0]
    w = re.findall(r'[a-z]+', first)
    w = [x[:-1] if len(x) > 3 and x.endswith('s') else x for x in w]
    return w


def judging_function(ingredient, usda_match):
    try:
        a = _clean(str(ingredient or ''))
        b = _clean(str(usda_match or ''))
        if not a.strip() or not b.strip():
            return 0.0
        # Split ingredient into main phrase and post-comma state
        a_main = a.split(',')[0]
        pa, pb = _profile(a), _profile(b)
        # Distance across processing profile; additions in USDA cost more than omissions
        dist = 0.0
        for d in _DIMS:
            diff = pb[d] - pa[d]
            if diff > 0:
                dist += 1.6 * diff
            else:
                dist += 0.6 * (-diff)
        # "without salt/sugar" is a reward for plain
        plain_hits = sum(1 for n in _NEG if re.search(r'\b' + n + r'\b', b))
        # Head-noun agreement
        ha, hb = _head(a_main), _head(b)
        hb_set = set(hb)
        a_words = [x[:-1] if len(x) > 3 and x.endswith('s') else x for x in re.findall(r'[a-z]+', a_main)]
        a_set = set(a_words)
        # last word of ingredient phrase is usually the food noun
        noun = a_words[-1] if a_words else ''
        noun_hit = 1.0 if noun and (noun in hb_set or noun in set(re.findall(r'[a-z]+', b))) else 0.0
        jacc = len(a_set & set(re.findall(r'[a-z]+', b))) / float(len(a_set) or 1)
        # number of comma-separated descriptor segments (more = more specified/processed)
        segs = len([x for x in b.split(',') if x.strip()])
        seg_pen = max(0, segs - 3) * 0.3
        # base: noun/overlap match
        base = 3.0 * noun_hit + 3.0 * jacc
        score = base - dist + 0.5 * min(plain_hits, 2) - seg_pen
        return float(score)
    except Exception:
        return 0.0
