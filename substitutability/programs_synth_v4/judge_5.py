import re

# Preparation states a cook can trivially apply or ignore.
_TRIVIAL_STATES = {
    "raw", "fresh", "chopped", "diced", "minced", "sliced", "shredded", "thawed",
    "frozen", "grated", "cubed", "trimmed", "peeled", "halved", "quartered",
    "crushed", "julienned", "torn", "rinsed", "washed", "drained", "uncooked",
    "whole", "pitted", "seeded", "cut", "skin", "on", "with", "without", "leftover",
    "optional", "divided", "packed", "cleaned", "deveined", "boneless", "skinless",
}

# State families that change cooking/outcome. Members of a family are equivalent.
_STATE_FAMILIES = {
    "fried": {"fried", "frying", "deep-fried", "pan-fried", "fryers"},
    "oilroast": {"oil-roasted"},
    "roasted": {"roasted", "dry-roasted"},
    "heat": {"cooked", "baked", "grilled", "broiled", "heat", "braised", "boiled",
             "simmered", "stewed", "poached", "steamed", "sauteed", "seared"},
    "toasted": {"toasted"},
    "smoked": {"smoked", "cured"},
    "canned": {"canned"},
    "dried": {"dried", "dehydrated", "dry"},
    "melted": {"melted"},
    "fermented": {"fermented", "pickled"},
    "sauce": {"sauce", "nectar", "juice", "syrup", "drink", "beverage", "soup"},
    "puree": {"puree", "purée", "pureed", "sauce", "applesauce", "mashed"},
}

_FILLER = {
    "and", "or", "of", "the", "a", "an", "for", "to", "in", "from", "made", "mixed",
    "species", "regular", "type", "style", "all", "varieties", "plain", "salad",
    "cooking", "ns", "nfs", "as", "ingredient", "by-products", "products", "meats",
    "variety", "separable", "lean", "fat", "choice", "select", "includes", "broilers",
}

_ALIASES = {
    "innards": "giblets", "gizzards": "giblets", "livers": "giblets",
    "pinyon": "pine", "sufu": "tofu", "fuyu": "tofu", "applesauce": "apple",
    "purée": "puree", "yellow": "golden", "oleic": "oleic",
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)?\b", " ", t)
    t = re.sub(r"[^a-zéè\-\s]", " ", t)
    return [w.strip("-") for w in t.split() if w.strip("-")]


def _split(text):
    """Return (core token set, state-family set, trivial-state count, raw tokens)."""
    words = _tokens(text)
    core, fams, triv = set(), set(), 0
    for w in words:
        hit = False
        for fam, members in _STATE_FAMILIES.items():
            if w in members:
                fams.add(fam)
                hit = True
        if w in ("dry", "heat") and "heat" in fams:
            hit = True
        if w in _TRIVIAL_STATES:
            triv += 1
            continue
        if w in _FILLER:
            continue
        s = _stem(_ALIASES.get(w, w))
        s = _ALIASES.get(s, s)
        if hit and w not in ("applesauce",):
            continue
        if len(s) > 1:
            core.add(s)
    return core, fams, triv, words


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        i_core, i_fam, i_triv, i_words = _split(ingredient)
        u_core, u_fam, _, u_words = _split(usda_match)
        if not i_core or not u_core:
            return 1.0

        # Primary USDA food: first comma segment.
        primary_raw = str(usda_match).split(",")[0]
        p_core, _, _, _ = _split(primary_raw)

        shared = i_core & u_core
        ing_cov = len(shared) / len(i_core)
        usda_cov = len(shared) / len(u_core)
        prim_hit = 1.0 if (p_core & i_core) else 0.0

        identity = 6.0 * ing_cov + 2.0 * usda_cov + 2.0 * prim_hit
        if not shared:
            identity = 0.0

        # Preparation-state equivalence.
        state = 0.0
        only_u = u_fam - i_fam
        only_i = i_fam - u_fam
        matched = i_fam & u_fam
        state += 1.0 * len(matched)
        # "for frying" in the ingredient is a usage, not the ingredient state.
        if "fried" in only_i and re.search(r"for\s+fry", str(ingredient).lower()):
            only_i.discard("fried")
        state -= 2.5 * len(only_u)
        state -= 2.0 * len(only_i)
        # Pure trivial differences (raw/fresh/diced) are free.
        if not only_u and not only_i:
            state += 1.5

        # Multi-food ingredient ("X and Y") is not one substitutable item.
        compound = 0.0
        if re.search(r"\b(and|&)\b", re.sub(r"\([^)]*\)", "", str(ingredient).lower().split(",")[0])):
            compound = -3.0

        score = identity + (state if shared else min(state, 0.0)) + compound
        return round(max(0.0, min(15.0, score)), 3)
    except Exception:
        return 0.0
