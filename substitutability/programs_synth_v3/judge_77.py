import re

# Variant 5: multiplicative "survival" model over qualifier axes.
# Each axis is a family of mutually exclusive values. A contradiction on an axis
# multiplies the survival probability by (1 - salience). Agreement multiplies a
# small bonus. Unmatched ingredient-side flavor/state qualifiers apply a soft decay.

_AXES = {
    "color": (0.55, {
        "red": "red", "green": "green", "yellow": "yellow", "orange": "orange",
        "white": "white", "black": "black", "brown": "brown", "purple": "purple",
        "golden": "yellow", "gold": "yellow",
    }),
    "fat": (0.45, {
        "whole": "full", "full-fat": "full", "fullfat": "full", "regular": "full",
        "skim": "none", "nonfat": "none", "fat-free": "none", "fatfree": "none",
        "lowfat": "low", "low-fat": "low", "reduced-fat": "low", "reducedfat": "low",
        "light": "low", "lite": "low", "lean": "low", "2%": "low", "1%": "low",
    }),
    "sweet": (0.45, {
        "sweetened": "sweet", "unsweetened": "unsweet", "sugar-free": "unsweet",
        "sugarfree": "unsweet", "sweet": "sweet", "dark": "bitter", "bittersweet": "bitter",
        "semisweet": "semi", "semi-sweet": "semi", "milk": None,
    }),
    "salt": (0.3, {
        "salted": "salt", "unsalted": "nosalt", "low-sodium": "lowsalt",
        "lowsodium": "lowsalt", "nosalt": "nosalt",
    }),
    "cut": (0.55, {
        "breast": "breast", "thigh": "thigh", "wing": "wing", "drumstick": "leg",
        "leg": "leg", "loin": "loin", "tenderloin": "loin", "shoulder": "shoulder",
        "rib": "rib", "ribs": "rib", "belly": "belly", "chuck": "chuck",
        "brisket": "brisket", "flank": "flank", "sirloin": "sirloin", "shank": "shank",
        "liver": "liver", "heart": "heart", "kidney": "kidney", "tongue": "tongue",
        "giblets": "giblets", "ground": "ground", "mince": "ground", "minced": "ground",
    }),
    "plantpart": (0.5, {
        "leaves": "leaf", "leaf": "leaf", "greens": "leaf", "seeds": "seed",
        "seed": "seed", "root": "root", "stalk": "stalk", "stalks": "stalk",
        "stem": "stalk", "bulb": "bulb", "flower": "flower", "zest": "peel",
        "peel": "peel", "juice": "juice", "kernels": "seed",
    }),
    "form": (0.35, {
        "dried": "dry", "dry": "dry", "dehydrated": "dry", "powder": "powder",
        "powdered": "powder", "ground": None, "fresh": "fresh", "raw": None,
        "canned": "canned", "frozen": None, "paste": "paste", "puree": "paste",
        "pureed": "paste", "flakes": "flake", "flaked": "flake",
    }),
    "grain": (0.4, {
        "wholewheat": "ww", "whole-wheat": "ww", "wholegrain": "ww",
        "white": None, "enriched": "refined", "refined": "refined",
        "brown": None, "wild": "wild",
    }),
    "variety": (0.6, {
        "bell": "bell", "jalapeno": "jalapeno", "serrano": "serrano",
        "habanero": "habanero", "chipotle": "chipotle", "poblano": "poblano",
        "cayenne": "cayenne", "russet": "russet", "sweet-potato": "sweetpotato",
        "cheddar": "cheddar", "mozzarella": "mozzarella", "parmesan": "parmesan",
        "swiss": "swiss", "feta": "feta", "provolone": "provolone",
        "basmati": "basmati", "jasmine": "jasmine", "arborio": "arborio",
        "roma": "roma", "cherry": "cherry", "granny": "granny",
        "kidney": None, "pinto": "pinto", "navy": "navy", "garbanzo": "chickpea",
        "chickpea": "chickpea", "chickpeas": "chickpea", "lentil": "lentil",
        "lentils": "lentil",
    }),
}

# Species / base-food words that discriminate the primary food (pecan vs peanut).
_BASES = {
    "chicken", "turkey", "duck", "beef", "pork", "lamb", "veal", "goat", "fish",
    "salmon", "tuna", "cod", "shrimp", "crab", "peanut", "pecan", "almond",
    "cashew", "walnut", "hazelnut", "pistachio", "macadamia", "sunflower",
    "sesame", "cow", "goat", "soy", "soymilk", "oat", "rice", "coconut",
    "lemon", "lime", "orange", "grapefruit", "apple", "pear", "onion",
    "shallot", "leek", "garlic", "ginger", "cabbage", "lettuce", "spinach",
    "kale", "corn", "wheat", "rye", "barley", "potato", "olive", "olives",
}

# Ingredient-side flavor additions that a diner would notice if missing in USDA.
_FLAVOR_ADDS = {
    "garlic", "herb", "herbs", "honey", "chili", "chilli", "spicy", "smoked",
    "roasted", "marinated", "seasoned", "flavored", "flavoured", "cinnamon",
    "vanilla", "chocolate", "pepper", "lemon", "barbecue", "bbq", "teriyaki",
    "candied", "glazed", "caramelized", "pickled", "stuffed", "breaded", "fried",
}

_STOP = {"and", "or", "with", "in", "of", "the", "a", "for", "from", "to",
         "raw", "fresh", "chopped", "sliced", "diced", "thawed", "plus", "tube"}


def _norm(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb|grams?)\b\.?", " ", t)
    t = t.replace("whole wheat", "whole-wheat").replace("whole grain", "wholegrain")
    t = t.replace("reduced fat", "reduced-fat").replace("low fat", "low-fat")
    t = t.replace("fat free", "fat-free").replace("low sodium", "low-sodium")
    t = t.replace("semi sweet", "semi-sweet").replace("full fat", "full-fat")
    t = t.replace("sugar free", "sugar-free").replace("sweet potato", "sweet-potato")
    t = t.replace("no salt", "nosalt")
    return t


def _tokens(text):
    return [w.rstrip("s") if len(w) > 4 and w.endswith("es") is False and w.endswith("s") and w not in ("leaves", "giblets", "ribs", "seeds", "olives", "lentils", "chickpeas", "greens", "stalks", "flakes", "kernels") else w
            for w in re.findall(r"[a-z0-9%\-]+", text)]


def _axis_values(tokset):
    out = {}
    for axis, (_, table) in _AXES.items():
        vals = set()
        for tok in tokset:
            if tok in table and table[tok] is not None:
                vals.add(table[tok])
        if vals:
            out[axis] = vals
    return out


def _main_text(ing):
    # parenthetical and post-comma pieces kept separately (they're weaker evidence)
    paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
    core = re.sub(r"\([^)]*\)", " ", ing)
    parts = core.split(",", 1)
    head = parts[0]
    tail = parts[1] if len(parts) > 1 else ""
    return head, tail, paren


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        head, tail, paren = _main_text(ing)
        head_toks = set(_tokens(head))
        ing_all = set(_tokens(head + " " + tail + " " + paren))
        usda_toks = set(_tokens(re.sub(r"[()]", " ", usda)))
        if not head_toks:
            head_toks = ing_all

        survival = 1.0

        # Axis comparison: contradictions multiply survival down.
        ia = _axis_values(head_toks)
        ua = _axis_values(usda_toks)
        agreements = 0
        for axis, ivals in ia.items():
            sal = _AXES[axis][0]
            uvals = ua.get(axis)
            if not uvals:
                # unspecified on USDA side: tolerated, mild uncertainty
                survival *= (1.0 - sal * 0.12)
                continue
            if ivals & uvals:
                agreements += 1
            else:
                survival *= (1.0 - sal)
        for axis, uvals in ua.items():
            if axis not in ia:
                # USDA specifies something ingredient left open: tiny decay
                survival *= (1.0 - _AXES[axis][0] * 0.06)

        # Base food identity: base words present on both sides must overlap.
        ib = head_toks & _BASES
        ub = usda_toks & _BASES
        if ib and ub:
            if not (ib & ub):
                survival *= 0.15
            else:
                missing = ib - ub
                survival *= (0.8 ** len(missing))
        elif ib and not ub:
            # ingredient names a base that USDA doesn't mention at all
            survival *= 0.55

        # Flavor additions in ingredient (whole text) not reflected in USDA.
        adds = (ing_all & _FLAVOR_ADDS) - usda_toks
        adds -= ib  # base food already accounted
        if adds:
            survival *= (0.62 ** len(adds))

        # General lexical support: share of meaningful head words found in USDA.
        content = [w for w in head_toks if w not in _STOP and len(w) > 2 and not w.isdigit()]
        if content:
            hit = sum(1 for w in content
                      if w in usda_toks or any(u.startswith(w[:5]) for u in usda_toks if len(w) >= 5))
            coverage = hit / float(len(content))
        else:
            coverage = 0.5
        lexical = 0.35 + 0.65 * coverage

        score = 100.0 * survival * lexical * (1.0 + 0.05 * min(agreements, 3))
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
