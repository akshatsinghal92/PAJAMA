import re

# Variant 3: "anatomical ontology lattice".
# Each recognized part term maps to (system, region) where system is a coarse
# tissue/organ family and region is a finer location. Compatibility between the
# ingredient's part set and the USDA part set is computed with a pairwise
# distance in this lattice (same region = 0, same system = 1, different = 2),
# then combined with a source-organism agreement factor via a multiplicative model.

_PART_LATTICE = {
    # plant organs
    "leaf": ("plant_leaf", "leaf"), "leaves": ("plant_leaf", "leaf"),
    "greens": ("plant_leaf", "leaf"), "green": None, "tops": ("plant_leaf", "leaf"),
    "sprouts": ("plant_shoot", "sprout"), "sprout": ("plant_shoot", "sprout"),
    "shoots": ("plant_shoot", "shoot"), "shoot": ("plant_shoot", "shoot"),
    "stem": ("plant_shoot", "stem"), "stems": ("plant_shoot", "stem"),
    "stalk": ("plant_shoot", "stem"), "stalks": ("plant_shoot", "stem"),
    "root": ("plant_root", "root"), "roots": ("plant_root", "root"),
    "tuber": ("plant_root", "tuber"), "bulb": ("plant_root", "bulb"),
    "seed": ("plant_seed", "seed"), "seeds": ("plant_seed", "seed"),
    "kernels": ("plant_seed", "kernel"), "kernel": ("plant_seed", "kernel"),
    "germ": ("plant_seed", "germ"), "bran": ("plant_seed", "bran"),
    "flower": ("plant_flower", "flower"), "flowers": ("plant_flower", "flower"),
    "blossom": ("plant_flower", "flower"), "blossoms": ("plant_flower", "flower"),
    "peel": ("plant_rind", "peel"), "zest": ("plant_rind", "peel"),
    "rind": ("plant_rind", "peel"), "skin": ("skin", "skin"),
    "pulp": ("plant_flesh", "flesh"), "flesh": ("plant_flesh", "flesh"),
    "juice": ("plant_juice", "juice"), "pod": ("plant_seed", "pod"),
    "pods": ("plant_seed", "pod"), "hearts": ("plant_shoot", "heart"),
    # animal muscle cuts
    "breast": ("poultry_white", "breast"), "tenderloins": ("poultry_white", "tender"),
    "thigh": ("poultry_dark", "thigh"), "thighs": ("poultry_dark", "thigh"),
    "drumstick": ("poultry_dark", "drum"), "drumsticks": ("poultry_dark", "drum"),
    "leg": ("poultry_dark", "leg"), "legs": ("poultry_dark", "leg"),
    "wing": ("poultry_wing", "wing"), "wings": ("poultry_wing", "wing"),
    "back": ("poultry_frame", "back"), "neck": ("poultry_frame", "neck"),
    "loin": ("muscle_middle", "loin"), "tenderloin": ("muscle_middle", "tenderloin"),
    "sirloin": ("muscle_middle", "sirloin"), "ribeye": ("muscle_middle", "rib"),
    "rib": ("muscle_middle", "rib"), "ribs": ("muscle_rib", "ribs"),
    "chop": ("muscle_middle", "chop"), "chops": ("muscle_middle", "chop"),
    "shoulder": ("muscle_fore", "shoulder"), "chuck": ("muscle_fore", "chuck"),
    "blade": ("muscle_fore", "blade"), "brisket": ("muscle_fore", "brisket"),
    "foreshank": ("muscle_shank", "foreshank"), "shank": ("muscle_shank", "shank"),
    "hind-shank": ("muscle_shank", "hindshank"), "hindshank": ("muscle_shank", "hindshank"),
    "round": ("muscle_hind", "round"), "rump": ("muscle_hind", "rump"),
    "ham": ("muscle_hind", "ham"), "flank": ("muscle_belly", "flank"),
    "belly": ("muscle_belly", "belly"), "plate": ("muscle_belly", "plate"),
    "skirt": ("muscle_belly", "skirt"), "oxtail": ("muscle_tail", "tail"),
    "tail": ("muscle_tail", "tail"), "cheek": ("muscle_head", "cheek"),
    # organs
    "liver": ("organ", "liver"), "kidney": ("organ", "kidney"),
    "kidneys": ("organ", "kidney"), "heart": ("organ", "heart"),
    "tongue": ("organ", "tongue"), "tripe": ("organ", "tripe"),
    "gizzard": ("organ", "gizzard"), "gizzards": ("organ", "gizzard"),
    "giblets": ("organ", "giblets"), "brain": ("organ", "brain"),
    "sweetbread": ("organ", "sweetbread"), "lung": ("organ", "lung"),
    "spleen": ("organ", "spleen"), "marrow": ("organ", "marrow"),
    "feet": ("extremity", "feet"), "trotters": ("extremity", "feet"),
    "hocks": ("extremity", "hock"), "hock": ("extremity", "hock"),
    "fat": ("fat", "fat"), "lard": ("fat", "fat"), "suet": ("fat", "suet"),
    "fillet": ("fish_body", "fillet"), "fillets": ("fish_body", "fillet"),
    "steak": ("fish_body", "steak"), "roe": ("egg", "roe"),
    # egg
    "yolk": ("egg", "yolk"), "yolks": ("egg", "yolk"),
    "white": ("egg", "white"), "whites": ("egg", "white"),
}

# Physical form of the foodstuff (whole / ground / extracted)
_FORM_LATTICE = {
    "ground": "comminuted", "minced": "comminuted", "mince": "comminuted",
    "powder": "powder", "powdered": "powder", "flour": "powder", "meal": "powder",
    "whole": "intact", "fresh": "intact", "leaves": "intact",
    "oil": "extract", "extract": "extract", "juice": "extract", "paste": "paste",
    "puree": "paste", "butter": "paste", "dried": "dried", "dehydrated": "dried",
}

_FORM_COST = {
    frozenset(["comminuted", "intact"]): 1.5,
    frozenset(["powder", "intact"]): 2.5,
    frozenset(["extract", "intact"]): 3.0,
    frozenset(["extract", "powder"]): 3.0,
    frozenset(["extract", "comminuted"]): 3.0,
    frozenset(["paste", "intact"]): 1.5,
    frozenset(["dried", "intact"]): 1.5,
    frozenset(["powder", "comminuted"]): 1.0,
}

_SPECIES = {
    "beef": "cattle", "veal": "cattle", "ox": "cattle", "steer": "cattle",
    "pork": "pig", "ham": "pig", "bacon": "pig", "lamb": "sheep", "mutton": "sheep",
    "goat": "goat", "chicken": "chicken", "hen": "chicken", "broiler": "chicken",
    "turkey": "turkey", "duck": "duck", "goose": "goose", "venison": "deer",
    "deer": "deer", "bison": "bison", "rabbit": "rabbit", "salmon": "salmon",
    "tuna": "tuna", "cod": "cod",
}

_ANIMAL_CONTEXT = set(_SPECIES) | {"meat", "variety", "by-products", "egg", "eggs", "fish"}

_STOP = {
    "g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "and", "or",
    "with", "without", "of", "the", "a", "an", "for", "in", "raw", "cooked", "nfs",
    "salt", "added", "only", "separable", "lean", "sliced", "chopped", "diced",
    "cubed", "fresh", "frozen", "thawed", "boiled", "drained", "baked", "roasted",
    "simmered", "fried", "pan-fried", "plain", "imported", "new", "zealand",
    "bone-in", "boneless", "skinless", "trimmed", "large", "small", "medium",
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    t = re.sub(r"[^a-z\- ,]", " ", t)
    return t


def _tokens(text):
    return [w.strip("-") for w in re.split(r"[\s,]+", text) if w.strip("-")]


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _parts(tokens, animal):
    out = []
    for i, w in enumerate(tokens):
        info = _PART_LATTICE.get(w)
        if info is None:
            continue
        # disambiguation: "white"/"green"/"heart"/"back" are only parts in some contexts
        if w in ("white", "whites") and not any(x in ("egg", "eggs") for x in tokens):
            continue
        if w in ("heart", "back", "neck", "tail", "skin", "fat", "round", "plate", "leg", "legs") and not animal:
            if w == "heart":
                info = ("plant_shoot", "heart")
            elif w == "skin":
                info = ("skin", "skin")
            else:
                continue
        if w == "steak" and animal:
            info = ("muscle_middle", "steak")
        out.append(info)
    return out


def _forms(tokens):
    return {_FORM_LATTICE[w] for w in tokens if w in _FORM_LATTICE}


def _pair_distance(a, b):
    if a[1] == b[1]:
        return 0.0
    if a[0] == b[0]:
        return 1.0
    # muscle families are closer to each other than to organs
    if a[0].startswith("muscle") and b[0].startswith("muscle"):
        return 1.4
    if a[0].startswith("poultry") and b[0].startswith("poultry"):
        return 1.3
    if a[0].startswith("plant") and b[0].startswith("plant"):
        return 1.8
    return 2.0


def _set_distance(pa, pb):
    """Symmetric average nearest-neighbor distance between two part sets."""
    if not pa and not pb:
        return 0.0, "none"
    if not pa:
        # ingredient unspecified: an explicit USDA part is a mild narrowing
        # unless it's an organ/extremity (those are distinctive foods)
        heavy = any(p[0] in ("organ", "extremity", "plant_rind", "plant_juice") for p in pb)
        return (1.2 if heavy else 0.3), "usda_only"
    if not pb:
        heavy = any(p[0] in ("organ", "extremity", "plant_rind", "plant_juice") for p in pa)
        return (1.4 if heavy else 0.5), "ing_only"
    fwd = [min(_pair_distance(a, b) for b in pb) for a in pa]
    bwd = [min(_pair_distance(b, a) for a in pa) for b in pb]
    return max(sum(fwd) / len(fwd), 0.6 * sum(bwd) / len(bwd)), "both"


def _species(tokens):
    return {_SPECIES[w] for w in tokens if w in _SPECIES}


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = _clean(usda_match)
        it = _tokens(ing_raw)
        ut = _tokens(usda_raw)
        if not it or not ut:
            return 0.0

        ing_animal = any(w in _ANIMAL_CONTEXT for w in it)
        usda_animal = any(w in _ANIMAL_CONTEXT for w in ut)

        pa = _parts(it, ing_animal)
        pb = _parts(ut, usda_animal)
        dist, mode = _set_distance(pa, pb)

        # Part compatibility in [0,1]: exponential decay on lattice distance
        part_fit = 2.718281828 ** (-1.1 * dist)

        # Form compatibility
        fa, fb = _forms(it), _forms(ut)
        form_pen = 0.0
        if fa and fb and not (fa & fb):
            form_pen = max(_FORM_COST.get(frozenset([x, y]), 1.0) for x in fa for y in fb)
        elif fb - fa and not fa:
            # USDA processed into a form not requested (e.g. sage -> ground)
            form_pen = max(0.8 if f in ("comminuted", "dried", "paste") else 1.4 for f in fb - fa)
        elif fa - fb and not fb:
            form_pen = max(0.6 if f in ("intact", "comminuted") else 1.4 for f in fa - fb)
        form_fit = 1.0 / (1.0 + 0.45 * form_pen)

        # Source organism agreement
        sa, sb = _species(it), _species(ut)
        if sa and sb:
            src_fit = 1.0 if sa & sb else 0.15
        elif sa or sb:
            src_fit = 0.55 if (ing_animal != usda_animal) else 0.8
        else:
            src_fit = 1.0

        # Anchor: is the core named food present in the USDA head segment?
        content_i = {_singular(w) for w in it if w not in _STOP and w not in _PART_LATTICE and len(w) > 2}
        segs = [s.strip() for s in usda_raw.split(",") if s.strip()]
        head = {_singular(w) for w in _tokens(segs[0])} if segs else set()
        allu = {_singular(w) for w in ut}
        if content_i:
            in_head = len(content_i & head) / len(content_i)
            in_all = len(content_i & allu) / len(content_i)
            anchor = 0.25 + 0.45 * in_head + 0.30 * in_all
        else:
            anchor = 0.6
        # A part word used as a non-part (kidney beans vs beef kidney): head is plant, ing is animal organ
        if any(p[0] == "organ" for p in pa) and not usda_animal:
            anchor *= 0.3
            part_fit *= 0.4

        # Extra parts in USDA not mentioned (e.g. 'with vegetables', 'and sauerkraut')
        extras = 0
        for s in segs[1:] + [segs[0]] if segs else []:
            if re.search(r"\b(with|and)\b", s):
                extras += 1
        if re.search(r"\b(and|with)\b", ing_raw):
            extras = max(0, extras - 1)
        combo_fit = 1.0 / (1.0 + 0.5 * extras)

        score = 100.0 * (part_fit ** 1.0) * (form_fit ** 0.9) * (src_fit ** 1.2) * (anchor ** 0.8) * combo_fit
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
