import re

# Specificity and Generality Alignment, variant 3: typed qualifier slots.
# Qualifiers are sorted into SLOTS (fat level, sugar level, sodium level,
# flavour, grade, cut/part, variety, brand, processing). Per slot:
#   both filled, same value        -> reward
#   both filled, different value   -> strong penalty
#   ingredient filled, USDA empty  -> penalty (USDA too generic)
#   USDA filled, ingredient empty  -> small penalty if the USDA value is the
#                                     slot DEFAULT (whole milk, regular),
#                                     larger if it is a noticeable variant.

_SLOTS = {
    "fat": {"lowfat": "low", "low fat": "low", "reduced fat": "low", "light": "low",
            "nonfat": "none", "fat free": "none", "skim": "none", "whole": "full",
            "full fat": "full", "regular": "full", "lean": "low", "extra lean": "low"},
    "sugar": {"sweetened": "sweet", "unsweetened": "unsweet", "sugar free": "unsweet",
              "no sugar added": "unsweet", "sweet": "sweet", "honey": "sweet"},
    "sodium": {"low sodium": "low", "reduced sodium": "low", "no salt added": "none",
               "unsalted": "none", "salted": "full", "with salt": "full",
               "without salt": "none"},
    "calorie": {"reduced calorie": "low", "low calorie": "low", "diet": "low", "lite": "low"},
    "flavour": {w: w for w in ("vanilla", "chocolate", "strawberry", "banana", "lemon",
                               "orange", "maple", "cinnamon", "garlic", "italian", "ranch",
                               "honey mustard", "bbq", "barbecue", "mint", "peach")},
    "grade": {"extra virgin": "ev", "virgin": "v", "light olive": "light", "pure": "pure",
              "all purpose": "ap", "bread flour": "bread", "cake flour": "cake"},
    "part": {w: w for w in ("breast", "thigh", "wing", "leg", "drumstick", "loin", "rib",
                            "shoulder", "light meat", "dark meat", "skin", "fillet",
                            "ground", "tenderloin", "brisket", "white", "yolk")},
    "variety": {w: w for w in ("cottage", "cheddar", "swiss", "parmesan", "mozzarella",
                               "brown", "white rice", "basmati", "jasmine", "russet",
                               "red", "green", "yellow", "black", "kidney", "pinto",
                               "navy", "granny smith", "roma", "cherry")},
    "processing": {"smoked": "smoked", "cured": "cured", "instant": "instant",
                   "quick": "quick", "rolled": "rolled", "steel cut": "steel",
                   "frozen": "frozen", "canned": "canned", "dried": "dried"},
}
_DEFAULTS = {"fat": {"full"}, "sodium": {"full"}, "sugar": set(), "calorie": set(),
             "flavour": set(), "grade": {"pure", "ap"}, "part": set(), "variety": set(),
             "processing": set()}
_SLOT_W = {"fat": 2.2, "sugar": 2.0, "sodium": 1.0, "calorie": 2.2, "flavour": 2.6,
           "grade": 1.4, "part": 2.0, "variety": 2.6, "processing": 1.6}


def _fill(text):
    t = " " + re.sub(r"[^a-z ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    slots = {}
    for slot, table in _SLOTS.items():
        # longest phrases first so "extra virgin" beats "virgin"
        for phrase in sorted(table, key=len, reverse=True):
            if " " + phrase + " " in t:
                slots.setdefault(slot, table[phrase])
                t = t.replace(" " + phrase + " ", " ")
    return slots


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        ing = re.sub(r"\([^)]*\)", " ", ing.lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        if not ing.strip() or not usda.strip():
            return 0.0
        si, su = _fill(ing), _fill(usda)
        # "skin not eaten" means no skin
        if "skin not eaten" in usda.lower() or "without skin" in usda.lower():
            su.pop("part", None) if su.get("part") == "skin" else None
        score = 10.0
        for slot in set(si) | set(su):
            a, b = si.get(slot), su.get(slot)
            w = _SLOT_W[slot]
            if a and b:
                score += 0.4 * w if a == b else -1.6 * w
            elif a and not b:
                score -= 1.0 * w
            else:
                score -= 0.25 * w if b in _DEFAULTS[slot] else 0.8 * w
        # brand added to an unbranded ingredient
        if re.search(r"\b[A-Z]{3,}\b", usda) and not re.search(r"\b[A-Z]{3,}\b", str(ingredient)):
            score -= 1.2
        # generic markers suit unqualified ingredients
        if re.search(r"\bnfs\b|\bregular\b|\bplain\b", usda.lower()) and not si:
            score += 0.5
        # cheap identity gate: ingredient head noun should appear in USDA text
        words = re.findall(r"[a-z]+", ing)
        if words:
            stem = words[-1][:5]
            if stem not in usda.lower():
                score = min(score, 3.0)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
