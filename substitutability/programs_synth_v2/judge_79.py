import re
import math

# Modifier and Qualifier Consistency, variant 7: Bayesian log-likelihood
# ratio accumulation.
# Hypothesis H: "the USDA entry's qualifiers are consistent with the
# ingredient's". Each piece of evidence carries a log-likelihood ratio
# log P(e|H) / P(e|not H):
#   qualifier matched on both sides         -> positive LLR
#   same-dimension contradiction            -> strongly negative LLR
#   ingredient qualifier missing in USDA    -> mildly negative LLR
#   USDA qualifier not mentioned by recipe  -> slightly negative LLR
#   no qualifiers anywhere                  -> neutral
# LLR magnitudes differ by dimension (part and variety contradictions are
# more telling than size). Posterior = sigmoid(prior + sum LLR), score 0-100.

_LEX = {
    "colour": ("red green yellow orange white black brown purple golden", 2.2),
    "fat": ("whole skim nonfat lowfat reduced lean full 2% 1%", 2.4),
    "sweet": ("sweet sweetened unsweetened semisweet bittersweet", 2.0),
    "part": ("breast thigh wing drumstick leg loin tenderloin rib shoulder brisket liver", 3.0),
    "meat": ("lightmeat darkmeat", 2.6),
    "skin": ("withskin skinless", 1.6),
    "plantpart": ("leaf root seed stem stalk peel zest bulb", 2.2),
    "flavour": ("vanilla chocolate strawberry honey cinnamon maple lemon coffee peach plain", 2.6),
    "cheese": ("cheddar cottage mozzarella swiss parmesan feta ricotta", 3.0),
    "dressing": ("italian ranch caesar french", 2.6),
    "pepper": ("bell jalapeno serrano habanero poblano chipotle", 2.6),
    "calorie": ("reducedcal regularcal", 2.0),
    "size": ("baby jumbo large small mini", 0.6),
}
_W2D = {}
for _d, (_ws, _llr) in _LEX.items():
    for _w in _ws.split():
        _W2D[_w] = _d
_PHRASES = [("light meat", "lightmeat"), ("white meat", "lightmeat"), ("dark meat", "darkmeat"),
            ("low fat", "lowfat"), ("fat free", "nonfat"), ("reduced fat", "reduced"),
            ("reduced calorie", "reducedcal"), ("low calorie", "reducedcal"),
            ("skin not eaten", "skinless"), ("without skin", "skinless"), ("with skin", "withskin"),
            ("skin and", "withskin and"), ("and skin", "and withskin")]
_EQUIV = [{"skim", "nonfat"}, {"sweet", "sweetened"}, {"lowfat", "1%"}, {"reduced", "2%"}]
_PRIOR = 1.2           # mild prior that a retrieved USDA match is qualifier-consistent


def _qualifiers(text):
    t = " " + re.sub(r"[^a-z0-9% ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    for a, b in _PHRASES:
        t = t.replace(" " + a + " ", " " + b + " ")
    out = {}
    for w in t.split():
        d = _W2D.get(w)
        if d:
            out.setdefault(d, set()).add(w)
    return out


def _equivalent(a, b):
    return a == b or any(a in s and b in s for s in _EQUIV)


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing).split(",")[0]
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        qi, qu = _qualifiers(ing), _qualifiers(usda)
        llr = 0.0
        for d in set(qi) | set(qu):
            base = _LEX[d][1]
            a, b = qi.get(d, set()), qu.get(d, set())
            if a and b:
                if any(_equivalent(x, y) for x in a for y in b):
                    llr += 0.5 * base
                    # partially matched multi-valued qualifiers
                    if len(a) > 1 and not all(any(_equivalent(x, y) for y in b) for x in a):
                        llr -= 0.6 * base
                else:
                    llr -= 1.6 * base
            elif a:
                llr -= 0.35 * base
            else:
                llr -= 0.15 * base
        z = _PRIOR + llr
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        return round(100.0 * p, 2)
    except Exception:
        return 0.0
