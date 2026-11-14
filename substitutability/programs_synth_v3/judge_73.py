import re

# Qualifier axes: each axis maps a canonical value -> list of surface forms.
# Within one axis, different values contradict each other.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange": ["orange"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden", "gold"],
    },
    "fat": {
        "whole": ["whole milk", "full fat", "full-fat", "3.25%", "regular fat"],
        "reduced": ["reduced fat", "reduced-fat", "2%", "lowfat", "low fat", "low-fat", "1%"],
        "skim": ["skim", "nonfat", "non-fat", "fat free", "fat-free", "0%"],
        "lean": ["lean", "extra lean"],
    },
    "sweetness": {
        "sweet": ["sweet", "sweetened", "sugared"],
        "unsweet": ["unsweetened", "no sugar", "sugar free", "sugar-free", "tart", "sour", "bitter", "dry"],
    },
    "salt": {
        "salted": ["salted"],
        "unsalted": ["unsalted", "no salt", "low sodium", "sodium free"],
    },
    "poultry_cut": {
        "breast": ["breast"], "thigh": ["thigh"], "drumstick": ["drumstick", "leg"],
        "wing": ["wing", "wings"], "back": ["back"], "neck": ["neck"],
        "liver": ["liver", "livers"], "gizzard": ["gizzard"], "heart": ["heart"],
        "skin": ["skin"],
    },
    "beef_cut": {
        "ground": ["ground beef", "minced", "mince", "hamburger"],
        "loin": ["loin", "sirloin", "tenderloin"], "rib": ["rib", "ribeye", "ribs"],
        "chuck": ["chuck"], "round": ["round"], "brisket": ["brisket"], "flank": ["flank"],
        "shank": ["shank"], "belly": ["belly"], "shoulder": ["shoulder"],
    },
    "pepper_kind": {
        "bell": ["bell", "sweet pepper"], "chili": ["chili", "chile", "jalapeno", "serrano", "habanero", "cayenne", "hot pepper"],
    },
    "plant_part": {
        "leaf": ["leaf", "leaves", "greens"], "root": ["root"], "seed": ["seed", "seeds"],
        "stalk": ["stalk", "stem", "stems"], "flower": ["flower", "blossom"],
        "juice": ["juice"], "peel": ["peel", "zest", "rind"],
    },
    "grain_form": {
        "whole_grain": ["whole wheat", "whole grain", "whole-wheat", "brown rice"],
        "refined": ["white flour", "all-purpose", "all purpose", "enriched", "white rice", "refined"],
    },
    "milk_animal": {
        "cow": ["cow"], "goat": ["goat"], "sheep": ["sheep"], "soy": ["soy", "soymilk"],
        "almond": ["almond"], "oat": ["oat"], "coconut": ["coconut"], "rice_milk": ["rice milk"],
    },
    "egg_part": {
        "yolk": ["yolk", "yolks"], "white_egg": ["egg white", "egg whites"],
    },
    "caffeine": {
        "decaf": ["decaf", "decaffeinated"], "caffeinated": ["regular brewed", "caffeinated"],
    },
}

# Axes where a contradiction is especially noticeable to a diner.
_AXIS_WEIGHT = {
    "color": 2.0, "fat": 1.2, "sweetness": 1.8, "salt": 0.8, "poultry_cut": 2.5,
    "beef_cut": 2.0, "pepper_kind": 2.5, "plant_part": 2.2, "grain_form": 1.5,
    "milk_animal": 2.6, "egg_part": 2.4, "caffeine": 0.6,
}

# Terms that are neutral descriptors (don't count against a match).
_NEUTRAL = {
    "raw", "fresh", "frozen", "uncooked", "cooked", "dried", "dry", "canned", "boiled",
    "baked", "roasted", "ns", "as", "to", "form", "prepared", "with", "without", "and",
    "or", "of", "the", "a", "in", "plain", "regular", "domesticated", "whole", "solids",
    "liquids", "drained", "includes", "commercial", "type", "style", "fluid", "all",
    "varieties", "edible", "portion", "only", "meat", "flesh", "fat", "lean",
}

_PREP = {
    "chopped", "diced", "sliced", "minced", "grated", "shredded", "thawed", "peeled",
    "optional", "large", "small", "medium", "finely", "coarsely", "fresh", "freshly",
    "softened", "melted", "divided", "packed", "trimmed", "rinsed", "cut", "into",
    "pieces", "taste", "about", "strong", "brewed", "ground", "crushed", "beaten",
    "room", "temperature", "halved", "quartered", "cubed", "equal", "parts",
}


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = t.split(",")[0]
    return " " + re.sub(r"[^a-z0-9%\- ]+", " ", t) + " "


def _clean_usda(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", t)
    return " " + re.sub(r"[^a-z0-9%\-, ]+", " ", t).replace(",", " , ") + " "


def _find_values(text):
    found = {}
    for axis, values in _AXES.items():
        hits = set()
        for canon, forms in values.items():
            for f in forms:
                if re.search(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", text):
                    hits.add(canon)
                    break
        if hits:
            found[axis] = hits
    return found


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text, drop):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if len(w) > 1 and w not in drop}


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        ing = _clean_ingredient(ingredient)
        usd = _clean_usda(usda_match)

        ing_q = _find_values(ing)
        usd_q = _find_values(usd)

        # Qualifier consistency ledger
        agree = 0.0
        conflict = 0.0
        unspecified = 0
        for axis in set(ing_q) | set(usd_q):
            w = _AXIS_WEIGHT.get(axis, 1.0)
            a = ing_q.get(axis)
            b = usd_q.get(axis)
            if a and b:
                if a & b:
                    agree += w
                else:
                    conflict += w
            elif a and not b:
                # recipe specifies a qualifier the USDA entry leaves open: mild uncertainty
                unspecified += 1
                conflict += 0.15 * w
            else:
                # USDA is more specific than recipe: usually acceptable
                unspecified += 1
                conflict += 0.05 * w

        # Head-food anchoring: the primary USDA term (before first comma) should
        # appear among ingredient words, otherwise qualifiers are moot.
        ing_tok = _tokens(ing, _PREP | _NEUTRAL)
        primary = usda_match.lower().split(",")[0]
        prim_tok = _tokens(primary, _NEUTRAL)
        usd_tok = _tokens(usd, _NEUTRAL)

        if prim_tok and ing_tok:
            head_hit = len(prim_tok & ing_tok) / float(len(prim_tok))
        else:
            head_hit = 0.0
        if ing_tok:
            cover = len(ing_tok & usd_tok) / float(len(ing_tok))
        else:
            cover = 0.0

        # Prefix match as fallback for near-synonyms (e.g. "cherry"/"cherries").
        if head_hit == 0.0 and prim_tok and ing_tok:
            for p in prim_tok:
                for q in ing_tok:
                    if len(p) >= 4 and len(q) >= 4 and (p.startswith(q[:4]) or q.startswith(p[:4])):
                        head_hit = 0.5
                        break

        # Unexplained USDA descriptors (product forms not in recipe) e.g. "ball", "patty"
        extra = usd_tok - ing_tok
        qual_words = set()
        for vals in _AXES.values():
            for forms in vals.values():
                for f in forms:
                    qual_words.update(_stem(x) for x in f.split())
        extra = {e for e in extra if e not in qual_words and not e.isupper()}
        extra_pen = min(len(extra), 6) * 0.35

        score = 5.0
        score += 2.2 * agree ** 0.8 if agree > 0 else 0.0
        score -= 2.0 * conflict
        score += 3.0 * head_hit ** 2 + 1.5 * cover
        score -= extra_pen
        if head_hit == 0.0 and cover == 0.0:
            score -= 3.0

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
