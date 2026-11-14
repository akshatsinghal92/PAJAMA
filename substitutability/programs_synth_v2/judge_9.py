import re

# Preparation-State Equivalence, variant 1: state-class extraction and a
# compatibility matrix between the dominant state class on each side.

_STATE_CLASS = {
    # trivially applied mechanical prep: never changes the dish
    "chopped": "mech", "diced": "mech", "minced": "mech", "sliced": "mech",
    "shredded": "mech", "grated": "mech", "cubed": "mech", "segmented": "mech",
    "peeled": "mech", "halved": "mech", "quartered": "mech", "crushed": "mech",
    "julienned": "mech", "trimmed": "mech", "cored": "mech", "pitted": "mech",
    "seeded": "mech", "mashed": "mech", "rinsed": "mech", "drained": "mech",
    "thawed": "mech", "softened": "mech", "melted": "mech",
    # raw-ish states
    "raw": "raw", "fresh": "raw", "uncooked": "raw", "unheated": "raw",
    # cooked via thermal method
    "cooked": "cooked", "boiled": "cooked", "steamed": "cooked", "baked": "cooked",
    "roasted": "cooked", "grilled": "cooked", "broiled": "cooked", "braised": "cooked",
    "stewed": "cooked", "simmered": "cooked", "poached": "cooked", "heat": "cooked",
    "microwaved": "cooked", "toasted": "cooked", "blanched": "cooked",
    # fried is its own class: adds oil / crust
    "fried": "fried", "deep": "fried", "sauteed": "fried", "breaded": "fried",
    "battered": "fried", "pan": "fried",
    # preserved forms
    "canned": "preserved", "frozen": "frozen", "dried": "dried", "dehydrated": "dried",
    "smoked": "cured", "cured": "cured", "pickled": "cured", "salted": "cured",
    "creamed": "processed", "pureed": "processed", "juice": "processed",
    "powder": "dried", "powdered": "dried",
}

# compatibility (0..1) between ingredient state class and USDA state class
_COMPAT = {
    ("raw", "raw"): 1.0, ("raw", "mech"): 1.0, ("mech", "raw"): 1.0,
    ("mech", "mech"): 1.0, ("raw", "frozen"): 0.75, ("frozen", "raw"): 0.8,
    ("frozen", "frozen"): 1.0, ("mech", "frozen"): 0.75,
    ("cooked", "cooked"): 1.0, ("raw", "cooked"): 0.2, ("cooked", "raw"): 0.35,
    ("mech", "cooked"): 0.3, ("raw", "fried"): 0.05, ("cooked", "fried"): 0.3,
    ("fried", "fried"): 1.0, ("fried", "cooked"): 0.3, ("fried", "raw"): 0.15,
    ("preserved", "preserved"): 1.0, ("preserved", "raw"): 0.35,
    ("raw", "preserved"): 0.35, ("preserved", "cooked"): 0.6,
    ("cooked", "preserved"): 0.6, ("dried", "dried"): 1.0, ("raw", "dried"): 0.1,
    ("dried", "raw"): 0.1, ("cured", "cured"): 1.0, ("raw", "cured"): 0.15,
    ("processed", "processed"): 1.0, ("processed", "raw"): 0.15,
    ("raw", "processed"): 0.15, ("frozen", "cooked"): 0.4, ("cooked", "frozen"): 0.6,
}

_PRIORITY = ["fried", "dried", "cured", "processed", "cooked", "preserved", "frozen", "raw", "mech"]


def _states(text):
    words = re.findall(r"[a-z]+", text.lower())
    return [_STATE_CLASS[w] for w in words if w in _STATE_CLASS]


def _dominant(classes):
    for c in _PRIORITY:
        if c in classes:
            return c
    return None


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz)\b", " ", ing.lower())
        # parentheticals often carry state ("from tube", "thawed"); keep their words
        ing = ing.replace("(", " ").replace(")", " ")
        usda = re.sub(r"[()]", " ", usda.lower())

        ic = _states(ing)
        uc = _states(usda)
        di, du = _dominant(ic), _dominant(uc)

        if di is None and du is None:
            return 8.0                     # neither specifies: assume default state
        if di is None:
            # ingredient default is usually raw/as-purchased
            di = "raw"
            base = 0.9
        elif du is None:
            du = "raw" if di in ("raw", "mech") else di
            base = 0.85
        else:
            base = 1.0
        compat = _COMPAT.get((di, du), 0.4 if di == du else 0.25)
        score = 10.0 * base * compat

        # each additional non-trivial USDA state word lowers confidence slightly
        heavy = [c for c in uc if c not in ("mech", "raw")]
        if di in ("raw", "mech"):
            score -= 0.5 * max(0, len(heavy) - 1)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
