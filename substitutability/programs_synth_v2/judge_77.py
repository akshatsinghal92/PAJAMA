import re
from itertools import permutations

# Modifier and Qualifier Consistency, variant 5: optimal qualifier assignment.
# The qualifiers of each side (all non-head, non-neutral words) are paired
# by a minimum-cost ASSIGNMENT (exhaustive search for small sets, greedy
# beyond). Pair costs:
#   identical or synonym           0.0 / 0.1
#   same dimension, other value    1.0   (a contradiction: red vs green)
#   different dimensions           0.35  (not comparable, mild)
#   left unpaired                  0.25  (unspecified on the other side)
# Dimensions and synonyms come from a compact lexicon. The total cost is
# normalised by the number of qualifiers and turned into a 0-10 score.

_DIM = {}
for _d, _ws in {
    "colour": "red green yellow orange white black brown purple golden",
    "fat": "whole skim nonfat lowfat reduced lean light full",
    "sweet": "sweet sweetened unsweetened semisweet bittersweet",
    "part": "breast thigh wing drumstick leg loin tenderloin rib shoulder brisket liver back",
    "meatcolour": "lightmeat darkmeat",
    "plantpart": "leaf root seed stem stalk peel zest juice bulb",
    "flavour": "vanilla chocolate strawberry honey cinnamon maple lemon coffee peach plain",
    "cheese": "cheddar cottage mozzarella swiss parmesan feta ricotta",
    "dressing": "italian ranch caesar french",
    "pepper": "bell jalapeno serrano habanero poblano chipotle",
    "calorie": "regularcal reducedcal",
    "salt": "salted unsalted",
}.items():
    for _w in _ws.split():
        _DIM[_w] = _d
_SYN = {("skim", "nonfat"), ("lowfat", "reduced"), ("light", "reducedcal"), ("sweet", "sweetened"),
        ("leaf", "stem")}
_NEUTRAL = set("""raw fresh frozen canned cooked uncooked boiled baked roasted fried grilled
steamed drained chopped diced minced sliced shredded grated thawed segmented peeled large
small medium nfs ns regular prepared with without and or of the a an in to from not eaten
only meat broilers fryers mature commercial heat dry moist solids liquids style type made
fat calorie""".split())
_PHRASES = [("light meat", "lightmeat"), ("dark meat", "darkmeat"), ("low fat", "lowfat"),
            ("fat free", "nonfat"), ("reduced calorie", "reducedcal"), ("low calorie", "reducedcal"),
            ("reduced fat", "reduced"), ("skin not eaten", " ")]


def _prep(text):
    t = " " + re.sub(r"[^a-z ]", " ", text.lower()) + " "
    for a, b in _PHRASES:
        t = t.replace(" " + a + " ", " " + b + " ")
    return t


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _cost(a, b):
    if a == b:
        return 0.0
    if (a, b) in _SYN or (b, a) in _SYN:
        return 0.1
    da, db = _DIM.get(a), _DIM.get(b)
    if da and da == db:
        return 1.0
    return 0.35


def _assign(A, B):
    """Minimum total cost matching between lists A and B (unpaired = 0.25)."""
    if len(A) > len(B):
        A, B = B, A
    if not A:
        return 0.25 * len(B)
    best = None
    if len(B) <= 6:
        for perm in permutations(range(len(B)), len(A)):
            c = sum(min(_cost(A[i], B[j]), 0.25 * 2) for i, j in enumerate(perm))
            c += 0.25 * (len(B) - len(A))
            if best is None or c < best:
                best = c
        return best
    used, total = set(), 0.0
    for a in A:
        j = min((j for j in range(len(B)) if j not in used), key=lambda j: _cost(a, B[j]))
        used.add(j)
        total += _cost(a, B[j])
    return total + 0.25 * (len(B) - len(A))


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        iw = [_sing(w) for w in _prep(ing).split()]
        uw = [_sing(w) for w in _prep(str(usda_match or "")).split()]
        if not iw or not uw:
            return 0.0
        content = [w for w in iw if w not in _NEUTRAL] or iw
        u_set = set(uw)
        head = next((w for w in reversed(content) if w in u_set), content[-1])
        qi = [w for w in content if w != head and (w in _DIM or len(w) > 2)][:5]
        qu = [w for w in uw if w != head and w not in _NEUTRAL and w in _DIM][:6]
        # only qualifiers of a known dimension on the USDA side are compared;
        # other USDA words are food names or boilerplate, not qualifiers
        if not qi and not qu:
            return 9.0
        cost = _assign(qi, qu)
        n = max(len(qi), len(qu))
        contradictions = sum(1 for a in qi for b in qu if _cost(a, b) == 1.0)
        score = 10.0 - 4.0 * cost / n - 1.5 * contradictions
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
