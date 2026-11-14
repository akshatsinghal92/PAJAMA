import re

# Specificity and Generality Alignment, variant 6: regex specificity markers
# and a decision table.
# USDA entries signal variant-level specificity through recognisable
# PATTERNS rather than single words: percentages ("2% milkfat", "93% lean"),
# grades ("Grade A", "choice"), brand names in capitals, "with added ...",
# "includes ...", "ready-to-eat", "prepared with ...", fat/calorie labels.
# Generic entries signal themselves with "NFS", "regular", "plain",
# "all-purpose", "unspecified". The ingredient is classed as unqualified or
# qualified (and which markers it carries); a decision table assigns a base
# score, refined by agreement on numeric values.

_VARIANT_RX = {
    "percent": r"\d+(\.\d+)?\s*%",
    "grade": r"\bgrade [a-z]\b|\b(choice|select|prime)\b",
    "brand": r"\b[A-Z][A-Z'&]{2,}\b",
    "added": r"\bwith added\b|\bfortified\b|\benriched\b|\bwith vitamin\b",
    "includes": r"\bincludes\b|\bformerly\b|\bsuch as\b",
    "rte": r"\bready[- ]to[- ](eat|serve|drink)\b|\bprepared with\b|\bprepared from\b",
    "fatlabel": r"\blow ?fat\b|\bnonfat\b|\bfat free\b|\breduced fat\b|\blight\b|\blean\b",
    "callabel": r"\breduced calorie\b|\blow calorie\b|\bdiet\b",
    "sodium": r"\blow sodium\b|\breduced sodium\b|\bno salt\b|\bunsalted\b",
    "flavour": r"\b(vanilla|chocolate|strawberry|honey|maple|cinnamon|lemon|garlic|bbq|ranch|italian|spicy)\b",
    "grade_oil": r"\bextra virgin\b|\bvirgin\b|\bcold[- ]pressed\b",
}
_GENERIC_RX = r"\bnfs\b|\bregular\b|\bplain\b|\ball[- ]purpose\b|\bunspecified\b|\bns as to\b"
_WEIGHT = {"percent": 1.5, "grade": 1.0, "brand": 2.0, "added": 0.8, "includes": 0.5,
           "rte": 1.2, "fatlabel": 2.0, "callabel": 2.2, "sodium": 1.0, "flavour": 2.4,
           "grade_oil": 1.4}


def _markers(text, case_text):
    found = {}
    for k, rx in _VARIANT_RX.items():
        src = case_text if k == "brand" else text
        m = re.findall(rx, src)
        if m:
            found[k] = m
    return found


def _percents(text):
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).split(",")[0]
        ing_raw = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing_raw)
        usda_raw = str(usda_match or "")
        ing, usda = ing_raw.lower(), usda_raw.lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        mi = _markers(ing, ing_raw)
        mu = _markers(usda, usda_raw)
        generic_u = bool(re.search(_GENERIC_RX, usda))

        # identity gate on the head noun
        words = re.findall(r"[a-z]+", ing)
        head = words[-1] if words else ""
        if head and not re.search(r"\b" + re.escape(head[:4]), usda):
            return 1.0

        if not mi:
            # unqualified ingredient: generic USDA is ideal, variants are not
            score = 9.0 if not mu else 8.0
            if generic_u:
                score += 1.0
            score -= sum(_WEIGHT[k] for k in mu)
        else:
            score = 9.0
            for k in set(mi) | set(mu):
                if k in mi and k in mu:
                    if set(mi[k]) == set(mu[k]) or k in ("brand", "added", "includes"):
                        score += 0.4
                    else:
                        score -= 0.9 * _WEIGHT[k]
                elif k in mi:
                    score -= 1.2 * _WEIGHT[k]   # USDA too generic for a stated variant
                else:
                    score -= 0.8 * _WEIGHT[k]
            if generic_u:
                score -= 1.0
            pi, pu = _percents(ing), _percents(usda)
            if pi and pu:
                gap = min(abs(a - b) for a in pi for b in pu)
                score -= min(3.0, gap / 5.0)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
