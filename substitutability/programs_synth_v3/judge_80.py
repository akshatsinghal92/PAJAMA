import re
import math

# Qualifier axes: each axis maps a canonical value to its surface cues.
# Values on the same axis are mutually exclusive; a clash is a contradiction.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange_c": ["orange-fleshed"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
        "golden": ["golden", "gold"],
    },
    "fat": {
        "full": ["whole", "full fat", "full-fat", "regular fat", "3.25%"],
        "reduced": ["reduced fat", "reduced-fat", "2%", "low fat", "lowfat", "low-fat", "1%", "light", "lite"],
        "none": ["skim", "nonfat", "non-fat", "fat free", "fat-free", "0%"],
    },
    "sweet": {
        "sweetened": ["sweetened", "with added sugar", "sugared", "in heavy syrup", "in light syrup", "syrup"],
        "unsweetened": ["unsweetened", "no sugar added", "without added sugar", "sugar free", "sugar-free", "plain", "in water", "juice pack"],
    },
    "salt": {
        "salted": ["salted", "with salt"],
        "unsalted": ["unsalted", "without salt", "no salt added", "low sodium", "reduced sodium"],
    },
    "animal_part": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"], "drumstick": ["drumstick", "leg"],
        "liver": ["liver"], "heart": ["heart"], "kidney": ["kidney"], "tongue": ["tongue"],
        "loin": ["loin", "tenderloin"], "shoulder": ["shoulder", "chuck"], "rib": ["rib", "ribs", "ribeye"],
        "sirloin": ["sirloin"], "brisket": ["brisket"], "shank": ["shank"], "belly": ["belly"],
        "ground": ["ground", "minced", "mince"], "yolk": ["yolk"], "white_egg": ["egg white", "whites"],
    },
    "plant_part": {
        "leaf": ["leaf", "leaves", "greens"], "seed": ["seed", "seeds"], "root": ["root"],
        "stalk": ["stalk", "stalks", "stem"], "flower": ["flower", "blossom"], "juice": ["juice"],
        "peel": ["peel", "zest", "rind"], "bulb": ["bulb"],
    },
    "processing": {
        "fresh": ["fresh", "raw"], "cooked": ["cooked", "boiled", "roasted", "baked", "fried", "grilled", "braised", "stewed", "steamed"],
        "canned": ["canned", "tinned"], "frozen": ["frozen"], "dried": ["dried", "dry", "dehydrated"],
        "smoked": ["smoked"], "cured": ["cured", "pickled"],
    },
    "form": {
        "whole_f": ["whole kernel", "whole bean"], "ground_f": ["powder", "powdered", "ground spice"],
        "paste": ["paste", "puree", "pureed"], "flakes": ["flakes", "flaked"], "sauce": ["sauce"],
        "loaf": ["loaf"], "patty": ["patty", "patties"], "sausage": ["sausage"], "flour": ["flour"],
        "oil": ["oil"],
    },
    "grain": {
        "wholegrain": ["whole wheat", "whole grain", "whole-grain", "wholemeal"],
        "refined": ["enriched", "refined", "white flour", "all-purpose", "all purpose"],
    },
    "species_pepper": {
        "bell": ["bell", "sweet pepper"], "hot": ["jalapeno", "chili", "chile", "serrano", "habanero", "cayenne", "hot"],
    },
}

# How noticeable a contradiction on each axis is for a diner (0..1)
_AXIS_WEIGHT = {
    "color": 0.75, "fat": 0.55, "sweet": 0.6, "salt": 0.3, "animal_part": 1.0,
    "plant_part": 0.9, "processing": 0.7, "form": 0.95, "grain": 0.5, "species_pepper": 0.9,
}

# Pairs within processing that a diner would not usually notice
_COMPATIBLE = {
    ("processing", "fresh", "frozen"): 0.35,
    ("processing", "frozen", "fresh"): 0.35,
    ("sweet", "unsweetened", "sweetened"): 0.8,
}

_UNITS = r"(?:kg|g|grams?|mg|ml|l|oz|lb|lbs|cups?|tbsp|tsp|tablespoons?|teaspoons?|pieces?|slices?|cloves?)"
_PREP = {
    "diced", "chopped", "sliced", "minced_x", "thawed", "drained", "rinsed", "peeled", "grated",
    "shredded", "crushed", "trimmed", "cut", "into", "pieces", "finely", "roughly", "thinly",
    "about", "for", "the", "a", "an", "of", "and", "or", "to", "with", "taste", "bagged",
    "large", "small", "medium", "optional", "mixed", "halved", "quartered", "softened", "melted",
}
_USDA_FILLER = {
    "raw", "all", "commercial", "varieties", "regular", "ns", "as", "to", "nfs", "includes",
    "prepared", "made", "with", "salad", "or", "cooking", "type", "the", "and", "of", "from",
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*" + _UNITS + r"?\b\.?", " ", t)
    return t


def _split_ingredient(text):
    t = _clean(text)
    parens = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    if "," in t:
        main, state = t.split(",", 1)
    else:
        main, state = t, ""
    return main.strip(), (state + " " + parens).strip()


def _cue_hits(text):
    """Return {axis: set(values)} using whole-phrase matching."""
    padded = " " + re.sub(r"[^a-z0-9%\- ]+", " ", text) + " "
    found = {}
    for axis, values in _AXES.items():
        for val, cues in values.items():
            for cue in cues:
                if re.search(r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])", padded):
                    found.setdefault(axis, set()).add(val)
                    break
    return found


def _content_words(text, stop):
    words = re.findall(r"[a-z]+", text)
    out = []
    for w in words:
        if len(w) < 3 or w in stop:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxzh":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def _qualifier_vocab():
    v = set()
    for values in _AXES.values():
        for cues in values.values():
            for c in cues:
                for w in c.split():
                    v.add(w)
    return v


_QVOCAB = _qualifier_vocab()


def _soft_eq(a, b):
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return False


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_main, ing_state = _split_ingredient(ingredient)
        usda = str(usda_match).lower()
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        if not usda_parts:
            return 0.0
        usda_primary = usda_parts[0]

        # --- anchor: does the food identity line up at all? ---
        ing_nouns = [w for w in _content_words(ing_main, _PREP) if w not in _QVOCAB] or _content_words(ing_main, _PREP)
        usda_words = _content_words(usda, _USDA_FILLER)
        usda_nouns = [w for w in usda_words if w not in _QVOCAB] or usda_words
        if not ing_nouns or not usda_nouns:
            return 5.0
        primary_words = set(_content_words(usda_primary, _USDA_FILLER))

        matched = 0.0
        for w in ing_nouns:
            if any(_soft_eq(w, u) for u in usda_nouns):
                matched += 1.5 if any(_soft_eq(w, p) for p in primary_words) else 1.0
        anchor = min(1.0, matched / (len(ing_nouns) * 1.0 + 0.5))
        # head noun (last word of ingredient phrase) gets special check
        head = ing_nouns[-1]
        head_hit = any(_soft_eq(head, u) for u in usda_nouns)
        if not head_hit:
            anchor *= 0.55

        # --- qualifier ledger ---
        ing_q = _cue_hits(ing_main + " " + ing_state)
        usda_q = _cue_hits(usda)
        agree, clash, unspecified = 0.0, 0.0, 0.0
        for axis in set(ing_q) | set(usda_q):
            w = _AXIS_WEIGHT.get(axis, 0.5)
            a = ing_q.get(axis, set())
            b = usda_q.get(axis, set())
            if a and b:
                if a & b:
                    agree += w
                else:
                    best = 1.0
                    for x in a:
                        for y in b:
                            best = min(best, _COMPATIBLE.get((axis, x, y), 1.0))
                    clash += w * best
            elif a and not b:
                # ingredient demands a qualifier USDA is silent on: mild uncertainty
                unspecified += 0.25 * w
            else:
                # USDA adds a qualifier the recipe did not specify: mostly fine,
                # but strongly-noticed axes (part/form) still carry some risk
                unspecified += (0.35 if w >= 0.9 else 0.1) * w

        # Multi-ingredient recipes ("x and y, mixed") are hard to match by one entry
        compound = 1.0
        if re.search(r"\b(and|&)\b", ing_main) and re.search(r"\bmixed|blend|combined\b", ing_main + " " + ing_state):
            compound = 0.45
        elif re.search(r"\b(and|&)\b", ing_main) and len(ing_nouns) >= 3:
            compound = 0.7

        # Qualifier consistency in (0,1): logistic over net evidence
        net = 1.2 * agree - 2.2 * clash - unspecified + 0.6
        consistency = 1.0 / (1.0 + math.exp(-2.0 * net))

        score = 100.0 * (anchor ** 0.8) * (0.25 + 0.75 * consistency) * compound
        if score != score:  # NaN guard
            return 0.0
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
