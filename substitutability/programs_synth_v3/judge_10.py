import re

# Each state word maps to a "state class". Classes within the same group are
# trivially interconvertible by a cook; transitions between groups cost points.
_STATE_CLASS = {
    # trivial mechanical cuts (group "cut")
    "chopped": "cut", "diced": "cut", "minced": "cut", "sliced": "cut",
    "shredded": "cut", "grated": "cut", "cubed": "cut", "julienned": "cut",
    "halved": "cut", "quartered": "cut", "crushed": "cut", "trimmed": "cut",
    "peeled": "cut", "pitted": "cut", "cored": "cut", "seeded": "cut",
    "deveined": "cut", "boneless": "cut", "skinless": "cut", "fillets": "cut",
    "fillet": "cut", "whole": "cut", "torn": "cut", "rinsed": "cut",
    "washed": "cut", "drained": "cut", "zested": "cut",
    # temperature / storage states that are trivial
    "thawed": "temp", "frozen": "temp", "chilled": "temp", "refrigerated": "temp",
    "defrosted": "temp", "softened": "temp", "room": "temp",
    # raw-ish
    "raw": "raw", "fresh": "raw", "uncooked": "raw",
    # wet heat
    "boiled": "wet", "braised": "wet", "stewed": "wet", "simmered": "wet",
    "poached": "wet", "steamed": "wet", "blanched": "wet",
    # dry heat
    "roasted": "dry", "baked": "dry", "grilled": "dry", "broiled": "dry",
    "toasted": "dry", "seared": "dry",
    # fat heat
    "fried": "fat", "sauteed": "fat", "deep-fried": "fat", "pan-fried": "fat",
    "breaded": "fat", "battered": "fat",
    # generic cooked
    "cooked": "cooked", "heated": "cooked", "prepared": "cooked",
    # preservation that changes outcome
    "dried": "preserved", "dehydrated": "preserved", "canned": "preserved",
    "smoked": "preserved", "cured": "preserved", "pickled": "preserved",
    "salted": "preserved", "candied": "preserved", "sweetened": "preserved",
    "powdered": "form", "powder": "form", "ground": "form", "paste": "form",
    "puree": "form", "pureed": "form", "juice": "form", "flakes": "form",
}

# cost of moving from ingredient class (row) to usda class (col)
_GROUP_COST = {
    ("raw", "raw"): 0, ("raw", "cut"): 0, ("raw", "temp"): 0.5,
    ("raw", "cooked"): 4, ("raw", "wet"): 4, ("raw", "dry"): 4.5, ("raw", "fat"): 6,
    ("raw", "preserved"): 5, ("raw", "form"): 4,
    ("cooked", "wet"): 1, ("cooked", "dry"): 1, ("cooked", "fat"): 2.5,
    ("cooked", "raw"): 3.5, ("cooked", "preserved"): 3.5, ("cooked", "form"): 3,
    ("wet", "dry"): 3, ("wet", "fat"): 4, ("dry", "fat"): 3,
    ("wet", "raw"): 4, ("dry", "raw"): 4.5, ("fat", "raw"): 6,
    ("preserved", "raw"): 5, ("preserved", "cooked"): 3.5,
    ("form", "raw"): 4, ("form", "preserved"): 2.5, ("form", "form"): 0,
}

_STOP = set("""g kg mg ml l oz lb lbs tsp tbsp cup cups of and or the a an with
for to from in into on nfs ns not further specified made type style tube
variety meats products by-products by about approx large small medium
plain regular""".split())


def _cost(a, b):
    if a == b:
        return 0.0
    if (a, b) in _GROUP_COST:
        return _GROUP_COST[(a, b)]
    if (b, a) in _GROUP_COST:
        return _GROUP_COST[(b, a)]
    if "cut" in (a, b) or "temp" in (a, b):
        return 0.3
    return 3.0


def _tok(text):
    text = text.lower()
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb|lbs)?\b", " ", text)
    text = text.replace("sautéed", "sauteed")
    return [t for t in re.findall(r"[a-z][a-z\-]*", text)]


def _norm(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _split(tokens):
    states, content = [], []
    for t in tokens:
        if t in _STATE_CLASS:
            states.append(_STATE_CLASS[t])
        elif t not in _STOP and len(t) > 1:
            content.append(_norm(t))
    return states, content


def _dominant(states):
    # most "transformative" state wins; cut/temp are ignorable
    order = ["fat", "preserved", "form", "dry", "wet", "cooked", "raw"]
    for o in order:
        if o in states:
            return o
    return "raw"  # unstated state defaults to raw/as-purchased


def _tri(s):
    s = " " + s + " "
    return set(s[i:i + 3] for i in range(len(s) - 2))


def _soft_overlap(a, b):
    # fraction of tokens in a that match some token in b (exact, prefix, or trigram)
    if not a:
        return 0.0
    tot = 0.0
    for x in a:
        best = 0.0
        for y in b:
            if x == y:
                best = 1.0
                break
            if len(x) >= 4 and len(y) >= 4 and (x.startswith(y[:4]) or y.startswith(x[:4])):
                best = max(best, 0.8)
            else:
                tx, ty = _tri(x), _tri(y)
                j = len(tx & ty) / float(len(tx | ty) or 1)
                best = max(best, j)
        tot += best
    return tot / len(a)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = ing.split(",")[0]
        it, ut = _tok(ing), _tok(usda)
        i_states, i_content = _split(it)
        u_states, u_content = _split(ut)
        _, i_main = _split(_tok(ing_main))
        if not i_main:
            i_main = i_content
        _, u_primary = _split(_tok(usda.split(",")[0]))

        cov_ing = _soft_overlap(i_main, u_content)       # ingredient covered by usda
        cov_usda = _soft_overlap(u_content, i_content)   # usda covered by ingredient
        prim = _soft_overlap(u_primary, i_content) if u_primary else 0.0
        identity = 0.5 * cov_ing + 0.25 * cov_usda + 0.25 * prim   # 0..1

        di, du = _dominant(i_states), _dominant(u_states)
        trans_cost = _cost(di, du)
        trans_i = set(s for s in i_states if s not in ("cut", "temp"))
        trans_u = set(s for s in u_states if s not in ("cut", "temp", "raw"))
        extra_pen = 0.6 * len(trans_u - trans_i - {du})
        shared = set(t for t in it if t in _STATE_CLASS) & set(t for t in ut if t in _STATE_CLASS)
        bonus = 0.3 * len([w for w in shared if _STATE_CLASS[w] not in ("cut", "temp")])

        state_pen = min(4.0, 0.7 * trans_cost + extra_pen) - min(0.6, bonus)
        score = 7.0 * identity + 3.0 - state_pen
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
