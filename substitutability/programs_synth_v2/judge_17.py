import re
import math

# Preservation and Form Match, variant 1: physical-form profile comparison.
# Each preservation / delivery form is mapped to a profile of
#   (moisture 0..1, concentration factor, handling class)
# The score combines moisture difference, log concentration ratio and a
# handling-class compatibility term. Frozen <-> fresh is nearly free when
# the recipe thaws it; fresh herb vs dried spice is a strong concentration gap.

_FORMS = {
    "fresh":       (0.85, 1.0, "whole"),
    "raw":         (0.85, 1.0, "whole"),
    "frozen":      (0.83, 1.0, "frozen"),
    "thawed":      (0.84, 1.0, "whole"),
    "canned":      (0.88, 1.0, "packed"),
    "jarred":      (0.86, 1.0, "packed"),
    "bottled":     (0.90, 1.0, "packed"),
    "packed":      (0.88, 1.0, "packed"),
    "dried":       (0.12, 5.0, "dry"),
    "dehydrated":  (0.08, 6.0, "dry"),
    "powder":      (0.05, 8.0, "dry"),
    "ground":      (0.08, 6.0, "dry"),
    "flakes":      (0.10, 5.0, "dry"),
    "paste":       (0.45, 3.0, "paste"),
    "puree":       (0.75, 1.5, "paste"),
    "concentrate": (0.50, 3.5, "liquid"),
    "concentrated": (0.50, 3.5, "liquid"),
    "condensed":   (0.55, 2.0, "liquid"),
    "juice":       (0.90, 1.0, "liquid"),
    "syrup":       (0.30, 2.5, "liquid"),
    "broth":       (0.97, 1.0, "liquid"),
    "stock":       (0.96, 1.1, "liquid"),
    "soup":        (0.90, 1.0, "liquid"),
    "evaporated":  (0.70, 2.0, "liquid"),
    "instant":     (0.05, 8.0, "dry"),
    "dry":         (0.10, 5.0, "dry"),
}

_HANDLING_COMPAT = {
    frozenset(["whole", "frozen"]): 0.9,
    frozenset(["whole", "packed"]): 0.55,
    frozenset(["frozen", "packed"]): 0.5,
    frozenset(["paste", "packed"]): 0.6,
    frozenset(["paste", "liquid"]): 0.45,
    frozenset(["paste", "dry"]): 0.35,
    frozenset(["dry", "whole"]): 0.15,
    frozenset(["dry", "frozen"]): 0.15,
    frozenset(["dry", "liquid"]): 0.2,
    frozenset(["liquid", "whole"]): 0.25,
    frozenset(["liquid", "packed"]): 0.6,
    frozenset(["paste", "whole"]): 0.3,
}


def _profile(words, default_fresh=True):
    hits = [w for w in words if w in _FORMS]
    # "ground" beef/turkey is a cut, not a dry spice
    if "ground" in hits and any(m in words for m in ("beef", "turkey", "pork", "chicken", "lamb", "meat")):
        hits = [h for h in hits if h != "ground"]
    # "dry heat" is a cooking method, not a dried product
    if "dry" in hits and "heat" in words:
        hits = [h for h in hits if h != "dry"]
    if not hits:
        return (_FORMS["fresh"] if default_fresh else None), False
    # use the most transformed form (lowest moisture / highest concentration)
    best = max(hits, key=lambda h: (abs(math.log(_FORMS[h][1])), -_FORMS[h][0]))
    if best in ("fresh", "raw", "thawed") and len(hits) > 1:
        others = [h for h in hits if h not in ("fresh", "raw", "thawed")]
        best = others[0]
    return _FORMS[best], True


def _words(text):
    t = text.lower().replace("-", " ")
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    return re.findall(r"[a-z]+", t)


def judging_function(ingredient, usda_match):
    try:
        iw, uw = _words(str(ingredient or "")), _words(str(usda_match or ""))
        if not iw or not uw:
            return 0.0
        pi, ei = _profile(iw)
        pu, eu = _profile(uw)
        # "frozen ..., thawed" in the ingredient: cook thaws it, frozen USDA fine
        if "thawed" in iw and pu[2] == "frozen":
            pi = pu
        moist_gap = abs(pi[0] - pu[0])
        conc_gap = abs(math.log(pi[1]) - math.log(pu[1]))
        if pi[2] == pu[2]:
            handling = 1.0
        else:
            handling = _HANDLING_COMPAT.get(frozenset([pi[2], pu[2]]), 0.3)
        score = 10.0 * handling * math.exp(-1.4 * moist_gap - 0.6 * conc_gap)
        if not ei and not eu:
            score = min(score, 8.5)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
