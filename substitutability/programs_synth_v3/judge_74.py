import re

# Qualifier axes: each axis has mutually exclusive values, each value with trigger stems.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange": ["orange"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden"],
    },
    "fat": {
        "full": ["whole", "full fat", "full-fat", "regular"],
        "reduced": ["reduced fat", "lowfat", "low fat", "low-fat", "light", "lite", "2%", "1%", "part skim", "part-skim"],
        "none": ["nonfat", "non-fat", "fat free", "fat-free", "skim"],
    },
    "sweet": {
        "sweetened": ["sweetened", "sweet", "honey", "sugared", "candied"],
        "unsweetened": ["unsweetened", "no sugar", "sugar free", "sugar-free", "plain", "dry"],
    },
    "part": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing"], "drumstick": ["drumstick", "leg"],
        "neck": ["neck"], "gizzard": ["gizzard"], "liver": ["liver"], "kidney": ["kidney"],
        "heart": ["heart"], "seed": ["seed", "seeds"], "leaf": ["leaf", "leaves"], "root": ["root"],
        "stem": ["stem", "stalk"], "skin": ["skin"], "yolk": ["yolk"], "egg white": ["egg white"],
        "tail": ["tail", "tails"], "loin": ["loin", "tenderloin"], "shoulder": ["shoulder"],
        "rib": ["rib", "ribs"], "shank": ["shank"], "zest": ["zest", "peel"], "juice": ["juice"],
    },
    "variety_pepper": {
        "bell": ["bell"], "chili": ["chili", "chile", "jalapeno", "serrano", "cayenne"],
    },
    "fish": {
        "salmon": ["salmon"], "swordfish": ["swordfish"], "tuna": ["tuna"], "cod": ["cod"],
        "tilapia": ["tilapia"], "halibut": ["halibut"], "trout": ["trout"], "lobster": ["lobster"],
        "crayfish": ["crayfish", "crawfish"], "shrimp": ["shrimp", "prawn"], "crab": ["crab"],
    },
    "milk_source": {
        "cow": ["cow"], "goat": ["goat"], "sheep": ["sheep"], "coconut": ["coconut"],
        "almond": ["almond"], "soy": ["soy", "soya"], "oat": ["oat"],
    },
    "salt": {
        "salted": ["salted"], "unsalted": ["unsalted", "no salt", "low sodium", "sodium free"],
    },
    "grain": {
        "whole grain": ["whole wheat", "whole grain", "wholemeal"], "refined": ["white flour", "enriched", "all-purpose", "all purpose"],
    },
    "dairy_form": {
        "cheese": ["cheese"], "milk": ["milk"], "yogurt": ["yogurt", "yoghurt"], "kefir": ["kefir"],
        "cream": ["cream"], "butter": ["butter"], "souffle": ["souffle"],
    },
}

# Axes on which a mismatch is highly noticeable to a diner.
_WEIGHTS = {
    "color": 2.0, "fat": 2.5, "sweet": 2.0, "part": 3.0, "variety_pepper": 2.5,
    "fish": 4.0, "milk_source": 2.0, "salt": 0.8, "grain": 1.5, "dairy_form": 3.0,
}

# Qualifiers in the USDA entry that alter the food beyond what an unqualified ingredient implies.
_USDA_ONLY_PENALTY = {"fat": 1.5, "sweet": 0.6, "part": 1.0, "grain": 0.5}

_NOISE = re.compile(r"\b(raw|fresh|uncooked|cooked|frozen|thawed|chopped|diced|sliced|minced|shredded|grated|"
                    r"canned|imported|prepared|for serving|to taste|optional|large|small|medium)\b")


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = t.split(",")[0]
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def _clean_usda(text):
    t = text.lower().replace(",", " , ")
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def _has(text, stem):
    return re.search(r"(?<![a-z])" + re.escape(stem) + r"(?![a-z])", text) is not None


def _axis_values(text):
    found = {}
    for axis, values in _AXES.items():
        hits = set()
        for val, stems in values.items():
            for s in stems:
                if _has(text, s):
                    hits.add(val)
                    break
        if hits:
            found[axis] = hits
    return found


def _head_tokens(text):
    t = _NOISE.sub(" ", text)
    toks = re.findall(r"[a-z]+", t)
    out = set()
    for w in toks:
        if len(w) < 3:
            continue
        if w.endswith("ies"):
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxzh":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        usd = _clean_usda(str(usda_match))
        if not ing.strip() or not usd.strip():
            return 0.0

        iq = _axis_values(ing)
        uq = _axis_values(usd)

        score = 6.0
        agreements = 0
        conflicts = 0.0

        for axis in set(iq) | set(uq):
            w = _WEIGHTS.get(axis, 1.0)
            a = iq.get(axis)
            b = uq.get(axis)
            if a and b:
                if a & b:
                    # Matching qualifier; extra values in USDA (e.g. neck vs neck+gizzard) partial.
                    agreements += 1
                    if a - b:
                        conflicts += 0.5 * w
                else:
                    conflicts += w
            elif a and not b:
                # Ingredient specifies something USDA leaves unspecified: mild uncertainty.
                conflicts += 0.25 * w
            elif b and not a:
                conflicts += _USDA_ONLY_PENALTY.get(axis, 0.2)

        score += 0.8 * agreements
        score -= conflicts

        # Anchor check: primary food should share vocabulary with the ingredient.
        it = _head_tokens(ing)
        primary = usd.split(",")[0]
        ut_all = _head_tokens(usd)
        ut_primary = _head_tokens(primary)
        shared = it & ut_all
        if not shared:
            score -= 3.5
        else:
            coverage = len(shared) / float(max(1, len(it)))
            score += 2.0 * coverage
            if it & ut_primary:
                score += 0.7

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
