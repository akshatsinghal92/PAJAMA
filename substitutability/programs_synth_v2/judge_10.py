import re
import math

# Preparation-State Equivalence, variant 2: multi-axis state vector.
# Each text is projected onto three ordinal axes:
#   thermal   : 0 raw .. 1 warmed/blanched .. 2 cooked .. 3 browned/fried
#   preserve  : 0 fresh .. 1 frozen .. 2 canned .. 3 cured/pickled .. 4 dried
#   transform : 0 intact/cut .. 1 mashed/creamed/pureed .. 2 juiced/powdered/paste
# Purely mechanical cuts (chopped, diced, minced, sliced, shredded) and
# thawing project to zero on every axis, so they are free.
# The score is an exponentially decaying function of the weighted distance.

_THERMAL = {
    "raw": 0, "fresh": 0, "uncooked": 0, "blanched": 1, "warmed": 1, "scalded": 1,
    "parboiled": 1, "cooked": 2, "boiled": 2, "steamed": 2, "poached": 2,
    "baked": 2, "stewed": 2, "simmered": 2, "braised": 2, "microwaved": 2,
    "heat": 2, "roasted": 3, "grilled": 3, "broiled": 3, "toasted": 3,
    "fried": 3, "sauteed": 3, "seared": 3, "charred": 3, "breaded": 3,
}
_PRESERVE = {
    "fresh": 0, "frozen": 1, "canned": 2, "jarred": 2, "bottled": 2,
    "smoked": 3, "cured": 3, "pickled": 3, "brined": 3, "salted": 3,
    "dried": 4, "dehydrated": 4, "sun": 4, "freeze": 4,
}
_TRANSFORM = {
    "mashed": 1, "creamed": 1, "pureed": 1, "whipped": 1, "crushed": 1,
    "juice": 2, "juiced": 2, "powder": 2, "powdered": 2, "paste": 2,
    "concentrate": 2, "extract": 2, "flakes": 1, "puree": 1,
}
_FREE = {"chopped", "diced", "minced", "sliced", "shredded", "grated", "thawed",
         "cubed", "halved", "segmented", "peeled", "trimmed", "rinsed", "drained"}
_W = (1.6, 1.0, 1.3)


def _project(words):
    t = [None, None, None]
    for w in words:
        if w in _FREE:
            continue
        for k, table in enumerate((_THERMAL, _PRESERVE, _TRANSFORM)):
            if w in table:
                v = table[w]
                t[k] = v if t[k] is None else max(t[k], v)
    return t


def _tokens(text, is_ing):
    s = text.lower()
    if is_ing:
        s = re.sub(r"^\s*\d+(\.\d+)?\s*[a-z]{0,2}\b", " ", s)
    s = s.replace("deep-fried", "fried").replace("freeze-dried", "freeze dried")
    return re.findall(r"[a-z]+", s)


def judging_function(ingredient, usda_match):
    try:
        iw = _tokens(str(ingredient or ""), True)
        uw = _tokens(str(usda_match or ""), False)
        if not iw or not uw:
            return 0.0
        vi, vu = _project(iw), _project(uw)
        dist2 = 0.0
        unknown = 0
        for k in range(3):
            a, b = vi[k], vu[k]
            if a is None and b is None:
                continue
            if a is None or b is None:
                # unspecified side defaults to the zero level, slight uncertainty
                unknown += 1
                a = 0 if a is None else a
                b = 0 if b is None else b
            d = b - a
            # moving the USDA entry further along processing than the cook
            # asked for is harder to undo than the reverse
            if d > 0:
                d *= 1.25
            dist2 += (_W[k] * d) ** 2
        dist = math.sqrt(dist2)
        score = 100.0 * math.exp(-0.45 * dist) - 3.0 * unknown
        # explicit mechanical-only ingredient matched to an explicitly raw USDA entry
        if any(w in _FREE for w in iw) and "raw" in uw and dist == 0:
            score = max(score, 98.0)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
