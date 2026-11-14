import re

FORMS = {
    'oil': {'oil', 'butter', 'lard', 'shortening', 'tallow', 'ghee'},
    'liquid': {'juice', 'milk', 'broth', 'stock', 'water', 'beverage', 'drink', 'nectar', 'wine', 'vinegar'},
    'sauce': {'sauce', 'paste', 'puree', 'pate', 'spread', 'dressing', 'gravy', 'salsa', 'ketchup'},
    'dairy': {'cheese', 'yogurt', 'kefir', 'cream', 'curd'},
    'meat': {'chicken', 'beef', 'pork', 'turkey', 'lamb', 'ham', 'sausage', 'bacon', 'duck', 'veal', 'fish', 'liver', 'giblets', 'tongue', 'steak'},
    'grain': {'flour', 'rice', 'pasta', 'bread', 'tortilla', 'cereal', 'cereals', 'oat', 'oats', 'noodles', 'wheat'},
    'fruitveg': {'fruit', 'berries', 'grapes', 'apple', 'plum', 'pea', 'beans', 'bean', 'tomato', 'onion', 'garlic', 'pepper'},
    'nut': {'nuts', 'nut', 'peanuts', 'almonds', 'hazelnut', 'walnuts', 'seeds', 'seed'},
    'dish': {'souffle', 'soup', 'pie', 'casserole', 'salad', 'cake', 'cookie', 'patty'},
}
STATE_MOD = {
    'canned': 'canned', 'frozen': 'frozen', 'dried': 'dry', 'dry': 'dry', 'powder': 'dry',
    'cooked': 'cooked', 'roasted': 'cooked', 'fried': 'cooked', 'baked': 'cooked', 'boiled': 'cooked',
    'raw': 'raw', 'fresh': 'raw', 'syrup': 'sweet', 'sweetened': 'sweet',
}
STOP = {'g', 'of', 'and', 'the', 'a', 'with', 'for', 'from', 'in', 'or', 'to', 'into', 'style', 'type', 'prepared',
        'sliced', 'diced', 'minced', 'chopped', 'crumbled', 'melted', 'thawed', 'leftover', 'fresh', 'large', 'small',
        'whole', 'lean', 'ground', 'unsalted', 'salted', 'low', 'sodium', 'added', 'no', 'fat', 'free', 'reduced',
        'jarred', 'toasted', 'garnish', 'tube', 'cooked', 'raw', 'dried', 'frozen', 'canned', 'dry', 'roasted', 'fried'}


def _tok(s):
    return re.findall(r"[a-z]+", s.lower())


def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", s or "")
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", s.lower())
    return s


def _stem(w):
    for suf in ('ies', 'es', 's'):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ('y' if suf == 'ies' else '')
    return w


def _forms(tokens):
    out = set()
    for t in tokens:
        for f, ws in FORMS.items():
            if t in ws or _stem(t) in ws:
                out.add(f)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ""))
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = ing.split(',')[0]
        parts = [p.strip() for p in usda.split(',')]
        u_head = parts[0]
        u_rest = ' '.join(parts[1:])
        it = _tok(ing)
        im = _tok(ing_main)
        uh = _tok(u_head)
        ur = _tok(u_rest)
        ua = uh + ur
        i_core = {_stem(w) for w in im if w not in STOP}
        u_core = {_stem(w) for w in ua if w not in STOP}
        if not i_core or not u_core:
            return 1.0

        # 1. role-bearing words overlap (function preserved)
        inter = i_core & u_core
        cover_i = len(inter) / len(i_core)
        cover_u = len(inter) / len(u_core)
        score = 6.0 * cover_i + 2.0 * cover_u

        # 2. head noun of ingredient (last core word) present in USDA primary food or descriptors
        ordered = [_stem(w) for w in im if w not in STOP]
        head = ordered[-1] if ordered else ''
        uh_core = {_stem(w) for w in uh}
        if head and head in uh_core:
            score += 2.0
        elif head and head in u_core:
            score += 1.0
        else:
            score -= 1.5

        # 3. functional form class agreement
        fi = _forms(im)
        fu = _forms(uh)
        if fi and fu:
            if fi & fu:
                score += 1.5
            else:
                score -= 2.5
        # whole food vs derived liquid/oil/paste with same word -> behaviour changes
        derived = {'oil', 'liquid', 'sauce'}
        if (fu & derived) and not (fi & derived):
            score -= 3.0
        if (fi & derived) and not (fu & derived) and fi:
            score -= 2.0
        if 'dish' in fu and 'dish' not in fi:
            score -= 3.0

        # 4. state conflicts (preparation changes)
        si = {STATE_MOD[t] for t in it if t in STATE_MOD}
        su = {STATE_MOD[t] for t in ua if t in STATE_MOD}
        if 'canned' in su and 'canned' not in si:
            score -= 1.5
        if 'sweet' in su and 'sweet' not in si:
            score -= 1.0
        if si and su and not (si & su):
            score -= 0.8
        # 5. extra specificity in USDA descriptors (variants forcing recipe change)
        extra = len(u_core - i_core - {'raw', 'cooked'})
        score -= min(extra, 6) * 0.25
        # 6. unmatched modifiers in ingredient (e.g. type of fat/dairy)
        missing = len(i_core - u_core)
        score -= min(missing, 4) * 0.5
        # generic words like "pork sausage" for "blood sausage": modifier mismatch with shared head
        if head and head in u_core and len(i_core) > 1 and cover_i < 1:
            score -= 1.0
        return float(max(-5.0, min(12.0, score)))
    except Exception:
        return 0.0
