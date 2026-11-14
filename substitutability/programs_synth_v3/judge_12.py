import re

# Preparation-state lattice: each state word maps to a "state class".
# Mechanical states are free (a cook can trivially apply them), so they map to None.
_STATE_CLASS = {
    # trivially applicable / ignorable
    "chopped": None, "diced": None, "minced": None, "sliced": None, "shredded": None,
    "grated": None, "cubed": None, "julienned": None, "halved": None, "quartered": None,
    "crushed": None, "peeled": None, "trimmed": None, "pitted": None, "seeded": None,
    "cut": None, "torn": None, "rinsed": None, "washed": None, "drained": None,
    "whole": None, "pieces": None, "boneless": None, "skinless": None,
    # raw-ish
    "raw": "RAW", "fresh": "RAW", "uncooked": "RAW", "unprepared": "RAW",
    # temperature preservation (ignorable relative to raw)
    "frozen": "COLD", "thawed": "COLD", "chilled": "COLD", "refrigerated": "COLD",
    # moist-heat cooking
    "cooked": "MOIST", "boiled": "MOIST", "simmered": "MOIST", "steamed": "MOIST",
    "poached": "MOIST", "stewed": "MOIST", "braised": "MOIST", "blanched": "MOIST",
    # dry-heat cooking
    "roasted": "DRY", "baked": "DRY", "grilled": "DRY", "broiled": "DRY",
    "toasted": "DRY", "smoked": "DRY", "seared": "DRY", "barbecued": "DRY",
    # fat cooking
    "fried": "FRY", "deep-fried": "FRY", "sauteed": "FRY", "pan-fried": "FRY",
    "breaded": "FRY", "battered": "FRY", "crispy": "FRY",
    # preserved
    "dried": "DRIED", "dehydrated": "DRIED", "sun-dried": "DRIED", "mature": "DRIED",
    "canned": "CANNED", "jarred": "CANNED", "pickled": "PICKLED", "brined": "PICKLED",
    "marinated": "PICKLED", "cured": "PICKLED",
    # processed forms
    "ground": "POWDER", "powdered": "POWDER", "powder": "POWDER",
    "paste": "PASTE", "puree": "PASTE", "pureed": "PASTE", "mashed": "PASTE",
    "juice": "LIQUID", "concentrate": "LIQUID",
}

# Pairwise transition costs between state classes (symmetric). Missing pairs -> default.
_COST = {
    frozenset(["RAW", "COLD"]): 0.5,
    frozenset(["MOIST", "DRY"]): 3.0,
    frozenset(["MOIST", "FRY"]): 6.0,
    frozenset(["DRY", "FRY"]): 4.5,
    frozenset(["RAW", "MOIST"]): 5.0,
    frozenset(["RAW", "DRY"]): 6.0,
    frozenset(["RAW", "FRY"]): 8.0,
    frozenset(["COLD", "MOIST"]): 4.5,
    frozenset(["COLD", "DRY"]): 5.5,
    frozenset(["COLD", "FRY"]): 7.0,
    frozenset(["DRIED", "RAW"]): 2.0,   # dried legumes listed as "mature seeds, raw"
    frozenset(["CANNED", "MOIST"]): 2.0,
    frozenset(["CANNED", "RAW"]): 4.0,
    frozenset(["PICKLED", "RAW"]): 6.5,
    frozenset(["POWDER", "RAW"]): 7.0,
    frozenset(["PASTE", "RAW"]): 4.0,
    frozenset(["LIQUID", "RAW"]): 7.5,
}
_DEFAULT_COST = 5.5

_STOP = {
    "and", "or", "with", "of", "the", "a", "an", "in", "for", "to", "from", "as",
    "ns", "nfs", "type", "style", "made", "prepared", "tube", "plain", "regular",
    "eaten", "fat", "added", "no", "not", "salt", "package", "commercial",
}


def _norm(word):
    w = word.lower().strip("-'")
    if w in _STATE_CLASS:
        return w
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            base = w[: -len(suf)] + ("y" if suf == "ies" else "")
            if base in _STATE_CLASS:
                return base
            return base
    return w


def _tokenize(text):
    text = (text or "").lower()
    text = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", text)
    text = text.replace("(", " ").replace(")", " ")
    raw = re.findall(r"[a-z][a-z\-']*", text)
    return [_norm(t) for t in raw]


def _split(tokens):
    states, core = set(), []
    for t in tokens:
        if t in _STATE_CLASS:
            cls = _STATE_CLASS[t]
            if cls is not None:
                states.add(cls)
        elif t not in _STOP and len(t) > 1:
            core.append(t)
    return states, core


def _state_penalty(ing_states, usda_states):
    """Minimal matching cost between the two state-class sets."""
    if not ing_states and not usda_states:
        return 0.0
    # An unstated side is treated as RAW-equivalent but with lighter penalty,
    # since a recipe ingredient without a state is usually the default form.
    a = set(ing_states) or {"UNSTATED"}
    b = set(usda_states) or {"UNSTATED"}
    total = 0.0
    for side, other in ((a, b), (b, a)):
        for s in side:
            if s in other:
                continue
            best = None
            for o in other:
                if s == "UNSTATED" or o == "UNSTATED":
                    t = s if o == "UNSTATED" else o
                    c = {"RAW": 0.3, "COLD": 0.6, "DRIED": 2.5, "CANNED": 2.5,
                         "MOIST": 2.5, "DRY": 3.5, "FRY": 5.0, "PICKLED": 4.0,
                         "POWDER": 4.5, "PASTE": 3.5, "LIQUID": 5.0}.get(t, 0.0)
                else:
                    c = _COST.get(frozenset([s, o]), _DEFAULT_COST)
                best = c if best is None else min(best, c)
            total += best if best is not None else _DEFAULT_COST
    # average over both directions so one differing state is not double counted too heavily
    return total / 2.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_tokens = _tokenize(str(ingredient))
        usda_tokens = _tokenize(str(usda_match))
        if not ing_tokens or not usda_tokens:
            return 0.0

        ing_states, ing_core = _split(ing_tokens)
        usda_states, usda_core = _split(usda_tokens)

        # The state dimension only matters if the foods are the same underneath.
        # Gate: identity anchor = how much of the ingredient core is present in USDA core,
        # weighted by position in USDA (primary food first).
        usda_pos = {}
        for i, t in enumerate(usda_core):
            usda_pos.setdefault(t, i)
        if ing_core:
            hits = 0.0
            for t in ing_core:
                if t in usda_pos:
                    hits += 1.0 / (1.0 + 0.15 * usda_pos[t])
                else:
                    # partial: prefix match (e.g. favas / fava, broadbeans)
                    for u in usda_pos:
                        if len(t) >= 4 and len(u) >= 4 and (u.startswith(t[:4]) or t in u or u in t):
                            hits += 0.6 / (1.0 + 0.15 * usda_pos[u])
                            break
            recall = hits / len(ing_core)
        else:
            recall = 0.3

        primary_hit = 1.0 if usda_core and any(
            usda_core[0] == t or (len(t) >= 4 and (usda_core[0] in t or t in usda_core[0]))
            for t in ing_core
        ) else 0.0

        # Unexplained extra USDA descriptors (non-state) that may imply a different product
        extra = [u for u in usda_core if u not in set(ing_core)]
        extra_ratio = len(extra) / max(1, len(usda_core))

        anchor = 0.55 * min(1.0, recall) + 0.30 * primary_hit + 0.15 * (1.0 - extra_ratio)

        penalty = _state_penalty(ing_states, usda_states)
        state_score = 10.0 / (1.0 + 0.45 * penalty)  # 10 when equivalent, decays with cost

        score = state_score * (0.15 + 0.85 * anchor)
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
