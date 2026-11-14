import re

# Variant 8: multi-axis "state vector" model.
# Each text is projected onto several preparation axes (heat, moisture, form,
# temperature, composition). Axes are weighted by how much a difference along
# them changes the dish. Mechanical/form axes are nearly free; heat and moisture
# axes are expensive. The state-distance is combined with a core-food anchor
# check computed from character-trigram Dice similarity of the leading noun.

_AXES = {
    # axis: (weight, {term: level})
    "heat": (3.2, {
        "raw": 0, "fresh": 0, "uncooked": 0, "unheated": 0,
        "warmed": 0.3, "warm": 0.3, "heated": 0.4, "blanched": 0.5,
        "steamed": 0.7, "boiled": 0.8, "poached": 0.8, "simmered": 0.8,
        "cooked": 0.8, "baked": 0.9, "toasted": 0.6, "roasted": 1.0,
        "braised": 1.0, "stewed": 1.0, "grilled": 1.0, "broiled": 1.0,
        "sauteed": 1.0, "pan-fried": 1.2, "fried": 1.3, "deep-fried": 1.5,
        "smoked": 1.2, "charred": 1.3,
    }),
    "moisture": (2.6, {
        "fresh": 0, "raw": 0, "canned": 0.4, "rehydrated": 0.3,
        "dried": 1.0, "dehydrated": 1.0, "dry": 1.0, "sun-dried": 1.0,
        "powdered": 1.2, "powder": 1.2, "concentrate": 0.9, "concentrated": 0.9,
        "evaporated": 0.8, "condensed": 0.9, "freeze-dried": 1.1,
    }),
    "form": (0.35, {
        "whole": 0, "chopped": 0.5, "diced": 0.5, "minced": 0.6, "sliced": 0.4,
        "shredded": 0.6, "grated": 0.6, "cubed": 0.5, "crushed": 0.7,
        "ground": 0.8, "mashed": 0.8, "pureed": 0.9, "paste": 0.9,
        "halved": 0.2, "quartered": 0.3, "julienned": 0.5, "rings": 0.4,
        "pieces": 0.3, "chunks": 0.4, "flakes": 0.6,
    }),
    "temperature": (0.2, {
        "frozen": 1.0, "thawed": 0.0, "chilled": 0.3, "refrigerated": 0.3,
        "room": 0.0, "defrosted": 0.0,
    }),
    "preservation": (1.6, {
        "pickled": 1.0, "cured": 1.0, "salted": 0.6, "brined": 0.9,
        "fermented": 1.0, "marinated": 0.7, "sweetened": 0.6, "candied": 1.0,
        "sulfured": 0.1, "unsweetened": 0.0,
    }),
    "fatlevel": (1.4, {
        "nonfat": 0.0, "fat-free": 0.0, "skim": 0.0, "lowfat": 0.4, "low-fat": 0.4,
        "reduced-fat": 0.5, "light": 0.5, "lite": 0.5, "whole": 1.0, "full-fat": 1.0,
    }),
    "sodium": (0.9, {
        "low-sodium": 0.2, "unsalted": 0.0, "no-salt": 0.0, "reduced-sodium": 0.3,
    }),
}

_STOP = set("""a an the and or of with in for to from as at by on ns nfs not
specified major type style made prepared plain regular all purpose about
g gram grams oz ml cup cups tbsp tsp teaspoon tablespoon salad cooking
meat only separable lean fat trimmed select choice brand spices spice
beverages beverage babyfood babyfoods snacks fast foods food products
broilers fryers""".split())

_ALL_STATE = set()
for _w, _m in _AXES.values():
    _ALL_STATE.update(_m.keys())


def _normalize(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d./]+\s*(g|gram|grams|kg|ml|oz|lb)?\b", " ", t)
    t = t.replace("low sodium", "low-sodium").replace("reduced sodium", "reduced-sodium")
    t = t.replace("no salt", "no-salt").replace("reduced fat", "reduced-fat")
    t = t.replace("low fat", "low-fat").replace("fat free", "fat-free")
    t = t.replace("deep fried", "deep-fried").replace("pan fried", "pan-fried")
    t = t.replace("sun dried", "sun-dried").replace("freeze dried", "freeze-dried")
    t = t.replace("full fat", "full-fat")
    t = re.sub(r"[^a-z\- ,]", " ", t)
    return t


def _project(text):
    """Return {axis: level} for axes that are explicitly mentioned."""
    vec = {}
    words = re.findall(r"[a-z][a-z\-]*", text)
    for axis, (_w, lex) in _AXES.items():
        hits = [lex[w] for w in words if w in lex]
        if hits:
            vec[axis] = max(hits)
    return vec


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    out = []
    for w in re.findall(r"[a-z][a-z\-]*", text):
        if w in _STOP or w in _ALL_STATE or len(w) < 3:
            continue
        out.append(_stem(w))
    return out


def _trigrams(s):
    s = "  " + s + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _dice(a, b):
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _anchor_score(ing_words, usda_text):
    """Fuzzy coverage of ingredient words by USDA words, plus a position-
    weighted anchor that rewards the ingredient's food appearing early in the
    USDA description."""
    segs = [s.strip() for s in usda_text.split(",") if s.strip()]
    if not segs or not ing_words:
        return 0.0, 0.0
    usda_words = []
    pos_weight = {}
    rank = 0
    for s in segs:
        cw = _content(s)
        if not cw:
            continue
        wgt = max(0.5, 1.0 - 0.15 * rank)
        for u in cw:
            usda_words.append(u)
            pos_weight[u] = max(pos_weight.get(u, 0.0), wgt)
        rank += 1
    if not usda_words:
        return 0.0, 0.0

    matched = 0.0
    for w in ing_words:
        best = max(_dice(w, u) for u in usda_words)
        matched += best if best >= 0.55 else 0.0
    coverage = matched / len(ing_words)

    head = 0.0
    for u in usda_words:
        best = max(_dice(u, w) for w in ing_words)
        if best >= 0.55:
            head = max(head, best * pos_weight[u])
    return coverage, head


def _state_distance(vi, vu):
    dist = 0.0
    for axis, (weight, _lex) in _AXES.items():
        a = vi.get(axis)
        b = vu.get(axis)
        if a is None and b is None:
            continue
        if a is None or b is None:
            # One side silent: assume trivially implied default (raw/whole/regular).
            present = a if a is not None else b
            if axis == "heat":
                # Implicit-raw vs a cooked USDA entry is a real change; warm is minor.
                gap = present if b is not None else present * 0.5
            elif axis == "moisture":
                gap = present * 0.8
            elif axis == "sodium" or axis == "fatlevel":
                gap = 0.7
            else:
                gap = present * 0.5
        else:
            gap = abs(a - b)
        dist += weight * gap
    return dist


def judging_function(ingredient, usda_match):
    try:
        ing = _normalize(ingredient)
        usda = _normalize(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_words = _content(ing)
        cov, head = _anchor_score(ing_words, usda)

        # Food-identity gate: preparation equivalence is meaningless if the
        # foods themselves differ (e.g. pecan vs peanut).
        identity = 0.6 * cov + 0.4 * head
        if head < 0.4:
            identity *= 0.6

        vi = _project(ing)
        vu = _project(usda)
        dist = _state_distance(vi, vu)
        state_equiv = 1.0 / (1.0 + 0.6 * dist)

        # Extra USDA qualifiers that are not states and not in ingredient
        # (e.g. specific cuts) mildly reduce equivalence.
        usda_words = _content(usda)
        ing_set = set(ing_words)
        extras = [u for u in usda_words if not any(_dice(u, w) >= 0.6 for w in ing_set)]
        extra_pen = min(0.35, 0.05 * len(extras))

        score = 100.0 * (identity ** 0.8) * state_equiv * (1.0 - extra_pen)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
