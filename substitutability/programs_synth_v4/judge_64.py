import re
import math
import unicodedata

# Variant 4: weighted "compositeness profile" per side, with a Gaussian
# agreement kernel over the profile difference, plus a role-aware check of
# WHERE the ingredient's head noun lands inside the USDA description
# (primary slot vs. buried inside a dish/mixture clause).

_DISH_NOUNS = {
    'salad': 1.0, 'soup': 1.0, 'casserole': 1.0, 'sandwich': 1.0, 'dinner': 1.0,
    'stew': 0.9, 'pie': 0.6, 'pizza': 1.0, 'burrito': 1.0, 'taco': 0.9,
    'lasagna': 1.0, 'entree': 1.0, 'meal': 0.9, 'chowder': 1.0, 'curry': 0.7,
    'stir': 0.6, 'fry': 0.3, 'pot': 0.4, 'quiche': 1.0, 'omelet': 0.8,
    'burger': 0.8, 'hash': 0.6, 'pilaf': 0.8, 'risotto': 0.8, 'chili': 0.6,
    'nuggets': 0.6, 'patty': 0.5, 'roll': 0.3, 'wrap': 0.6, 'dumpling': 0.5,
    'cocktail': 0.6, 'smoothie': 0.6, 'dessert': 0.6, 'pudding': 0.4,
    'gravy': 0.4, 'dip': 0.4, 'spread': 0.3, 'kit': 0.8, 'souffle': 0.9,
    'enchilada': 1.0, 'macaroni': 0.3, 'potpie': 1.0, 'frittata': 0.9,
    'sushi': 0.7, 'platter': 0.9, 'cobbler': 0.7, 'parmigiana': 1.0,
}
_MIX_WORDS = {
    'mix': 1.0, 'mixture': 1.0, 'blend': 0.9, 'blended': 0.7, 'prepared': 0.8,
    'stuffed': 1.0, 'filled': 0.8, 'breaded': 0.6, 'battered': 0.6,
    'combination': 0.9, 'assorted': 0.6, 'mixed': 0.8, 'medley': 0.9,
    'coated': 0.5, 'topped': 0.8, 'glazed': 0.3, 'flavored': 0.3,
    'recipe': 0.6, 'homemade': 0.4, 'frozen meal': 1.0, 'ready-to-eat': 0.4,
}
_CONNECTIVE_RE = [
    (re.compile(r'\bin\s+(?:\w+\s+)?(?:sauce|gravy|syrup|broth|oil|water|juice|brine)\b'), 1.0),
    (re.compile(r'\bwith\b'), 0.8),
    (re.compile(r'\band\b'), 0.6),
    (re.compile(r'&'), 0.6),
    (re.compile(r'\bmade with\b'), 0.9),
    (re.compile(r'\bplus\b'), 0.6),
    (re.compile(r'/'), 0.2),
]
# "with/and" uses that do NOT signal a mixture
_BENIGN_RE = re.compile(
    r'\b(?:without\s+\w+|with\s+salt|with\s+skin|with\s+bone|skin\s+and\s+bone|'
    r'meat\s+and\s+skin|lean\s+and\s+fat|separable\s+lean\s+and\s+fat|'
    r'half\s+and\s+half|salt\s+and\s+pepper|by-products|'
    r'(?:\w+\s+)?or\s+\w+)\b')
_PREP_STOP = {
    'g', 'kg', 'mg', 'ml', 'l', 'oz', 'lb', 'cup', 'cups', 'tbsp', 'tsp',
    'fresh', 'raw', 'chopped', 'diced', 'sliced', 'minced', 'cubed', 'melted',
    'crushed', 'thawed', 'frozen', 'sifted', 'grated', 'shredded', 'peeled',
    'large', 'small', 'medium', 'whole', 'finely', 'roughly', 'the', 'of', 'a',
    'an', 'to', 'for', 'into', 'pieces', 'piece', 'cut', 'plus', 'more', 'about',
    'optional', 'taste', 'softened', 'room', 'temperature', 'cold', 'warm',
    'hot', 'packed', 'divided', 'drained', 'rinsed', 'trimmed',
}


def _clean(text):
    t = str(text or '')
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode('ascii').lower()
    t = re.sub(r'\([^)]*\)', ' ', t)
    t = re.sub(r'^\s*[\d.,/]+\s*(?:g|kg|mg|ml|l|oz|lb)?\b', ' ', t)
    t = t.replace('’', "'")
    return re.sub(r'\s+', ' ', t).strip()


def _stem(w):
    w = w.strip("'")
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 5 and (w.endswith('ches') or w.endswith('shes') or w.endswith('xes')):
        return w[:-2]
    if len(w) > 4 and w.endswith('oes'):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _profile(text):
    """Return (dish_score, mix_score, connective_score) for a cleaned string."""
    t = _BENIGN_RE.sub(' ', text)
    words = [_stem(w) for w in re.findall(r"[a-z][a-z'\-]*", t)]
    dish = 0.0
    for w in words:
        dish = max(dish, _DISH_NOUNS.get(w, 0.0))
    mix = 0.0
    for k, v in _MIX_WORDS.items():
        if ' ' in k or '-' in k:
            if k in t:
                mix = max(mix, v)
        elif k in words:
            mix = max(mix, v)
    conn = 0.0
    for rx, wgt in _CONNECTIVE_RE:
        n = len(rx.findall(t))
        if n:
            conn += wgt * (1.0 - 0.5 ** n)
    conn = min(conn, 1.2)
    return dish, mix, conn


def _composite_index(p):
    d, m, c = p
    # noisy-OR combination keeps it in [0, 1)
    return 1.0 - (1.0 - 0.9 * d) * (1.0 - 0.85 * m) * (1.0 - 0.6 * min(c, 1.0))


def _head_tokens(ing):
    main = ing.split(',')[0]
    toks = [_stem(w) for w in re.findall(r"[a-z][a-z'\-]*", main)]
    toks = [w for w in toks if w not in _PREP_STOP and len(w) > 2]
    return toks


def _tok_hit(h, toks):
    for u in toks:
        if u == h:
            return 1.0
        if len(h) >= 4 and len(u) >= 4 and (u.startswith(h) or h.startswith(u)):
            return 0.8
    return 0.0


def _placement(head, usda_clean):
    """How the ingredient head lands in USDA text.
    Returns (in_primary, coverage, in_dish_clause)."""
    segs = [s.strip() for s in usda_clean.split(',') if s.strip()]
    if not segs or not head:
        return 0.0, 0.0, 0.0
    seg_toks = [[_stem(w) for w in re.findall(r"[a-z][a-z'\-]*", s)] for s in segs]
    n = float(len(head))
    lead = list(seg_toks[0])
    # primary may be a broad class ("Nuts", "Oil", "Sugars"); merge next segment
    if len(seg_toks) > 1 and len(seg_toks[0]) == 1:
        lead = lead + seg_toks[1]
    primary = sum(_tok_hit(h, lead) for h in head) / n
    all_toks = [w for st in seg_toks for w in st]
    coverage = sum(_tok_hit(h, all_toks) for h in head) / n
    dish_clause = 0.0
    start = 2 if (len(seg_toks) > 1 and len(seg_toks[0]) == 1) else 1
    for i in range(start, len(segs)):
        if re.search(r'\b(?:with|and|in|made|stuffed|filled|topped)\b', segs[i]):
            if not _BENIGN_RE.search(segs[i]):
                dish_clause = max(dish_clause, sum(_tok_hit(h, seg_toks[i]) for h in head) / n)
    m = re.search(r'\b(?:with|in|made with)\b(.*)', segs[0])
    if m:
        after = [_stem(w) for w in re.findall(r"[a-z][a-z'\-]*", m.group(1))]
        dish_clause = max(dish_clause, sum(_tok_hit(h, after) for h in head) / n)
    return primary, coverage, dish_clause


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        ci_ing = _composite_index(_profile(ing))
        ci_usda = _composite_index(_profile(usda))

        # Gaussian agreement kernel on compositeness: same kind -> ~1
        diff = ci_usda - ci_ing
        agree = math.exp(-(diff ** 2) / (2 * 0.22 ** 2))

        # Asymmetry: single ingredient -> dish is worse than dish -> single
        if diff > 0:
            asym = 1.0 - 0.35 * diff
        else:
            asym = 1.0 - 0.2 * (-diff)

        head = _head_tokens(ing)
        primary, coverage, dish_clause = _placement(head, usda)

        # Role component: ingredient as the primary food is good; ingredient
        # only appearing as a component of something else is bad.
        role = 0.15 + 0.45 * primary + 0.4 * coverage - 0.4 * dish_clause
        if ci_ing > 0.5 and primary > 0:
            role += 0.1  # dish-for-same-dish
        role = max(0.0, min(1.0, role))

        # Distinct head nouns in USDA primary segment (many foods named => mixture)
        first = usda.split(',')[0]
        parts = [p for p in re.split(r'\s*(?:\band\b|&|\bwith\b|/)\s*', first) if p.strip()]
        multi = max(0, len(parts) - 1)
        if _BENIGN_RE.search(first):
            multi = max(0, multi - 1)
        multi_pen = 1.0 / (1.0 + 0.25 * multi) if ci_ing < 0.4 else 1.0

        # compositeness agreement gates the score; role refines it
        score = 100.0 * agree * asym * (0.35 + 0.65 * role) * multi_pen
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
