import re
import math

COMPOUND_MARKERS = ('and', 'with', 'in', 'made', 'sauce', 'mix', 'dressing', 'seasoned',
                    'breaded', 'sweetened', 'flavored', 'salted', 'glazed', 'marinated',
                    'candied', 'coated', 'stuffed', 'filled', 'blend', 'syrup', 'gravy')


def _clean(s):
    s = s.lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^\s*\d+(\.\d+)?\s*[a-z]{0,2}\b', ' ', s)
    return s


def _grams(s, n=3):
    s = re.sub(r'[^a-z]', '', s)
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ''))
        usd = _clean(str(usda_match or ''))
        if not ing.strip() or not usd.strip():
            return 0.0
        ing_main = ing.split(',')[0]
        parts = [p.strip() for p in usd.split(',') if p.strip()]
        head = parts[0]
        descs = parts[1:]

        # 1. character-trigram similarity between ingredient and USDA head / whole
        g_ing = _grams(ing_main)
        sim_head = _jac(g_ing, _grams(head))
        sim_all = _jac(g_ing, _grams(' '.join(parts)))
        # containment of ingredient trigrams in the USDA text
        g_usd = _grams(' '.join(parts))
        contain = len(g_ing & g_usd) / float(len(g_ing) or 1)

        # 2. descriptor segments count: each extra comma-segment is added specificity
        seg_pen = 0.0
        ing_words = set(re.findall(r'[a-z]+', ing))
        for d in descs:
            dw = re.findall(r'[a-z]+', d)
            if not dw:
                continue
            novel = [w for w in dw if w[:4] not in {x[:4] for x in ing_words}]
            seg_pen += 0.35 * len(novel) / float(len(dw))

        # 3. compound marker asymmetry
        uw = re.findall(r'[a-z]+', usd)
        um = sum(1 for w in uw if w in COMPOUND_MARKERS and w not in ing_words)
        im = sum(1 for w in re.findall(r'[a-z]+', ing) if w in COMPOUND_MARKERS and w not in set(uw))
        asym = um + 0.8 * im

        # 4. length ratio of word counts (compound complexity)
        lr = min(len(uw), len(re.findall(r'[a-z]+', ing_main))) / float(max(len(uw), len(re.findall(r'[a-z]+', ing_main)), 1))

        z = 3.0 * contain + 2.5 * sim_head + 1.5 * sim_all + 1.0 * lr - seg_pen - 1.1 * asym
        return round(100.0 / (1.0 + math.exp(-(z - 3.0))), 3)
    except Exception:
        return 0.0
