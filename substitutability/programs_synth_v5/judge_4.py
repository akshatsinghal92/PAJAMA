import re
import math

_NOISE = {"fresh", "frozen", "chopped", "sliced", "diced", "minced", "warmed", "thawed",
          "optional", "large", "small", "medium", "and", "or", "of", "with", "the", "a",
          "from", "g", "kg", "oz", "ml", "lb", "nfs", "ns", "as", "to", "all", "whole"}


def _norm(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxzh":
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _words(s):
    return [_norm(w) for w in re.findall(r"[a-z]+", s.lower()) if w not in _NOISE]


def _lcs(a, b):
    n, m = len(a), len(b)
    if not n or not m:
        return 0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(m):
            if a[i] == b[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])
    return dp[n][m]


def _grams(w):
    w = "#" + w + "#"
    return set(w[i:i + 3] for i in range(len(w) - 2))


def _fuzzy(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / float(len(ga | gb))


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or ""))
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b", " ", ing.lower())
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        iw = _words(ing.split(",")[0])
        if not iw:
            iw = _words(ing)
        # USDA written inverted ("Oil, olive"): build a natural-order variant too
        parts = [p for p in usda.split(",")]
        uw_fwd = _words(" ".join(parts))
        uw_rev = _words(" ".join(reversed(parts[:2]))) + _words(" ".join(parts[2:]))
        if not iw or not uw_fwd:
            return 0.0

        best = 0.0
        for uw in (uw_fwd, uw_rev):
            l = _lcs(iw, uw)
            recall = l / float(len(iw))
            precision = l / float(len(uw))
            # head-noun: last ingredient word vs best fuzzy match among USDA words
            hf = max(_fuzzy(iw[-1], u) for u in uw)
            # whole-phrase exact containment bonus
            joined_i = " ".join(iw)
            joined_u = " ".join(uw)
            contig = 1.0 if joined_i in joined_u else 0.0
            # USDA surplus penalty: extra words in the first two comma segments
            core_u = _words(" ".join(parts[:2]))
            surplus = len([w for w in core_u if w not in iw])
            s = 5.0 * recall + 2.0 * precision + 2.0 * hf + 1.0 * contig - 0.8 * min(surplus, 4)
            if recall < 0.5 or hf < 0.5:
                s -= 2.0
            best = max(best, s)
        return max(0.0, min(10.0, best))
    except Exception:
        return 0.0
