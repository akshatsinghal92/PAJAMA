import re

# Variant 4: axis-based qualifier conflict model.
# Each axis is a set of mutually exclusive value classes. For every axis we find
# which classes the ingredient and the USDA entry express, then compute an
# agreement factor. Final score = 100 * product of axis factors * additive-modifier
# factor, plus a small bonus for explicitly confirmed qualifiers.

_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange": ["orange"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden", "gold"],
    },
    "fat": {
        "full": ["whole", "full fat", "full-fat", "regular", "3.25%", "4%"],
        "reduced": ["reduced fat", "2%", "lowfat", "low fat", "low-fat", "1%", "light", "lite", "lean", "extra lean", "90%", "93%", "85%"],
        "none": ["skim", "nonfat", "non-fat", "fat free", "fat-free", "0%"],
    },
    "sweetness": {
        "sweet": ["sweetened", "sweet", "with sugar", "honey", "candied", "syrup"],
        "unsweet": ["unsweetened", "no sugar", "sugar free", "sugar-free", "plain", "dry"],
    },
    "cut": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"],
        "leg": ["leg", "drumstick"], "neck": ["neck"], "back": ["back"],
        "loin": ["loin", "tenderloin", "sirloin"], "shoulder": ["shoulder", "chuck", "blade"],
        "rib": ["rib", "ribs", "ribeye"], "belly": ["belly"], "shank": ["shank"],
        "liver": ["liver"], "heart": ["heart"], "gizzard": ["gizzard"],
    },
    "plant_part": {
        "leaf": ["leaf", "leaves", "greens"], "root": ["root"], "seed": ["seed", "seeds"],
        "stem": ["stem", "stalk", "stalks"], "flower": ["flower", "blossom"],
        "peel": ["peel", "zest", "rind"], "juice": ["juice"],
    },
    "pepper_type": {
        "bell": ["bell"], "chili": ["chili", "chile", "jalapeno", "serrano", "habanero", "cayenne"],
    },
    "variety": {
        "concord": ["concord"], "muscadine": ["muscadine"], "thompson": ["thompson"],
        "atlantic": ["atlantic"], "pacific": ["pacific"],
        "granny": ["granny smith"], "fuji": ["fuji"], "gala": ["gala"],
        "russet": ["russet"], "yukon": ["yukon"], "sockeye": ["sockeye"], "coho": ["coho"],
        "chinook": ["chinook"], "albacore": ["albacore"], "romaine": ["romaine"],
        "iceberg": ["iceberg"], "basmati": ["basmati"], "jasmine": ["jasmine"],
        "arborio": ["arborio"],
    },
    "species": {
        "chicken": ["chicken", "broiler", "broilers", "fryers", "hen"],
        "turkey": ["turkey"], "duck": ["duck"], "goose": ["goose"],
        "beef": ["beef"], "pork": ["pork"], "lamb": ["lamb"], "veal": ["veal"],
    },
    "cookstate": {
        "raw": ["raw", "fresh", "uncooked"],
        "cooked": ["cooked", "roasted", "broiled", "baked", "fried", "simmered", "boiled",
                   "grilled", "braised", "steamed", "dry heat", "stewed"],
    },
    "preservation": {
        "smoked": ["smoked"], "canned": ["canned"], "dried": ["dried", "dehydrated"],
        "pickled": ["pickled"], "salted": ["salted", "cured"],
    },
    "form": {
        "whole": ["whole"], "ground": ["ground", "minced"], "paste": ["paste", "pate"],
        "fillet": ["fillet", "fillets"], "patty": ["patty", "patties"],
        "sliced": ["sliced"], "powder": ["powder", "powdered"],
    },
}

# How noticeable a contradiction on each axis is to a diner (0..1 penalty strength).
_AXIS_WEIGHT = {
    "color": 0.75, "fat": 0.55, "sweetness": 0.6, "cut": 0.7, "plant_part": 0.8,
    "pepper_type": 0.8, "variety": 0.7, "species": 0.9, "cookstate": 0.45,
    "preservation": 0.6, "form": 0.35,
}

# Generic umbrella terms that make a species axis compatible (poultry ~ chicken etc.)
_UMBRELLA = {
    "species": {"poultry": {"chicken", "turkey", "duck", "goose"}, "meat": None},
}

# Descriptors in the USDA entry that add components a diner would notice.
_ADDITIVE = ["with vegetables", "with fruit", "with sauce", "with cheese", "breaded",
             "battered", "with gravy", "in sauce", "flavored", "with added", "stuffed",
             "mixed with", "and "]

# Prep words in the ingredient that should not count as qualifiers.
_PREP_NOISE = {"thawed", "melted", "chopped", "diced", "minced into", "softened",
               "rinsed", "drained", "peeled", "pieces", "to taste", "frozen"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb)\b", " ", t)
    t = re.sub(r"[()\[\]]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return " " + t.strip() + " "


def _has(text, phrase):
    if phrase.endswith("%"):
        return phrase in text
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def _classes(text, axis):
    found = set()
    for cls, words in _AXES[axis].items():
        for w in words:
            if _has(text, w):
                found.add(cls)
                break
    return found


def _axis_factor(axis, ing_cls, usda_cls, ing_text):
    # Returns (factor, confirmed)
    if not ing_cls and not usda_cls:
        return 1.0, False
    if ing_cls and usda_cls:
        if ing_cls & usda_cls:
            # overlap; extra conflicting classes in USDA are a mild issue
            extra = usda_cls - ing_cls
            return (1.0 - 0.15 * _AXIS_WEIGHT[axis] * len(extra)), True
        return max(0.05, 1.0 - _AXIS_WEIGHT[axis]), False
    if ing_cls and not usda_cls:
        # ingredient specifies something the USDA entry leaves open: small doubt
        return 1.0 - 0.2 * _AXIS_WEIGHT[axis], False
    # USDA specifies, ingredient silent
    if axis == "species":
        for umb, members in _UMBRELLA["species"].items():
            if _has(ing_text, umb) and (members is None or usda_cls <= members):
                return 1.0, True
    if axis in ("cookstate", "form", "color"):
        return 1.0 - 0.1 * _AXIS_WEIGHT[axis], False
    if axis == "fat":
        # unspecified fat in recipe usually implies regular product
        return 1.0 - (0.5 if "full" not in usda_cls else 0.0) * _AXIS_WEIGHT[axis], False
    return 1.0 - 0.25 * _AXIS_WEIGHT[axis], False


def _ingredient_cookstate_hint(text):
    # "fresh" implies raw; post-comma cooking verbs imply cooked
    return text


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_q = ing
        for noise in _PREP_NOISE:
            ing_q = ing_q.replace(" " + noise + " ", " ")

        score = 1.0
        confirmed = 0
        conflicts = 0
        for axis in _AXES:
            try:
                ic = _classes(ing_q, axis)
                uc = _classes(usda, axis)
                f, conf = _axis_factor(axis, ic, uc, ing_q)
                if f < 0.5:
                    conflicts += 1
                score *= max(0.0, min(1.0, f))
                if conf:
                    confirmed += 1
            except Exception:
                continue

        # Added components in USDA not mentioned by ingredient
        for add in _ADDITIVE:
            try:
                if _has(usda, add.strip()) and not _has(ing, add.strip()):
                    if add.strip() == "and":
                        score *= 0.9
                    else:
                        score *= 0.45
            except Exception:
                continue

        # Lexical anchor: share of ingredient content words echoed in USDA
        stop = {"g", "of", "the", "a", "and", "or", "into", "with", "for"}
        iw = [w for w in re.findall(r"[a-z]+", ing_q) if len(w) > 2 and w not in stop]
        uw = set(re.findall(r"[a-z]+", usda))
        def _stem(w):
            return w[:-1] if w.endswith("s") and len(w) > 3 else w
        uws = {_stem(w) for w in uw}
        if iw:
            hit = sum(1 for w in iw if _stem(w) in uws) / float(len(iw))
        else:
            hit = 0.0
        anchor = 0.55 + 0.45 * hit

        final = 100.0 * score * anchor + 3.0 * min(confirmed, 4) - 4.0 * conflicts
        return round(max(0.0, min(100.0, final)), 3)
    except Exception:
        return 0.0
