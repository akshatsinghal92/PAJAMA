# Baseline — Character trigram cosine similarity between the de-noised ingredient
# and USDA strings (fuzzy spelling/variant match). Higher = more substitutable.
def judging_function(ingredient, usda_match):
    try:
        import re
        from collections import Counter
        from math import sqrt

        def denoise(text):
            text = re.sub(r"\([^)]*\)", " ", str(text).lower())
            text = re.sub(r"\d+\s*g\b", " ", text)
            text = re.sub(r"[^a-z\s]", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def trigrams(s):
            s = f"  {s} "
            return Counter(s[i:i + 3] for i in range(len(s) - 2))

        a, b = denoise(ingredient), denoise(usda_match)
        if not a or not b:
            return 1.0
        ta, tb = trigrams(a), trigrams(b)
        keys = set(ta) | set(tb)
        dot = sum(ta[k] * tb[k] for k in keys)
        na = sqrt(sum(v * v for v in ta.values()))
        nb = sqrt(sum(v * v for v in tb.values()))
        if na == 0 or nb == 0:
            return 1.0
        cos = dot / (na * nb)
        return round(10.0 * cos, 4)
    except Exception:
        return 1.0
