import re
import math

_NOISE = set("""chopped diced sliced minced cubed melted thawed fresh ripe large small medium finely
roughly boneless skinless peeled shredded grated crushed of and or with without the a in
raw cooked boiled dried dry prepared nfs plain regular""".split())


def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)?\b", " ", s)
    return s


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _grams(word, n=3):
    w = "#" + word + "#"
    return set(w[i:i + n] for i in range(max(1, len(w) - n + 1)))


def _wsim(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    return len(ga & gb) / float(len(ga | gb))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ""))
        usda = _clean(str(usda_match or ""))
        if not ing.strip() or not usda.strip():
            return 0.0
        iw = [_norm(w) for w in re.findall(r"[a-z]+", ing.split(",")[0])]
        iw = [w for w in iw if w not in _NOISE] or iw
        usegs = [s for s in usda.split(",") if s.strip()]
        if not iw or not usegs:
            return 0.0
        # The USDA "identity" is segment 0 plus the next segment(s) until a
        # state/qualifier word; USDA puts category first, so reorder.
        seg_w = [[_norm(w) for w in re.findall(r"[a-z]+", s) if _norm(w) not in _NOISE] for s in usegs]
        seg_w = [s for s in seg_w if s]
        if not seg_w:
            return 0.0
        # soft alignment: each ingredient word picks its best-matching USDA word,
        # weighted by where the USDA word sits (earlier segment = more identity-bearing)
        total = 0.0
        wsum = 0.0
        for k, w in enumerate(iw):
            weight = 2.0 if k == len(iw) - 1 else 1.0
            best = 0.0
            for si, seg in enumerate(seg_w):
                pos = 1.0 / (1.0 + 0.35 * si)
                for u in seg:
                    best = max(best, _wsim(w, u) * pos)
            total += weight * best
            wsum += weight
        align = total / wsum
        # reverse: USDA identity words (first two segments) explained by ingredient?
        ident = [u for seg in seg_w[:2] for u in seg]
        rev = 0.0
        for u in ident:
            rev += max([_wsim(u, w) for w in iw] + [0.0])
        rev = rev / float(len(ident)) if ident else 0.0
        # head conflict: USDA's primary noun differs from ingredient head
        head = iw[-1]
        prim = seg_w[0][-1] if seg_w[0] else ""
        conflict = 0.0
        if _wsim(head, prim) < 0.4 and not any(_wsim(head, u) > 0.8 for u in ident):
            conflict = 1.0
        elif prim and _wsim(head, prim) < 0.4:
            # category-first style ("Cheese, camembert"): head must match 2nd segment
            if len(seg_w) > 1 and _wsim(head, seg_w[1][0]) < 0.5 and not any(_wsim(head, u) > 0.8 for u in seg_w[1]):
                conflict = 0.5
        score = 10.0 * (0.55 * align + 0.45 * rev) - 4.0 * conflict
        # chain/restaurant penalty
        if re.search(r"\b(taco bell|mcdonald|burger king|wendy|kfc|subway|pizza hut|restaurant)\b", usda):
            score -= 3.0
        score -= 0.25 * max(0, len(seg_w) - 3)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
