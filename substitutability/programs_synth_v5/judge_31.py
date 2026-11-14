import re
import math


BENIGN = set(['raw','fresh','cooked','boiled','dried','frozen','drained','unprepared','ground','whole','roasted','baked','fried','simmered','steamed','low','fat','lowfat','reduced','nonfat','unsalted','plain','only','meat','flesh','skin','without','with','salt','all','varieties','drained','solids','liquid','and','or','the'])


def _clean(s):
    s = (s or '').strip()
    s = re.sub(r'^\s*\d+(\.\d+)?\s*(g|kg|oz|lb|ml)?\s+', '', s, flags=re.I)
    s = re.sub(r'\([^)]*\)', ' ', s)
    return s.strip()


def _bigrams(s):
    s = re.sub(r'[^a-z ]', '', s.lower())
    s = ' '.join(s.split())
    return [s[i:i + 2] for i in range(len(s) - 1)]


def _dice(a, b):
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    from collections import Counter
    ca, cb = Counter(A), Counter(B)
    inter = sum((ca & cb).values())
    return 2.0 * inter / (len(A) + len(B))


def _head(phrase):
    # head noun heuristic: last alphabetic word of the first comma chunk
    first = phrase.split(',')[0]
    w = re.findall(r'[a-z]+', first.lower())
    return w[-1] if w else ''


def _sing(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        raw_u = (usda_match or '').strip()
        if not ing or not raw_u:
            return 0.0
        chunks = [c.strip() for c in raw_u.split(',') if c.strip()]
        first = chunks[0] if chunks else raw_u
        rest = chunks[1:]
        ing_l = ing.lower()
        ing_words = set(_sing(w) for w in re.findall(r'[a-z]+', ing_l))

        # 1) identity: does the USDA head food appear as a word run in the ingredient
        ihead = _sing(_head(ing.split(',')[0]))
        uhead_words = [_sing(w) for w in re.findall(r'[a-z]+', first.lower())]
        head_hit = 1.0 if (ihead and ihead in uhead_words) else 0.0
        if not head_hit:
            ov = [w for w in uhead_words if w in ing_words and len(w) > 2]
            head_hit = 0.5 if ov else 0.0
        char_sim = _dice(ing.split(',')[0], first)
        identity = 0.6 * head_hit + 0.4 * char_sim

        # 2) complexity of the USDA entry: segments that are not echoed by ingredient
        unexplained = 0
        for c in rest:
            cw = set(_sing(w) for w in re.findall(r'[a-z]+', c.lower()))
            cw -= BENIGN
            if cw and not (cw & ing_words):
                unexplained += 1
        seg_pen = unexplained / float(max(1, len(rest))) if rest else 0.0

        # 3) compound marker detection in the USDA text
        compound = 0.0
        low = raw_u.lower()
        if re.search(r'\b(with|and)\b', low) and not re.search(r'\b(and)\b', ing_l):
            compound += 0.5
        if re.search(r'\b(added|contains|flavored|sweetened|salted|breaded|seasoned|sauce|mix|blend|filled|mixture)\b', low):
            compound += 1.0
        # brand-style all caps token or digits
        if re.search(r'\b[A-Z]{3,}\b', raw_u):
            compound += 0.7
        if len(re.findall(r'[a-z]+', first.lower())) > 3 and head_hit < 1:
            compound += 0.4

        # 4) shape mismatch: first chunk much longer/shorter than ingredient name
        li, lu = len(ing.split(',')[0].split()), len(first.split())
        shape = abs(math.log((li + 1.0) / (lu + 1.0)))

        full_words = set(_sing(w) for w in re.findall(r'[a-z]+', low))
        content = [w for w in ing_words if w not in BENIGN and len(w) > 2]
        cov = (len([w for w in content if w in full_words]) / float(len(content))) if content else 0.0
        identity = 0.5 * identity + 0.5 * cov
        damp = 1.0 - min(0.7, 0.18 * compound + 0.25 * seg_pen + 0.1 * min(shape, 1.5))
        score = 10.0 * identity * damp
        if not rest and compound == 0 and head_hit:
            score += 1.0
        return float(score)
    except Exception:
        return 0.0
