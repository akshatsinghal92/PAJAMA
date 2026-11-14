import re
import math

# Modifier and Qualifier Consistency, variant 2: contrast-pair conflict graph
# with implied defaults.
# A table of CONTRAST PAIRS (red/green, whole/skim, breast/thigh, sweet/
# unsweetened, light meat/dark meat, bell/jalapeno ...) each with a
# noticeability weight. Every modifier on one side is checked against every
# modifier on the other side; contrasting pairs add conflict weight.
# Unqualified ingredients carry IMPLIED DEFAULTS for a few dimensions
# (dairy/dressings default to regular fat, regular calorie; beverages and
# yogurts default to unflavoured), and a USDA qualifier that contradicts an
# implied default adds half the conflict weight. Score = 100*exp(-0.45*C)
# with a small bonus for explicitly shared discriminating modifiers.

_CONTRAST = {}
for group, w in [
    (["red", "green", "yellow", "orange", "white", "purple", "black"], 1.6),
    (["whole", "skim", "nonfat", "lowfat", "low fat", "reduced fat", "2%", "1%", "fat free"], 1.8),
    (["sweetened", "unsweetened"], 1.8),
    (["sweet", "hot", "spicy"], 1.4),
    (["breast", "thigh", "wing", "drumstick", "leg", "back", "neck"], 2.2),
    (["light meat", "dark meat"], 2.0),
    (["skin eaten", "skin not eaten"], 1.2),
    (["loin", "shoulder", "rib", "brisket", "round", "chuck", "flank", "sirloin"], 1.6),
    (["bell", "jalapeno", "chili", "serrano", "habanero", "poblano"], 1.8),
    (["russet", "red skin", "yukon", "sweet potato"], 1.2),
    (["basmati", "jasmine", "arborio", "brown", "wild"], 1.3),
    (["vanilla", "chocolate", "strawberry", "plain", "coffee", "lemon", "peach"], 2.0),
    (["cheddar", "cottage", "mozzarella", "swiss", "parmesan", "feta", "ricotta", "cream cheese"], 2.4),
    (["italian", "ranch", "caesar", "french", "thousand island", "blue cheese"], 2.0),
    (["regular", "reduced calorie", "light", "lite", "diet"], 1.5),
    (["salted", "unsalted"], 1.0),
    (["dark", "milk", "white"], 1.2),
    (["seed", "leaf", "root", "juice", "peel", "zest"], 1.8),
]:
    for a in group:
        for b in group:
            if a != b:
                _CONTRAST[(a, b)] = w
# nested / compatible variants that should not conflict
for a, b in [("lowfat", "low fat"), ("nonfat", "skim"), ("fat free", "nonfat"), ("fat free", "skim"),
             ("light", "lite"), ("reduced calorie", "light"), ("reduced calorie", "lite"),
             ("sweet", "sweetened"), ("hot", "spicy"), ("1%", "lowfat"), ("1%", "low fat")]:
    _CONTRAST.pop((a, b), None)
    _CONTRAST.pop((b, a), None)

_MODS = sorted({m for pair in _CONTRAST for m in pair}, key=len, reverse=True)
_DEFAULTS = [
    (r"\b(milk|cheese|yogurt|cottage|cream|dressing|mayonnaise)\b", ["regular", "whole"]),
    (r"\b(yogurt|milk|cereal|tea)\b", ["plain"]),
]


def _mods(text):
    t = " " + re.sub(r"[^a-z0-9% ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    found = []
    for m in _MODS:
        if " " + m + " " in t:
            found.append(m)
            t = t.replace(" " + m + " ", " ")
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        # normalise USDA skin phrasing
        usda_n = usda.replace("skin not eaten", "skinnoteaten")
        mi = _mods(ing)
        mu = _mods(usda_n)
        if "skinnoteaten" in usda_n:
            mu.append("skin not eaten")
        if re.search(r"\bskin\b", ing) and "skin not eaten" not in mi:
            mi.append("skin eaten")
        conflict = 0.0
        for a in mi:
            for b in mu:
                conflict += _CONTRAST.get((a, b), 0.0)
        # implied defaults for unqualified ingredients
        for rx, defaults in _DEFAULTS:
            if re.search(rx, ing):
                for d in defaults:
                    if not any((d, x) in _CONTRAST or (x, d) in _CONTRAST for x in mi if x != d) and d not in mi:
                        for b in mu:
                            conflict += 0.5 * _CONTRAST.get((d, b), 0.0)
        shared = [m for m in mi if m in mu]
        score = 100.0 * math.exp(-0.45 * conflict) + 3.0 * len(shared)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
