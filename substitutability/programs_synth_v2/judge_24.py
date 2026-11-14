import re
import math

# Preservation and Form Match, variant 8: hand-calibrated logistic model.
# A compact feature vector describes the relationship between the two forms
# and a logistic function with expert-set coefficients turns it into the
# probability that the preservation/delivery form is interchangeable.
# Features:
#   f_same     - identical primary form class
#   f_thaw     - frozen vs fresh (recoverable by thawing)
#   f_drain    - canned vs fresh/cooked (recoverable by draining, mostly)
#   f_phase    - solid vs liquid delivery (juice for fruit, soup for broth)
#   f_conc     - absolute log10 concentration ratio (paste/powder/dried vs whole)
#   f_medium   - syrup / oil / brine packing present on one side only
#   f_unknown  - neither side states a form
#   f_explicit - both sides state a form

_CLASS_CUES = [
    ("powder", r"\bpowder\w*|\binstant\b|\bgranul\w+"),
    ("dried", r"\bdried\b|\bdehydrated\b|\bdry\b(?!\s+heat)|\bflakes\b"),
    ("paste", r"\bpaste\b|\bpuree\b|\bconcentrate\b|\btube\b"),
    ("condensed", r"\bcondensed\b|\bevaporated\b|\bbouillon\b"),
    ("soup", r"\bsoup\b|\bchowder\b|\bready[ -]to[ -]serve\b"),
    ("liquid", r"\bjuice\b|\bbroth\b|\bstock\b|\bnectar\b"),
    ("canned", r"\bcanned\b|\btinned\b|\bjarred\b|\bbottled\b|\bsolids and liquids\b"),
    ("frozen", r"\bfrozen\b"),
    ("fresh", r"\bfresh\b|\braw\b"),
]
_CONC = {"fresh": 1.0, "frozen": 1.0, "canned": 1.0, "liquid": 1.0, "soup": 1.0,
         "condensed": 2.2, "paste": 3.5, "dried": 5.0, "powder": 8.0}
_LIQUID = {"liquid", "soup", "condensed"}
_MEDIUM_RX = r"\bsyrup\b|\bin oil\b|\boil[ -]pack\w*|\bbrine\b|\bin water\b|\bpickled\b"
_COEF = {"bias": 0.4, "f_same": 2.2, "f_thaw": 1.1, "f_drain": -0.6, "f_phase": -2.6,
         "f_conc": -2.2, "f_medium": -1.0, "f_unknown": 0.6, "f_explicit": 0.4}


def _klass(text):
    if re.search(r"\bground\b", text) and not re.search(r"beef|pork|turkey|chicken|lamb|meat", text):
        return "powder", True
    for k, rx in _CLASS_CUES:
        if re.search(rx, text):
            return k, True
    return "fresh", False


def _sigmoid(z):
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        main = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ki, ei = _klass(main)
        ku, eu = _klass(usda)
        f = dict.fromkeys(_COEF, 0.0)
        f["bias"] = 1.0
        f["f_same"] = 1.0 if ki == ku else 0.0
        f["f_thaw"] = 1.0 if {ki, ku} == {"fresh", "frozen"} else 0.0
        f["f_drain"] = 1.0 if "canned" in (ki, ku) and ki != ku and {ki, ku} <= {"canned", "fresh", "frozen"} else 0.0
        f["f_phase"] = 1.0 if (ki in _LIQUID) != (ku in _LIQUID) else 0.0
        f["f_conc"] = abs(math.log10(_CONC[ki]) - math.log10(_CONC[ku]))
        mi = bool(re.search(_MEDIUM_RX, ing))
        mu = bool(re.search(_MEDIUM_RX, usda))
        f["f_medium"] = 1.0 if mi != mu else 0.0
        f["f_unknown"] = 1.0 if not ei and not eu else 0.0
        f["f_explicit"] = 1.0 if ei and eu else 0.0
        z = sum(_COEF[k] * v for k, v in f.items())
        return round(100.0 * _sigmoid(z), 2)
    except Exception:
        return 0.0
