import re
import math

# Preparation states grouped into "process tiers". Each tier describes how far
# the food has moved from its raw form. Distance between tiers drives penalty.
#   0 = raw / mechanical (trivially applied or ignored)
#   1 = mild physical (thawed, frozen, chilled) - trivial
#   2 = moist heat (boiled, steamed, poached, braised, stewed)
#   3 = dry heat (roasted, baked, grilled, toasted, broiled)
#   4 = fat heat (fried, sauteed)
#   5 = preservation (dried, dehydrated, canned, pickled, smoked, cured)
STATE_TIER = {
    'raw': 0, 'fresh': 0, 'uncooked': 0, 'chopped': 0, 'diced': 0, 'minced': 0,
    'sliced': 0, 'shredded': 0, 'grated': 0, 'cubed': 0, 'peeled': 0,
    'trimmed': 0, 'halved': 0, 'quartered': 0, 'crushed': 0, 'julienned': 0,
    'whole': 0, 'pitted': 0, 'seeded': 0, 'cut': 0, 'torn': 0, 'ground': 0,
    'thawed': 1, 'frozen': 1, 'chilled': 1, 'refrigerated': 1, 'defrosted': 1,
    'boiled': 2, 'steamed': 2, 'poached': 2, 'braised': 2, 'stewed': 2,
    'simmered': 2, 'blanched': 2, 'cooked': 2,
    'roasted': 3, 'baked': 3, 'grilled': 3, 'toasted': 3, 'broiled': 3,
    'charred': 3, 'barbecued': 3, 'microwaved': 3,
    'fried': 4, 'sauteed': 4, 'deep-fried': 4, 'pan-fried': 4, 'stir-fried': 4,
    'dried': 5, 'dehydrated': 5, 'canned': 5, 'pickled': 5, 'smoked': 5,
    'cured': 5, 'salted': 5, 'candied': 5, 'sun-dried': 5, 'freeze-dried': 5,
}

# Penalty for tier transitions (ingredient tier -> usda tier); symmetric-ish.
def _tier_cost(a, b):
    if a == b:
        return 0.0
    lo, hi = min(a, b), max(a, b)
    if hi <= 1:
        return 0.3          # raw vs thawed/frozen: trivial
    if lo == 2 and hi == 2:
        return 1.0
    if 2 <= lo and hi <= 4:
        return 3.0          # different cooking methods
    if hi == 5:
        return 5.0          # preserved vs not changes texture strongly
    return 4.0              # raw vs cooked/fried

FILLER = {
    'g', 'kg', 'mg', 'ml', 'l', 'oz', 'lb', 'cup', 'cups', 'tbsp', 'tsp', 'and',
    'or', 'of', 'the', 'a', 'an', 'with', 'from', 'for', 'to', 'in', 'only',
    'eaten', 'regular', 'nfs', 'ns', 'as', 'to', 'tube', 'about', 'large',
    'small', 'medium', 'piece', 'pieces', 'lean', 'plain', 'unprepared',
    'prepared', 'type', 'style', 'variety', 'meats', 'by-products', 'products',
    'commercial', 'all', 'without', 'skin', 'bone', 'boneless', 'skinless',
}

def _norm_word(w):
    w = w.lower().strip("-'")
    if w in STATE_TIER:
        return w
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and w.endswith('oes'):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w

def _parse(text):
    text = (text or '').lower()
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b', ' ', text)
    words = re.findall(r"[a-z][a-z\-']*", text)
    states, foods = [], []
    for w in words:
        n = _norm_word(w)
        if n in STATE_TIER:
            states.append(n)
        elif n.replace('-', '') in STATE_TIER:
            states.append(n.replace('-', ''))
        elif n not in FILLER and len(n) > 1:
            foods.append(n)
    return states, foods

def _trigrams(word):
    s = '#' + word + '#'
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}

def _soft_match(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))

def _food_alignment(ing_foods, usda_foods, usda_head):
    """Fraction of ingredient food words that find a counterpart in USDA,
    with extra weight for the USDA head noun being covered."""
    if not ing_foods or not usda_foods:
        return 0.0, 0.0
    total = 0.0
    for w in ing_foods:
        best = max(_soft_match(w, u) for u in usda_foods)
        total += best if best >= 0.6 else 0.0
    coverage = total / len(ing_foods)
    head_cov = 0.0
    if usda_head:
        head_cov = max(_soft_match(h, w) for h in usda_head for w in ing_foods)
        if head_cov < 0.6:
            head_cov = 0.0
    return coverage, head_cov

def _state_profile(states):
    tiers = [STATE_TIER[s] for s in states]
    # Effective tier = the most transformative state present
    return max(tiers) if tiers else 0

def judging_function(ingredient, usda_match):
    try:
        ingredient = ingredient if isinstance(ingredient, str) else str(ingredient or '')
        usda_match = usda_match if isinstance(usda_match, str) else str(usda_match or '')
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        ing_states, ing_foods = _parse(ingredient)
        usda_states, usda_foods = _parse(usda_match)

        # USDA head = food words in the first comma segment
        head_seg = usda_match.split(',')[0]
        _, usda_head = _parse(head_seg)

        coverage, head_cov = _food_alignment(ing_foods, usda_foods, usda_head)

        # Gate: if the foods themselves don't line up, state is irrelevant.
        identity = 0.6 * coverage + 0.4 * head_cov
        if identity < 0.25:
            return round(10.0 * identity, 3)

        # Preparation-state comparison
        ti = _state_profile(ing_states)
        tu = _state_profile(usda_states)
        cost = _tier_cost(ti, tu)

        # Specific transformative states mentioned on one side only
        transformative_i = {s for s in ing_states if STATE_TIER[s] >= 2}
        transformative_u = {s for s in usda_states if STATE_TIER[s] >= 2}
        unmatched = transformative_i ^ transformative_u
        # 'cooked' is generic: if both have some heat tier, forgive it
        if 'cooked' in unmatched and ti >= 2 and tu >= 2:
            unmatched.discard('cooked')
        cost += 0.6 * len(unmatched)

        # Shared transformative states are a strong positive signal
        shared = transformative_i & transformative_u
        bonus = 1.2 * len(shared)

        # Extra ingredient food words not explained by USDA (different item)
        extra_penalty = 0.0
        if ing_foods:
            unexplained = sum(1 for w in ing_foods
                              if max(_soft_match(w, u) for u in usda_foods) < 0.6)
            extra_penalty = 1.5 * unexplained / math.sqrt(len(ing_foods))

        state_score = 10.0 * math.exp(-cost / 3.0)
        score = 0.55 * state_score + 4.5 * identity + bonus - extra_penalty
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
