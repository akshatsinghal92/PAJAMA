import re

# Qualifier groups: within a group, different members contradict each other.
_GROUPS = [
    {"red", "green", "yellow", "white", "black", "brown", "orange", "purple", "pink", "golden"},
    {"whole", "skim", "nonfat", "lowfat", "reduced", "fat-free", "2%", "1%"},
    {"breast", "thigh", "wing", "drumstick", "leg", "back", "neck", "liver", "tenderloin"},
    {"sweetened", "unsweetened"},
    {"raw", "cooked", "roasted", "boiled", "fried", "baked", "toasted", "grilled"},
    {"fresh", "frozen", "canned", "dried", "dry", "pickled", "smoked", "bottled"},
    {"beef", "pork", "lamb", "chicken", "turkey", "veal", "duck", "goat"},
    {"salted", "unsalted"},
    {"ground", "whole", "sliced", "chopped", "crushed", "powder", "powdered"},
    {"kidney", "pinto", "navy", "lima", "black", "garbanzo", "white"},
    {"leaves", "leaf", "seeds", "seed", "root", "stem", "bark", "juice", "oil", "flour", "starch", "bran", "sauce", "cracker", "crackers", "cereal"},
]
_FILL = {"and", "or", "the", "of", "with", "in", "a", "to", "for", "from", "only", "nfs", "usda",
         "optional", "divided", "g", "separable", "imported", "choice", "crude", "solids", "drained",
         "thawed", "trimmed", "fat", "lean", "style", "type", "mixed", "fresh"}
_SYN = {"cos": "romaine", "fryers": "chicken", "broilers": "chicken", "hearts": ""}


def _toks(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb|mg)?\b", " ", s)
    out = []
    for t in re.findall(r"[a-z0-9%\-]+", s):
        t = _SYN.get(t, t)
        if not t:
            continue
        out.append(t)
    return out


def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("es") and t[-3] in "sxzh":
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def judging_function(ingredient, usda_match):
    try:
        ing = [_stem(t) for t in _toks(ingredient)]
        usda_raw = (usda_match or "").lower()
        usda_head = usda_raw.split(",")[0]
        usda = [_stem(t) for t in _toks(usda_raw)]
        if not ing or not usda:
            return 0.0
        ing_set, usda_set = set(ing), set(usda)
        ing_c = {t for t in ing_set if t not in _FILL}
        usda_c = {t for t in usda_set if t not in _FILL}
        head_toks = {_stem(t) for t in _toks(usda_head)} - _FILL

        score = 5.0
        # Core noun coverage: ingredient content words found in USDA text.
        if ing_c:
            cov = len(ing_c & usda_c) / len(ing_c)
        else:
            cov = 0.0
        score += 4.0 * cov
        # Head noun of USDA description should appear in ingredient.
        if head_toks:
            hv = len(head_toks & ing_c) / len(head_toks)
            score += 2.0 * hv
        # Extra USDA content words not in the ingredient: mild penalty.
        extra = usda_c - ing_c
        score -= 0.5 * min(len(extra), 6) * (1.0 - 0.5 * cov)

        # Qualifier contradictions and agreements.
        for g in _GROUPS:
            gs = {_stem(x) for x in g}
            a = ing_set & gs
            b = usda_set & gs
            if a and b:
                if a & b:
                    score += 1.0
                else:
                    score -= 3.0
            elif a and not b:
                score -= 0.4
        # Ingredient has a qualifier word that USDA lacks entirely (part of plant, etc.)
        for w in ("leaf", "seed", "bran", "starch", "sauce", "relish", "cracker", "cereal", "souffle", "ball", "patty"):
            if (w in ing_set) != (w in usda_set):
                score -= 2.5
        return max(0.0, min(15.0, score))
    except Exception:
        return 0.0
