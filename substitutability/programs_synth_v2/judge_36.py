import re
import math

# Specificity and Generality Alignment, variant 4: information-content budget.
# Every descriptor carries "information" about which variant of a food is
# meant. Common, low-impact USDA boilerplate (raw, cooked, NFS, solids) has
# little information; rare words (cultivar names, brands, flavours) carry a
# lot. We estimate a word's information content as -log2(p) from a built-in
# relative-frequency prior, then compute:
#   EXCESS  = information in the USDA entry not explained by the ingredient
#   MISSING = information in the ingredient not explained by the USDA entry
# Score = 100 * exp(-(0.22*EXCESS + 0.32*MISSING)).

_PRIOR = {
    # high frequency boilerplate in USDA descriptions (p close to 1 -> low info)
    "raw": 0.6, "cooked": 0.45, "nfs": 0.5, "ns": 0.5, "boiled": 0.3, "drained": 0.3,
    "without": 0.4, "with": 0.4, "salt": 0.35, "added": 0.3, "solids": 0.3,
    "liquids": 0.3, "regular": 0.35, "plain": 0.35, "prepared": 0.3, "fresh": 0.4,
    "frozen": 0.25, "canned": 0.25, "unprepared": 0.3, "commercial": 0.3,
    "heat": 0.3, "dry": 0.25, "moist": 0.25, "meat": 0.25, "only": 0.3,
    "eaten": 0.25, "not": 0.3, "made": 0.25, "from": 0.35, "and": 0.6, "or": 0.6,
    "all": 0.25, "type": 0.3, "style": 0.25, "enriched": 0.25, "mature": 0.2,
    "whole": 0.2, "large": 0.2, "medium": 0.2, "small": 0.2,
    # moderate
    "low": 0.12, "fat": 0.12, "reduced": 0.1, "sodium": 0.1, "light": 0.08,
    "sweetened": 0.08, "unsweetened": 0.08, "skin": 0.1, "roasted": 0.12,
    "baked": 0.12, "fried": 0.1, "lowfat": 0.06, "nonfat": 0.06, "calorie": 0.06,
}
_UNKNOWN_P = 0.03          # unseen words are fairly specific
_STRIP = {"g", "kg", "ml", "oz", "lb", "chopped", "diced", "minced", "sliced", "shredded",
          "grated", "thawed", "segmented", "peeled", "of", "the", "a", "an", "to", "in"}


def _ic(w):
    return -math.log2(_PRIOR.get(w, _UNKNOWN_P))


def _norm(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _explained(w, pool):
    if w in pool:
        return True
    return any(len(w) >= 5 and len(p) >= 5 and (w.startswith(p[:5]) or p.startswith(w[:5])) for p in pool)


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\d+(\.\d+)?", " ", ing)
        iw = [_norm(w) for w in re.findall(r"[a-z]+", ing) if w not in _STRIP]
        uw = [_norm(w) for w in re.findall(r"[a-z]+", str(usda_match or "").lower()) if w not in _STRIP]
        if not iw or not uw:
            return 0.0
        brand = len(re.findall(r"\b[A-Z][A-Z'&]{2,}\b", str(usda_match or "")))
        i_set, u_set = set(iw), set(uw)
        excess = sum(_ic(w) for w in u_set if not _explained(w, i_set))
        missing = sum(_ic(w) for w in i_set if not _explained(w, u_set))
        excess += 2.0 * brand
        # the head noun missing is not a specificity issue but a different food;
        # treat it as maximal missing information
        if not _explained(iw[-1], u_set):
            missing += 12.0
        # generic markers in USDA offset excess for an unqualified ingredient
        if len(iw) == 1 and (u_set & {"nfs", "ns", "regular", "plain"}):
            excess = max(0.0, excess - 1.5)
        score = 100.0 * math.exp(-(0.22 * excess + 0.32 * missing) / 3.0)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
