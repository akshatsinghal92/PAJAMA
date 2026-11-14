import re

# Qualifier axes: each axis maps canonical value -> list of surface forms.
# Two different values on the same axis are a contradiction.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow", "golden"],
        "white": ["white"], "black": ["black"], "brown": ["brown"],
        "orange": ["orange"], "purple": ["purple", "violet"],
    },
    "fat": {
        "full": ["whole", "full-fat", "fullfat", "regular"],
        "reduced": ["reduced fat", "2%", "1%", "lowfat", "low-fat", "low fat", "light", "lite", "lean"],
        "none": ["skim", "nonfat", "non-fat", "fat-free", "fat free", "0%"],
    },
    "sweet": {
        "sweet": ["sweet", "sweetened", "sugared", "honey", "candied"],
        "unsweet": ["unsweetened", "sugar-free", "sugar free", "no sugar"],
        "sour": ["sour", "tart"],
    },
    "salt": {
        "salted": ["salted"],
        "unsalted": ["unsalted", "no salt", "low sodium", "without salt"],
    },
    "animal_part": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing", "wings"],
        "drumstick": ["drumstick", "leg"], "shank": ["shank"], "loin": ["loin", "tenderloin"],
        "rib": ["rib", "ribs"], "shoulder": ["shoulder", "chuck"], "belly": ["belly"],
        "liver": ["liver"], "heart": ["heart"], "ground": ["ground", "minced", "mince"],
    },
    "plant_part": {
        "leaf": ["leaf", "leaves", "greens"], "root": ["root", "roots"],
        "seed": ["seed", "seeds"], "zest": ["zest", "peel", "rind"],
        "juice": ["juice"], "flesh": ["raw fruit", "pulp"], "stem": ["stem", "stalk", "stalks"],
        "flower": ["flower", "blossom"],
    },
    "dairy_style": {
        "greek": ["greek", "strained"], "plain_style": ["regular style"],
    },
    "flavor": {
        "vanilla": ["vanilla"], "chocolate": ["chocolate", "cocoa"],
        "strawberry": ["strawberry"], "plain": ["plain", "unflavored"],
    },
    "pepper_kind": {
        "bell": ["bell", "sweet pepper"], "hot": ["jalapeno", "chili", "chile", "hot pepper", "serrano", "habanero"],
    },
    "grain": {
        "whole_grain": ["whole wheat", "whole grain", "wholemeal", "brown rice"],
        "refined": ["white rice", "enriched", "refined", "all-purpose"],
    },
    "diet": {
        "vegan": ["vegan", "plant-based", "plant based", "dairy-free", "meatless", "vegetarian"],
        "conventional": ["beef", "pork", "chicken", "egg yolk"],
    },
    "meal": {
        "breakfast_bar": ["bar"], "sausage": ["sausage", "links", "patty"],
    },
}

# Axes where a contradiction is very noticeable to a diner.
_AXIS_WEIGHT = {
    "color": 2.5, "fat": 2.0, "sweet": 2.0, "salt": 0.8, "animal_part": 2.5,
    "plant_part": 3.5, "dairy_style": 2.0, "flavor": 2.5, "pepper_kind": 3.0,
    "grain": 2.0, "diet": 3.0, "meal": 3.0,
}

_STOP = {
    "and", "or", "of", "with", "without", "the", "a", "in", "raw", "cooked", "fresh",
    "frozen", "thawed", "unprepared", "prepared", "nfs", "ns", "as", "to", "for", "from",
    "chopped", "diced", "sliced", "minced", "skin", "on", "off", "canned", "drained",
    "tube", "paste", "boiled", "baked", "fried", "large", "small", "medium", "into",
    "separable", "trimmed", "choice", "select", "fat", "piece", "pieces", "cut",
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?|cups?|tbsp|tsp)?\b", " ", t)
    t = t.replace("_", " ")
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def _forms_present(text, forms):
    for f in forms:
        pat = r"(?<![a-z0-9])" + re.escape(f) + r"(?![a-z0-9])"
        if re.search(pat, text):
            return True
    return False


def _axis_values(text):
    out = {}
    for axis, vals in _AXES.items():
        found = set()
        for canon, forms in vals.items():
            if _forms_present(text, forms):
                found.add(canon)
        # "unsweetened" also contains "sweet"-ish; resolve priority
        if axis == "sweet" and "unsweet" in found:
            found.discard("sweet")
        if axis == "salt" and "unsalted" in found:
            found.discard("salted")
        if found:
            out[axis] = found
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content_words(text):
    words = re.findall(r"[a-z]+", text)
    return {_stem(w) for w in words if len(w) > 2 and w not in _STOP}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        # Head food: first comma segment of USDA, and ingredient core before comma
        usda_head = usd.split(",")[0]
        ing_core = ing.split(",")[0]

        ing_ax = _axis_values(ing)
        usd_ax = _axis_values(usd)

        agree = 0.0
        conflict = 0.0
        missing = 0.0
        for axis, ivals in ing_ax.items():
            w = _AXIS_WEIGHT.get(axis, 1.5)
            uvals = usd_ax.get(axis)
            if uvals is None:
                # ingredient specifies a qualifier the USDA leaves open
                missing += w * 0.35
            elif ivals & uvals:
                agree += w
            else:
                conflict += w
        for axis, uvals in usd_ax.items():
            if axis not in ing_ax:
                # USDA adds a qualifier the recipe did not specify: mild uncertainty
                missing += _AXIS_WEIGHT.get(axis, 1.5) * 0.15

        # Base food identity overlap (gate: qualifiers only matter on the same food)
        iw = _content_words(ing_core)
        hw = _content_words(usda_head)
        aw = _content_words(usd)
        head_hit = len(iw & hw) / max(1, len(hw)) if hw else 0.0
        cover = len(iw & aw) / max(1, len(iw)) if iw else 0.0
        identity = 0.6 * head_hit + 0.4 * cover

        # Generic / multi-option USDA entries are vague about qualifiers
        vague = 0.0
        if re.search(r"\b(nfs|ns as to|not specified)\b", usd):
            vague += 1.5
        if usd.count(" or ") >= 1 and usd.count(",") >= 2:
            vague += 1.5

        score = 5.0
        score += 3.0 * (identity - 0.5)
        score += 0.8 * agree
        score -= 1.6 * conflict
        score -= missing
        score -= vague
        if identity < 0.15:
            score -= 2.5

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
