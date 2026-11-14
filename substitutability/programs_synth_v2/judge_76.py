import re

# Modifier and Qualifier Consistency, variant 4: numeric qualifiers and
# with/without binary features.
# Many discriminating qualifiers are either NUMERIC (2% milkfat, 93% lean,
# 70% cacao) or BINARY presence features with explicit negations
# (with skin / skinless / skin not eaten, bone-in / boneless, seeded /
# seedless, salted / unsalted, sweetened / unsweetened, light meat / dark
# meat). Ordinal levels (whole > 2% > 1% > skim) are mapped to numbers too.
# Numeric gaps cost proportionally; binary features cost when the two sides
# assert opposite values; a side that does not mention a feature is neutral.

_ORDINAL_FAT = [
    (r"\bwhole\b|\bfull[- ]fat\b|\bregular\b", 3.5), (r"\b2 ?%|\breduced[- ]fat\b", 2.0),
    (r"\b1 ?%|\blow[- ]?fat\b|\blowfat\b|\blight\b", 1.0), (r"\bskim\b|\bnonfat\b|\bfat[- ]free\b", 0.1),
]
_BINARY = [
    # feature, positive regex, negative regex, weight
    ("skin", r"\bwith skin\b|\bskin on\b|\bskin eaten\b|\bskin and\b|\band skin\b|\bskin\b(?! not)",
     r"\bskinless\b|\bwithout skin\b|\bskin not eaten\b|\bno skin\b", 2.0),
    ("bone", r"\bbone[- ]in\b|\bwith bone\b", r"\bboneless\b|\bbone removed\b|\bwithout bone\b", 1.0),
    ("seeds", r"\bseeded\b(?!less)|\bwith seeds\b", r"\bseedless\b|\bwithout seeds\b", 0.8),
    ("salt", r"\bsalted\b|\bwith salt\b", r"\bunsalted\b|\bwithout salt\b|\bno salt\b", 1.2),
    ("sugar", r"\bsweetened\b|\bwith sugar\b|\bsweet\b", r"\bunsweetened\b|\bno sugar\b|\bsugar[- ]free\b", 1.6),
    ("light_meat", r"\blight meat\b|\bwhite meat\b|\bbreast\b", r"\bdark meat\b|\bthigh\b|\bleg\b|\bdrumstick\b", 2.4),
    ("peel", r"\bpeel eaten\b|\bwith peel\b|\bunpeeled\b", r"\bpeeled\b|\bwithout peel\b|\bpeel not eaten\b", 0.8),
    ("lean_only", r"\blean only\b", r"\blean and fat\b", 1.2),
    ("calorie", r"\breduced calorie\b|\blow calorie\b|\bdiet\b|\blite\b", r"\bregular\b", 1.6),
]
_PCT = r"(\d+(?:\.\d+)?)\s*%\s*(milkfat|fat|lean|cacao|cocoa)?"


def _fat_level(text):
    for rx, lvl in _ORDINAL_FAT:
        if re.search(rx, text):
            return lvl
    return None


def _binary(text):
    out = {}
    for name, pos, neg, _w in _BINARY:
        n = re.search(neg, text) is not None
        p = re.search(pos, text) is not None
        if n:
            out[name] = False
        elif p:
            out[name] = True
    return out


def _percents(text):
    out = {}
    for val, kind in re.findall(_PCT, text):
        out[kind or "fat"] = float(val)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", str(ingredient or "").lower())
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        score = 10.0
        # ordinal fat level (only when both sides state it, or USDA reduces fat
        # of an unqualified dairy ingredient)
        fi, fu = _fat_level(ing), _fat_level(usda)
        if fi is not None and fu is not None:
            score -= 1.1 * abs(fi - fu)
        elif fi is None and fu is not None and fu < 3.0 and re.search(r"\b(milk|cheese|yogurt|cottage|cream|dressing)\b", ing):
            score -= 0.5 * (3.5 - fu)
        # numeric percentages
        pi, pu = _percents(ing), _percents(usda)
        for kind in set(pi) & set(pu):
            score -= min(3.0, abs(pi[kind] - pu[kind]) / 4.0)
        # binary features
        bi, bu = _binary(ing), _binary(usda)
        for name, _p, _n, w in _BINARY:
            if name in bi and name in bu:
                if bi[name] != bu[name]:
                    score -= 1.8 * w
                else:
                    score += 0.2 * w
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
