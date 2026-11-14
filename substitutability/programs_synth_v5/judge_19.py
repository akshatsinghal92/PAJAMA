import re

_VARIANT = {
    'low', 'lowfat', 'reduced', 'nonfat', 'fat-free', 'diet', 'light', 'lite', 'decaffeinated',
    'sweetened', 'unsweetened', 'salted', 'unsalted', 'smoked', 'dried', 'dehydrated', 'frozen',
    'canned', 'cooked', 'raw', 'boiled', 'roasted', 'fried', 'baked', 'extra', 'virgin',
    'organic', 'whole', 'skim', 'lean', 'fat', 'imitation', 'substitute', 'flavored', 'instant',
    'powder', 'powdered', 'ground', 'sliced', 'diced', 'chopped', 'juice', 'oil', 'paste',
    'sauce', 'mix', 'dressing', 'soup', 'patty', 'stew', 'bread', 'cake', 'cookie', 'cookies',
    'pickled', 'fermented', 'sprouted', 'enriched', 'fortified', 'hot', 'cold', 'pasteurized',
    'condensed', 'evaporated', 'cured', 'seasoned', 'breaded', 'stuffed', 'candied', 'glazed',
    'steak', 'roast', 'chop', 'chops', 'ribs', 'liver', 'heart', 'neck', 'gizzard', 'skin',
    'bone', 'bones', 'mayonnaise', 'butter', 'spread', 'cream', 'milk', 'flour', 'starch', 'syrup',
}
_STOP = {'and', 'or', 'with', 'without', 'of', 'the', 'a', 'in', 'from', 'for', 'to', 'made',
         'type', 'only', 'solids', 'drained', 'salt', 'added', 'contains', 'fresh', 'thawed',
         'cubed', 'peeled', 'minced', 'finely', 'large', 'small', 'medium', 'g', 'kg', 'oz'}
_FORM = {'raw', 'cooked', 'boiled', 'canned', 'frozen', 'dried', 'drained', 'roasted', 'baked', 'fried'}


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _toks(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '').lower()
        usda = str(usda_match or '').lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r'\([^)]*\)', ' ', ing)
        usda = re.sub(r'\([^)]*\)', ' ', usda)
        ing = re.sub(r'^\s*[\d.,/]+\s*(g|kg|mg|oz|lb|ml|l)?\b', ' ', ing)
        itok = [t for t in _toks(ing) if t not in _STOP]
        parts = [p for p in usda.split(',')]
        head = [t for t in _toks(parts[0]) if t not in _STOP]
        desc = [t for p in parts[1:] for t in _toks(p) if t not in _STOP]
        utok = head + desc
        if not itok or not utok:
            return 0.0
        iset, uset = set(itok), set(utok)
        stop_s = {_stem(w) for w in _STOP}
        vs = {_stem(w) for w in _VARIANT}
        fs = {_stem(w) for w in _FORM}

        # 1. content coverage of ingredient words by USDA words
        cover = len(iset & uset) / float(len(iset))
        # 2. head noun: last ingredient noun-ish word appears in USDA head
        key = itok[-1]
        head_hit = 1.0 if key in set(head) else (0.5 if key in uset else 0.0)
        # 3. qualifiers USDA adds that ingredient did not imply (unforced extras)
        extra = [t for t in uset - iset if t in vs and t not in fs]
        extra_form = [t for t in uset - iset if t in fs]
        # 4. qualifiers ingredient states but USDA drops
        dropped = [t for t in iset - uset if t in vs]
        # specificity: generic usda for unqualified ingredient
        ing_q = [t for t in iset if t in vs]
        specificity = 0.0
        if not ing_q:
            specificity = -0.9 * len(extra) - 0.2 * len(extra_form)
        else:
            specificity = -0.5 * len(extra) - 0.2 * len(extra_form)
        specificity -= 0.8 * len(dropped)
        # length mismatch of the head vs ingredient
        ratio = min(len(itok), len(head)) / float(max(len(itok), len(head)))
        # unmatched ingredient words (non-variant) also hurt
        miss = [t for t in iset - uset if t not in vs]
        score = 5.0 * cover + 3.0 * head_hit + 1.0 * ratio + specificity - 0.5 * len(miss)
        return float(score)
    except Exception:
        return 0.0
