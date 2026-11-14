import re

# Preservation and Form Match, variant 3: implicit-form inference from food
# nouns. Many foods carry their form in the noun itself, not in a descriptor:
# "raisins" are dried, "jam" is a cooked preserve, "juice" is liquid, a
# "Spices, ..." USDA entry is a dried product, "broth" is a thin liquid while
# "soup" is a ready-to-serve dish, "paste" is concentrated. We infer a PHASE
# for each side (whole solid / dry solid / semi-solid / thin liquid / thick
# liquid) from explicit descriptors first and noun cues second, then score
# phase compatibility and preservation-class agreement separately.

_PHASE_NOUNS = {
    "dry": ["raisin", "prune", "jerky", "spice", "spices", "powder", "flour", "flakes",
            "seasoning", "bouillon", "cracker", "chips", "cereal", "oats", "dried", "dehydrated"],
    "semi": ["paste", "puree", "jam", "jelly", "preserves", "butter", "spread", "sauce",
             "pesto", "hummus", "mashed", "creamed", "yogurt", "marmalade", "chutney"],
    "thin": ["juice", "broth", "stock", "water", "milk", "drink", "beverage", "tea",
             "coffee", "vinegar", "consomme", "nectar"],
    "thick": ["soup", "chowder", "stew", "syrup", "concentrate", "condensed", "gravy",
              "cream", "dressing", "smoothie"],
}
_PRESERVE = {
    "frozen": "frozen", "thawed": "frozen", "canned": "shelf", "jarred": "shelf",
    "bottled": "shelf", "tinned": "shelf", "dried": "dry", "dehydrated": "dry",
    "fresh": "fresh", "raw": "fresh", "refrigerated": "fresh", "pickled": "brine",
    "brined": "brine", "smoked": "cured", "cured": "cured",
}
_PHASE_COMPAT = {
    ("whole", "whole"): 1.0, ("dry", "dry"): 1.0, ("semi", "semi"): 1.0,
    ("thin", "thin"): 1.0, ("thick", "thick"): 1.0,
    ("thin", "thick"): 0.4, ("thick", "thin"): 0.35, ("semi", "thick"): 0.55,
    ("thick", "semi"): 0.55, ("whole", "semi"): 0.3, ("semi", "whole"): 0.35,
    ("whole", "dry"): 0.2, ("dry", "whole"): 0.2, ("whole", "thin"): 0.1,
    ("thin", "whole"): 0.1, ("dry", "thin"): 0.15, ("thin", "dry"): 0.15,
    ("semi", "dry"): 0.3, ("dry", "semi"): 0.3, ("whole", "thick"): 0.2,
    ("thick", "whole"): 0.2, ("dry", "thick"): 0.25, ("thick", "dry"): 0.25,
    ("semi", "thin"): 0.25, ("thin", "semi"): 0.25,
}
_PRES_COMPAT = {
    ("fresh", "frozen"): 0.8, ("frozen", "fresh"): 0.85, ("fresh", "shelf"): 0.45,
    ("shelf", "fresh"): 0.45, ("frozen", "shelf"): 0.45, ("shelf", "frozen"): 0.5,
    ("fresh", "dry"): 0.2, ("dry", "fresh"): 0.2, ("brine", "shelf"): 0.6,
    ("shelf", "brine"): 0.6, ("cured", "fresh"): 0.3, ("fresh", "cured"): 0.3,
}


def _phase(words):
    ws = [w for w in words]
    # explicit descriptors (later fields in USDA, adjectives in ingredient)
    last_hit = None
    for w in ws:
        for ph, nouns in _PHASE_NOUNS.items():
            base = w[:-1] if w.endswith("s") and w[:-1] in nouns else w
            if base in nouns or w in nouns:
                last_hit = ph
    if "ground" in ws and not any(m in ws for m in ("beef", "turkey", "pork", "chicken", "meat", "lamb")):
        last_hit = "dry"
    return last_hit or "whole"


def _preservation(words):
    for w in words:
        if w in _PRESERVE and _PRESERVE[w] != "fresh":
            return _PRESERVE[w]
    return "fresh"


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower().replace("-", " ")
        usda = str(usda_match or "").lower().replace("-", " ")
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        iw = re.findall(r"[a-z]+", ing_main.split(",")[0])
        iw_all = re.findall(r"[a-z]+", ing)
        uw = re.findall(r"[a-z]+", usda)
        if not iw or not uw:
            return 0.0
        # "dry heat" is a cooking method
        uw_f = [w for i, w in enumerate(uw) if not (w == "dry" and i + 1 < len(uw) and uw[i + 1] == "heat")]
        ph_i, ph_u = _phase(iw), _phase(uw_f)
        pr_i, pr_u = _preservation(iw_all), _preservation(uw_f)
        if "dried" in iw or "dry" in iw:
            pr_i = "dry"
        if pr_u == "dry" and ph_u == "whole":
            ph_u = "dry"
        if pr_i == "dry" and ph_i == "whole":
            ph_i = "dry"

        phase_score = _PHASE_COMPAT.get((ph_i, ph_u), 0.3)
        if pr_i == pr_u:
            pres_score = 1.0
        else:
            pres_score = _PRES_COMPAT.get((pr_i, pr_u), 0.35)
        score = 100.0 * (0.6 * phase_score + 0.4 * pres_score)
        # both entirely unmarked: default fresh-whole; keep below explicit agreement
        if ph_i == ph_u == "whole" and pr_i == pr_u == "fresh":
            score -= 6.0
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
