import re

# Taxonomy: part word -> (family, cut)
TAXON = {
    "breast": ("poultry_white", "breast"), "tenderloin": ("poultry_white", "breast"),
    "thigh": ("poultry_dark", "thigh"), "drumstick": ("poultry_dark", "leg"),
    "leg": ("poultry_dark", "leg"), "wing": ("poultry_wing", "wing"),
    "neck": ("offal", "neck"), "heart": ("offal", "heart"), "liver": ("offal", "liver"),
    "kidney": ("offal", "kidney"), "tongue": ("offal", "tongue"), "tripe": ("offal", "tripe"),
    "gizzard": ("offal", "gizzard"), "giblets": ("offal", "giblets"),
    "loin": ("prime", "loin"), "sirloin": ("prime", "loin"), "ribeye": ("prime", "loin"),
    "tri-tip": ("prime", "tritip"), "tip": ("prime", "tritip"), "round": ("lean", "round"),
    "flank": ("lean", "flank"), "brisket": ("braise", "brisket"),
    "chuck": ("braise", "shoulder"), "shoulder": ("braise", "shoulder"),
    "butt": ("braise", "shoulder"), "shank": ("braise", "shank"), "rib": ("rib", "rib"),
    "belly": ("belly", "belly"), "bacon": ("belly", "belly"),
    "yolk": ("egg", "yolk"), "white": ("egg", "white"),
    "leaves": ("green", "leaf"), "leaf": ("green", "leaf"), "greens": ("green", "leaf"),
    "root": ("under", "root"), "bulb": ("under", "root"), "tuber": ("under", "root"),
    "stem": ("stalk", "stem"), "stalk": ("stalk", "stem"), "shoots": ("stalk", "stem"),
    "seed": ("seed", "seed"), "kernel": ("seed", "seed"),
    "flower": ("flower", "flower"), "florets": ("flower", "flower"),
    "peel": ("skin", "peel"), "zest": ("skin", "peel"), "rind": ("skin", "peel"),
    "skin": ("skin", "skin"), "palm": ("stalk", "palm"),
}
PROCESSED = {"sausage", "frankfurter", "patty", "nuggets", "juice", "sauce", "relish",
             "pudding", "puddings", "mayonnaise", "soup", "dip", "spread", "jam",
             "cereal", "snack", "bar", "salami", "bologna", "hotdog", "paste", "powder",
             "extract", "oil", "flour", "syrup", "dressing"}
SPECIES = ["beef", "pork", "lamb", "veal", "turkey", "chicken", "duck", "goose", "fish",
           "salmon", "tuna", "cod", "pollock", "shrimp", "egg", "venison", "bison"]

def _strip(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|oz|lb|grams?)?\s+", " ", s)
    return s

def _words(s):
    return re.findall(r"[a-z][a-z\-]*", s)

def _sing(w):
    if w.endswith("ves"):
        return w[:-3] + "f" if w not in ("leaves", "olives", "gloves") else w
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3 and w not in ("greens", "leaves"):
        return w[:-1]
    return w

def _profile(s):
    ws = [_sing(w) if w not in TAXON else w for w in _words(s)]
    cuts = []
    for w in ws:
        if w in TAXON:
            cuts.append(TAXON[w])
    species = [w for w in ws if w in SPECIES]
    proc = [w for w in ws if w in PROCESSED]
    return ws, cuts, species, proc

def judging_function(ingredient, usda_match):
    try:
        a = _strip(ingredient)
        b = _strip(usda_match)
        a_main = a.split(",")[0]
        wa, ca, sa, pa = _profile(a_main)
        wb, cb, sb, pb = _profile(b)
        if not wa or not wb:
            return 0.0

        score = 5.0

        # species gate
        if sa and sb:
            score += 1.5 if set(sa) & set(sb) else -4.0
        elif sa != sb:
            score -= 1.0

        # hierarchical anatomical distance
        if ca and cb:
            best = 3
            for fa, ka in ca:
                for fb, kb in cb:
                    d = 0 if ka == kb else (1 if fa == fb else 2)
                    best = min(best, d)
            score += {0: 3.0, 1: 0.0, 2: -4.0}[best]
        elif ca and not cb:
            score -= 1.5
        elif cb and not ca:
            score -= 2.0
        else:
            score += 1.0

        # processed form mismatch: a processed word in one but not the other
        extra_proc = set(pb) - set(pa)
        missing_proc = set(pa) - set(pb)
        score -= 2.5 * len(extra_proc) + 1.5 * len(missing_proc)

        # first-word anchor: USDA headline word should appear in ingredient
        head_b = _sing(wb[0])
        ia = {_sing(w) for w in wa}
        if head_b in ia:
            score += 1.5
        else:
            # allow ingredient last word match (noun at end)
            if _sing(wa[-1]) in {_sing(w) for w in wb}:
                score += 1.0
            else:
                score -= 2.0

        # "ground" vs whole cut
        ga = "ground" in wa or "minced" in wa
        gb = "ground" in wb
        if ga != gb and (ca or cb or sa or sb):
            score -= 1.0

        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
