import re

GROUPS = {
    "color": ["red", "green", "yellow", "white", "black", "brown", "orange", "purple", "golden", "blue"],
    "fat": ["skim", "nonfat", "fat-free", "lowfat", "low-fat", "reduced", "light", "lite", "whole", "full-fat", "2%", "1%"],
    "part": ["breast", "thigh", "leg", "wing", "drumstick", "skin", "leaves", "leaf", "stalks", "stalk", "stem",
             "florets", "root", "seed", "seeds", "peel", "zest", "juice", "bone", "liver", "tenderloin", "loin",
             "sirloin", "round", "shoulder", "rib", "belly", "flank", "chuck", "brisket"],
    "state": ["raw", "cooked", "boiled", "baked", "fried", "roasted", "toasted", "frozen", "canned", "dried",
              "dry", "fresh", "pickled", "smoked", "steamed", "grilled", "prepared", "uncooked"],
    "sweet": ["sweet", "unsweetened", "sweetened", "sour", "bitter", "salted", "unsalted", "sugar-free"],
    "flavor": ["vanilla", "chocolate", "strawberry", "plain", "banana", "lemon", "honey", "cinnamon", "coconut",
               "almond", "peanut", "butter", "balsamic", "wine", "rice", "apple", "cider"],
    "variety": ["brown", "balsamic", "basmati", "jasmine", "wild", "greek", "regular", "instant", "ground",
                "whole", "powdered", "granulated", "chinese", "italian", "japanese"],
}
FAT_CANON = {"skim": "lean", "nonfat": "lean", "fat-free": "lean", "lowfat": "low", "low-fat": "low",
             "reduced": "low", "light": "low", "lite": "low", "whole": "full", "full-fat": "full"}
STATE_CANON = {"cooked": "cooked", "boiled": "cooked", "baked": "cooked", "fried": "cooked", "roasted": "cooked",
               "toasted": "cooked", "steamed": "cooked", "grilled": "cooked", "prepared": "cooked",
               "raw": "raw", "uncooked": "raw", "fresh": "raw", "frozen": "frozen", "canned": "canned",
               "dried": "dried", "dry": "dried"}
STOP = {"and", "or", "of", "the", "with", "without", "for", "from", "in", "a", "g", "ns", "as", "to", "eaten",
        "raw", "cooked", "fresh", "frozen", "ground", "free", "range", "style", "type", "brand"}


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb|grams?)?\s+", "", s)
    return s


def _toks(s):
    return re.findall(r"[a-z0-9%\-]+", s)


def _vals(tokens, group):
    out = set()
    for w in GROUPS[group]:
        if w in tokens:
            if group == "fat":
                out.add(FAT_CANON.get(w, w))
            elif group == "state":
                out.add(STATE_CANON.get(w, w))
            else:
                out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        it = set(_toks(ing))
        ut = set(_toks(usd))
        score = 10.0

        # core content words overlap (head food agreement)
        ic = {w for w in it if w not in STOP and len(w) > 2}
        uc = {w for w in ut if w not in STOP and len(w) > 2}
        def stem(w):
            return w[:-1] if w.endswith("s") and len(w) > 3 else w
        ics = {stem(w) for w in ic}
        ucs = {stem(w) for w in uc}
        if ics:
            cover = len(ics & ucs) / len(ics)
        else:
            cover = 0.5
        score -= (1 - cover) * 5.0

        # primary USDA food (before first comma) should appear in ingredient
        head = stem(_toks(usd.split(",")[0])[0]) if _toks(usd.split(",")[0]) else ""
        if head and head not in {stem(w) for w in it}:
            score -= 1.5

        weights = {"color": 2.5, "fat": 2.0, "part": 3.0, "state": 1.5, "sweet": 2.0, "flavor": 1.5, "variety": 0.7}
        for g, wt in weights.items():
            a, b = _vals(it, g), _vals(ut, g)
            if g == "variety":
                a = a - {"ground", "whole"}
                b = b - {"ground", "whole"}
            if a and b:
                if not (a & b):
                    score -= wt          # contradicted qualifier
                else:
                    score += 0.3         # explicit agreement
            elif a and not b:
                score -= wt * 0.35       # ingredient qualifier lost
            elif b and not a:
                if g in ("part",):
                    score -= wt * 0.3    # USDA is a specific part, ingredient generic
                elif g == "state":
                    score -= wt * 0.2
                else:
                    score -= wt * 0.1

        # extra tokens in USDA (brand/other foods) dilute match
        extra = len(ucs - ics)
        score -= min(extra, 8) * 0.15

        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
