import re
import math

# Specificity and Generality Alignment, variant 2: specificity-depth estimate.
# Rather than matching qualifier words one by one, each text is assigned a
# numeric SPECIFICITY DEPTH:
#   ingredient : number of informative modifiers before the head noun
#   USDA entry : informative descriptor fields after the primary food,
#                + 2 for an upper-case brand name, + 1 for flavour fields,
#                - 1 for explicit generic markers (NFS, regular, plain).
# Informative = not a trivial prep / measure / packaging word.
# The score is a Gaussian of the depth gap, with a steeper slope when the
# USDA entry is LESS specific than a qualified ingredient (lost variant),
# then gated by a cheap identity check on the head noun prefix.

_TRIVIAL = set("""g kg ml oz lb cup cups tbsp tsp fresh chopped diced minced sliced
shredded grated thawed segmented peeled drained rinsed large small medium raw
and or of with the a an to in for from as made type style only""".split())
_GENERIC_MARK = {"nfs", "ns", "regular", "plain", "unspecified", "all", "general"}
_FLAVOURS = {"vanilla", "chocolate", "strawberry", "banana", "lemon", "orange", "honey",
             "cinnamon", "garlic", "onion", "bbq", "barbecue", "ranch", "italian", "mint",
             "maple", "peach", "raspberry", "blueberry", "cherry", "coconut", "spicy"}


def _ing_depth(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\d+(\.\d+)?", " ", t)
    words = [w for w in re.findall(r"[a-z]+", t) if w not in _TRIVIAL]
    if not words:
        return 0, ""
    return len(words) - 1, words[-1]


def _usda_depth(text):
    raw = str(text)
    brand = 2 if re.search(r"\b[A-Z][A-Z'&]{2,}\b", raw) else 0
    fields = [re.findall(r"[a-z]+", f) for f in raw.lower().split(",")]
    fields = [[w for w in f if w not in _TRIVIAL] for f in fields]
    fields = [f for f in fields if f]
    if not fields:
        return 0, []
    depth = 0.0
    first = fields[0]
    depth += max(0, len(first) - 1) * 0.8          # multi-word primary is already specific
    for f in fields[1:]:
        if set(f) & _GENERIC_MARK:
            depth -= 1.0
            continue
        depth += 1.0
        if set(f) & _FLAVOURS:
            depth += 0.6
    depth += brand
    # a single-word category primary followed by the actual food is not depth
    if len(first) == 1 and len(fields) > 1:
        depth -= 1.0
    return max(0.0, depth), [w for f in fields for w in f]


def judging_function(ingredient, usda_match):
    try:
        if not str(ingredient or "").strip() or not str(usda_match or "").strip():
            return 0.0
        di, head = _ing_depth(str(ingredient))
        du, uwords = _usda_depth(str(usda_match))
        if not head or not uwords:
            return 0.0
        key = head[:5].rstrip("s")
        found = any(w.startswith(key) or key.startswith(w[:5]) for w in uwords if len(w) >= 3)
        gap = du - di
        if gap >= 0:
            sigma = 1.7          # USDA added detail: tolerable up to a point
        else:
            sigma = 1.1          # USDA dropped the ingredient's variant
        score = 100.0 * math.exp(-(gap * gap) / (2.0 * sigma * sigma))
        if not found:
            score *= 0.25
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
