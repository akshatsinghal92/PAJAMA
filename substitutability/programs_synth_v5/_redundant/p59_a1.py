import re

_VARIANT = {
    'vanilla', 'chocolate', 'strawberry', 'flavored', 'flavoured', 'coconut', 'almond',
    'soy', 'oat', 'rice', 'plant', 'vegan', 'imitation', 'substitute', 'artificial',
    'powdered', 'powder', 'dried', 'dehydrated', 'butter', 'oil', 'milk', 'cream',
    'seeds', 'seed', 'juice', 'flour', 'paste', 'syrup', 'extract', 'chips', 'sauce',
    'balsamic', 'smoked', 'canned', 'frozen', 'raw', 'cooked', 'low', 'fat', 'nonfat',
    'sweetened', 'unsweetened', 'diet', 'sugar', 'free', 'ground', 'whole'
}
_STOP = {'and', 'or', 'of', 'the', 'a', 'with', 'for', 'in', 'from', 'to', 'nfs', 'ns',
         'g', 'raw', 'fresh', 'cold', 'warm', 'warmed', 'ripe', 'cubed', 'sliced',
         'chopped', 'diced', 'thawed', 'drained', 'serving', 'tube', 'by', 'type',
         'cooked', 'frozen', 'canned', 'dried'}
_BRANDWORDS = {'tm', 'brand', 'inc', 'co', 'company', 'restaurant', 'fast', 'foods',
               'kraft', 'nestle', 'kellogg', 'campbell', 'mcdonald', 'burger', 'king',
               'wendy', 'pizza', 'hut', 'subway', 'starbucks', 'oreo', 'heinz', 'hershey'}


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _clean_ing(s):
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = s.split(',')[0] if ',' in s else s
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b', ' ', s.lower())
    return s


def _toks(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or '')
        usda_raw = str(usda_match or '')
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        # brand detection on the USDA side: all-caps tokens, parenthetical, trailing segment
        caps = re.findall(r"\b[A-Z][A-Z'!&\.]{2,}\b", usda_raw)
        usda_parts = [p.strip() for p in usda_raw.split(',')]
        brand_marks = len(caps)
        if re.search(r"\([^)]*\)", usda_raw):
            brand_marks += 0.5
        for p in usda_parts[1:]:
            if re.search(r"\b(brand|inc|co)\b", p.lower()):
                brand_marks += 1
        ub = [w for w in _toks(usda_raw) if w in _BRANDWORDS]
        brand_marks += 0.5 * len(ub)

        ing_clean = _clean_ing(ing_raw)
        ing_t = [w for w in _toks(ing_clean) if w not in {'g', 'kg', 'oz', 'ml'}]
        ing_core = set(w for w in ing_t if w not in _STOP)

        # usda tokens without the all-caps brand segment
        usda_nobrand = re.sub(r"\b[A-Z][A-Z'!&\. ]{2,}\b", ' ', usda_raw)
        usda_t = _toks(usda_nobrand)
        usda_core = set(w for w in usda_t if w not in _STOP)
        head = set(_toks(usda_parts[0]))

        if not ing_core or not usda_core:
            return 0.0

        # weighted coverage: ingredient words found in usda
        inter = ing_core & usda_core
        cover = len(inter) / len(ing_core)
        # head noun of the ingredient (last token) must appear in usda
        last = ing_t[-1] if ing_t else ''
        head_hit = 1.0 if last in usda_core or last in head else 0.0
        # first usda token should be in ingredient (primary food)
        prim = [w for w in _toks(usda_parts[0]) if w not in _STOP]
        prim_hit = 1.0 if any(w in ing_core for w in prim) else 0.0

        # variant mismatch: variant words on only one side
        ing_var = ing_core & _VARIANT
        usda_var = usda_core & _VARIANT
        # words that matter if present in one side and not the other
        sym = (ing_var ^ usda_var)
        mismatch = len(sym - {'raw', 'cooked', 'frozen', 'canned', 'whole', 'ground'})

        # brand penalty only when brand-carrying entry introduces non-matching variant words
        extra = usda_core - ing_core
        extra_var = extra & _VARIANT
        brand_pen = 0.0
        if brand_marks > 0:
            brand_pen = 0.4 * len(extra_var) + (0.3 if cover < 0.6 else 0.0)
        # standard-example bonus: branded entry that fully covers the ingredient
        brand_bonus = 0.8 if (brand_marks > 0 and cover >= 0.99 and not extra_var) else 0.0

        score = 4.0 * cover + 2.5 * head_hit + 1.5 * prim_hit
        score -= 1.6 * mismatch
        score -= brand_pen
        score += brand_bonus
        # mild penalty for very long unrelated usda descriptions
        score -= 0.05 * max(0, len(usda_core) - len(ing_core) - 4)
        return round(score, 3)
    except Exception:
        return 0.0
