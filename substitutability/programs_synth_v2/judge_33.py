import re

# Specificity and Generality Alignment, variant 1: qualifier accounting.
# The ingredient's qualifiers (modifiers around its head noun) are compared
# to the USDA entry's qualifiers (all descriptor words beyond the primary
# food). Each extra USDA qualifier the ingredient did not imply costs points
# according to how noticeable it is; each ingredient qualifier the USDA entry
# drops also costs. Generic markers (NFS, regular, plain, raw) are rewarded
# when the ingredient itself is unqualified.

_GENERIC = {"nfs", "ns", "regular", "plain", "raw", "all", "purpose", "unprepared",
            "unenriched", "enriched", "commercial", "fresh", "average"}
_NEUTRAL = {"and", "or", "with", "without", "of", "in", "the", "a", "to", "as",
            "not", "made", "from", "type", "style", "includes", "only", "g", "ml"}
_PREP_FREE = {"chopped", "diced", "minced", "sliced", "shredded", "grated", "thawed",
              "segmented", "peeled", "drained", "rinsed", "cubed", "halved"}
# how noticeable an unrequested qualifier is (default 1.0)
_NOTICE = {
    "extra": 1.4, "virgin": 1.0, "low": 1.2, "fat": 1.0, "lowfat": 1.6, "nonfat": 1.8,
    "reduced": 1.4, "calorie": 1.2, "sodium": 0.8, "light": 1.4, "sweetened": 1.6,
    "unsweetened": 1.0, "flavored": 1.6, "vanilla": 1.8, "chocolate": 2.0,
    "strawberry": 1.8, "smoked": 1.8, "spicy": 1.6, "frozen": 1.0, "canned": 1.0,
    "dried": 1.8, "fried": 2.0, "breaded": 2.0, "roasted": 1.4, "cooked": 1.2,
    "heat": 0.4, "dry": 0.6, "skin": 1.2, "eaten": 0.2, "salted": 0.8, "unsalted": 0.6,
    "organic": 0.3, "large": 0.2, "small": 0.2, "medium": 0.2, "whole": 0.6,
    "baby": 0.8, "instant": 1.6, "added": 0.6, "vitamin": 0.3, "fortified": 0.3,
}


def _w(text):
    return re.findall(r"[a-z]+", text.lower())


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
        ing = str(ingredient or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = [_sing(w) for w in _w(ing) if w not in _NEUTRAL and w not in _PREP_FREE]
        fields = [[_sing(w) for w in _w(f)] for f in str(usda_match or "").split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        head = iw[-1]
        i_quals = set(iw[:-1]) - _GENERIC
        # primary food: first field, plus second field if first is a single category word
        primary = list(fields[0])
        rest = fields[1:]
        if len(primary) == 1 and rest and head not in primary:
            primary += rest[0]
            rest = rest[1:]
        elif len(primary) == 1 and rest and set(rest[0]) & set(iw):
            primary += rest[0]
            rest = rest[1:]
        u_words = set(w for w in primary + [x for f in rest for x in f]) - _NEUTRAL

        if head not in u_words:
            return 1.0        # different food altogether: specificity is moot

        u_quals = u_words - {head} - _GENERIC
        extra = u_quals - set(iw)
        dropped = i_quals - u_words

        score = 10.0
        for q in extra:
            score -= 0.9 * _NOTICE.get(q, 1.0)
        for q in dropped:
            score -= 1.3 * _NOTICE.get(q, 1.0)
        # generic markers are good for an unqualified ingredient, bad for a qualified one
        generic_hits = (u_words & _GENERIC) - {"fresh"}
        if not i_quals and generic_hits:
            score += 0.8
        elif i_quals and generic_hits and dropped:
            score -= 0.5
        # perfect qualifier agreement bonus
        if i_quals and not dropped and not extra:
            score += 0.5
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
