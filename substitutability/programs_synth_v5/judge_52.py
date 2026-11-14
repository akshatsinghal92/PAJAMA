import re

_QUALS = [
    ("low sodium", 3.0), ("reduced sodium", 3.0), ("no salt", 2.0), ("unsalted", 2.0),
    ("fat free", 3.0), ("fat-free", 3.0), ("nonfat", 3.0), ("non-fat", 3.0),
    ("low fat", 3.0), ("lowfat", 3.0), ("reduced fat", 3.0), ("light", 2.0),
    ("lite", 2.0), ("sweetened", 2.5), ("unsweetened", 2.0), ("sugar free", 3.0),
    ("sugar-free", 3.0), ("with salt", 2.5), ("salted", 2.5), ("flavored", 2.5),
    ("enriched", 1.5), ("fortified", 2.0), ("added vitamin", 2.0), ("fat added", 3.0),
    ("decaffeinated", 2.5), ("sulfured", 0.0), ("with added", 2.0), ("imitation", 3.0),
    ("substitute", 3.0), ("dietetic", 3.0), ("diet", 2.0), ("low calorie", 3.0),
    ("added sugar", 2.5), ("sodium added", 2.5), ("fried", 1.5), ("breaded", 2.5),
]
_STOP = set("a an and the of or with in for from to g kg oz ml lb lbs cup cups tsp tbsp raw fresh plain regular".split())
_PREP = set("chopped diced sliced minced drained thawed frozen cooked dried fresh large small medium ground whole segments slices rings leaves optional garnish".split())


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return s


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _toks(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s) if w not in _STOP]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _norm(str(ingredient))
        usda_raw = _norm(str(usda_match))
        ing_raw = re.sub(r"^\s*[\d.]+\s*(g|kg|oz|ml|lb)?\b", "", ing_raw)
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0
        # Asymmetric qualifier penalty: only qualifiers in USDA but absent from ingredient
        penalty = 0.0
        for q, w in _QUALS:
            pat = r"\b" + re.escape(q) + r"\b"
            if re.search(pat, usda_raw) and not re.search(pat, ing_raw):
                # avoid double counting e.g. 'sweetened' within 'unsweetened'
                penalty += w
        if re.search(r"\b(\d+)%\s*(lean|fat)", usda_raw) and not re.search(r"\d+%", ing_raw):
            penalty += 0.5
        # Content match: primary food head of USDA should appear in ingredient
        it = set(_toks(ing_raw))
        ut = _toks(usda_raw)
        uset = set(ut)
        core = [t for t in it if t not in _PREP] or list(it)
        cov_ing = sum(1 for t in core if t in uset) / float(len(core))
        ucore = [t for t in ut if t not in _PREP] or ut
        if not ucore:
            return 0.0
        cov_us = sum(1 for t in ucore if t in it) / float(len(ucore))
        match = 0.5 * cov_ing + 0.5 * cov_us
        if cov_ing == 0.0:
            match = 0.0
        # extra descriptor mass in USDA not in ingredient (non-neutral) mildly penalized
        extra = [t for t in ut if t not in it and t not in _PREP]
        neutral = {"raw", "plain", "regular", "whole", "all", "commercially", "prepared", "type", "nfs"}
        extra_n = len([t for t in extra if t not in neutral])
        extra_pen = min(1.5, 0.2 * extra_n)
        score = 10.0 * match - penalty - extra_pen
        return max(-10.0, min(10.0, score))
    except Exception:
        return 0.0
