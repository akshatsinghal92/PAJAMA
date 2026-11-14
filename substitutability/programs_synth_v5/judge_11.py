import re
import math

# Transition cost table between preservation/delivery states (symmetric lookup).
_STATE_WORDS = {
    "frozen": {"frozen", "thawed", "thaw"},
    "canned": {"canned", "tinned", "jarred", "bottled", "drained", "pickled", "brined"},
    "dried": {"dried", "dry", "dehydrated", "powdered", "powder", "flakes"},
    "raw": {"raw", "fresh", "uncooked"},
    "cooked": {"cooked", "boiled", "baked", "roasted", "fried", "toasted", "steamed", "grilled",
               "prepared", "sauteed", "sautéed", "braised", "stewed", "heated"},
    "paste": {"paste", "puree", "purée", "concentrate", "extract"},
    "liquid": {"juice", "nectar", "drink", "broth", "stock", "soup", "sauce", "syrup", "beverage"},
}
_COST = {
    ("frozen", "raw"): 0.1, ("canned", "cooked"): 0.15, ("dried", "raw"): 0.7,
    ("raw", "cooked"): 0.8, ("frozen", "cooked"): 0.6, ("dried", "cooked"): 0.5,
    ("canned", "raw"): 0.5, ("frozen", "dried"): 0.8, ("canned", "dried"): 0.8,
    ("canned", "frozen"): 0.6, ("paste", "raw"): 0.9, ("paste", "dried"): 0.8,
    ("liquid", "raw"): 1.0, ("liquid", "dried"): 1.0, ("liquid", "cooked"): 0.9,
    ("liquid", "canned"): 0.8, ("liquid", "frozen"): 0.9, ("paste", "cooked"): 0.8,
    ("paste", "canned"): 0.6, ("paste", "frozen"): 0.9, ("liquid", "paste"): 0.7,
}


def _states(text):
    toks = set(re.findall(r"[a-zé]+", text.lower()))
    return {k for k, w in _STATE_WORDS.items() if toks & w}


def _cost(a, b):
    if a == b:
        return 0.0
    return _COST.get((a, b), _COST.get((b, a), 0.5))


def _trigrams(s):
    s = re.sub(r"[^a-z]", "", s)
    if len(s) < 3:
        return {s} if s else set()
    return {s[i:i + 3] for i in range(len(s) - 2)}


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)\b", "", ing)
        ing_np = re.sub(r"\([^)]*\)", "", ing).split(",")[0]
        if not ing_np.strip() or not usda.strip():
            return 0.0

        si, su = _states(ing), _states(usda)
        # form distance: average best-match cost between state sets
        if si and su:
            d = sum(min(_cost(a, b) for b in su) for a in si) / len(si)
            d2 = sum(min(_cost(a, b) for a in si) for b in su) / len(su)
            dist = (d + d2) / 2
        elif si or su:
            extra = si or su
            dist = 0.25 + 0.15 * sum(1 for e in extra if e in ("paste", "liquid", "cooked"))
        else:
            dist = 0.1
        form_factor = math.exp(-2.2 * dist)

        # lexical anchor: trigram dice between ingredient noun phrase and USDA primary + descriptors
        head = usda.split(",")[0]
        ta = _trigrams(ing_np)
        tb = _trigrams(head)
        tall = _trigrams(usda)
        dice_head = 2 * len(ta & tb) / (len(ta) + len(tb)) if ta and tb else 0.0
        recall = len(ta & tall) / len(ta) if ta else 0.0
        anchor = 0.5 * dice_head + 0.5 * recall

        # specificity: too many extra descriptors in USDA slightly lowers fit
        nseg = usda.count(",") + 1
        spec = 1.0 / (1.0 + 0.06 * max(0, nseg - 3))

        return round(100.0 * (anchor ** 1.3) * (0.35 + 0.65 * form_factor) * spec, 3)
    except Exception:
        return 0.0
