import re

# Processing and Additive Difference, variant 1: additive inventory with
# taste-impact weights.
# Both texts are scanned for ADDITIVE / PROCESSING cues (salt, sugar,
# sweeteners, oil, butter, sauces, breading, seasoning blends, flavours,
# smoking, curing, compound "and"/"with" components). Each cue has a taste
# impact weight. Cues present in the USDA entry but not implied by the
# ingredient are subtracted with full weight; cues the ingredient has but the
# USDA entry lacks are subtracted at half weight (the cook may add them).
# Explicit "without salt", "unsweetened", "no sugar added" count as plain.

_CUES = [
    # (label, regex, impact)
    ("salt", r"\bsalted\b|\bwith salt\b|\bsalt added\b|\bbrined?\b|\bin brine\b", 1.6),
    ("sugar", r"\bsweetened\b|\bsugar(ed)?\b(?! free)|\bcandied\b|\bglazed\b|\bfrosted\b|\bhoney\b|\bsyrup\b", 2.2),
    ("oil", r"\bin oil\b|\boil[- ]packed\b|\bwith (added )?oil\b|\bfried\b|\bsauteed\b", 2.0),
    ("butter", r"\bbuttered\b|\bwith butter\b|\bbutter sauce\b", 2.0),
    ("sauce", r"\bsauce\b|\bgravy\b|\bdressing\b|\bmarinade\b|\bmarinated\b|\bglaze\b", 2.6),
    ("breading", r"\bbreaded\b|\bbattered\b|\bcoated\b|\bcrumbs?\b|\btempura\b", 2.8),
    ("seasoning", r"\bseasoned\b|\bseasoning\b|\bspiced\b|\bspicy\b|\bherbs?\b|\band pepper\b|\bblend\b", 2.0),
    ("flavour", r"\bflavou?red\b|\bvanilla\b|\bchocolate\b|\bstrawberry\b|\bcinnamon\b|\bmaple\b|\bbbq\b|\bbarbecue\b|\branch\b", 2.4),
    ("smoked", r"\bsmoked\b|\bcured\b|\bpickled\b", 2.4),
    ("cheese", r"\bwith cheese\b|\bcheese sauce\b|\bau gratin\b", 2.4),
    ("cream", r"\bcreamed\b|\bcream style\b|\bcreamy\b|\bwith cream\b", 2.2),
    ("compound", r"\b(with|and) [a-z]+(?!\s*(eaten|added))", 1.2),
    ("fortified", r"\bfortified\b|\benriched\b|\bwith added\b|\bvitamin\b", 0.4),
    ("prepared", r"\bprepared\b|\bready[- ]to[- ](eat|serve)\b|\bfrom recipe\b|\bmix\b", 1.4),
]
_PLAIN_RX = [
    ("salt", r"\bwithout salt\b|\bunsalted\b|\bno salt\b|\blow sodium\b"),
    ("sugar", r"\bunsweetened\b|\bno sugar\b|\bsugar free\b|\bwithout sugar\b"),
]


def _scan(text):
    found = {}
    for label, rx, w in _CUES:
        if re.search(rx, text):
            found[label] = w
    for label, rx in _PLAIN_RX:
        if re.search(rx, text):
            found.pop(label, None)
    # "and"/"with" inside descriptors that are not food components
    if "compound" in found and re.search(r"\b(skin|bone|liquids|solids|peel)\b", text):
        found.pop("compound")
    return found


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\([^)]*\)", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        if not ing.strip() or not usda.strip():
            return 0.0
        ai, au = _scan(ing), _scan(usda)
        # the ingredient's own food noun is not an additive ("garlic paste" vs sauce)
        extra = {k: v for k, v in au.items() if k not in ai}
        missing = {k: v for k, v in ai.items() if k not in au}
        score = 10.0 - sum(extra.values()) - 0.5 * sum(missing.values())
        if not ai and not au:
            score = 10.0
        # matching additive profile (both sweetened, both breaded) is fine
        score += 0.3 * len(set(ai) & set(au))
        # a primary-field food change ("Garlic sauce" for garlic paste) adds components
        words = re.findall(r"[a-z]+", ing.split(",")[0])
        first = usda.split(",")[0]
        if words and words[-1] in ("paste", "puree", "powder") and re.search(r"\bsauce\b|\bdressing\b", first):
            score -= 1.0
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
