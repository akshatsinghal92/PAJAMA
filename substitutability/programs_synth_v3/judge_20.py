import re

# Form classes with lexical cues
_FORM_CUES = {
    "fresh": ["fresh", "raw", "uncooked", "unprocessed"],
    "frozen": ["frozen", "freeze", "thawed", "iqf"],
    "canned": ["canned", "can", "tinned", "drained", "jarred", "jar", "bottled", "in syrup", "in water", "in brine", "pickled"],
    "dried": ["dried", "dry", "dehydrated", "sun-dried", "freeze-dried", "soaked", "mature seeds"],
    "powder": ["powder", "powdered", "ground", "flour", "meal", "granules", "granulated"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated", "tube", "mashed"],
    "liquid": ["broth", "stock", "juice", "milk", "liquid", "extract", "syrup"],
    "soup": ["soup", "ready-to-serve", "ready to serve", "condensed", "prepared", "ready-to-eat"],
    "cooked": ["cooked", "roasted", "boiled", "baked", "fried", "grilled", "braised", "stewed", "steamed", "smoked", "toasted"],
}

# Recoverability: how easily form a (ingredient) is reached from form b (usda)
# 1.0 identical, 0 incompatible
_COMPAT = {
    ("fresh", "frozen"): 0.6, ("frozen", "fresh"): 0.75,
    ("fresh", "canned"): 0.25, ("canned", "fresh"): 0.35,
    ("fresh", "dried"): 0.15, ("dried", "fresh"): 0.3,
    ("fresh", "cooked"): 0.25, ("cooked", "fresh"): 0.55,
    ("dried", "powder"): 0.45, ("powder", "dried"): 0.4,
    ("paste", "powder"): 0.2, ("powder", "paste"): 0.15,
    ("paste", "fresh"): 0.35, ("fresh", "paste"): 0.15,
    ("liquid", "soup"): 0.15, ("soup", "liquid"): 0.3,
    ("liquid", "paste"): 0.3, ("paste", "liquid"): 0.2,
    ("canned", "frozen"): 0.35, ("frozen", "canned"): 0.3,
    ("frozen", "cooked"): 0.25, ("cooked", "frozen"): 0.4,
    ("canned", "cooked"): 0.5, ("cooked", "canned"): 0.5,
    ("dried", "cooked"): 0.3, ("cooked", "dried"): 0.2,
    ("dried", "canned"): 0.35, ("canned", "dried"): 0.3,
}

_STOP = set("and or with of the a an in to for from cut into small large medium fine finely "
            "chopped diced sliced minced cubed trimmed visible fat optional peeled seeded "
            "whole pieces piece about plus more taste divided overnight".split())


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)\b\.?", " ", t)
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    head, _, tail = t.partition(",")
    return head.strip(), (tail + " " + paren).strip()


def _detect_forms(text):
    t = " " + re.sub(r"[^a-z\- ]", " ", text.lower()) + " "
    found = {}
    for form, cues in _FORM_CUES.items():
        best = 0
        for c in cues:
            if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", t):
                best = max(best, len(c.split()))
        if best:
            found[form] = best
    return found


def _tokens(text):
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) < 3 or w in _STOP:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "shxo":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return out


def _pair_compat(a, b):
    if a == b:
        return 1.0
    return _COMPAT.get((a, b), 0.1)


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = str(ingredient)
        usda = str(usda_match)
        head, state = _clean_ingredient(ing)
        if not head:
            head = ing.lower()

        ing_forms = _detect_forms(head + " " + state)
        usda_forms = _detect_forms(usda)

        # Ingredient implicitly fresh/raw when no form stated
        if not ing_forms:
            ing_forms = {"fresh": 1}
            implicit = True
        else:
            implicit = False
        if not usda_forms:
            usda_forms = {"fresh": 1}

        # 'thawed' implies frozen source which is recoverable to fresh-like
        # Form agreement: average over ingredient forms of best matching usda form
        scores = []
        for f in ing_forms:
            scores.append(max(_pair_compat(f, g) for g in usda_forms))
        form_score = sum(scores) / len(scores)

        # Penalize USDA forms that ingredient never asked for (extra processing)
        extras = [g for g in usda_forms if g not in ing_forms]
        for g in extras:
            worst = max(_pair_compat(f, g) for f in ing_forms)
            if implicit and g == "cooked":
                form_score -= 0.25
            elif g in ("soup", "paste", "powder", "dried", "canned") and worst < 0.5:
                form_score -= 0.2 * (1 - worst)
        form_score = max(0.0, min(1.0, form_score))

        # Identity gate: form match only matters if same food
        it = _tokens(head)
        primary = usda.split(",")[0]
        ut = _tokens(usda)
        pt = _tokens(primary)
        if it:
            overlap = len(it & ut) / len(it)
            prim_hit = 1.0 if (it & pt) else 0.0
        else:
            overlap, prim_hit = 0.0, 0.0
        identity = 0.6 * overlap + 0.4 * prim_hit
        # Unmatched ingredient qualifier words (e.g. variety) reduce identity
        missing = it - ut
        if missing and overlap > 0:
            identity *= 0.85 ** len(missing)

        score = 10.0 * (0.55 * form_score * (0.3 + 0.7 * identity) + 0.45 * identity)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
