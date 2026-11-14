import re

_NEG_WORDS = {"no", "without", "non", "not", "free", "un"}
_POLAR = {
    "salt": (["unsalted", "saltfree"], ["salted", "salt"]),
    "sweet": (["unsweetened", "sugarless", "sugarfree"], ["sweetened", "sweet", "syrup", "candied", "sugar"]),
    "skin": (["skinless", "peeled"], ["skin", "unpeeled"]),
    "bone": (["boneless", "deboned"], ["bone", "bones", "bonein"]),
    "seed": (["seedless", "pitted"], ["seeds", "seeded"]),
    "hull": (["hulled", "shelled"], ["unhulled", "unshelled", "inshell"]),
    "fat": (["nonfat", "lowfat", "skim", "lean", "reduced", "fatfree", "light"], ["whole", "regular", "fatty"]),
    "caf": (["decaf", "decaffeinated"], ["caffeinated"]),
}
_STOP = {"and", "or", "of", "the", "with", "in", "a", "for", "from", "to", "nfs", "g", "added"}


def _toks(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(?:\.\d+)?\s*[a-z]{0,2}\b", " ", s)
    s = s.replace("-", "")
    t = re.findall(r"[a-z]+", s)
    return [w[:-1] if (len(w) > 4 and w.endswith("s") and not w.endswith("ss")) else w for w in t]


def _lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def _polarity(toks):
    res = {}
    for i, w in enumerate(toks):
        flip = (i > 0 and toks[i - 1] in _NEG_WORDS) or (i + 1 < len(toks) and toks[i + 1] == "free") \
            or (i > 1 and toks[i - 2] in ("no", "without"))
        for attr, (ng, ps) in _POLAR.items():
            if w in ng or (w + "") in [n for n in ng]:
                res.setdefault(attr, set()).add(1 if flip else -1)
            elif w in ps:
                res.setdefault(attr, set()).add(-1 if flip else 1)
    return res


def judging_function(ingredient, usda_match):
    try:
        a = [w for w in _toks(ingredient) if w not in _STOP]
        b = [w for w in _toks(usda_match) if w not in _STOP]
        if not a or not b:
            return 0.0
        # ordered overlap (subsequence), normalised by both lengths -> F-measure
        l = _lcs(a, b)
        rec = l / float(len(a))
        prec = l / float(len(b))
        f = 0.0 if l == 0 else 2 * rec * prec / (rec + prec)
        # set overlap of ingredient words that appear anywhere in USDA
        cov = len(set(a) & set(b)) / float(len(set(a)))
        base = 0.6 * f + 0.4 * cov

        pa, pb = _polarity(a), _polarity(b)
        clash = 0.0
        for k in set(pa) & set(pb):
            if not (pa[k] & pb[k]):
                clash += 1.0
        mult = 0.35 ** clash
        return round(10.0 * base * mult, 4)
    except Exception:
        return 0.0
