import re

# Specificity and Generality Alignment, variant 7: F-beta over qualifier
# character 4-grams.
# Qualifier text = everything except the shared head food. We measure
#   precision : share of USDA qualifier 4-grams that the ingredient implied
#               (low precision = USDA adds unrequested detail)
#   recall    : share of ingredient qualifier 4-grams found in the USDA entry
#               (low recall = USDA dropped a variant the cook asked for)
# Character 4-grams tolerate spelling/morphology variants (lowfat / low fat,
# sweetened / sweet). Boilerplate qualifiers are removed first, so a generic
# USDA entry for an unqualified ingredient gets full precision.
# Recall weighs more (beta = 1.5): losing a stated variant is more noticeable.

_BOILER = re.compile(
    r"\b(raw|nfs|ns|regular|plain|fresh|unprepared|commercial|all|purpose|"
    r"includes|usda|commodity|average|mature|whole|large|medium|small|"
    r"chopped|diced|minced|sliced|shredded|grated|thawed|segmented|peeled|drained|"
    r"and|or|of|with|the|a|an|in|to|for|from|as|type|style|made)\b")
_BETA = 1.5


def _grams(text):
    t = re.sub(r"\s+", " ", text).strip()
    out = {}
    for w in t.split():
        w = "_" + w + "_"
        if len(w) < 4:
            out[w] = out.get(w, 0) + 1
            continue
        for i in range(len(w) - 3):
            g = w[i:i + 4]
            out[g] = out.get(g, 0) + 1
    return out


def _overlap(a, b):
    return sum(min(v, b.get(k, 0)) for k, v in a.items())


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        iw = [_sing(w) for w in re.findall(r"[a-z]+", ing)]
        uw = [_sing(w) for w in re.findall(r"[a-z]+", usda)]
        if not iw or not uw:
            return 0.0
        iw_c = [w for w in iw if not _BOILER.fullmatch(w)]
        if not iw_c:
            iw_c = iw[-1:]
        head = iw_c[-1]
        if head not in uw:
            return 0.0 if not any(head[:4] == w[:4] for w in uw) else 15.0
        i_qual = " ".join(w for w in iw_c if w != head)
        u_qual = " ".join(w for w in uw if w != head and not _BOILER.fullmatch(w))
        gi, gu = _grams(i_qual), _grams(u_qual)
        ni, nu = sum(gi.values()), sum(gu.values())
        ov = _overlap(gi, gu)
        precision = ov / nu if nu else 1.0
        recall = ov / ni if ni else 1.0
        if precision == 0 and recall == 0:
            f = 0.0
        else:
            b2 = _BETA * _BETA
            f = (1 + b2) * precision * recall / (b2 * precision + recall)
        # long tails of extra qualifiers are increasingly noticeable
        extra_words = len([w for w in u_qual.split() if w not in i_qual.split()])
        score = 100.0 * f - 4.0 * max(0, extra_words - 1)
        # generic markers are positive evidence for an unqualified ingredient
        if not i_qual and re.search(r"\bnfs\b|\bregular\b|\bplain\b", usda):
            score += 5.0
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
