import re

FORMS = {
    'frozen': ['frozen', 'thawed', 'thaw'],
    'canned': ['canned', 'can', 'drained', 'tinned'],
    'dried': ['dried', 'dry', 'dehydrated', 'chips', 'raisins', 'jerky'],
    'cooked': ['cooked', 'baked', 'braised', 'roasted', 'fried', 'boiled', 'grilled',
               'broiled', 'steamed', 'pan-broiled', 'leftover', 'sauteed', 'toasted'],
    'raw': ['raw', 'fresh Uncooked'.lower()],
    'pickled': ['pickled', 'brined', 'smoked', 'cured', 'salted'],
    'powder': ['powder', 'powdered', 'ground', 'granulated', 'flour', 'meal'],
    'paste': ['paste', 'puree', 'concentrate'],
    'juice': ['juice'],
    'ready': ['ready-to-serve', 'ready-to-eat', 'condensed', 'prepared'],
}
# groups that change water/concentration/handling
STRONG = {'frozen': 1.0, 'canned': 2.0, 'dried': 3.0, 'cooked': 3.0, 'pickled': 3.0,
          'paste': 2.0, 'juice': 2.0, 'powder': 1.5, 'raw': 0.5, 'ready': 1.0}
ALT = {('frozen', 'raw'), ('raw', 'frozen')}


def _forms(text):
    toks = set(re.findall(r"[a-z\-]+", text.lower()))
    out = set()
    for f, words in FORMS.items():
        for w in words:
            if w in toks:
                out.add(f)
                break
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '').lower()
        usda = str(usda_match or '').lower()
        ing = re.sub(r"\(.*?\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        # ingredient "fresh" counts as raw
        fi = _forms(ing)
        if 'fresh' in ing.split() or 'fresh' in re.findall(r"[a-z]+", ing):
            fi.add('raw')
        fu = _forms(usda)
        if 'raw or frozen' in usda:
            fu = {'raw', 'frozen'}
        # in USDA 'ground' for meat is not powder; only count powder when spice-like
        if 'ground' in fu and False:
            pass
        score = 10.0
        # states stated on only one side
        for f in set(FORMS):
            a, b = f in fi, f in fu
            if a == b:
                continue
            w = STRONG.get(f, 1.0)
            if f == 'raw':
                # usda raw while ingredient silent is okay; ingredient fresh but usda not raw is bad
                if b and not a:
                    w = 0.3
                else:
                    w = 1.5
            if f == 'frozen' and (('raw' in fu) or ('raw' in fi)):
                w = 0.4
            if f == 'powder':
                w = 0.8 if (a and not b) or (b and not a) else w
            if f == 'cooked' and b and not a:
                w = 3.5   # USDA cooked but ingredient not stated cooked
            if f == 'ready':
                w = 0.5
            score -= w
        # matching forms get a small bonus
        shared = fi & fu
        score += 0.7 * len(shared - {'raw'})
        # product-name overlap: primary food noun must agree
        stop = set(FORMS_ALL) if False else set()
        it = set(re.findall(r"[a-z]{3,}", ing))
        ut = re.findall(r"[a-z]{3,}", usda.split(',')[0])
        ut_all = set(re.findall(r"[a-z]{3,}", usda))
        content = [w for w in ut if w not in ('and', 'the', 'nfs')]
        if content:
            hit = sum(1 for w in content if w in it or w.rstrip('s') in it or w + 's' in it)
            if hit == 0:
                # check any usda word in ingredient
                if not (ut_all & it):
                    score -= 6.0
                else:
                    score -= 2.5
        # extra descriptors in USDA that ingredient does not mention
        extra = len([w for w in ut_all if w not in it and w in ('lowfat', 'nonfat', 'low', 'sodium', 'pickled', 'additives', 'trimmed', 'separable')])
        score -= 0.6 * extra
        return max(0.0, min(15.0, score))
    except Exception:
        return 0.0
