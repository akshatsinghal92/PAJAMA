import re
import math

# Variant 5: "process-axis vector distance".
# Each text is projected onto a small set of processing axes (heat, preservation,
# moisture, fat-added). The state distance between the two vectors is weighted by
# axis severity; trivial mechanical states (chop, dice, thaw...) are zero-cost.
# A food-identity gate based on character trigram overlap of the residual
# (state-stripped) tokens scales the final score.

_AXES = {
    # axis: {keyword: level}
    "heat": {
        "raw": 0, "fresh": 0, "uncooked": 0, "unheated": 0,
        "cooked": 2, "boiled": 2, "steamed": 2, "simmered": 2, "poached": 2,
        "blanched": 1, "parboiled": 1, "microwaved": 2, "stewed": 2, "braised": 2,
        "baked": 3, "roasted": 3, "grilled": 3, "broiled": 3, "toasted": 3,
        "fried": 4, "sauteed": 3, "pan-fried": 4, "deep-fried": 4, "smoked": 3,
    },
    "preserve": {
        "canned": 2, "pickled": 3, "cured": 3, "brined": 2, "salted": 2,
        "fermented": 3, "jarred": 2,
    },
    "moisture": {
        "dried": 3, "dehydrated": 3, "powder": 3, "powdered": 3, "dry": 2,
        "juice": 2, "puree": 1, "pureed": 1, "concentrate": 3, "paste": 2,
    },
    "fat": {
        "breaded": 3, "battered": 3, "buttered": 2, "oil": 1,
    },
}
_AXIS_WEIGHT = {"heat": 1.4, "preserve": 1.1, "moisture": 0.9, "fat": 0.7}

_TRIVIAL = set("""chopped diced minced sliced shredded thawed cubed grated peeled trimmed
halved quartered crushed julienned cut torn rinsed drained washed cleaned deveined
boneless skinless segments leaves pieces whole large small medium finely roughly
coarsely thinly thick thin frozen chilled cold room temperature softened melted
beaten separated packed loosely firmly""".split())

_NOISE = set("""and or with without from in of the a an to for tube style type mixed species
farmed wild added salt ns as nfs prepared ready serve unprepared plain regular
all commercial commercially variety meats by products product made""".split())

_EXEMPT_CONTEXT = {"dried": {"bean", "beans", "fava", "favas", "broadbeans", "lentil",
                             "lentils", "pea", "peas", "chickpea", "chickpeas", "seeds",
                             "mature", "herb", "spices", "pasta", "rice"},
                   "dry": {"pasta", "rice", "spices", "mature", "seeds"}}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|tbsp|tsp|cups?)\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = t.replace("deep fried", "deep-fried").replace("pan fried", "pan-fried")
    return [w for w in re.split(r"[^a-z\-]+", t) if w]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _vector(tokens):
    vec = {a: None for a in _AXES}
    toks = set(tokens)
    for axis, table in _AXES.items():
        best = None
        for w in tokens:
            if w in table:
                ctx = _EXEMPT_CONTEXT.get(w)
                if ctx and toks & ctx:
                    continue
                lvl = table[w]
                if best is None or lvl > best:
                    best = lvl
        vec[axis] = best
    return vec


def _residual(tokens):
    out = []
    for w in tokens:
        if w in _TRIVIAL or w in _NOISE:
            continue
        if any(w in t for t in _AXES.values()):
            continue
        if len(w) < 3:
            continue
        out.append(_stem(w))
    return out


def _trigrams(words):
    grams = set()
    for w in words:
        p = "#" + w + "#"
        for i in range(len(p) - 2):
            grams.add(p[i:i + 3])
    return grams


def _identity(ing_words, usda_words, usda_head):
    if not ing_words or not usda_words:
        return 0.0
    # best per-word trigram match for ingredient words
    scores = []
    for iw in ing_words:
        g1 = _trigrams([iw])
        best = 0.0
        for uw in usda_words:
            g2 = _trigrams([uw])
            if not g1 or not g2:
                continue
            j = len(g1 & g2) / float(len(g1 | g2))
            if j > best:
                best = j
        scores.append(best)
    coverage = sum(scores) / len(scores)
    # head of USDA (primary food) must relate to some ingredient word
    head_hit = 0.0
    for hw in usda_head:
        g = _trigrams([hw])
        for iw in ing_words:
            gi = _trigrams([iw])
            if g and gi:
                head_hit = max(head_hit, len(g & gi) / float(len(g | gi)))
    # extra unmatched USDA specifier words (e.g. variety mismatch) penalize lightly
    unmatched = 0
    for uw in usda_words:
        g2 = _trigrams([uw])
        if max((len(g2 & _trigrams([iw])) / float(len(g2 | _trigrams([iw])))
                for iw in ing_words), default=0.0) < 0.3:
            unmatched += 1
    spec_pen = min(0.35, 0.06 * unmatched)
    return max(0.0, 0.6 * coverage + 0.4 * max(head_hit, coverage * 0.8) - spec_pen)


def _state_distance(vi, vu):
    dist = 0.0
    for axis in _AXES:
        a, b = vi[axis], vu[axis]
        w = _AXIS_WEIGHT[axis]
        if a is None and b is None:
            continue
        if axis == "heat":
            a = 0 if a is None else a
            b = 0 if b is None else b
            dist += w * abs(a - b)
        else:
            if a is None or b is None:
                lvl = a if a is not None else b
                # one side declares a preservation/moisture state the other lacks
                dist += w * 0.5 * lvl
            else:
                dist += w * 0.3 * abs(a - b)
    return dist


def judging_function(ingredient, usda_match):
    try:
        ing_tokens = _clean(ingredient)
        usda_tokens = _clean(usda_match)
        if not ing_tokens or not usda_tokens:
            return 0.0
        head_raw = str(usda_match or "").lower().split(",")[0]
        head = [_stem(w) for w in re.split(r"[^a-z]+", head_raw) if len(w) > 2]

        vi = _vector(ing_tokens)
        vu = _vector(usda_tokens)
        dist = _state_distance(vi, vu)
        state_score = math.exp(-dist / 2.2)  # 1.0 when equivalent

        ident = _identity(_residual(ing_tokens), _residual(usda_tokens), head)
        gate = 1.0 / (1.0 + math.exp(-12.0 * (ident - 0.42)))

        score = 100.0 * gate * (0.35 + 0.65 * state_score)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
