import re
from difflib import SequenceMatcher

# Processing and Additive Difference, variant 7: edit-script analysis.
# The ingredient and the USDA entry (rewritten into natural reading order)
# are aligned as token sequences with difflib. The resulting edit script
# tells us exactly which spans the USDA entry INSERTS relative to the plain
# ingredient and which it REPLACES. Each inserted / replacing span is then
# costed by what it contains: additive vocabulary (salt, sugar, sauce,
# breading, seasoning, flavour, oil), compound joins ("and X", "with X"),
# or harmless boilerplate (raw, NFS, drained, cooked). Deleted spans
# (ingredient words the entry lacks) are costed lightly.

_ADDITIVE_COST = {
    "salt": 1.8, "salted": 1.8, "sugar": 2.2, "sweetened": 2.2, "syrup": 2.0, "honey": 1.8,
    "candied": 2.4, "glazed": 2.2, "frosted": 2.4, "sauce": 3.0, "gravy": 3.0,
    "dressing": 2.6, "breaded": 3.0, "battered": 3.0, "coated": 2.5, "crumbs": 2.0,
    "seasoned": 2.2, "seasoning": 2.2, "spiced": 2.0, "blend": 1.8, "mix": 1.8,
    "flavored": 2.4, "flavoured": 2.4, "smoked": 2.2, "cured": 2.0, "pickled": 2.2,
    "marinated": 2.4, "fried": 2.0, "oil": 1.6, "butter": 1.8, "buttered": 2.0,
    "cheese": 2.0, "cream": 1.6, "creamed": 2.0, "pepper": 1.4, "garlic": 1.0,
    "onion": 1.0, "spicy": 2.2, "bbq": 2.4, "barbecue": 2.4, "teriyaki": 2.6,
    "vanilla": 2.0, "chocolate": 2.6, "cinnamon": 1.8, "strawberry": 2.2, "maple": 2.0,
}
_HARMLESS = set("""raw nfs ns drained cooked boiled steamed unprepared unheated plain
regular fresh frozen canned solids liquids heat dry moist only meat whole mature
commercial enriched fortified unenriched separable lean trimmed skin eaten not peel
without unsalted unsweetened all purpose type style""".split())
_NOISE = set("""g kg ml oz lb of the a an in to for from as chopped diced minced sliced
shredded grated thawed segmented peeled rinsed cubed large small medium""".split())
_JOINS = {"and", "with", "&"}


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3 and w not in ("solids", "liquids"):
        return w[:-1]
    return w


def _seq(text, natural_order):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    if not natural_order:
        t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t).split(",")[0]
        return [_sing(w) for w in re.findall(r"[a-z&]+", t) if w not in _NOISE]
    fields = [[_sing(w) for w in re.findall(r"[a-z&]+", f) if w not in _NOISE] for f in t.split(",")]
    fields = [f for f in fields if f]
    out = []
    for f in reversed(fields):
        out.extend(f)
    return out


def _span_cost(span):
    cost = 0.0
    negate = False
    for i, w in enumerate(span):
        if w in ("without", "no", "unsalted", "unsweetened"):
            negate = True
            continue
        if w in _HARMLESS:
            continue
        if w in _JOINS:
            nxt = span[i + 1] if i + 1 < len(span) else ""
            if nxt and nxt not in _HARMLESS:
                cost += 1.0
            continue
        c = _ADDITIVE_COST.get(w, _ADDITIVE_COST.get(w.rstrip("s"), 0.5))
        cost += 0.0 if negate else c
        negate = False
    return cost


def judging_function(ingredient, usda_match):
    try:
        a = _seq(str(ingredient or ""), False)
        b = _seq(str(usda_match or ""), True)
        if not a or not b:
            return 0.0
        sm = SequenceMatcher(None, a, b, autojunk=False)
        inserted = 0.0
        deleted = 0.0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "insert":
                inserted += _span_cost(b[j1:j2])
            elif tag == "replace":
                inserted += _span_cost(b[j1:j2])
                deleted += 0.4 * _span_cost(a[i1:i2])
            elif tag == "delete":
                deleted += 0.4 * _span_cost(a[i1:i2])
        score = 10.0 - 1.15 * inserted - 0.8 * deleted
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
