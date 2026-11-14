import re

# Lexical and Token Overlap, variant 5: landing-field weighted coverage.
# WHERE an ingredient token lands inside the USDA description matters: a
# match in the primary field (or the qualifier right after a one-word
# category header) is food-defining; a match in a trailing descriptor field
# is usually a modifier. Each ingredient token earns the weight of the
# earliest USDA field that contains it (1.0, 0.75, 0.45, 0.3 ...). The
# coverage score is combined with the Szymkiewicz-Simpson overlap
# coefficient of the ingredient vs the "identity zone" (first 1-2 fields),
# and unmatched words in the identity zone are subtracted (they name
# something the recipe did not ask for).

_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with without the a an in as for fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed finely
roughly large small medium nfs ns""".split())
_FIELD_W = [1.0, 0.75, 0.45, 0.3, 0.2]


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _words(text):
    return [_sing(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _NOISE and len(w) > 1]


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing, flags=re.I)
        itoks = _words(ing)
        fields = [_words(f) for f in re.sub(r"\([^)]*\)", " ", str(usda_match or "")).split(",")]
        fields = [f for f in fields if f]
        if not itoks or not fields:
            return 0.0
        # identity zone: first field, plus the second when the first is a 1-word header
        zone = set(fields[0])
        zone_fields = 1
        if len(fields[0]) == 1 and len(fields) > 1:
            zone |= set(fields[1])
            zone_fields = 2

        # landing-field coverage, head token weighted double
        total_w = 0.0
        got = 0.0
        for idx, tok in enumerate(itoks):
            tw = 2.0 if idx == len(itoks) - 1 else 1.0
            total_w += tw
            for fi, f in enumerate(fields):
                if tok in f:
                    # fields inside the identity zone all count as primary
                    eff = 0 if fi < zone_fields else fi - zone_fields + 1
                    got += tw * _FIELD_W[min(eff, len(_FIELD_W) - 1)]
                    break
        coverage = got / total_w if total_w else 0.0

        iset = set(itoks)
        inter = iset & zone
        ssc = len(inter) / float(min(len(iset), len(zone))) if iset and zone else 0.0
        unmatched_zone = len(zone - iset)

        score = 60.0 * coverage + 40.0 * ssc - 8.0 * unmatched_zone
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
