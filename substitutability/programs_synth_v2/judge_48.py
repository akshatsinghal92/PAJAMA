import re

# Lexical and Token Overlap, variant 8: Smith-Waterman local alignment over
# token sequences.
# Ordered n-gram matching is brittle when USDA fields are inverted
# ("Cheese, cottage"). We therefore build the USDA token sequence in natural
# reading order (later fields first, primary field last) and align it to the
# ingredient token sequence with a local alignment (Smith-Waterman) whose
# match reward depends on the token's role: food-defining words +3,
# ordinary words +2, modifiers +0.6; mismatches -1, gaps -0.6.
# The best local alignment is normalised by the ingredient's self-alignment.

_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with without the a an in as for fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed finely
roughly large small medium nfs ns""".split())
_MODS = set("""raw cooked boiled baked roasted fried grilled steamed frozen canned dried
low fat lowfat nonfat reduced calorie sodium light lean salted sweetened unsweetened
whole plain regular prepared ready heat dry skin not eaten only style made sweet""".split())
_GAP, _MISMATCH = -0.6, -1.0


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _toks(text):
    return [_sing(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _NOISE and len(w) > 1]


def _reward(tok, is_head):
    if is_head:
        return 3.5
    if tok in _MODS:
        return 0.6
    return 2.0


def _align(a, b, head_idx):
    rows, cols = len(a) + 1, len(b) + 1
    H = [[0.0] * cols for _ in range(rows)]
    best = 0.0
    for i in range(1, rows):
        for j in range(1, cols):
            if a[i - 1] == b[j - 1]:
                diag = H[i - 1][j - 1] + _reward(a[i - 1], i - 1 == head_idx)
            else:
                diag = H[i - 1][j - 1] + _MISMATCH
            H[i][j] = max(0.0, diag, H[i - 1][j] + _GAP, H[i][j - 1] + _GAP)
            if H[i][j] > best:
                best = H[i][j]
    return best


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing, flags=re.I)
        a = _toks(ing)
        fields = [_toks(f) for f in re.sub(r"\([^)]*\)", " ", str(usda_match or "")).split(",")]
        fields = [f for f in fields if f]
        if not a or not fields:
            return 0.0
        b = [t for f in reversed(fields) for t in f]
        content = [i for i, t in enumerate(a) if t not in _MODS]
        head_idx = content[-1] if content else len(a) - 1
        s = _align(a, b, head_idx)
        self_s = _align(a, a, head_idx)
        if self_s <= 0:
            return 0.0
        rel = s / self_s
        # mild penalty for long USDA tails that the alignment did not use
        unused = max(0, len(b) - len(a) - 2)
        score = 100.0 * rel - 3.0 * unused
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
