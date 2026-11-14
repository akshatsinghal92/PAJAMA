import re
import math

# Lexical and Token Overlap, variant 2: BLEU-style n-gram agreement.
# The USDA description is rewritten into natural word order by reading its
# comma fields from most specific to least ("Cheese, cottage, low fat" ->
# "low fat cottage cheese"), so ordered n-grams become comparable with the
# recipe phrase. We then compute clipped unigram and bigram precision in
# BOTH directions (USDA vs ingredient and ingredient vs USDA), combine them
# with a geometric mean (smoothed), and apply a BLEU brevity/length penalty
# so a long USDA entry that merely contains the ingredient words scores less
# than a tight match.

_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with the a an in as for fresh chopped diced minced
sliced shredded grated thawed segmented peeled drained rinsed cubed finely roughly
large small medium nfs ns""".split())


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _clean_words(text):
    return [_sing(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _NOISE and len(w) > 1]


def _ing_seq(text):
    t = re.sub(r"\([^)]*\)", " ", text).split(",")[0]
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t, flags=re.I)
    return _clean_words(t)


def _usda_seq(text):
    fields = [_clean_words(f) for f in re.sub(r"\([^)]*\)", " ", text).split(",")]
    fields = [f for f in fields if f]
    seq = []
    for f in reversed(fields):
        seq.extend(f)
    return seq


def _ngrams(seq, n):
    out = {}
    for i in range(len(seq) - n + 1):
        g = tuple(seq[i:i + n])
        out[g] = out.get(g, 0) + 1
    return out


def _precision(cand, ref, n):
    c, r = _ngrams(cand, n), _ngrams(ref, n)
    total = sum(c.values())
    if total == 0:
        return None
    clipped = sum(min(v, r.get(g, 0)) for g, v in c.items())
    return (clipped + 0.1) / (total + 0.1)      # light smoothing


def _bleu(cand, ref):
    p1 = _precision(cand, ref, 1) or 0.0
    p2 = _precision(cand, ref, 2)
    if p2 is None:
        geo = p1
    else:
        geo = math.sqrt(p1 * p2)
    bp = 1.0 if len(cand) >= len(ref) else math.exp(1 - len(ref) / float(max(len(cand), 1)))
    return bp * geo


def judging_function(ingredient, usda_match):
    try:
        ing = _ing_seq(str(ingredient or ""))
        usda = _usda_seq(str(usda_match or ""))
        if not ing or not usda:
            return 0.0
        forward = _bleu(usda, ing)     # how much of USDA is supported by the ingredient
        backward = _bleu(ing, usda)    # how much of the ingredient is covered
        score = 2.0 * forward * backward / (forward + backward) if forward + backward else 0.0
        # the ingredient's last word is the food head; missing it is fatal for overlap
        if ing[-1] not in usda:
            score *= 0.35
        return round(100.0 * max(0.0, min(1.0, score)), 2)
    except Exception:
        return 0.0
