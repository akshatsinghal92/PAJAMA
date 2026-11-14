import re

# qualifier groups: (pattern, penalty weight, group key)
_QUALS = [
    (r"\b(low|reduced|less|no)[\s-]*(sodium|salt)\b|\bunsalted\b|\bwithout salt\b", 2.5, "sodium_lo"),
    (r"\b(fat[\s-]*free|non[\s-]*fat|nonfat|skim)\b", 3.0, "fatfree"),
    (r"\blow[\s-]*fat\b|\breduced[\s-]*fat\b|\blite\b|\blight\b", 2.5, "lowfat"),
    (r"\bsugar[\s-]*free\b|\bno sugar\b|\bunsweetened\b|\breduced sugar\b|\blow sugar\b", 3.0, "sugarfree"),
    (r"\bsweetened\b|\bwith sugar\b|\bsyrup\b|\bglazed\b", 2.0, "sweet"),
    (r"\bsalted\b|\bwith salt\b|\bsalt added\b", 2.0, "salt"),
    (r"\bflavou?red\b|\bartificial(ly)?\b", 1.5, "flavor"),
    (r"\benriched\b|\bfortified\b|\bwith added\b|\badded (vitamin|calcium|iron)", 1.5, "fort"),
    (r"\b(decaffeinated|decaf|caffeine[\s-]*free)\b", 2.5, "decaf"),
    (r"\b(smoked|roasted|toasted|fried|breaded|candied|pickled|cured|seasoned)\b", 1.2, "proc"),
    (r"\b(imitation|substitute|analog)\b", 2.5, "imit"),
]
_NEUTRAL = {"raw", "plain", "regular", "nfs", "fresh", "whole", "ground", "dried", "canned", "frozen", "drained", "solids"}


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|gram|grams|kg|oz|ml|lb)\b", " ", s)
    return s


def _tokens(s):
    return [t for t in re.findall(r"[a-z]+", s) if len(t) > 2]


def _stem(t):
    for suf in ("ies", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        # asymmetric qualifier penalty: only those in USDA but not in ingredient
        penalty = 0.0
        for pat, w, key in _QUALS:
            in_u = re.search(pat, usda) is not None
            in_i = re.search(pat, ing) is not None
            if in_u and not in_i:
                penalty += w
            elif in_i and not in_u:
                penalty += w * 0.4  # missing a stated qualifier is also noticeable, but less
        # content overlap
        it = set(_stem(t) for t in _tokens(ing))
        ut = set(_stem(t) for t in _tokens(usda))
        it_c = it - _NEUTRAL
        ut_c = ut - _NEUTRAL
        if not it_c:
            it_c = it
        cover = len(it_c & ut_c) / float(len(it_c)) if it_c else 0.0
        # extra unmatched descriptors in USDA count as potential unstated additions
        extra = ut_c - it_c
        extra_pen = min(len(extra), 6) * 0.25
        # primary food head match
        head = _stem(_tokens(usda.split(",")[0])[0]) if _tokens(usda.split(",")[0]) else ""
        head_hit = 1.0 if head and head in it else 0.0
        score = 6.0 * cover + 2.5 * head_hit + 1.5 - penalty - extra_pen
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
