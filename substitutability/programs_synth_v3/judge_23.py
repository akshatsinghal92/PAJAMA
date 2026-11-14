import re
import math

# Variant 7: form-state probability vectors + transition cost matrix.
# Each text is mapped to a soft distribution over physical/preservation states.
# The expected "transition cost" between the two distributions (earth-mover style
# over a small hand-built cost matrix) drives the score, modulated by a
# primary-food anchor check and a concentration/derived-product detector.

_STATES = ["fresh", "frozen", "canned", "dried", "powder", "paste",
           "liquid", "cooked", "cured", "dessert"]

_CUES = {
    "fresh": ["fresh", "raw", "ripe", "uncooked", "chunks", "cubed", "sliced", "diced",
              "chopped", "whole", "plain"],
    "frozen": ["frozen", "thawed", "ice"],
    "canned": ["canned", "can", "tinned", "jarred", "jar", "bottled", "drained",
               "in syrup", "in water", "in brine", "in oil", "pickled"],
    "dried": ["dried", "dry", "dehydrated", "sun-dried", "flakes", "flaked"],
    "powder": ["powder", "powdered", "ground", "granulated", "meal", "flour", "spices"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated", "tube",
              "spread", "butter"],
    "liquid": ["juice", "broth", "stock", "soup", "nectar", "drink", "beverage",
               "milk", "ready-to-serve", "ready to serve", "condensed", "smoothie"],
    "cooked": ["cooked", "fried", "pan-fried", "roasted", "baked", "boiled", "steamed",
               "grilled", "braised", "stewed", "broiled", "simmered", "microwaved"],
    "cured": ["smoked", "cured", "salted", "sausage", "jerky", "pickled"],
    "dessert": ["frozen yogurt", "ice cream", "sherbet", "sorbet", "pie", "cake",
                "candied", "with vegetables", "with fruit", "dessert", "pudding"],
}

# Symmetric-ish transition cost between states (0 = identical, 1 = incompatible).
_COST = {
    ("fresh", "frozen"): 0.2, ("fresh", "canned"): 0.55, ("fresh", "dried"): 0.8,
    ("fresh", "powder"): 0.9, ("fresh", "paste"): 0.7, ("fresh", "liquid"): 0.95,
    ("fresh", "cooked"): 0.6, ("fresh", "cured"): 0.6, ("fresh", "dessert"): 1.0,
    ("frozen", "canned"): 0.5, ("frozen", "dried"): 0.8, ("frozen", "powder"): 0.9,
    ("frozen", "paste"): 0.7, ("frozen", "liquid"): 0.85, ("frozen", "cooked"): 0.55,
    ("frozen", "cured"): 0.65, ("frozen", "dessert"): 0.95,
    ("canned", "dried"): 0.75, ("canned", "powder"): 0.85, ("canned", "paste"): 0.55,
    ("canned", "liquid"): 0.6, ("canned", "cooked"): 0.35, ("canned", "cured"): 0.5,
    ("canned", "dessert"): 0.9,
    ("dried", "powder"): 0.35, ("dried", "paste"): 0.6, ("dried", "liquid"): 0.9,
    ("dried", "cooked"): 0.7, ("dried", "cured"): 0.45, ("dried", "dessert"): 0.9,
    ("powder", "paste"): 0.55, ("powder", "liquid"): 0.85, ("powder", "cooked"): 0.8,
    ("powder", "cured"): 0.8, ("powder", "dessert"): 0.95,
    ("paste", "liquid"): 0.6, ("paste", "cooked"): 0.6, ("paste", "cured"): 0.7,
    ("paste", "dessert"): 0.9,
    ("liquid", "cooked"): 0.8, ("liquid", "cured"): 0.9, ("liquid", "dessert"): 0.85,
    ("cooked", "cured"): 0.45, ("cooked", "dessert"): 0.9,
    ("cured", "dessert"): 1.0,
}

_DERIVED_NOUNS = ["juice", "soup", "frozen yogurt", "ice cream", "nectar", "sauce",
                  "pie", "cake", "drink", "smoothie", "chips", "bar", "patty",
                  "nuggets", "sticks", "with vegetables", "with fruit", "babyfood"]

_STOP = {"g", "kg", "ml", "of", "and", "or", "the", "a", "an", "with", "without",
         "in", "for", "to", "from", "raw", "fresh", "plain", "ripe", "cubed",
         "sliced", "diced", "chopped", "whole", "chunks", "large", "small", "medium"}


def _cost(a, b):
    if a == b:
        return 0.0
    return _COST.get((a, b), _COST.get((b, a), 0.8))


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b", " ", t)
    return t


def _state_vector(text, default_fresh=True):
    t = " " + re.sub(r"[(),;]", " , ", text) + " "
    mass = dict.fromkeys(_STATES, 0.0)
    for st, cues in _CUES.items():
        for cue in cues:
            pat = r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])"
            n = len(re.findall(pat, t))
            if n:
                mass[st] += n * (1.5 if " " in cue else 1.0)
    # 'thawed' after frozen means the delivered form is still frozen-origin produce
    if "frozen yogurt" in t or "ice cream" in t:
        mass["frozen"] = max(0.0, mass["frozen"] - 1.0)
    total = sum(mass.values())
    if total <= 0:
        if default_fresh:
            mass["fresh"] = 1.0
            total = 1.0
        else:
            return None
    return {k: v / total for k, v in mass.items()}


def _transport_cost(p, q):
    # Greedy earth-mover approximation over the small state space.
    p = dict(p)
    q = dict(q)
    cost = 0.0
    for s in _STATES:
        m = min(p[s], q[s])
        p[s] -= m
        q[s] -= m
    pairs = sorted(((_cost(a, b), a, b) for a in _STATES for b in _STATES if a != b))
    for c, a, b in pairs:
        if p[a] <= 1e-9 or q[b] <= 1e-9:
            continue
        m = min(p[a], q[b])
        cost += m * c
        p[a] -= m
        q[b] -= m
    return cost


def _tokens(text):
    toks = re.findall(r"[a-z]+", text)
    out = set()
    for w in toks:
        if w in _STOP or len(w) < 3:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Strip parentheticals from ingredient for anchor but keep them for state cues
        ing_core = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        primary = usda.split(",")[0].strip()

        # --- Anchor: does the USDA primary food relate to the ingredient? ---
        ing_t = _tokens(ing_core)
        usda_t = _tokens(usda)
        prim_t = _tokens(primary)
        if not ing_t:
            ing_t = _tokens(ing)
        shared = ing_t & usda_t
        prim_hit = len(ing_t & prim_t) > 0
        anchor = 0.0
        if ing_t:
            anchor = len(shared) / float(len(ing_t))
        if prim_hit:
            anchor = min(1.0, anchor + 0.35)
        if not shared:
            # different food altogether: form match is meaningless
            return round(1.0 + 0.5 * (1 - _transport_cost(_state_vector(ing),
                                                           _state_vector(usda))), 3)

        # --- Form distributions and transport cost ---
        p = _state_vector(ing)
        q = _state_vector(usda)
        tc = _transport_cost(p, q)
        form_sim = 1.0 - tc

        # --- Derived-product / concentration shift ---
        penalty = 0.0
        for d in _DERIVED_NOUNS:
            if d in usda and d not in ing:
                # stronger if it is part of the primary noun phrase
                penalty += 0.35 if d in primary else 0.2
        # unrequested composite additions like "with X"
        if re.search(r"\bwith\s+[a-z]+", usda) and "with" not in ing:
            penalty += 0.1
        # unrequested composition modifiers (lowfat, reduced) change texture/taste
        mods = re.findall(r"\b(lowfat|low fat|nonfat|fat free|reduced|lactose|light|"
                          r"sweetened|unsweetened|condensed|instant)\b", usda)
        unreq = [m for m in mods if m not in ing]
        if unreq:
            # if ingredient explicitly says "plain" or nothing about fat, mild hit
            penalty += min(0.3, 0.12 * len(unreq))
        # cooking state the recipe did not ask for (recipe will cook it itself)
        if q.get("cooked", 0) > 0.3 and p.get("cooked", 0) == 0:
            penalty += 0.15
        penalty = min(penalty, 0.8)

        # --- Combine ---
        score = 10.0 * (0.45 * form_sim + 0.35 * anchor + 0.2) * (1.0 - penalty)
        # bonus for exact same primary noun phrase
        if primary and primary in ing_core:
            score += 0.8
        score = max(0.0, min(10.0, score))
        if math.isnan(score):
            return 0.0
        return round(score, 3)
    except Exception:
        return 0.0
