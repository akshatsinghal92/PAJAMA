import re

# Preparation-State Equivalence, variant 4: residual-difference analysis.
# Words shared by both texts are cancelled out (they describe the same food
# in the same state). Only the RESIDUAL words that appear on just one side
# are examined. Each residual word carries a "state cost": zero for trivial
# kitchen operations, larger for transformations that change cooking or the
# eating experience. Costs on the USDA side are weighted higher because the
# cook cannot undo something already done to the product.

_COST = {
    # trivially applied / ignorable
    "chopped": 0, "diced": 0, "minced": 0, "sliced": 0, "shredded": 0,
    "grated": 0, "thawed": 0, "defrosted": 0, "cubed": 0, "halved": 0,
    "peeled": 0.2, "segmented": 0, "trimmed": 0, "rinsed": 0, "drained": 0.3,
    "raw": 0.2, "fresh": 0.2, "uncooked": 0.4, "whole": 0.1, "cut": 0,
    "softened": 0.1, "melted": 0.3, "crushed": 0.3, "pitted": 0, "cored": 0,
    # moderate: change handling but often recoverable
    "frozen": 1.2, "blanched": 1.5, "chilled": 0.3, "refrigerated": 0.3,
    "canned": 2.5, "jarred": 2.0, "steamed": 2.5, "boiled": 2.5, "cooked": 3.0,
    "heat": 1.0, "moist": 0.8, "dry": 1.0, "poached": 2.5, "stewed": 3.0,
    "simmered": 2.5, "microwaved": 2.5, "baked": 3.0, "braised": 3.0,
    # strong: change flavour or texture
    "roasted": 3.5, "grilled": 3.5, "broiled": 3.5, "toasted": 3.0,
    "fried": 4.5, "sauteed": 3.5, "breaded": 4.0, "battered": 4.0,
    "smoked": 4.0, "cured": 4.0, "pickled": 4.5, "dried": 4.0,
    "dehydrated": 4.0, "creamed": 3.5, "pureed": 3.0, "mashed": 2.5,
    "powdered": 4.0, "candied": 4.0, "caramelized": 4.0, "charred": 4.0,
}
_USDA_WEIGHT = 1.0
_ING_WEIGHT = 0.7


def _words(text):
    t = text.lower().replace("-", " ")
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    return re.findall(r"[a-z]+", t)


def judging_function(ingredient, usda_match):
    try:
        iw = _words(str(ingredient or ""))
        uw = _words(str(usda_match or ""))
        if not iw or not uw:
            return 0.0
        i_states = {w for w in iw if w in _COST}
        u_states = {w for w in uw if w in _COST}

        shared = i_states & u_states
        only_i = i_states - u_states
        only_u = u_states - i_states

        # "raw"/"fresh"/"uncooked" are synonyms: cancel across sides
        rawish = {"raw", "fresh", "uncooked"}
        if only_i & rawish and only_u & rawish:
            only_i -= rawish
            only_u -= rawish

        cost_u = sum(_COST[w] for w in only_u)
        cost_i = sum(_COST[w] for w in only_i)
        # an ingredient that explicitly says raw/fresh makes USDA cooking worse
        if i_states & rawish:
            cost_u *= 1.3
        # an ingredient that is cooked matched to an explicitly raw entry
        if u_states & rawish and any(_COST[w] >= 2.5 for w in only_i):
            cost_i *= 1.3

        total = _USDA_WEIGHT * cost_u + _ING_WEIGHT * cost_i
        score = 10.0 - 1.4 * total
        # agreement on a non-trivial state is positive evidence
        score += 0.5 * sum(1 for w in shared if _COST[w] >= 1.0)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
