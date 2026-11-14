import re

# Preparation-State Equivalence, variant 8: noisy-OR "would an eater notice?"
# Every unmatched preparation cue is an independent cause that might make the
# dish noticeably different in taste, texture or appearance, or force a
# different cooking procedure. Each cue has a probability of causing a
# noticeable change. P(noticeable) = 1 - prod(1 - p_i). The score is the
# probability that NOTHING noticeable changes, on a 0-100 scale.

# (texture, taste, appearance, procedure) change probabilities per cue
_CUE = {
    "cooked":   (0.55, 0.35, 0.40, 0.55), "boiled": (0.55, 0.30, 0.35, 0.50),
    "steamed":  (0.50, 0.25, 0.30, 0.50), "baked": (0.55, 0.45, 0.45, 0.55),
    "roasted":  (0.55, 0.55, 0.50, 0.55), "grilled": (0.55, 0.55, 0.55, 0.55),
    "broiled":  (0.55, 0.50, 0.50, 0.55), "fried": (0.70, 0.65, 0.65, 0.65),
    "breaded":  (0.70, 0.55, 0.70, 0.65), "smoked": (0.30, 0.70, 0.40, 0.30),
    "canned":   (0.45, 0.35, 0.30, 0.35), "frozen": (0.20, 0.05, 0.05, 0.15),
    "dried":    (0.70, 0.45, 0.50, 0.55), "pickled": (0.40, 0.75, 0.30, 0.30),
    "creamed":  (0.65, 0.45, 0.60, 0.45), "pureed": (0.70, 0.15, 0.60, 0.40),
    "mashed":   (0.65, 0.15, 0.55, 0.40), "toasted": (0.45, 0.45, 0.40, 0.30),
    "stewed":   (0.55, 0.40, 0.40, 0.50), "braised": (0.60, 0.45, 0.45, 0.55),
    "sweetened": (0.05, 0.50, 0.05, 0.10), "salted": (0.05, 0.40, 0.05, 0.10),
    "heat":     (0.20, 0.10, 0.10, 0.20), "juice": (0.80, 0.30, 0.80, 0.70),
    "powder":   (0.80, 0.30, 0.70, 0.60),
    # trivially applied - near zero
    "chopped":  (0.02, 0.0, 0.02, 0.02), "diced": (0.02, 0.0, 0.02, 0.02),
    "minced":   (0.03, 0.0, 0.02, 0.02), "sliced": (0.02, 0.0, 0.02, 0.02),
    "shredded": (0.03, 0.0, 0.03, 0.02), "thawed": (0.01, 0.0, 0.0, 0.01),
    "raw":      (0.0, 0.0, 0.0, 0.0), "fresh": (0.0, 0.0, 0.0, 0.0),
    "uncooked": (0.0, 0.0, 0.0, 0.0), "segmented": (0.02, 0.0, 0.02, 0.0),
}
_RAWISH = {"raw", "fresh", "uncooked"}


def _cues(text):
    t = text.lower().replace("-", " ")
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    words = re.findall(r"[a-z]+", t)
    out = set()
    for w in words:
        if w in _CUE:
            out.add(w)
        elif w.endswith("ed") and w[:-1] in _CUE:
            out.add(w[:-1])
    if "dry" in words and "heat" in words:
        out.add("roasted")
    return out


def _p_change(cue, raw_requested):
    t, s, a, p = _CUE[cue]
    p_any = 1.0 - (1 - t) * (1 - s) * (1 - a) * (1 - p)
    if raw_requested and cue not in _RAWISH and p_any > 0.3:
        p_any = min(0.99, p_any * 1.15)
    return p_any


def judging_function(ingredient, usda_match):
    try:
        ci = _cues(str(ingredient or ""))
        cu = _cues(str(usda_match or ""))
        if not str(ingredient or "").strip() or not str(usda_match or "").strip():
            return 0.0
        raw_req = bool(ci & _RAWISH) or not (ci - _RAWISH)
        unmatched = (ci ^ cu) - _RAWISH
        # a raw request against an explicitly cooked entry: the "raw" itself conflicts
        p_same = 1.0
        for c in unmatched:
            pc = _p_change(c, raw_req and c in cu)
            # cues only in the ingredient are partly achievable by the cook
            if c in ci and c not in cu:
                pc *= 0.6
            p_same *= (1.0 - pc)
        # matching heavy cues are mild positive evidence
        shared_heavy = [c for c in (ci & cu) if _p_change(c, False) > 0.3]
        p_same = min(1.0, p_same + 0.03 * len(shared_heavy))
        if not ci and not cu:
            p_same *= 0.95
        return round(100.0 * p_same, 2)
    except Exception:
        return 0.0
