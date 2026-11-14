import re
import math

_STOP = set("""fresh frozen thawed chopped diced sliced minced grated shredded dried canned cooked raw large small
medium whole boneless skinless trimmed peeled optional garnish of and or with for from the a an to taste
fillet fillets slices pieces flaked g kg ml oz lb nfs type style""".split())


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and w[-3] in "sxzh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = ing.split(",")[0]
        ing = re.sub(r"\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        it = [_norm(w) for w in re.findall(r"[a-z]+", ing)]
        it = [w for w in it if w not in _STOP]
        us = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        segs = [[_norm(w) for w in re.findall(r"[a-z]+", s)] for s in us.split(",")]
        segs = [[w for w in s if w not in _STOP] for s in segs]
        segs = [s for s in segs if s]
        if not it or not segs:
            return 0.0
        # ingredient weights: head noun (last word) strongest, geometric decay leftwards
        n = len(it)
        iw = {}
        for i, w in enumerate(it):
            iw[w] = max(iw.get(w, 0.0), 0.6 ** (n - 1 - i))
        # usda weights: decay by comma-segment depth, mild decay within a segment
        uw = {}
        for si, s in enumerate(segs):
            for wi, w in enumerate(s):
                weight = math.exp(-0.9 * si) * (0.85 ** wi)
                uw[w] = max(uw.get(w, 0.0), weight)
        tot_i = sum(iw.values())
        tot_u = sum(uw.values())
        # recall: how much of ingredient mass is found, discounted by where it sits in usda
        rec = sum(iw[w] * uw[w] ** 0.5 for w in iw if w in uw) / tot_i
        # precision: how much of usda leading mass is explained by the ingredient
        prec = sum(uw[w] for w in uw if w in iw) / tot_u
        # headness: is the first usda content word / last word of first segment in ingredient
        first = segs[0]
        lead = 0.0
        if first[0] in iw:
            lead += 0.5
        if first[-1] in iw:
            lead += 0.5
        if len(segs) > 1 and lead == 0.0 and (segs[1][0] in iw or segs[1][-1] in iw):
            lead = 0.4
        head_hit = 1.0 if it[-1] in uw else 0.0
        # ingredient head appears only as a non-final modifier in first segment: demotion
        demote = 0.0
        if it[-1] in first and first[-1] != it[-1] and first[-1] not in iw:
            demote = 1.0
        score = 10.0 * (0.35 * rec + 0.25 * prec + 0.25 * lead + 0.15 * head_hit) - 3.0 * demote
        return float(score)
    except Exception:
        return 0.0
