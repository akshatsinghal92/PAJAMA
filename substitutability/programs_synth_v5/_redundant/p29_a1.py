import re

ADDITIVES = {
    'salt': 2.0, 'salted': 2.0, 'sugar': 2.0, 'sweetened': 2.5, 'sugars': 1.5,
    'sauce': 2.5, 'breaded': 3.0, 'breading': 3.0, 'battered': 3.0, 'coated': 2.5,
    'seasoned': 2.5, 'seasoning': 2.0, 'flavored': 2.0, 'flavoured': 2.0,
    'glazed': 2.0, 'candied': 2.5, 'pickled': 2.0, 'marinated': 2.5,
    'canned': 1.0, 'syrup': 2.5, 'honey': 1.5, 'oil': 1.0, 'butter': 1.0,
    'cream': 1.0, 'cheese': 1.0, 'gravy': 2.5, 'mix': 2.0, 'blend': 2.0,
    'dressing': 1.5, 'spread': 1.5, 'pepper': 1.0, 'garlic': 0.8,
    'smoked': 1.0, 'cured': 1.5, 'fried': 1.0, 'prepared': 1.0,
    'enriched': 1.0, 'fortified': 1.0, 'chocolate': 2.0, 'vanilla': 1.0,
    'filled': 2.0, 'stuffed': 2.0, 'frosting': 2.0, 'jelly': 1.5,
}
PLAIN = {'plain', 'raw', 'unsweetened', 'unsalted', 'unprepared', 'unseasoned',
         'fresh', 'pure', 'natural', 'unenriched', 'nfs'}
STOP = {'and', 'or', 'with', 'in', 'of', 'the', 'a', 'to', 'for', 'from', 'style',
        'type', 'made', 'taste', 'g', 'fat', 'not', 'no', 'added', 'without'}
PREP = {'chopped', 'sliced', 'diced', 'minced', 'shredded', 'grated', 'fresh',
        'thawed', 'frozen', 'large', 'small', 'medium', 'fine', 'finely', 'cut',
        'trimmed', 'peeled', 'optional', 'taste', 'cooked', 'raw', 'whole', 'ground'}


def _tok(s):
    s = s.lower()
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b', ' ', s)
    return re.findall(r"[a-z]+", s)


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = _tok(str(ingredient or ''))
        usd = _tok(str(usda_match or ''))
        if not ing or not usd:
            return 0.0
        ing_s = {_stem(w) for w in ing}
        usd_s = [_stem(w) for w in usd]
        add_s = {_stem(k): v for k, v in ADDITIVES.items()}
        plain_s = {_stem(p) for p in PLAIN}
        stop_s = {_stem(p) for p in STOP}

        # Additive penalty: additives in USDA not in ingredient
        pen = 0.0
        for w in set(usd_s):
            if w in add_s and w not in ing_s:
                pen += add_s[w]
        # Additives in ingredient but missing from USDA (lost components)
        loss = 0.0
        for w in ing_s:
            if w in add_s and w not in set(usd_s):
                loss += add_s[w] * 0.8

        # Coverage of ingredient content words by USDA, and vice versa
        ic = [w for w in ing_s if w not in stop_s and w not in {_stem(p) for p in PREP}]
        uc = [w for w in set(usd_s) if w not in stop_s and w not in plain_s]
        cov_i = sum(1 for w in ic if w in set(usd_s)) / float(len(ic) or 1)
        # primary food (first USDA token) in ingredient?
        head = 1.0 if usd_s[0] in ing_s else 0.0
        extra = [w for w in uc if w not in ing_s]
        extra_ratio = len(extra) / float(len(uc) or 1)

        plain_bonus = 0.5 * sum(1 for w in set(usd_s) if w in plain_s)
        # compound ingredient (and/or) in recipe that USDA doesn't cover
        compound = 1.5 if (re.search(r'\band\b', str(ingredient).lower()) and cov_i < 1.0) else 0.0

        score = 4.0 * cov_i + 2.0 * head - 2.5 * extra_ratio - pen - loss \
            - compound + min(plain_bonus, 1.0) + 2.0
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
