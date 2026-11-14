import re

# Processing and Additive Difference, variant 5: layered USDA-field analysis
# with ordinal severity scales.
# Layer A - PRIMARY FIELD composition: is the USDA product itself a compound
#           ("Garlic sauce", "Salt and pepper", "Seasoning mix", "Chicken
#           patty")? If the ingredient is not the same kind of compound, the
#           entry adds components (largest penalty).
# Layer B - DESCRIPTOR FIELDS: each later field is typed as neutral (raw,
#           drained, cooked), additive-bearing (with salt, sweetened,
#           breaded, with sauce), or a packing medium with an ordinal sugar
#           scale: water < juice < extra light < light < heavy < extra heavy.
# Layer C - reverse check: the ingredient specifies additives the entry lacks.

_COMPOUND_HEAD = r"\b(sauce|dressing|gravy|mix|blend|seasoning|soup|salad|stew|casserole|patty|patties|nuggets|sandwich|pie|spread|dip|marinade|and)\b"
_ADD_FIELD = [
    (r"\bwith salt\b|\bsalted\b|\bsalt added\b", 2.0),
    (r"\bsweetened\b|\bwith sugar\b|\bsugar added\b|\bcandied\b|\bglazed\b|\bfrosted\b", 2.5),
    (r"\bbreaded\b|\bbattered\b|\bcoated\b|\bflour coated\b", 3.0),
    (r"\bwith (sauce|gravy|cheese|butter|cream|oil)\b|\bin (sauce|gravy|oil|butter sauce)\b", 3.0),
    (r"\bfried\b|\bsauteed\b", 2.2),
    (r"\bseasoned\b|\bspiced\b|\bflavou?red\b|\bsmoked\b|\bmarinated\b|\bcured\b", 2.5),
    (r"\bprepared\b|\bfrom recipe\b|\bready-to-(eat|serve)\b", 1.2),
]
_SYRUP_SCALE = [(r"\bextra heavy syrup\b", 5), (r"\bheavy syrup\b", 4), (r"\blight syrup\b", 3),
                (r"\bextra light syrup\b", 2), (r"\bjuice pack\b|\bin juice\b", 1),
                (r"\bwater pack\b|\bin water\b", 0)]
_ING_ADD = r"\b(salted|sweetened|breaded|battered|seasoned|smoked|fried|glazed|candied|flavou?red|in syrup|in oil|marinated)\b"


def _syrup_level(text):
    for rx, lvl in _SYRUP_SCALE:
        if re.search(rx, text):
            return lvl
    return None


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0].strip()
        fields = [f.strip() for f in re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower()).split(",") if f.strip()]
        if not ing or not fields:
            return 0.0
        score = 10.0
        primary = fields[0]
        # Layer A
        u_comp = re.findall(_COMPOUND_HEAD, primary)
        i_comp = re.findall(_COMPOUND_HEAD, ing)
        if u_comp and not i_comp:
            score -= 4.0
        elif u_comp and i_comp and set(u_comp) != set(i_comp):
            score -= 1.5
        # "Salad dressing, italian dressing" style: compound named again in field 2
        # Layer B
        desc = " , ".join(fields[1:])
        for rx, cost in _ADD_FIELD:
            if re.search(rx, desc) and not re.search(rx, ing):
                score -= cost
        su = _syrup_level(desc)
        si = _syrup_level(ing)
        if su is not None:
            base = si if si is not None else (0 if re.search(r"\bfresh\b|\braw\b", ing) or si is None else si)
            score -= 0.9 * max(0, su - base)
        # explicitly plain descriptors are good evidence
        if re.search(r"\bwithout salt\b|\bunsalted\b|\bunsweetened\b|\bplain\b|\bno sugar added\b", desc):
            score += 0.5
        # Layer C
        for m in set(re.findall(_ING_ADD, ing)):
            if m not in " ".join(fields):
                score -= 1.0
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
