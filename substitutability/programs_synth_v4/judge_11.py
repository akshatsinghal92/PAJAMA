import re


# Form/preservation states. Each state has a "water" level (0 dry .. 3 liquid)
# and a "processing" level (0 untouched .. 3 heavily transformed).
_STATES = {
    "fresh":    (2, 0, ("fresh", "raw", "uncooked", "whole", "unprocessed", "skin on", "with skin")),
    "frozen":   (2, 1, ("frozen", "thawed", "defrosted", "ice")),
    "canned":   (2, 1, ("canned", "tinned", "can", "jarred", "jar", "bottled", "in brine", "pickled", "drained", "in syrup", "in water", "in oil")),
    "dried":    (0, 1, ("dried", "dry", "dehydrated", "sun-dried", "sundried", "freeze-dried", "jerky")),
    "powder":   (0, 2, ("powder", "powdered", "ground", "granulated", "flour", "meal", "dust")),
    "paste":    (1, 2, ("paste", "puree", "pureed", "concentrate", "concentrated", "tube", "mashed")),
    "liquid":   (3, 2, ("juice", "broth", "stock", "soup", "nectar", "ready-to-serve", "drink", "beverage", "milk")),
    "cooked":   (2, 2, ("cooked", "boiled", "roasted", "toasted", "baked", "fried", "sauteed", "sautéed", "grilled", "steamed", "braised", "prepared", "fat added", "stewed", "drained")),
    "formed":   (1, 3, ("chopped and formed", "formed", "patty", "restructured", "processed", "nfs")),
}

_GRAM = re.compile(r"^\s*[\d.,/]+\s*(?:g|kg|mg|ml|l|oz|lb|tbsp|tsp|cups?)?\b\.?\s*", re.I)
_PAREN = re.compile(r"\([^)]*\)")


_ADJ = ("fresh", "raw", "uncooked", "whole", "frozen", "thawed", "defrosted", "canned",
        "tinned", "jarred", "bottled", "drained", "dried", "dehydrated", "sun-dried",
        "freeze-dried", "cooked", "boiled", "roasted", "toasted", "baked", "fried",
        "sauteed", "grilled", "steamed", "braised", "prepared", "trimmed", "chopped",
        "sliced", "diced", "minced", "large", "small", "medium", "organic")

# Product-type tokens: if the USDA entry is this kind of product but the
# ingredient does not mention it, the delivery form changed.
_PRODUCT = (("soup", ("soup",)), ("ready-to-serve", ("ready-to-serve", "soup")),
            ("condensed", ("condensed",)), ("juice", ("juice",)),
            ("nectar", ("nectar",)), ("concentrate", ("concentrate",)),
            ("powder", ("powder", "powdered", "ground")),
            ("dry mix", ("mix",)), ("from mix", ("mix",)))


def _product_penalty(ing, usda):
    pen = 0.0
    for tok, alts in _PRODUCT:
        if tok in usda and not any(a in ing for a in alts):
            pen += 0.35
    return min(pen, 0.8)


def _norm(s):
    s = str(s or "").lower()
    s = s.replace("é", "e")
    return s


def _state_profile(text):
    text = " " + re.sub(r"[^a-z0-9\- ]+", " ", _norm(text)) + " "
    found = {}
    for name, (_w, _p, cues) in _STATES.items():
        for cue in cues:
            c = cue.replace("é", "e")
            if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", text):
                found[name] = found.get(name, 0) + 1
    return found


def _trigrams(s):
    s = re.sub(r"[^a-z]+", " ", s).strip()
    out = set()
    for w in s.split():
        if len(w) < 3:
            continue
        w2 = "#" + w[:-1] + "#" if w.endswith("s") and len(w) > 4 else "#" + w + "#"
        for i in range(len(w2) - 2):
            out.add(w2[i:i + 3])
    return out


def _identity(ing_core, usda):
    # Character-trigram containment of the ingredient core inside the whole USDA text,
    # weighted toward the USDA primary segment.
    a = _trigrams(ing_core)
    if not a:
        return 0.0
    full = _trigrams(usda)
    head = _trigrams(usda.split(",")[0])
    cont_full = len(a & full) / float(len(a))
    cont_head = len(a & head) / float(len(a)) if head else 0.0
    return 0.65 * cont_full + 0.35 * cont_head


def _form_compat(si, su):
    # Returns a value in [-1, 1]
    if not si and not su:
        return 0.3
    if not si:
        # Ingredient implicitly fresh/as-sold; penalize strong transformations on USDA side
        worst = 0.0
        for st in su:
            w, p, _ = _STATES[st]
            if st == "fresh":
                worst = max(worst, -0.0)
            elif st in ("liquid", "formed"):
                worst = min(worst, -0.7) if worst <= 0 else -0.7
            elif st == "cooked":
                worst = min(worst, -0.25)
            elif st in ("dried", "powder", "paste"):
                worst = min(worst, -0.2)
        return 0.25 + worst
    if not su:
        # USDA unqualified (e.g. "Gnocchi, potato"): mostly fine unless ingredient form is extreme
        pen = 0.0
        for st in si:
            if st in ("dried", "powder", "liquid"):
                pen -= 0.25
        return 0.25 + pen
    shared = set(si) & set(su)
    score = 0.0
    if shared:
        score += 0.6 + 0.15 * min(len(shared), 2)
    # Physical distance between closest pair of states
    best = 99.0
    for a in si:
        wa, pa, _ = _STATES[a]
        for b in su:
            wb, pb, _ = _STATES[b]
            d = abs(wa - wb) * 1.2 + abs(pa - pb) * 0.8
            best = min(best, d)
    score += max(-1.0, 0.4 - 0.35 * best)
    # Recoverable pairs
    recover = {frozenset(("frozen", "fresh")), frozenset(("canned", "cooked"))}
    for a in si:
        for b in su:
            if a != b and frozenset((a, b)) in recover:
                score += 0.2
    # Explicit conflicts
    if "fresh" in si and "cooked" in su and "fresh" not in su:
        score -= 0.6
    if "fresh" in si and ("dried" in su or "powder" in su) and "fresh" not in su:
        score -= 0.6
    if "liquid" in su and "liquid" not in si:
        score -= 0.6
    if "formed" in su and "formed" not in si:
        score -= 0.5
    return max(-1.0, min(1.0, score))


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_nog = _GRAM.sub("", ing)
        ing_nop = _PAREN.sub(" ", ing_nog)
        core = ing_nop.split(",")[0]
        usda_nop = _PAREN.sub(" ", usda)

        si = _state_profile(ing_nog)
        su = _state_profile(usda_nop)

        # Strip pure state adjectives (not product nouns like broth/juice/milk) from core
        core_clean = core
        for c in _ADJ:
            core_clean = re.sub(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", " ", core_clean)
        if not core_clean.strip():
            core_clean = core

        ident = _identity(core_clean, usda_nop)
        form = _form_compat(si, su)
        form = max(-1.0, form - _product_penalty(ing_nog, usda_nop))

        # Identity gates the form judgement: form agreement only counts for the same food.
        gate = ident ** 1.2
        score = 100.0 * gate * (0.45 + 0.55 * (form + 1.0) / 2.0)
        if ident < 0.2:
            score *= 0.5
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
