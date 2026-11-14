import re

PART_GROUPS = {
    "breast": ["breast", "breasts", "tenderloin", "tenders"],
    "thigh": ["thigh", "thighs"],
    "wing": ["wing", "wings"],
    "drumstick": ["drumstick", "drumsticks", "leg", "legs"],
    "loin": ["loin", "sirloin", "tenderloin", "striploin", "ribeye", "rib-eye"],
    "shoulder": ["shoulder", "chuck", "butt", "blade"],
    "shank": ["shank", "shanks", "hock", "osso"],
    "rib": ["rib", "ribs", "spareribs"],
    "belly": ["belly", "bacon", "pancetta"],
    "organ": ["heart", "liver", "kidney", "tongue", "tripe", "neck", "gizzard", "giblets", "brain"],
    "ground": ["ground", "mince", "minced"],
    "fillet": ["fillet", "fillets", "filet", "steak", "steaks"],
    "yolk": ["yolk", "yolks"],
    "white": ["white", "whites"],
    "leaf": ["leaf", "leaves", "greens", "herb", "herbs", "lettuce", "spinach", "basil"],
    "root": ["root", "roots", "bulb", "tuber", "tubers"],
    "stem": ["stem", "stems", "stalk", "stalks", "shoots", "sprouts"],
    "seed": ["seed", "seeds", "nut", "nuts", "kernel", "kernels", "bean", "beans"],
    "flower": ["flower", "flowers", "blossom", "florets", "floret"],
    "peel": ["peel", "zest", "rind", "skin", "skins"],
    "flesh": ["flesh", "pulp", "meat"],
    "juice": ["juice"],
    "sausage": ["sausage", "frankfurter", "hot dog", "merguez", "chorizo", "salami", "bologna"],
    "palm": ["palm", "palms"],
}

TOKEN_TO_GROUPS = {}
for g, ws in PART_GROUPS.items():
    for w in ws:
        TOKEN_TO_GROUPS.setdefault(w, set()).add(g)

STOP = {"and", "or", "of", "the", "a", "with", "without", "for", "in", "to", "from", "raw",
        "cooked", "fresh", "frozen", "dried", "canned", "boiled", "drained", "salt", "optional",
        "serving", "regular", "type", "style", "fat", "lean", "trimmed", "choice", "all",
        "grades", "separable", "baked", "roasted", "prepared", "ready", "thawed", "sliced",
        "cubed", "chopped", "diced", "whole", "large", "small", "medium", "g", "ml"}

def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb|grams?)?\b", " ", s)
    return s

def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w

def _toks(s):
    return re.findall(r"[a-z]+", s)

def _parts(tokens):
    found = set()
    for t in tokens:
        if t in TOKEN_TO_GROUPS:
            found |= TOKEN_TO_GROUPS[t]
    return found

def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        # primary food of USDA entry = text before first comma
        usda_primary = usda.split(",")[0]
        ing_main = ing.split(",")[0]

        it = _toks(ing_main)
        ut = _toks(usda)
        up = _toks(usda_primary)
        if not it or not ut:
            return 0.0

        ip_set = _parts(it)
        up_set = _parts(ut)

        # core noun-ish content word stems
        icore = {_stem(w) for w in it if w not in STOP and len(w) > 2}
        ucore = {_stem(w) for w in ut if w not in STOP and len(w) > 2}
        if not icore or not ucore:
            return 1.0
        cover = len(icore & ucore) / float(len(icore))
        rev = len(icore & ucore) / float(len(ucore))

        # head noun of ingredient (last word) should appear in usda
        head = _stem(it[-1]) if it[-1] not in STOP else None
        head_hit = 1.0 if head and head in ucore else 0.0

        score = 4.0 * cover + 1.0 * rev + 1.5 * head_hit

        # Part agreement logic
        if ip_set and up_set:
            if ip_set & up_set:
                score += 3.0
            else:
                score -= 5.0
        elif ip_set and not up_set:
            # ingredient names a specific part, USDA entry does not
            score -= 2.5
        elif up_set and not ip_set:
            # USDA names a part that the ingredient did not
            unspecified_ok = {"flesh", "ground"}
            if up_set <= unspecified_ok:
                score += 0.5
            else:
                score -= 3.0
        else:
            score += 1.5

        # USDA primary food entirely absent from ingredient => different thing
        up_core = {_stem(w) for w in up if w not in STOP and len(w) > 2}
        if up_core and not (up_core & icore):
            score -= 2.0

        # extra unmatched usda primary words suggest processed/different item
        extra = len(up_core - icore)
        score -= 0.7 * extra

        # form conflicts
        forms = [("ground", "whole"), ("juice", "whole")]
        if "juice" in ut and "juice" not in it:
            score -= 2.0
        if "sauce" in ut and "sauce" not in it:
            score -= 2.0
        if "sausage" in ut and "sausage" not in it:
            score -= 2.0

        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
