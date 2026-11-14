import re

# Variant 4: position-weighted word alignment using normalized Levenshtein
# distance. Ingredient words are weighted by closeness to the END of the
# head phrase (English head-final noun phrases); USDA words are weighted by
# closeness to the START of the description (primary food first).

_NOISE = set("""
g gram grams kg ml oz lb cup cups tbsp tsp fresh frozen canned chopped diced
sliced minced raw cooked uncooked large small medium thawed drained peeled
of and with or the a an nfs ns style type plain regular to in for from
""".split())


def _lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _sim(a, b):
    if a.endswith("s") and len(a) > 3:
        a = a[:-1]
    if b.endswith("s") and len(b) > 3:
        b = b[:-1]
    if a == b:
        return 1.0
    d = _lev(a, b)
    s = 1.0 - d / float(max(len(a), len(b)))
    # only near-identical spellings count (gnocchi/gnochi), not guava/garlic
    return s if s >= 0.75 else 0.0


def _ing_words(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t).split(",")[0]
    t = re.sub(r"\d+(\.\d+)?", " ", t)
    words = [w for w in re.findall(r"[a-z]+", t) if w not in _NOISE]
    n = len(words)
    # head-final weighting: last word 1.0, earlier words decay
    return [(w, 0.45 ** (n - 1 - i)) for i, w in enumerate(words)]


def _usda_words(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    out = []
    for si, seg in enumerate(t.split(",")):
        words = [w for w in re.findall(r"[a-z]+", seg) if w not in _NOISE]
        n = len(words)
        for wi, w in enumerate(words):
            seg_w = 1.0 if si == 0 else (0.8 if si == 1 else 0.25 / si)
            # inside a segment the last word is the head
            in_w = 1.0 if wi == n - 1 else 0.6
            out.append((w, seg_w * in_w))
    return out


def _align(src, tgt):
    """Greedy max-weight alignment. Returns weighted coverage of src."""
    pairs = []
    for i, (ws, as_) in enumerate(src):
        for j, (wt, at) in enumerate(tgt):
            s = _sim(ws, wt)
            if s > 0:
                pairs.append((s * as_ * at, s, i, j))
    pairs.sort(reverse=True)
    used_i, used_j, cov = set(), set(), 0.0
    for _, s, i, j in pairs:
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        cov += s * src[i][1]
    total = sum(a for _, a in src)
    return cov / total if total else 0.0


def judging_function(ingredient, usda_match):
    try:
        iw = _ing_words(str(ingredient or ""))
        uw = _usda_words(str(usda_match or ""))
        if not iw or not uw:
            return 0.0
        forward = _align(iw, uw)          # how much of the ingredient head is found
        backward = _align(uw, iw)         # how much of the USDA primary is explained
        head_word = iw[-1][0]
        head_hit = max(_sim(head_word, w) * a for w, a in uw)
        score = 100.0 * (0.4 * forward + 0.3 * backward + 0.3 * head_hit)
        if head_hit == 0.0:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
