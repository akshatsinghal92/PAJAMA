import re
import math

_NOISE = set("""fresh frozen thawed dried dry canned cooked raw chopped minced diced sliced ground crushed
crumbled grated shredded peeled large small medium whole of and or with in from the a an to for into
boneless skinless trimmed organic tube g kg mg oz lb ml cup cups tbsp tsp""".split())


def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    return s


def _eq(a, b):
    # fuzzy token equality via shared 4-char prefix / plural tolerance
    if a == b:
        return True
    n = min(len(a), len(b))
    if n >= 4 and a[:n - 1] == b[:n - 1] and abs(len(a) - len(b)) <= 2:
        return True
    return n >= 5 and a[:5] == b[:5]


def _tri(a, b):
    def g(x):
        x = " " + x + " "
        return set(x[i:i + 3] for i in range(len(x) - 2))
    A, B = g(a), g(b)
    if not A or not B:
        return 0.0
    return 2.0 * len(A & B) / (len(A) + len(B))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or "")).split(",")[0]
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(kg|mg|g|oz|lb|ml)?\b", " ", ing)
        iw = [w for w in re.findall(r"[a-z]+", ing) if w not in _NOISE]
        segs = [re.findall(r"[a-z]+", s) for s in _clean(str(usda_match or "")).split(",")]
        segs = [s for s in segs if s]
        if not iw or not segs:
            return 0.0
        flat = []
        segid = []
        for i, s in enumerate(segs):
            for w in s:
                flat.append(w)
                segid.append(i)
        head = iw[-1]
        # locate head food (try last word, then earlier words right-to-left)
        hp = None
        for cand in [head] + list(reversed(iw[:-1])):
            for p, w in enumerate(flat):
                if _eq(cand, w):
                    hp = p
                    break
            if hp is not None:
                found = cand
                break
        if hp is None:
            return 1.5 * _tri(" ".join(iw), " ".join(segs[0]))
        # (a) how deep into the description the food appears: segment index + intra offset
        seg_depth = segid[hp]
        seg_start = segid.index(seg_depth)
        offset = hp - seg_start
        s = 5.0 * math.exp(-0.3 * seg_depth) * (1.0 / (1.0 + 0.2 * offset))
        if found != head:
            s *= 0.25
            s -= 1.0
        # (b) words that precede the head inside its segment and are not in the ingredient
        pre = [w for w in flat[seg_start:hp] if not any(_eq(w, x) for x in iw)]
        s -= 0.5 * min(len(pre), 3)
        # (c) the primary segment: fraction of its words accounted for by ingredient
        first = segs[0]
        acc = sum(1 for w in first if any(_eq(w, x) for x in iw)) / float(len(first))
        s += (3.0 if found == head else 1.0) * acc
        # (d) adjacency bonus for ingredient bigram preserved in order
        bi = 0
        for a, b in zip(iw, iw[1:]):
            for p in range(len(flat) - 1):
                if _eq(a, flat[p]) and _eq(b, flat[p + 1]):
                    bi += 1
                    break
        s += 1.0 * bi
        # (e) other ingredient words missing from description entirely
        miss = sum(1 for x in iw if not any(_eq(x, w) for w in flat))
        s -= 0.5 * miss
        s += 1.5 * _tri(" ".join(iw), " ".join(segs[0]))
        return max(0.0, min(10.0, s))
    except Exception:
        return 0.0
