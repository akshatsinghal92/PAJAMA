import re

_NOTICEABLE = {
    'smoked', 'cured', 'fried', 'baked', 'roasted', 'boiled', 'canned', 'frozen', 'dried', 'dehydrated',
    'sweetened', 'unsweetened', 'salted', 'unsalted', 'sodium', 'fat', 'fatfree', 'lowfat', 'reduced',
    'flavored', 'pickled', 'processed', 'pasteurized', 'vegetables', 'vegetable', 'sauce', 'cream',
    'creamed', 'breaded', 'stuffed', 'instant', 'powder', 'powdered', 'juice', 'concentrate', 'chocolate',
    'vanilla', 'sugar', 'imitation', 'substitute', 'whole', 'skim', 'nonfat', 'organic', 'decaffeinated',
    'toasted', 'grilled', 'braised', 'stewed', 'cooked', 'raw', 'fresh', 'ground', 'whipped', 'sliced',
    'diced', 'hawaii', 'mountain', 'wild', 'sprouted', 'pickle', 'brined', 'seasoned', 'spiced',
}
_NEUTRAL = {'raw', 'without', 'salt', 'imported', 'new', 'zealand', 'all', 'varieties', 'variety', 'ns', 'as',
            'to', 'major', 'flour', 'separable', 'by', 'products', 'and', 'or', 'with', 'of', 'the', 'a', 'in',
            'type', 'commercially', 'prepared', 'usda', 'nfs', 'mature', 'seeds', 'meat', 'only', 'domesticated'}
_PREP = {'sliced', 'diced', 'chopped', 'minced', 'cubed', 'shredded', 'grated', 'crushed', 'peeled', 'thawed',
         'optional', 'serving', 'taste', 'divided', 'packed', 'drained', 'rinsed', 'trimmed', 'halved', 'cut',
         'large', 'small', 'medium', 'fine', 'finely', 'coarsely', 'leftover', 'extra', 'good', 'quality',
         'for', 'garnish', 'room', 'temperature', 'softened', 'melted', 'cold', 'warm', 'hot', 'about', 'plus'}
_ORGAN = {'liver', 'livers', 'kidney', 'kidneys', 'heart', 'tongue', 'neck', 'giblets', 'gizzard', 'gizzards',
          'seeds', 'seed', 'leaves', 'leaf', 'skin', 'shank', 'leg', 'wing', 'wings', 'thigh', 'breast', 'chop'}


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _tok(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0
        brand = bool(re.match(r"^[A-Z][A-Z\s'&]{3,}[,\s]", usda))
        ing_c = re.sub(r"\([^)]*\)", " ", ing)
        ing_c = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing_c)
        ing_main = ing_c.split(',')[0]
        ing_post = ' '.join(ing_c.split(',')[1:])
        ing_t = [t for t in _tok(ing_main) if t not in {_stem(p) for p in _PREP}]
        post_t = set(_tok(ing_post))
        segs = [s.strip() for s in usda.split(',') if s.strip()]
        primary = _tok(segs[0]) if segs else []
        usda_all = _tok(usda)
        usda_set = set(usda_all)
        if not ing_t:
            return 0.0
        neutral = {_stem(n) for n in _NEUTRAL}
        noticeable = {_stem(n) for n in _NOTICEABLE}
        organ = {_stem(n) for n in _ORGAN}
        ing_set = set(ing_t)

        # 1. head noun: last ingredient content word must appear in the USDA text
        head = ing_t[-1]
        head_hit = 1.0 if head in usda_set else 0.0
        primary_hit = 1.0 if (ing_set & set(primary)) else 0.0
        cover = sum(1 for t in ing_set if t in usda_set) / float(len(ing_set))
        score = 40.0 * cover + 15.0 * head_hit + 10.0 * primary_hit

        # 2. qualifiers the ingredient states but USDA drops
        ing_q = {t for t in ing_set if t in noticeable or t in organ}
        dropped = [t for t in ing_q if t not in usda_set]
        score -= 12.0 * len(dropped)
        kept = [t for t in ing_q if t in usda_set]
        score += 6.0 * len(kept)

        # 3. qualifiers USDA adds that ingredient did not imply
        extra = [t for t in usda_set if t in noticeable and t not in ing_set and t not in post_t]
        extra += [t for t in usda_set if t in organ and t not in ing_set]
        # raw/cooked defaults are mild
        mild = {_stem('raw'), _stem('fresh'), _stem('whole'), _stem('cooked'), _stem('ground')}
        pen = 0.0
        for t in set(extra):
            pen += 3.0 if t in mild else 9.0
        score -= pen

        # 4. unmatched primary-food words (USDA names a different food)
        foreign = [t for t in primary if t not in ing_set and t not in neutral and t not in noticeable
                   and len(t) > 2]
        score -= 6.0 * len(foreign)

        # 5. generality: specificity gap measured by descriptor count
        n_desc = max(0, len(segs) - 1)
        ing_spec = len(ing_set)
        if ing_spec <= 2:
            score -= 2.0 * max(0, n_desc - 2)
        if brand:
            score -= 25.0
        if head_hit == 0 and primary_hit == 0:
            score -= 20.0
        return float(score)
    except Exception:
        return 0.0
