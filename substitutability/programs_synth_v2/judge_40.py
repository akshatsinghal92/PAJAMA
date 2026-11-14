import re

# Specificity and Generality Alignment, variant 8: field-by-field retention.
# We walk through the USDA description field by field. Each field either is
# IMPLIED by the ingredient (its words appear there), is BOILERPLATE (raw,
# NFS, regular ...), or is an UNREQUESTED qualifier. Unrequested fields
# multiply the score by a retention factor that depends on the field type
# (a flavour or fat label is very noticeable; a cooking-method sub-detail
# such as "dry heat" much less) and on its depth (later fields are finer).
# Ingredient modifiers that no USDA field consumes multiply the score by a
# separate, harsher retention factor (the entry is too generic).

_TYPE_RX = [
    ("boiler", r"^(raw|nfs|ns|regular|plain|unprepared|fresh|commercial|all purpose|"
               r"not further specified|includes .*|usda .*|mature|average)$"),
    ("flavour", r"\b(vanilla|chocolate|strawberry|honey|maple|cinnamon|lemon|lime|garlic|"
                r"bbq|barbecue|ranch|italian|spicy|cheese|banana|peach|mint|coconut)\b"),
    ("nutrient", r"\b(low ?fat|lowfat|nonfat|fat free|reduced|light|lite|lean|sodium|"
                 r"calorie|sugar|sweetened|unsweetened|salt|vitamin|fortified|enriched|\d+ ?%)\b"),
    ("anatomy", r"\b(breast|thigh|wing|leg|loin|skin|meat only|light meat|dark meat|"
                r"fillet|bone|boneless|separable|lean only|peel)\b"),
    ("method", r"\b(cooked|boiled|baked|roasted|fried|grilled|broiled|steamed|braised|"
               r"stewed|heat|microwaved|toasted|prepared|ready)\b"),
    ("pack", r"\b(canned|frozen|dried|dehydrated|jarred|solids|liquids|drained|syrup|"
             r"juice pack|water pack|in oil)\b"),
]
_RETAIN = {"boiler": 1.0, "flavour": 0.55, "nutrient": 0.62, "anatomy": 0.7,
           "method": 0.8, "pack": 0.78, "other": 0.72}
_ING_SKIP = set("""g kg ml oz lb fresh chopped diced minced sliced shredded grated thawed
segmented peeled drained rinsed and or of with the a an to in for from""".split())


def _ftype(field):
    for t, rx in _TYPE_RX:
        if re.search(rx, field):
            return t
    return "other"


def _norm(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = [_norm(w) for w in re.findall(r"[a-z]+", ing) if w not in _ING_SKIP]
        fields = [f.strip() for f in str(usda_match or "").lower().split(",") if f.strip()]
        if not iw or not fields:
            return 0.0
        head = iw[-1]
        consumed = set()
        score = 10.0
        head_found = False
        for depth, field in enumerate(fields):
            fw = [_norm(w) for w in re.findall(r"[a-z]+", field)]
            hits = [w for w in fw if w in iw]
            if head in fw:
                head_found = True
            consumed.update(hits)
            if hits:
                # partially implied field: unrequested remainder is a mild cost
                rest = [w for w in fw if w not in iw and w not in ("and", "or", "with")]
                if rest and depth > 0:
                    score *= 0.93
                continue
            t = _ftype(field)
            retain = _RETAIN[t]
            if depth == 0:
                # the primary field itself unrelated to the ingredient: category header
                retain = 0.9 if len(fw) == 1 else 0.6
            else:
                retain = retain + (1.0 - retain) * min(0.5, 0.12 * (depth - 1))
            score *= retain
        if not head_found:
            score *= 0.2
        leftover = [w for w in iw[:-1] if w not in consumed]
        for _w in leftover:
            score *= 0.6
        # brand present in USDA but not asked for
        if re.search(r"\b[A-Z][A-Z'&]{2,}\b", str(usda_match)) and not re.search(
                r"\b[A-Z][A-Z'&]{2,}\b", str(ingredient)):
            score *= 0.75
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
