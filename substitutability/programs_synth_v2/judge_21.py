import re

# Preservation and Form Match, variant 5: weighted Hamming distance over a
# binary "form signature". Each text sets a bit for a feature when it gives
# positive evidence; a few features have NEGATIVE evidence too (e.g. "fresh"
# asserts not-dried, not-canned). Features where neither side asserts
# anything are skipped. Weights express how strongly a mismatch changes
# water content, concentration or handling. Score = 100 * (1 - d / D).

_FEATURES = [
    # name, weight, positive cues, negative cues
    ("frozen", 0.6, ["frozen", "thawed", "defrosted", "iqf"], ["fresh"]),
    ("canned", 1.6, ["canned", "tinned", "jarred", "jar", "bottled", "can"], ["fresh"]),
    ("dried", 2.4, ["dried", "dehydrated", "sundried", "raisins", "flakes"], ["fresh", "raw"]),
    ("powder", 2.4, ["powder", "powdered", "ground", "granulated", "instant"], ["fresh", "whole"]),
    ("paste", 2.0, ["paste", "puree", "pureed", "tube", "concentrate"], ["whole"]),
    ("liquid", 2.2, ["juice", "broth", "stock", "liquid", "nectar", "drink", "beverage"], ["whole", "segmented"]),
    ("condensed", 1.8, ["condensed", "concentrated", "concentrate", "bouillon", "base"], ["ready"]),
    ("ready", 1.4, ["ready", "soup", "prepared", "reconstituted", "serve"], ["condensed", "mix"]),
    ("mix", 1.8, ["mix", "dry"], ["prepared"]),
    ("syrup", 1.2, ["syrup", "sweetened"], ["unsweetened"]),
    ("brine", 1.2, ["brine", "pickled", "water", "drained"], []),
    ("oilpack", 1.2, ["oil"], []),
]
_MEATS = {"beef", "pork", "turkey", "chicken", "lamb", "meat", "veal"}


def _evidence(words, is_usda):
    ws = set(words)
    out = {}
    for name, _w, pos, neg in _FEATURES:
        p = bool(ws & set(pos))
        n = bool(ws & set(neg))
        if name == "powder" and "ground" in ws and ws & _MEATS:
            p = bool(ws & (set(pos) - {"ground"}))
        if name == "mix" and "dry" in ws and "heat" in ws:
            p = "mix" in ws
        if name == "oilpack":
            # oil as a food (olive oil) is not an oil-pack medium
            p = bool(re.search(r"\bin oil\b|\bpacked in oil\b|\boil pack", " ".join(words)))
        if name == "brine" and "water" in ws and not re.search(r"\bin water\b|\bwater pack", " ".join(words)):
            p = bool(ws & (set(pos) - {"water"}))
        if p:
            out[name] = 1
        elif n:
            out[name] = 0
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower().replace("-", " ")
        usda = str(usda_match or "").lower().replace("-", " ")
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", usda)
        if not iw or not uw:
            return 0.0
        ei, eu = _evidence(iw, False), _evidence(uw, True)
        d = 0.0
        total = 0.0
        for name, w, _p, _n in _FEATURES:
            a, b = ei.get(name), eu.get(name)
            if a is None and b is None:
                continue
            total += w
            if a is None:
                a = 0          # unstated in recipe: assume the plain form
            if b is None:
                b = 0
            if a != b:
                # frozen ingredient described as thawed vs frozen USDA is identical
                d += w
        if total == 0.0:
            return 85.0        # no form information at all: plain vs plain
        score = 100.0 * (1.0 - d / max(total, 3.0))
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
