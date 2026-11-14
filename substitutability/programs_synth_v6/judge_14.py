import re

# macro shifter words with (direction, magnitude): shifts energy/fat/water of the food
_SHIFT = {
    "dried": 3.0, "dehydrated": 3.0, "dry": 2.5, "powder": 3.0, "powdered": 3.0, "concentrate": 2.5, "jerky": 3.0,
    "fried": 1.5, "battered": 1.2, "breaded": 1.0, "roasted": 0.6, "oil": 1.0,
    "boiled": -0.4, "steamed": -0.3, "cooked": 0.3, "braised": 0.4, "simmered": 0.0, "broiled": 0.4, "baked": 0.4,
    "sweetened": 1.0, "candied": 2.0, "syrup": 1.0, "glazed": 1.0,
    "lean": -1.0, "nonfat": -2.0, "lowfat": -1.5, "fat-free": -2.0, "light": -1.2, "lite": -1.2, "reduced": -1.2, "skim": -2.0, "diet": -1.5,
    "added": 0.8, "buttered": 1.0, "creamed": 1.0, "whole": 0.3,
    "juice": -1.5, "broth": -1.5, "drained": 0.0,
}
_FATTY_PARTS = {"skin", "bacon", "shortening", "lard", "marbled", "prime", "brisket"}
_SYN = {"filbert": "hazelnut", "clementine": "tangerine", "mandarin": "tangerine", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "para": "brazil", "linseed": "flaxseed", "plant": "vegan"}
_FILL = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless lean drained of and or the a with in for from to into steak fillet seed segment floret slice piece raw nfs toasted".split())

def _t(s):
    r = []
    for w in re.findall(r"[a-zé\-]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        r.append(_SYN.get(w, w))
    return r

def _shift_total(tokens):
    return sum(_SHIFT[w] for w in set(tokens) if w in _SHIFT)

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _t(ing)
        ut = _t(u)
        main = _t(ing.split(",")[0])
        if not main or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        core = [w for w in main if w not in _FILL and w not in _SHIFT] or [w for w in main if w not in _FILL] or main
        cov = sum(1 for w in core if w in uset) / float(len(core))
        head = 1.0 if core[-1] in uset else 0.0
        # macro swing estimate: difference in shifter totals, ingredient default 0
        swing = abs(_shift_total(it) - _shift_total(ut))
        # forms that change macro class outright
        classes = [("oil", "fat"), ("butter", "fat"), ("juice", "liquid"), ("syrup", "sugar"), ("sauce", "sauce"), ("soup", "liquid"), ("cookie", "bakery"), ("cake", "bakery"), ("candy", "sugar"), ("taco", "dish"), ("sandwich", "dish"), ("entree", "dish")]
        def cls(tokens):
            return set(c for w, c in classes if w in tokens)
        ci, cu = cls(it), cls(ut)
        class_pen = 3.0 if ci != cu else 0.0
        # fatty/lean part markers
        fi = len(iset & _FATTY_PARTS)
        fu = len(uset & _FATTY_PARTS)
        fat_pen = 0.8 * abs(fi - fu)
        # lean marker agreement (only matters for meat)
        score = 4.5 * cov + 2.0 * head - 1.1 * min(swing, 4.0) - class_pen - fat_pen
        # extras in USDA first segment => composition drift
        first = _t(u.split(",")[0])
        extra = [w for w in first if w not in iset and w not in _FILL and w not in _SHIFT]
        score -= 0.45 * min(len(extra), 3)
        # cottage cheese / dairy specific macro shift: low fat variants
        if re.search(r"lowfat|low fat|nonfat|reduced fat|fat free|fat-free", u) and "cheese" in uset and not re.search(r"low|reduced|free|nonfat|light", ing):
            score -= 1.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score + 3.0)
    except Exception:
        return 0.0
