import re

# Qualifier axes: each axis maps canonical value -> surface forms.
# Two texts that both specify an axis with different values = contradiction.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange": ["orange"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden"],
    },
    "fat": {
        "nonfat": ["nonfat", "non-fat", "fat-free", "fat free", "skim", "0%"],
        "lowfat": ["lowfat", "low-fat", "low fat", "reduced fat", "light", "lite", "2%", "1%"],
        "full": ["whole", "full-fat", "full fat", "regular", "3.25%"],
    },
    "animal_part": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"],
        "drumstick": ["drumstick", "leg"], "loin": ["loin", "chop", "chops", "tenderloin"],
        "shoulder": ["shoulder"], "belly": ["belly"], "rib": ["rib", "ribs"],
        "kidney": ["kidney", "kidneys"], "liver": ["liver"], "heart": ["heart", "hearts"],
        "tail": ["tail", "tails"], "ground": ["ground", "minced", "mince"],
        "tongue": ["tongue"],
    },
    "plant_part": {
        "seed": ["seed", "seeds"], "leaf": ["leaf", "leaves", "greens"],
        "root": ["root"], "flesh": ["raw", "flesh", "pulp"], "peel": ["peel", "zest", "rind"],
        "flour": ["flour", "starch"], "chips": ["chips", "crisps"], "juice": ["juice"],
        "oil": ["oil"],
    },
    "sweetness": {
        "sweet": ["sweet", "sweetened"], "sour": ["sour", "tart"],
        "unsweet": ["unsweetened", "no sugar"],
    },
    "sugar_type": {
        "granulated": ["granulated", "white sugar"], "brown": ["brown sugar"],
        "maple": ["maple"], "powdered": ["powdered", "confectioners", "icing"],
        "honey": ["honey"],
    },
    "pepper_kind": {
        "bell": ["bell"], "chili": ["chili", "chile", "jalapeno", "cayenne"],
    },
    "prep_fat": {
        "fat_added": ["fat added", "with oil", "fried in"], "plain": ["without fat", "no fat added"],
    },
    "salt": {
        "salted": ["salted"], "unsalted": ["unsalted", "no salt", "without salt"],
    },
    "smoke": {
        "smoked": ["smoked"],
    },
    "dairy_style": {
        "greek": ["greek"], "plain_style": ["regular yogurt"],
    },
}

# Axes where an ingredient value absent from USDA but USDA-specified other
# value is a strong miss; unspecified on either side is neutral.
_AXIS_WEIGHT = {
    "color": 2.0, "fat": 1.5, "animal_part": 3.0, "plant_part": 2.5, "sweetness": 1.5,
    "sugar_type": 3.0, "pepper_kind": 2.5, "prep_fat": 1.5, "salt": 0.8,
    "smoke": 0.0, "dairy_style": 1.0,
}

_SYN = {
    "linseed": "flaxseed", "linseeds": "flaxseed", "flaxseeds": "flaxseed",
    "plant-based": "vegan", "dehydrated": "dried", "dry": "dried",
    "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro",
    "prawn": "shrimp", "prawns": "shrimp", "garbanzo": "chickpea",
}

_STOP = set("""a an and or of the with in for to from on as at by into
raw fresh frozen thawed cooked uncooked chopped diced sliced cubed minced flaked
cold hot warm large small medium pan-fried fried boiled baked roasted grilled
nfs ns prepared made commercial imported domestic boneless skinless serving
separable lean fat only all grades whole style type plain""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b\.?", " ", t)
    t = re.sub(r"\([^)]*\)", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _sing(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    out = []
    for w in re.findall(r"[a-z][a-z\-']*", text):
        w = _SYN.get(w, w)
        out.append(_sing(w))
    return out


def _axis_values(text):
    padded = " " + re.sub(r"[^a-z0-9%\- ]", " ", text) + " "
    found = {}
    for axis, vals in _AXES.items():
        hits = set()
        for canon, forms in vals.items():
            for f in forms:
                if re.search(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", padded):
                    hits.add(canon)
                    break
        if hits:
            found[axis] = hits
    return found


def _trigrams(w):
    w = "  " + w + " "
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _soft_match(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def judging_function(ingredient, usda_match):
    try:
        ing_full = _clean(ingredient)
        usda_full = _clean(usda_match)
        if not ing_full or not usda_full:
            return 0.0

        # Ingredient: the part before the first comma is the food; after is prep state.
        ing_main = ing_full.split(",")[0].strip()
        usda_parts = [p.strip() for p in usda_full.split(",") if p.strip()]
        usda_primary = usda_parts[0] if usda_parts else usda_full

        ing_words = [w for w in _words(ing_main) if w not in _STOP]
        usda_words = [w for w in _words(usda_full) if w not in _STOP]
        prim_words = [w for w in _words(usda_primary) if w not in _STOP]
        if not ing_words or not usda_words:
            return 5.0 if ing_main and ing_main in usda_full else 1.0

        # --- 1. Core identity gate: ingredient head noun vs USDA primary food ---
        head = ing_words[-1]
        head_best = max(_soft_match(head, u) for u in usda_words)
        prim_best = max([_soft_match(head, p) for p in prim_words] or [0.0])
        identity = max(head_best, 0.9 * prim_best)

        # coverage of ingredient content words
        cover = sum(max(_soft_match(w, u) for u in usda_words) for w in ing_words) / len(ing_words)

        # --- 2. Qualifier consistency across axes ---
        ia = _axis_values(ing_main)
        ua = _axis_values(usda_full)
        agree, conflict = 0.0, 0.0
        for axis in set(ia) | set(ua):
            w = _AXIS_WEIGHT.get(axis, 1.0)
            iv, uv = ia.get(axis), ua.get(axis)
            if iv and uv:
                if iv & uv:
                    agree += w
                else:
                    conflict += w
            elif uv and not iv:
                # USDA adds a qualifier the recipe didn't ask for.
                if axis in ("plant_part", "animal_part", "sugar_type", "prep_fat"):
                    conflict += 0.5 * w
            elif iv and not uv:
                # recipe specifies something USDA is silent on: mild penalty only
                # for axes a diner notices strongly
                if axis in ("animal_part", "plant_part", "sugar_type"):
                    conflict += 0.4 * w

        # head noun absorbed into a different food ("hearts of palm" vs "beef heart"):
        # if USDA primary does not contain any ingredient word, that's suspicious.
        prim_overlap = any(_soft_match(w, p) >= 0.85 for w in ing_words for p in prim_words)

        # Multiple foods in ingredient ("whitefish and salmon") but USDA covers one.
        compound_pen = 0.0
        if " and " in ing_main:
            missing = [w for w in ing_words if max(_soft_match(w, u) for u in usda_words) < 0.5]
            if missing and " and " not in usda_full:
                compound_pen = 2.0

        # Unspecified USDA catch-all
        vague_pen = 1.0 if re.search(r"\bnfs\b", usda_match.lower() if usda_match else "") and len(ing_words) > 1 else 0.0

        score = 0.0
        score += 4.0 * identity
        score += 2.5 * cover
        score += 1.5 if prim_overlap else -1.0
        score += 0.6 * agree
        score -= 1.2 * conflict
        score -= compound_pen
        score -= vague_pen
        if identity < 0.4:
            score -= 2.0

        # map to 0-10
        return round(max(0.0, min(10.0, score + 1.0)), 4)
    except Exception:
        return 0.0
