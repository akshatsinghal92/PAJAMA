import re
import math

# axes: moisture, added fat, browning/maillard, tenderness, smoke/char, dehydration
_VEC = {
    'raw': (0.7, 0.0, 0.0, 0.1, 0.0, 0.0),
    'fresh': (0.7, 0.0, 0.0, 0.1, 0.0, 0.0),
    'uncooked': (0.7, 0.0, 0.0, 0.1, 0.0, 0.0),
    'frozen': (0.7, 0.0, 0.0, 0.1, 0.0, 0.0),
    'boiled': (1.0, 0.0, 0.0, 0.8, 0.0, 0.0),
    'poached': (1.0, 0.0, 0.0, 0.8, 0.0, 0.0),
    'simmered': (1.0, 0.0, 0.0, 0.8, 0.0, 0.0),
    'stewed': (1.0, 0.0, 0.0, 0.8, 0.0, 0.0),
    'steamed': (0.9, 0.0, 0.0, 0.7, 0.0, 0.0),
    'microwaved': (0.8, 0.0, 0.0, 0.6, 0.0, 0.0),
    'cooked': (0.7, 0.1, 0.2, 0.6, 0.0, 0.0),
    'prepared': (0.7, 0.1, 0.2, 0.6, 0.0, 0.0),
    'baked': (0.4, 0.1, 0.6, 0.6, 0.0, 0.3),
    'roasted': (0.4, 0.2, 0.7, 0.6, 0.1, 0.3),
    'broiled': (0.4, 0.1, 0.7, 0.6, 0.3, 0.2),
    'grilled': (0.4, 0.1, 0.8, 0.6, 0.8, 0.2),
    'barbecued': (0.4, 0.1, 0.8, 0.6, 0.8, 0.2),
    'charbroiled': (0.4, 0.1, 0.8, 0.6, 0.8, 0.2),
    'smoked': (0.4, 0.0, 0.4, 0.5, 1.0, 0.3),
    'fried': (0.3, 0.8, 0.8, 0.6, 0.0, 0.3),
    'pan-fried': (0.3, 0.7, 0.8, 0.6, 0.0, 0.3),
    'pan-broiled': (0.4, 0.4, 0.7, 0.6, 0.0, 0.2),
    'sauteed': (0.4, 0.6, 0.6, 0.6, 0.0, 0.2),
    'sautéed': (0.4, 0.6, 0.6, 0.6, 0.0, 0.2),
    'stir-fried': (0.4, 0.6, 0.6, 0.6, 0.0, 0.2),
    'deep-fried': (0.2, 1.0, 0.9, 0.5, 0.0, 0.4),
    'toasted': (0.1, 0.0, 0.9, 0.0, 0.0, 0.8),
    'dried': (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    'dehydrated': (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    'canned': (0.9, 0.0, 0.0, 0.7, 0.0, 0.0),
}
_W = (1.0, 1.4, 1.0, 0.8, 1.0, 1.2)
_NEUTRAL = (0.6, 0.0, 0.0, 0.3, 0.0, 0.0)
_NOISE = set('the and with without from for into of in a an g kg ml oz lb cup tbsp tsp small large medium chopped sliced diced minced shredded grated cubed crumbled thawed cold hot warm whole nfs regular type added no salt fresh raw cooked boiled baked roasted fried toasted dried'.split())


def _strip(s):
    s = (s or '').lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    return re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b\s*', '', s)


def _vec(text):
    hits = []
    for m in re.finditer(r"[a-zé\-]+", text):
        w = m.group(0)
        if w in _VEC:
            hits.append(_VEC[w])
    if not hits:
        return None
    n = float(len(hits))
    return tuple(sum(h[i] for h in hits) / n for i in range(6))


def _grams(s, n=3):
    s = re.sub(r'[^a-z]', '', s)
    if len(s) < n:
        return set([s]) if s else set()
    return set(s[i:i + n] for i in range(len(s) - n + 1))


def _core(text, primary_only=False):
    if primary_only:
        text = text.split(',')[0]
    toks = [t for t in re.findall(r'[a-z]+', text) if t not in _NOISE and len(t) > 2]
    return ''.join(sorted(toks)), toks


def judging_function(ingredient, usda_match):
    try:
        ing = _strip(ingredient)
        usda = (usda_match or '').lower().strip()
        if not ing.strip() or not usda:
            return 0.0
        vi, vu = _vec(ing), _vec(usda)
        # method distance (weighted euclid on 6-d state vectors, neutral if unstated)
        a = vi if vi is not None else _NEUTRAL
        b = vu if vu is not None else _NEUTRAL
        d = math.sqrt(sum(_W[i] * (a[i] - b[i]) ** 2 for i in range(6)))
        method_sim = math.exp(-1.6 * d)
        if vi is None and vu is None:
            method_sim = 0.9

        # identity via character trigram containment of ingredient words in USDA text
        _, itoks = _core(ing)
        _, ptoks = _core(usda, True)
        gi = _grams(''.join(itoks))
        gu = _grams(''.join(_core(usda)[1]))
        gp = _grams(''.join(ptoks))
        contain = len(gi & gu) / float(len(gi)) if gi else 0.0
        back = len(gp & gi) / float(len(gp)) if gp else 0.0
        ident = 0.6 * contain + 0.4 * back
        ident = ident ** 1.3

        return round(100.0 * (0.4 * method_sim + 0.6 * ident) * (0.5 + 0.5 * ident), 2)
    except Exception:
        return 0.0
