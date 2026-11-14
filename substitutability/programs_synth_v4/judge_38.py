import re

# Qualifier dimensions: each maps a canonical value -> surface forms.
# Values within the same dimension are mutually exclusive; disagreement = conflict.
_DIMENSIONS = {
    "color": (3.0, {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange_c": ["orange-colored"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden"],
    }),
    "fat": (2.5, {
        "full": ["whole", "full fat", "full-fat", "regular"],
        "reduced": ["reduced fat", "reduced-fat", "2%", "low fat", "lowfat", "low-fat", "light", "lite", "1%"],
        "none": ["skim", "nonfat", "non-fat", "fat free", "fat-free", "0%"],
    }),
    "sweet": (2.0, {
        "sweetened": ["sweetened", "sugared", "with added sugar"],
        "unsweetened": ["unsweetened", "no sugar added", "sugar free", "sugar-free", "diet"],
    }),
    "animal_part": (3.0, {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"], "drumstick": ["drumstick", "leg"],
        "skin": ["skin"], "liver": ["liver"], "heart": ["heart"], "giblets": ["giblets"],
        "loin": ["loin", "tenderloin"], "shoulder": ["shoulder"], "belly": ["belly"],
        "ribs": ["rib", "ribs"], "chuck": ["chuck"], "brisket": ["brisket"],
        "sirloin": ["sirloin"], "round": ["round"], "flank": ["flank"], "shank": ["shank"],
    }),
    "plant_part": (3.0, {
        "leaf": ["leaf", "leaves", "greens"], "root": ["root", "roots"], "stalk": ["stalk", "stalks", "stem", "stems"],
        "seed": ["seed", "seeds"], "floret": ["floret", "florets", "flower", "flowers"],
        "fruit": ["fruit"], "bran": ["bran"], "germ": ["germ"], "peel": ["peel", "zest", "rind"],
        "sprout": ["sprouts", "sprouted"], "kernel": ["kernel", "kernels"],
    }),
    "state": (1.5, {
        "raw": ["raw", "uncooked", "fresh"],
        "cooked": ["cooked", "boiled", "baked", "roasted", "grilled", "fried", "toasted", "steamed", "braised", "broiled"],
        "frozen": ["frozen"], "canned": ["canned"], "dried": ["dried", "dehydrated", "dry"],
    }),
    "form": (1.5, {
        "ground": ["ground", "powder", "powdered"], "whole_f": ["whole kernel", "whole seeds"],
        "sliced": ["sliced"], "paste": ["paste", "puree", "pureed"], "juice": ["juice"],
    }),
    "variety_pepper": (2.5, {
        "bell": ["bell", "sweet pepper"], "chili": ["chili", "chile", "jalapeno", "serrano", "habanero", "cayenne"],
    }),
    "variety_vinegar": (3.0, {
        "balsamic": ["balsamic"], "wine": ["wine vinegar"], "cider": ["cider"], "rice_v": ["rice vinegar"],
        "distilled": ["distilled"],
    }),
    "sugar_kind": (3.0, {
        "brown_s": ["brown sugar", "sugar, brown", "sugars, brown"], "coconut_s": ["coconut sugar"],
        "white_s": ["granulated", "white sugar"], "powdered_s": ["powdered sugar", "confectioners"],
    }),
    "salt": (1.0, {
        "salted": ["salted", "with salt"], "unsalted": ["unsalted", "without salt", "no salt"],
    }),
}

_NOISE = set("""g gram grams kg ml oz cup cups tbsp tsp a an the of and or for to with in on from
fresh large small medium chopped diced minced finely thinly about optional taste
ns as eaten prepared mix""".split())


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|grams?)\b", " ", t)
    t = t.replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def _find_values(text, forms_map):
    padded = " " + re.sub(r"[^a-z0-9%,' -]", " ", text) + " "
    found = set()
    for value, forms in forms_map.items():
        for f in forms:
            if re.search(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", padded):
                found.add(value)
                break
    return found


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if len(w) > 2 and w not in _NOISE}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        # Ingredient: ignore post-comma usage notes ("for frying") but keep
        # descriptor text before the comma.
        ing_main = ing.split(",")[0]
        ing_full = ing

        score = 50.0
        conflicts = 0.0
        agreements = 0.0
        dims_checked = 0

        for dim, (weight, forms_map) in _DIMENSIONS.items():
            iv = _find_values(ing_full if dim == "state" else ing_main, forms_map)
            uv = _find_values(usda, forms_map)
            if not iv and not uv:
                continue
            dims_checked += 1
            if iv and uv:
                if iv & uv:
                    agreements += weight
                else:
                    conflicts += weight
            elif iv and not uv:
                # Ingredient specifies something the entry is silent on: mild penalty
                # for discriminating parts, near-neutral otherwise.
                if dim in ("plant_part", "animal_part", "variety_vinegar", "sugar_kind", "color"):
                    conflicts += weight * 0.6
                else:
                    conflicts += weight * 0.15
            else:
                # Entry adds a qualifier the ingredient leaves unspecified: tolerated,
                # except where it changes identity (e.g. leaves/stalks only).
                if dim in ("plant_part", "animal_part"):
                    conflicts += weight * 0.35
                elif dim == "fat":
                    conflicts += weight * 0.05

        score += agreements * 6.0
        score -= conflicts * 9.0

        # Anchor check: the main noun of the ingredient should show up in the entry,
        # so that qualifier agreement is about the same food.
        ing_words = _content(ing_main)
        usda_primary = usda.split(",")[0]
        usda_words = _content(usda)
        prim_words = _content(usda_primary)
        if ing_words:
            overlap = len(ing_words & usda_words) / float(len(ing_words))
            prim_hit = bool(ing_words & prim_words)
            score += overlap * 20.0
            if prim_hit:
                score += 8.0
            elif overlap == 0:
                score -= 15.0
            # Entry's primary looks like a brand / unrelated product with the word buried.
            if not prim_hit and overlap > 0 and len(usda.split(",")) >= 3:
                score -= 6.0

        # Entry listing several alternative foods ("x, y, or z") is a generic blend.
        if re.search(r",\s*or\s+|\bor\b.*\bleaves\b", usda) and usda.count(",") >= 3:
            score -= 10.0

        if dims_checked == 0:
            score += 3.0  # nothing contradicted

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
