import re
import math

# approximate per-100g (kcal, protein, carb, fat) by food keyword
_MACROS = {
    'oil': (884, 0, 0, 100), 'shortening': (884, 0, 0, 100), 'lard': (900, 0, 0, 100),
    'butter': (717, 1, 0, 81), 'margarine': (717, 0, 1, 80), 'ghee': (900, 0, 0, 99),
    'sugar': (387, 0, 100, 0), 'sugars': (387, 0, 100, 0), 'honey': (304, 0, 82, 0),
    'syrup': (300, 0, 75, 0), 'molasses': (290, 0, 75, 0),
    'chicken': (190, 20, 0, 11), 'turkey': (170, 20, 0, 9), 'beef': (250, 20, 0, 18),
    'pork': (240, 19, 0, 18), 'lamb': (260, 18, 0, 20), 'veal': (170, 20, 0, 9),
    'sausage': (320, 14, 2, 28), 'bacon': (540, 37, 1, 42), 'ham': (150, 20, 1, 7),
    'liver': (140, 20, 4, 4), 'fish': (140, 22, 0, 5), 'salmon': (200, 20, 0, 13),
    'tuna': (130, 28, 0, 1), 'shrimp': (100, 20, 1, 1), 'egg': (150, 12, 1, 10),
    'eggs': (150, 12, 1, 10), 'tofu': (80, 8, 2, 5), 'bean': (130, 8, 23, 1),
    'beans': (130, 8, 23, 1), 'lentils': (115, 9, 20, 0), 'chickpeas': (160, 9, 27, 3),
    'milk': (60, 3, 5, 3), 'cream': (300, 2, 3, 30), 'yogurt': (70, 6, 6, 2),
    'cheese': (350, 22, 2, 28), 'cottage': (100, 11, 3, 4),
    'bread': (265, 9, 49, 3), 'rice': (130, 3, 28, 0), 'noodles': (140, 5, 28, 2),
    'pasta': (150, 5, 30, 1), 'flour': (360, 10, 76, 1), 'oats': (380, 13, 66, 7),
    'cereal': (370, 8, 80, 2), 'cracker': (430, 9, 70, 12), 'crackers': (430, 9, 70, 12),
    'cookie': (480, 5, 65, 22), 'cake': (350, 5, 55, 13), 'pie': (270, 3, 40, 12),
    'chocolate': (540, 6, 55, 32), 'cocoa': (230, 20, 58, 14),
    'peanut': (590, 26, 16, 50), 'almond': (580, 21, 22, 50), 'nuts': (600, 18, 20, 52),
    'pecan': (690, 9, 14, 72), 'walnut': (650, 15, 14, 65), 'seeds': (570, 20, 20, 48),
    'apple': (52, 0, 14, 0), 'apples': (52, 0, 14, 0), 'banana': (89, 1, 23, 0),
    'orange': (47, 1, 12, 0), 'berries': (45, 1, 11, 0), 'grapes': (69, 1, 18, 0),
    'fruit': (60, 1, 15, 0), 'juice': (45, 0, 11, 0), 'applesauce': (42, 0, 11, 0),
    'potato': (80, 2, 18, 0), 'potatoes': (80, 2, 18, 0), 'corn': (90, 3, 19, 1),
    'tomato': (20, 1, 4, 0), 'tomatoes': (20, 1, 4, 0), 'pepper': (25, 1, 6, 0),
    'peppers': (25, 1, 6, 0), 'onion': (40, 1, 9, 0), 'onions': (40, 1, 9, 0),
    'garlic': (150, 6, 33, 0), 'spinach': (23, 3, 4, 0), 'lettuce': (15, 1, 3, 0),
    'kale': (35, 3, 6, 1), 'cabbage': (25, 1, 6, 0), 'broccoli': (34, 3, 7, 0),
    'carrots': (41, 1, 10, 0), 'carrot': (41, 1, 10, 0), 'mushrooms': (22, 3, 3, 0),
    'chrysanthemum': (24, 3, 4, 0), 'vegetables': (30, 2, 6, 0), 'greens': (25, 2, 5, 0),
    'avocado': (160, 2, 9, 15), 'olives': (115, 1, 6, 11),
    'sauce': (70, 2, 12, 2), 'soup': (50, 3, 6, 2), 'broth': (10, 1, 1, 0),
    'dressing': (300, 1, 10, 28), 'mayonnaise': (680, 1, 1, 75), 'ketchup': (100, 1, 26, 0),
    'spices': (290, 12, 55, 6), 'spice': (290, 12, 55, 6), 'seasoning': (200, 8, 40, 3),
    'ginger': (80, 2, 18, 1), 'salt': (0, 0, 0, 0), 'vinegar': (20, 0, 1, 0),
    'water': (0, 0, 0, 0), 'wine': (85, 0, 3, 0), 'beer': (43, 0, 4, 0),
    'coffee': (2, 0, 0, 0), 'tea': (1, 0, 0, 0), 'candies': (390, 1, 90, 2),
}
_STATE = {
    'raw': 0, 'cooked': 1, 'fried': 2, 'roasted': 1, 'baked': 1, 'boiled': 1,
    'braised': 1, 'dried': 3, 'dehydrated': 3, 'canned': 1, 'frozen': 0,
}
_NOISE = set('of and or the a an with in for to from as ns fresh fluid raw whole style plain'.split())
_VARIANT = ['low', 'lowfat', 'reduced', 'nonfat', 'fat-free', 'free', 'sodium', 'sugar',
            'light', 'lite', 'diet', 'unsweetened', 'sweetened', 'smoked', 'vegetables',
            'pie', 'filling', 'cookie', 'cake', 'sulfured']


def _toks(s):
    s = re.sub(r'\([^)]*\)', ' ', s.lower())
    s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|oz|ml|lb|lbs|tbsp|tsp|cup|cups)?\b', ' ', s)
    return re.findall(r"[a-z][a-z\-']*", s)


def _vec(tokens, primary_first=False):
    found = []
    for i, t in enumerate(tokens):
        cands = [t, t[:-1] if t.endswith('s') else t, t[:-2] if t.endswith('es') else t]
        for c in cands:
            if c in _MACROS:
                found.append((i, _MACROS[c]))
                break
    if not found:
        return None
    # weight: earlier (primary) and later-in-phrase head noun items count more
    ws = []
    for k, (i, v) in enumerate(found):
        w = 1.0 / (1 + 0.5 * k)
        ws.append((w, v))
    tot = sum(w for w, _ in ws)
    return [sum(w * v[j] for w, v in ws) / tot for j in range(4)]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or '')
        usda = str(usda_match or '')
        if not ing.strip() or not usda.strip():
            return 0.0
        it = _toks(ing.split(',')[0])
        ut_all = _toks(usda)
        ut_primary = _toks(usda.split(',')[0])
        va = _vec(it)
        vb = _vec(ut_primary) or _vec(ut_all)
        # macro distance (normalised)
        if va is not None and vb is not None:
            d = (abs(va[0] - vb[0]) / 300.0 + abs(va[1] - vb[1]) / 15.0 +
                 abs(va[2] - vb[2]) / 30.0 + abs(va[3] - vb[3]) / 20.0) / 4.0
            macro = math.exp(-1.6 * d) * 3.0
        else:
            macro = 2.0
        # content overlap
        ci = set(t for t in it if t not in _NOISE and len(t) > 2)
        cu = set(t for t in ut_all if t not in _NOISE and len(t) > 2)
        stem = lambda w: w.rstrip('s')
        ci_s = set(map(stem, ci))
        cu_s = set(map(stem, cu))
        inter = len(ci_s & cu_s)
        recall = inter / float(len(ci_s)) if ci_s else 0.0
        macro += 5.0 * recall
        if ci_s and ci_s <= cu_s:
            macro += 1.0
        # extra qualifiers on USDA side that swing nutrition or identity
        extra = cu_s - ci_s
        swing = 0
        for w in _VARIANT:
            if stem(w) in extra:
                swing += 1
        macro -= 0.9 * swing
        # qualifiers in ingredient not reflected in USDA
        miss = 0
        for w in ('smoked', 'reduced', 'lowfat', 'low', 'nonfat', 'unsweetened', 'dried', 'sweetened'):
            if w in ci and w not in cu:
                miss += 1
        macro -= 0.7 * miss
        # cooking state mismatch
        si = set(_STATE[t] for t in it if t in _STATE)
        su = set(_STATE[t] for t in ut_all if t in _STATE)
        if si and su and not (si & su):
            macro -= 0.8
        # many extra descriptors (cut/grade) imply a specific product
        macro -= 0.12 * max(0, len(ut_all) - len(it) - 3)
        # primary food of USDA absent from ingredient
        if ut_primary and not (set(map(stem, ut_primary)) & ci_s):
            macro -= 1.0
        return max(0.0, min(10.0, macro))
    except Exception:
        return 0.0
