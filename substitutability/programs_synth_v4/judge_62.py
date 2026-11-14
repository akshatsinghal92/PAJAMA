import re
import math

# Variant 2: profile-vector approach. Each side is mapped to a small vector of
# "composite-ness" dimensions (connectors, dish nouns, multi-component lists,
# prepared/processing markers). The score combines the distance between the two
# profiles with an asymmetry penalty and an anchor check that the ingredient's
# core noun survives in the USDA primary segment.

_DISH_NOUNS = {
    'salad': 1.0, 'soup': 1.0, 'casserole': 1.0, 'sandwich': 1.0, 'stew': 0.9,
    'taco': 1.0, 'burrito': 1.0, 'pizza': 1.0, 'pie': 0.6, 'dinner': 1.0,
    'entree': 1.0, 'meal': 0.8, 'chili': 0.7, 'lasagna': 1.0, 'quiche': 1.0,
    'omelet': 0.9, 'omelette': 0.9, 'burger': 0.8, 'sushi': 0.9, 'roll': 0.4,
    'stir-fry': 0.9, 'stirfry': 0.9, 'curry': 0.6, 'pasta': 0.3, 'dish': 0.9,
    'platter': 0.9, 'kabob': 0.7, 'enchilada': 1.0, 'nachos': 1.0,
    'dressing': 0.4, 'gravy': 0.5, 'chowder': 1.0, 'bisque': 1.0, 'broth': 0.4,
    'pot': 0.3, 'potpie': 1.0, 'hash': 0.6, 'fried rice': 1.0, 'dumpling': 0.6,
}
_MIX_WORDS = {'mix': 1.0, 'mixture': 1.0, 'blend': 0.9, 'medley': 1.0,
              'combination': 0.9, 'assorted': 0.6, 'mixed': 0.7, 'variety pack': 0.8}
_PREP_WORDS = {'prepared': 1.0, 'stuffed': 1.0, 'breaded': 0.6, 'battered': 0.6,
               'frozen meal': 1.0, 'ready-to-eat': 0.5, 'ready-to-heat': 0.7,
               'from recipe': 0.8, 'restaurant': 0.6, 'fast food': 0.8,
               'homemade': 0.5, 'fat added': 0.6, 'with sauce': 1.0,
               'in sauce': 1.0, 'in gravy': 1.0, 'in oil': 0.4, 'filled': 0.8,
               'topped': 0.8, 'glazed': 0.4, 'creamed': 0.6, 'scalloped': 0.8,
               'au gratin': 0.9, 'marinated': 0.4}
_CONNECT = {'with': 1.0, 'and': 0.8, '&': 0.8, 'plus': 0.8, 'w/': 1.0}
_NEUTRAL_AND = re.compile(r'\b(salt and pepper|separable lean and fat|lean and fat|'
                          r'by-products|meats and|drained,? or|boiled,? drained|'
                          r'granulated or|or lump|cooked or|and/or)\b')
_STOP = {'g', 'kg', 'oz', 'lb', 'ml', 'cup', 'cups', 'tbsp', 'tsp', 'fresh',
         'frozen', 'raw', 'chopped', 'sliced', 'diced', 'minced', 'cubed',
         'shredded', 'grated', 'plain', 'boneless', 'skinless', 'whole', 'large',
         'small', 'medium', 'thawed', 'warmed', 'optional', 'for', 'serving',
         'garnish', 'the', 'a', 'of', 'to', 'soft', 'dried', 'ground', 'cooked',
         'nfs', 'ns', 'as', 'to', 'in', 'or', 'and', 'with'}


def _clean(text):
    t = str(text or '').lower()
    t = re.sub(r'\([^)]*\)', ' ', t)
    t = re.sub(r'^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|lbs|grams?)?\b', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _stem(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and w.endswith('oes'):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def _weighted_hits(text, lexicon):
    total = 0.0
    for phrase, w in lexicon.items():
        if ' ' in phrase or '-' in phrase or '/' in phrase or '&' in phrase:
            if phrase in text:
                total += w
        else:
            if re.search(r'\b' + re.escape(phrase) + r's?\b', text):
                total += w
    return total


def _profile(text, is_usda):
    """Return [connector, dish, mix, prep, listness] in [0,1]."""
    t = _NEUTRAL_AND.sub(' ', text)
    conn = 0.0
    for c, w in _CONNECT.items():
        if c in ('&', 'w/'):
            if c in t:
                conn += w
        elif re.search(r'\b' + c + r'\b', t):
            conn += w
    dish = _weighted_hits(t, _DISH_NOUNS)
    mix = _weighted_hits(t, _MIX_WORDS)
    prep = _weighted_hits(t, _PREP_WORDS)
    # listness: for USDA, many distinct food nouns before descriptors
    # e.g. "Taco, flour tortilla, beef, cheese" -> several food-ish segments
    listness = 0.0
    if is_usda:
        segs = [s.strip() for s in t.split(',') if s.strip()]
        foodish = 0
        for s in segs[1:]:
            if re.search(r'\b(beef|chicken|pork|cheese|bean|rice|tortilla|'
                         r'sauce|vegetable|egg|potato|noodle|turkey|ham|'
                         r'bacon|tomato|gravy|fish|shrimp)s?\b', s):
                foodish += 1
        listness = min(1.0, foodish / 2.0)
    vec = [min(1.0, conn), min(1.0, dish), min(1.0, mix), min(1.0, prep), listness]
    return vec


def _magnitude(vec):
    weights = [0.9, 1.3, 1.0, 0.8, 0.7]
    return sum(v * w for v, w in zip(vec, weights)) / sum(weights)


def _content_tokens(text):
    toks = re.findall(r"[a-z][a-z\-]+", text)
    return [_stem(w) for w in toks if w not in _STOP and len(w) > 2]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        # Ignore post-comma state on ingredient for profiling (e.g. ", thawed")
        ing_core = ing.split(',')[0].strip() or ing

        p_ing = _profile(ing_core, False)
        p_usda = _profile(usda, True)
        m_ing = _magnitude(p_ing)
        m_usda = _magnitude(p_usda)

        # Euclidean distance between profiles (normalized to [0,1])
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(p_ing, p_usda)) / len(p_ing))

        # Classification: composite if magnitude above threshold
        ing_comp = m_ing >= 0.15
        usda_comp = m_usda >= 0.15

        # Anchor: does the ingredient's core noun appear in USDA primary segments?
        ing_toks = _content_tokens(ing_core)
        usda_segs = [s.strip() for s in usda.split(',') if s.strip()]
        primary = set(_content_tokens(' '.join(usda_segs[:2]))) if usda_segs else set()
        all_usda = set(_content_tokens(usda))
        if ing_toks:
            head = ing_toks[-1]
            head_primary = 1.0 if head in primary else (0.5 if head in all_usda else 0.0)
            overlap = sum(1 for w in set(ing_toks) if w in all_usda) / float(len(set(ing_toks)))
        else:
            head_primary = 0.0
            overlap = 0.0

        score = 60.0
        # Profile similarity drives the main score
        score += 25.0 * (1.0 - min(1.0, dist * 2.0))

        if ing_comp and usda_comp:
            # dish vs dish: reward only if they look like the same dish
            score += 10.0 * overlap - 5.0
        elif not ing_comp and usda_comp:
            # single ingredient matched into a dish containing it
            penalty = 35.0 + 25.0 * m_usda
            # worse if the ingredient is only a side component (not primary)
            if head_primary < 1.0:
                penalty += 8.0
            score -= penalty
        elif ing_comp and not usda_comp:
            # composite ingredient matched to a single component
            score -= 30.0 + 25.0 * m_ing
        else:
            score += 8.0

        # Light anchor term so unrelated singles do not tie with matching singles
        score += 10.0 * head_primary + 6.0 * overlap - 6.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
