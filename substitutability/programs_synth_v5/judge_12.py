import re

FORMS = {
    'fresh': ['fresh', 'raw', 'leaves', 'whole'],
    'frozen': ['frozen', 'thawed', 'thaw'],
    'canned': ['canned', 'can', 'tinned', 'drained', 'solids and liquids'],
    'dried': ['dried', 'dry', 'dehydrated', 'mature seeds', 'freeze-dried'],
    'ground': ['ground', 'powder', 'powdered', 'granulated', 'flour', 'starch'],
    'paste': ['paste', 'puree', 'concentrate', 'tube'],
    'juice': ['juice', 'nectar', 'drink', 'beverage'],
    'sauce': ['sauce', 'dressing', 'gravy', 'soup', 'broth', 'stock'],
    'cooked': ['cooked', 'boiled', 'simmered', 'baked', 'roasted', 'fried', 'pan-fried', 'grilled', 'steamed', 'braised', 'stewed'],
    'processed': ['chips', 'cookies', 'cookie', 'cake', 'bar', 'patty', 'nuggets', 'sandwich', 'snack', 'candy', 'cereal', 'pie', 'bread', 'breaded', 'imitation', 'substitute'],
    'pickled': ['pickled', 'pickles', 'jarred', 'brined', 'marinated'],
}
# pairs of forms that are mutually recoverable (small penalty)
NEAR = {('fresh', 'cooked'), ('frozen', 'fresh'), ('dried', 'ground'), ('canned', 'cooked'), ('frozen', 'cooked'), ('fresh', 'dried')}
STOP = set('a an the of and or with in for to from as ns nfs nonfat lowfat low fat reduced regular plain style type brand choice select not no added'.split())
SHARED_MODS = set(['fresh', 'raw', 'frozen', 'dried', 'canned', 'cooked', 'ground'])


def _clean(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|lbs)\b', ' ', s)
    return s


def _forms(text):
    found = set()
    for k, ws in FORMS.items():
        for w in ws:
            if re.search(r'\b' + re.escape(w) + r'\b', text):
                found.add(k)
                break
    return found


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _content(text):
    toks = re.findall(r'[a-z]+', text)
    allform = set(w for ws in FORMS.values() for w in ws)
    return set(_stem(t) for t in toks if t not in STOP and t not in allform and len(t) > 2)


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        # core identity: head segment of usda vs ingredient text
        head = usda.split(',')[0]
        ic = _content(ing)
        uc_all = _content(usda)
        hc = _content(head)
        if not ic or not uc_all:
            return 0.5
        cov = len(ic & uc_all) / float(len(ic))        # how much of ingredient is found
        prec = len(ic & uc_all) / float(len(uc_all))   # how much of usda is explained
        headhit = 1.0 if (hc & ic) else 0.0
        identity = 0.5 * cov + 0.2 * prec + 0.3 * headhit
        if not (ic & uc_all):
            identity = 0.0

        fi = _forms(ing)
        fu = _forms(usda)
        # form agreement
        score_form = 0.0
        if not fi and not fu:
            score_form = 0.7
        else:
            common = fi & fu
            only_i = fi - fu
            only_u = fu - fi
            score_form = 0.55 + 0.25 * len(common)
            for a in only_i:
                for b in only_u:
                    if (a, b) in NEAR or (b, a) in NEAR:
                        score_form += 0.05
            # implicit: no form stated in ingredient => assume fresh/raw is fine
            if not fi and fu <= set(['fresh', 'cooked']):
                score_form += 0.1
            for b in only_u:
                if b in ('processed', 'sauce', 'juice', 'paste', 'pickled', 'canned'):
                    score_form -= 0.3
                elif b in ('frozen', 'dried', 'ground', 'cooked') and fi:
                    score_form -= 0.15
            for a in only_i:
                if a in ('paste', 'ground', 'dried', 'juice', 'sauce', 'cooked'):
                    score_form -= 0.15
            score_form = max(0.0, min(1.0, score_form))

        # extra penalty for processed-food words only in usda (e.g. cookies, chips)
        if 'processed' in fu and 'processed' not in fi:
            identity *= 0.5

        total = 10.0 * identity * (0.4 + 0.6 * score_form)
        return float(max(0.0, min(10.0, total)))
    except Exception:
        return 0.0
