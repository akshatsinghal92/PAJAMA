import re

TRIVIAL = {"raw", "fresh", "chopped", "diced", "minced", "sliced", "shredded", "thawed",
           "grated", "crushed", "cubed", "peeled", "trimmed", "whole", "pieces", "frozen",
           "optional", "fine", "finely", "coarsely", "large", "small", "medium", "unsalted",
           "leaves", "seeds", "skin", "with", "without", "and", "or", "of", "the", "for",
           "a", "to", "taste", "g", "lean", "separable", "fat", "choice", "select", "all",
           "grades", "boneless", "skinless", "regular", "ground", "dried", "drained",
           "rinsed", "washed", "halved", "torn", "packed", "cut", "into", "from", "on",
           "in", "made", "tube", "heated", "warm", "cold", "mixed", "species", "common"}

# cooking / processing states that change the dish
CHANGE = {
    "cooked": "cook", "fried": "fry", "baked": "bake", "roasted": "roast", "boiled": "boil",
    "grilled": "grill", "broiled": "broil", "toasted": "toast", "steamed": "steam",
    "braised": "braise", "stewed": "stew", "sauteed": "fry", "smoked": "smoke",
    "pickled": "pickle", "canned": "can", "cured": "cure", "fermented": "ferment",
    "melted": "melt", "pureed": "puree", "puree": "puree", "purée": "puree",
    "juice": "juice", "sauce": "sauce", "powder": "powder", "dehydrated": "dry",
    "candied": "sweet", "sweetened": "sweet", "unsweetened": "unsweet", "breaded": "bread",
    "battered": "batter", "leftover": "cook", "stuffed": "stuff", "salted": "salt",
    "nectar": "juice", "paste": "paste", "microwaved": "cook", "poached": "poach",
    "heated": "cook", "creamed": "cream", "glazed": "glaze", "marinated": "marinate",
    "dry": "dry", "dried": "dry",
}
EQUIV = {"cook": {"cook"}}


def _clean(s):
    s = s.lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|gr|grams?|kg|ml|oz)?\b", " ", s)
    s = re.sub(r"[\(\)\[\]\"/;:%0-9]", " ", s)
    s = s.replace("-", " ")
    return s


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxzh":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(s):
    return [_stem(w) for w in re.findall(r"[a-zà-ÿ]+", s)]


def _states(toks):
    out = set()
    for t in toks:
        for k, v in CHANGE.items():
            if t == _stem(k) or t == k:
                out.add(v)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient or ""))
        usd = _clean(str(usda_match or ""))
        if not ing.strip() or not usd.strip():
            return 0.0
        ing_t = _tokens(ing)
        # primary food = first comma segment of USDA
        usd_segments = [seg for seg in usd.split(",") if seg.strip()]
        usd_t = _tokens(usd)
        primary_t = _tokens(usd_segments[0]) if usd_segments else usd_t
        # ingredient main part before comma
        ing_main = _tokens(ing.split(",")[0])

        triv = {_stem(x) for x in TRIVIAL}
        chg = {_stem(x) for x in CHANGE}
        ing_food = [t for t in ing_main if t not in triv and t not in chg and len(t) > 1]
        usd_food = [t for t in usd_t if t not in triv and t not in chg and len(t) > 1]
        prim_food = [t for t in primary_t if t not in triv and t not in chg and len(t) > 1]
        if not ing_food or not usd_food:
            ing_food = [t for t in ing_t if len(t) > 1]
            usd_food = [t for t in usd_t if len(t) > 1]
            if not ing_food or not usd_food:
                return 0.0

        # food-identity score
        iset, uset = set(ing_food), set(usd_food)
        inter = iset & uset
        # prefix-tolerant matches (e.g. sufu/tofu not; asadero/asadero yes)
        fuzzy = 0
        for a in iset - inter:
            for b in uset - inter:
                if len(a) >= 5 and len(b) >= 5 and (a[:5] == b[:5]):
                    fuzzy += 1
                    break
        cover = (len(inter) + 0.6 * fuzzy) / max(1, len(iset))
        back = len(inter) / max(1, len(uset))
        head_hit = 1.0 if (ing_food[-1] in uset or any(p in iset for p in prim_food)) else 0.0
        identity = 0.5 * cover + 0.2 * min(1.0, back * 1.5) + 0.3 * head_hit
        if not inter and not fuzzy:
            identity *= 0.2

        # multi-food ingredient ("X and Y") vs single-food USDA entry
        if re.search(r"\b(and|with|&)\b", ing.split(",")[0]) and " and " in ing.split(",")[0]:
            if len(uset) < len(iset):
                identity *= 0.6

        # preparation-state comparison
        si = _states(ing_t)
        su = _states(usd_t)
        # treat cooking verbs as one family
        cookfam = {"cook", "fry", "bake", "roast", "boil", "grill", "broil", "steam", "braise", "stew", "poach"}
        def fam(S):
            return {("cook" if x in cookfam else x) for x in S}
        # keep exact method too
        mism = 0.0
        for x in si - su:
            if x in cookfam and (su & cookfam):
                mism += 0.5  # both cooked, different method
            else:
                mism += 1.0
        for x in su - si:
            if x in cookfam and (si & cookfam):
                continue
            mism += 1.0
        # USDA "raw" and ingredient has a changing state, or vice versa
        if "raw" in usd_t and (si & (cookfam | {"fry", "melt", "smoke", "pickle", "can"})):
            mism += 1.0
        # trivially-ignorable state words give small reward when matching
        bonus = 0.0
        if "raw" in ing_t and "raw" in usd_t:
            bonus += 0.4
        if si == su:
            bonus += 0.3
        # USDA descriptors piling up with unrelated detail = lower fidelity
        extra = max(0, len(uset - iset) - 3)
        clutter = min(0.3, 0.05 * extra)

        score = 10.0 * identity - 3.5 * mism + 1.5 * bonus - 10.0 * clutter * 0.3
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
