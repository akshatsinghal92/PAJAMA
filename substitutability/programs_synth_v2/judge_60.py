import re

# Processing and Additive Difference, variant 4: added-taste dimension
# profile with a max-norm ("most noticeable added taste") criterion.
# Each additive / processing cue contributes intensity to sensory
# dimensions a diner perceives: salty, sweet, fatty, savoury/umami, heat,
# smoky, sour, coating/crunch, and "foreign flavour". Ingredient and USDA
# entry each get a vector; we look at what the USDA entry ADDS
# (positive part of usda - ingredient) and what it REMOVES (negative part).
# A diner notices the strongest single change most, so the score is driven
# by the max-norm of the added vector, plus a smaller L1 term.

_DIMS = ("salty", "sweet", "fatty", "savory", "heat", "smoky", "sour", "coating", "foreign")
_CUE_VEC = {
    r"\bsalted\b|\bwith salt\b|\bsalt added\b": {"salty": 0.6},
    r"\bbrine\b|\bpickled\b": {"salty": 0.5, "sour": 0.6},
    r"\bsoy sauce\b|\bteriyaki\b": {"salty": 0.7, "savory": 0.5, "sweet": 0.3},
    r"\bsweetened\b|\bsugar(ed)?\b|\bsyrup\b|\bcandied\b|\bfrosted\b|\bglazed\b": {"sweet": 0.7},
    r"\bhoney\b": {"sweet": 0.6, "foreign": 0.2},
    r"\bfried\b|\bin oil\b|\boil[- ]packed\b|\bbuttered\b|\bwith butter\b": {"fatty": 0.6},
    r"\bcreamed\b|\bcream style\b|\bcreamy\b|\bcheese sauce\b|\bau gratin\b": {"fatty": 0.5, "savory": 0.3},
    r"\bbreaded\b|\bbattered\b|\bcoated\b|\btempura\b|\bcrumbs?\b": {"coating": 0.8, "fatty": 0.3},
    r"\bsauce\b|\bgravy\b|\bmarinade\b|\bmarinated\b": {"savory": 0.5, "salty": 0.3, "foreign": 0.4},
    r"\bdressing\b": {"sour": 0.4, "fatty": 0.4, "foreign": 0.3},
    r"\bseasoned\b|\bseasoning\b|\bblend\b|\band pepper\b|\bherbs\b|\bspiced\b": {"foreign": 0.5, "salty": 0.2},
    r"\bspicy\b|\bhot\b|\bchili\b|\bjalapeno\b|\bbuffalo\b": {"heat": 0.8},
    r"\bsmoked\b|\bbbq\b|\bbarbecue\b|\bcured\b": {"smoky": 0.7, "salty": 0.3},
    r"\bflavou?red\b|\bvanilla\b|\bchocolate\b|\bstrawberry\b|\bcinnamon\b|\bmaple\b|\branch\b": {"foreign": 0.6, "sweet": 0.2},
    r"\bvinegar\b|\blemon juice\b|\bcitric\b": {"sour": 0.5},
}
_CANCEL = {
    r"\bwithout salt\b|\bunsalted\b|\bno salt\b|\blow sodium\b": "salty",
    r"\bunsweetened\b|\bno sugar\b|\bsugar free\b": "sweet",
}


def _vector(text):
    v = dict.fromkeys(_DIMS, 0.0)
    for rx, contrib in _CUE_VEC.items():
        if re.search(rx, text):
            for d, x in contrib.items():
                v[d] = min(1.0, v[d] + x)
    for rx, d in _CANCEL.items():
        if re.search(rx, text):
            v[d] = 0.0
    return v


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        usda = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        if not ing.strip() or not usda.strip():
            return 0.0
        # the USDA primary food named "oil"/"honey"/"sauce" equal to the ingredient's
        # own food is identity, not an additive: neutralise shared words
        shared = set(re.findall(r"[a-z]+", ing)) & set(re.findall(r"[a-z]+", usda))
        u_text = usda
        for w in shared:
            u_text = re.sub(r"\b" + re.escape(w) + r"\b", " ", u_text)
            ing_text = ing
        vi = _vector(ing)
        vu = _vector(u_text)
        added = [max(0.0, vu[d] - vi[d]) for d in _DIMS]
        removed = [max(0.0, vi[d] - vu[d]) for d in _DIMS]
        peak = max(added)
        l1 = sum(added)
        loss = 0.55 * peak + 0.15 * l1 + 0.2 * max(removed) + 0.05 * sum(removed)
        score = 100.0 * (1.0 - min(1.0, loss))
        return round(max(0.0, score), 2)
    except Exception:
        return 0.0
