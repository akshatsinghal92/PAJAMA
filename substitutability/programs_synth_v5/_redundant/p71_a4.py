import re

_FORM = {
    'ground', 'meal', 'flour', 'powder', 'oil', 'juice', 'paste', 'extract', 'sauce', 'butter',
    'kernels', 'seeds', 'seed', 'leaves', 'greens', 'peel', 'zest', 'yolk', 'white', 'skin',
    'liver', 'kidney', 'heart', 'giblets', 'tongue', 'breast', 'thigh', 'wing', 'drumstick',
    'shank', 'loin', 'rib', 'shoulder', 'belly', 'bone', 'root', 'stem', 'flower', 'fillet',
}
_SKIP = set('a an the of and or with without in for to from raw cooked fresh frozen sliced chopped '
            'diced minced cubed thawed dried canned whole large small lean only nfs salt'.split())


def _norm(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s+', '', s)
    return s


def _st(w):
    for suf in ('ies', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _words(s):
    return [_st(w) for w in re.findall(r'[a-z]+', s)]


_FORM = {_st(w) for w in _FORM} | {'leave', 'leaf', 'green', 'giblet'}


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        iparts = [p for p in ing.split(',')]
        uparts = [p for p in usd.split(',')]
        iw = _words(iparts[0])
        icore = [w for w in iw if w not in _SKIP]
        iall = set(_words(ing))
        uhead = [w for w in _words(uparts[0]) if w not in _SKIP]
        udesc = set()
        for p in uparts[1:]:
            udesc.update(w for w in _words(p) if w not in _SKIP)
        uall = set(uhead) | udesc
        if not icore or not uhead:
            return 0.0

        # stage 1: does the USDA head food denote what the ingredient names?
        # drop "or X" alternatives from head words
        head_text = re.sub(r'\bor\b.*', '', uparts[0])
        uhead2 = [w for w in _words(head_text) if w not in _SKIP] or uhead
        head_hit = sum(1 for w in uhead2 if w in iall)
        gate = 0.1 + 0.9 * (head_hit / float(len(uhead2)))
        if head_hit == 0 and any(w in udesc for w in icore):
            gate = 0.5  # category-first USDA naming, e.g. "Spices, ginger, ground"
        stray = [w for w in uhead2 if w not in iall]
        if head_hit:
            gate *= 0.85 ** len(stray)

        # stage 2: the ingredient's nouns must show up somewhere in USDA
        ing_missing = [w for w in icore if w not in uall]
        gate *= 0.6 ** len(ing_missing)

        # stage 3: form/part words appearing on only one side
        iform = {w for w in iall if w in _FORM}
        uform = {w for w in uall if w in _FORM}
        only_u = uform - iform
        only_i = iform - uform
        gate *= 0.55 ** len(only_u)
        gate *= 0.7 ** len(only_i)
        if iform & uform:
            gate *= 1.25

        # stage 4: order/head-final bonus: last core word of ingredient is the USDA first word
        if _st(icore[-1]) == uhead[0]:
            gate *= 1.2

        # stage 5: short exact-ish descriptions
        if set(icore) == set(uhead):
            gate *= 1.3

        return round(100.0 * min(gate, 1.5) / 1.5, 3)
    except Exception:
        return 0.0
