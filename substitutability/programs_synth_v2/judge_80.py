import re

# Modifier and Qualifier Consistency, variant 8: ordinal vs nominal
# qualifier scales with worst-conflict aggregation.
# Qualifier dimensions are of two kinds:
#   ORDINAL - values lie on a scale and nearby values are close:
#             fat (skim < 1% < 2% < whole), sweetness (unsweetened < lightly
#             < sweetened < candied), heat (mild < medium < hot), size
#             (baby < small < medium < large < jumbo), ripeness (green < ripe
#             < overripe), calorie (diet < reduced < regular)
#   NOMINAL - any difference is a full conflict: colour, animal part,
#             plant part, cheese variety, dressing style, flavour
# Each dimension yields a conflict in 0..1 (ordinal: normalised distance,
# nominal: 0 or 1) times a noticeability weight. A diner notices the WORST
# conflict most, so score = 10 * (1 - 0.7*max_conflict - 0.3*mean_conflict).

_ORDINAL = {
    "fat": ({"skim": 0, "nonfat": 0, "fat free": 0, "1%": 1, "lowfat": 1, "low fat": 1, "light": 1,
             "2%": 2, "reduced fat": 2, "whole": 3, "full fat": 3, "regular": 3}, 3, 1.0),
    "sweet": ({"unsweetened": 0, "no sugar added": 0, "lightly sweetened": 1, "sweetened": 2,
               "sweet": 2, "candied": 3, "frosted": 3}, 3, 0.9),
    "heat": ({"mild": 0, "medium hot": 1, "hot": 2, "extra hot": 3, "spicy": 2}, 3, 0.8),
    "size": ({"baby": 0, "small": 1, "medium": 2, "large": 3, "jumbo": 4, "extra large": 4}, 4, 0.3),
    "ripeness": ({"green": 0, "unripe": 0, "ripe": 1, "overripe": 2}, 2, 0.6),
    "calorie": ({"diet": 0, "reduced calorie": 1, "low calorie": 1, "lite": 1}, 2, 0.8),
}
_NOMINAL = {
    "colour": ({"red", "yellow", "orange", "white", "black", "brown", "purple"}, 0.8),
    "part": ({"breast", "thigh", "wing", "drumstick", "leg", "loin", "tenderloin", "rib", "shoulder",
              "brisket", "liver", "light meat", "dark meat"}, 1.0),
    "plantpart": ({"leaf", "leaves", "root", "seed", "seeds", "stem", "stalk", "peel", "zest", "juice"}, 0.9),
    "cheese": ({"cheddar", "cottage", "mozzarella", "swiss", "parmesan", "feta", "ricotta"}, 1.0),
    "dressing": ({"italian", "ranch", "caesar", "french", "thousand island"}, 0.9),
    "flavour": ({"vanilla", "chocolate", "strawberry", "honey", "cinnamon", "maple", "lemon", "coffee", "plain"}, 0.9),
    "pepper": ({"bell", "jalapeno", "serrano", "habanero", "poblano", "chipotle"}, 0.9),
}


def _norm(text):
    t = " " + re.sub(r"[^a-z0-9% ]", " ", text.lower()) + " "
    return re.sub(r"\s+", " ", t)


def _find(t, phrases):
    hits = []
    for p in sorted(phrases, key=len, reverse=True):
        if " " + p + " " in t:
            hits.append(p)
            t = t.replace(" " + p + " ", " ")
    return hits, t


def _extract(text):
    t = _norm(text)
    # "green" is a ripeness word for bananas/tomatoes but a colour for peppers
    ripeness_ctx = re.search(r"\b(banana|plantain|tomato(es)?|mango)\b", t) is not None
    ords, noms = {}, {}
    for dim, (scale, _rng, _w) in _ORDINAL.items():
        if dim == "ripeness" and not ripeness_ctx:
            continue
        hits, t = _find(t, scale)
        if hits:
            ords[dim] = [scale[h] for h in hits]
    for dim, (vals, _w) in _NOMINAL.items():
        vs = set(vals) | ({"green"} if dim == "colour" and not ripeness_ctx else set())
        hits, t = _find(t, vs)
        if hits:
            noms[dim] = set(h.replace("leaves", "leaf").replace("seeds", "seed") for h in hits)
    return ords, noms


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower().replace("skin not eaten", " ")
        if not ing.strip() or not usda.strip():
            return 0.0
        oi, ni = _extract(ing)
        ou, nu = _extract(usda)
        conflicts = []
        for dim, (_scale, rng, w) in _ORDINAL.items():
            if dim in oi and dim in ou:
                d = min(abs(a - b) for a in oi[dim] for b in ou[dim]) / float(rng)
                conflicts.append(w * d)
            elif dim in ou and dim == "fat" and re.search(r"\b(milk|cheese|yogurt|cottage|cream)\b", ing):
                # unqualified dairy implies the regular (full) level
                d = abs(3 - min(ou[dim])) / 3.0
                conflicts.append(0.5 * w * d)
        for dim, (_vals, w) in _NOMINAL.items():
            if dim in ni and dim in nu:
                conflicts.append(0.0 if ni[dim] & nu[dim] else w)
        if not conflicts:
            return 9.0 if (oi or ni) else 8.5
        worst = max(conflicts)
        mean = sum(conflicts) / len(conflicts)
        score = 10.0 * (1.0 - 0.7 * worst - 0.3 * mean)
        if worst == 0.0:
            score = 10.0
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
