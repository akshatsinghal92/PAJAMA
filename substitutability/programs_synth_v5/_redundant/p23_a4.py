import re

_UNITS = set("g kg mg oz lb lbs ml l cup cups tbsp tsp piece pieces".split())
_PREP = set("sliced diced chopped minced grated shredded crushed cubed cubes chunks chunk fresh thawed divided optional taste garnish tube from for to of and or the a an with in plus about ripe large small medium whole fillets fillet equal parts part raw cooked".split())
# words that change the food's identity/form when present on only one side
_SHIFT = set("juice oil crackers souffle syrup leaves leaf powder dried canned pickled candied flour starch paste frozen smoked fried mountain liver giblets neck skin bone bones broth stock vegetables".split())


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(s):
    s = re.sub(r"\([^)]*\)", " ", (s or "").lower())
    s = re.sub(r"\b\d+(\.\d+)?(g|kg|mg|oz|lb|ml)?\b", " ", s)
    return [_norm(w) for w in re.findall(r"[a-z]+", s)]


def judging_function(ingredient, usda_match):
    try:
        iw_full = _words(ingredient)
        uw_full = _words(usda_match)
        ing = [w for w in iw_full if w not in _UNITS and w not in _PREP]
        prim = [w for w in _words((usda_match or "").split(",")[0]) if w not in _PREP]
        usda = [w for w in uw_full if w not in _UNITS and w not in _PREP]
        if not ing or not usda:
            return 0.0
        I, U, P = set(ing), set(usda), set(prim)
        inter = I & U
        # Tier from set relation
        if I == P or I == U:
            tier = 8.0
        elif P and P <= I and (I - P) <= U | set():
            tier = 7.0
        elif I <= U:
            tier = 6.0
        elif P and P <= I:
            tier = 5.0
        elif inter:
            tier = 2.0 + 2.0 * len(inter) / len(I | U) * 2
        else:
            tier = 0.0
        # Modifier adjustments, counted as unmatched descriptors on either side
        only_u = U - I
        only_i = I - U
        tier -= 0.35 * len(only_u - _SHIFT)
        tier -= 0.35 * len(only_i)
        tier -= 2.5 * len(only_u & _SHIFT)
        tier -= 2.0 * len(only_i & _SHIFT)
        # head-noun alignment: last meaningful ingredient word vs first USDA primary word
        if ing[-1] in P:
            tier += 1.0
        elif prim and prim[0] in I:
            tier += 0.5
        return tier
    except Exception:
        return 0.0
