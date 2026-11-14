import re

# Mutually exclusive qualifier axes. Each axis maps a value label to trigger phrases.
_AXES = {
    "color": {
        "red": ["red"], "green": ["green"], "yellow": ["yellow"], "orange": ["orange"],
        "white": ["white"], "black": ["black"], "brown": ["brown"], "purple": ["purple"],
    },
    "fat": {
        "full": ["whole milk", "full fat", "full-fat", "regular fat", "whole"],
        "reduced": ["reduced fat", "2%", "low fat", "lowfat", "low-fat", "light", "lite", "1%"],
        "none": ["skim", "nonfat", "non-fat", "fat free", "fat-free", "0%"],
    },
    "sweet": {
        "sweetened": ["sweetened", "with added sugar", "sugar added", "candied", "honey"],
        "unsweetened": ["unsweetened", "no sugar", "without added sugar", "sugar free", "sugar-free"],
    },
    "flavor": {
        "vanilla": ["vanilla"], "chocolate": ["chocolate"], "strawberry": ["strawberry"],
        "smoked": ["smoked"], "plain": ["plain"],
    },
    "animal": {
        "chicken": ["chicken", "broiler", "fryer"], "beef": ["beef", "ox ", "chuck", "brisket", "veal"],
        "pork": ["pork", "ham", "bacon"], "lamb": ["lamb", "mutton"], "turkey": ["turkey"],
        "fish": ["salmon", "tuna", "cod", "fish"],
    },
    "cut": {
        "breast": ["breast"], "thigh": ["thigh"], "wing": ["wing"], "leg": ["leg", "drumstick"],
        "heart": ["heart"], "liver": ["liver"], "tongue": ["tongue"], "feet": ["feet", "foot"],
        "loin": ["loin", "sirloin"], "round": ["round"], "shank": ["shank"], "chuck": ["chuck"],
        "ground": ["ground", "minced", "loaf", "patty"],
    },
    "plant_part": {
        "leaf": ["leaf", "leaves", "greens"], "seed": ["seed", "seeds"], "root": ["root"],
        "oil": ["oil"], "juice": ["juice"], "flesh": [],
    },
    "state": {
        "dried": ["dried", "dry", "dehydrated", "chips"], "canned": ["canned", "creamed"],
        "cooked": ["cooked", "boiled", "braised", "roasted", "baked", "fried", "grilled"],
        "fresh": ["fresh", "raw"], "frozen": ["frozen"],
    },
    "milk_base": {
        "coconut": ["coconut"], "soy": ["soy", "soya"], "almond": ["almond"], "oat": ["oat "],
        "dairy": ["cow", "dairy"],
    },
    "pepper": {"bell": ["bell"], "chili": ["chili", "chile", "jalapeno", "hot pepper"]},
    "process": {"processed": ["process", "processed", "pasteurized process"], "natural": ["natural"]},
}

# Pairs within an axis that a diner would barely notice
_SOFT = {
    ("state", "fresh", "frozen"), ("state", "frozen", "fresh"),
    ("state", "cooked", "fresh"),  # recipe says cooked later; USDA raw is usual
}

# Axis weights: how noticeable a contradiction is
_W = {"color": 2.5, "fat": 2.0, "sweet": 1.5, "flavor": 2.5, "animal": 5.0, "cut": 3.0,
      "plant_part": 3.0, "state": 2.5, "milk_base": 3.0, "pepper": 3.0, "process": 2.0}

_PREP = {"diced", "chopped", "sliced", "minced", "warmed", "thawed", "trimmed", "optional",
         "peeled", "grated", "shredded", "crushed", "boneless", "skin", "on", "of", "visible",
         "and", "the", "a", "or", "with", "to", "fat", "into", "cut", "pieces", "large", "small"}


def _clean_ing(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _clean_usda(s):
    s = s.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract(text):
    padded = " " + re.sub(r"[^a-z0-9%\- ]", " ", text) + " "
    found = {}
    for axis, vals in _AXES.items():
        for val, trig in vals.items():
            for t in trig:
                pat = r"(?<![a-z])" + re.escape(t.strip()) + r"(?![a-z])"
                if re.search(pat, padded):
                    found.setdefault(axis, set()).add(val)
                    break
    return found


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if len(w) > 2 and w not in _PREP}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ing(str(ingredient or ""))
        usda = _clean_usda(str(usda_match or ""))
        if not ing or not usda:
            return 0.0

        # Head-food anchor: does the ingredient's core noun appear in the USDA primary terms?
        ing_main = ing.split(",")[0]
        it = _tokens(ing_main)
        ut = _tokens(usda)
        head = _tokens(usda.split(",")[0])
        score = 5.0
        if it:
            overlap = len(it & ut) / len(it)
            score += 2.0 * overlap
            if not (it & ut):
                score -= 2.5
            # brand-like USDA (capitalized multiword primary w/o commas) with weak anchor
            if head and not (head & it) and len(usda.split(",")) == 1 and len(head) >= 3:
                score -= 1.5

        qi = _extract(ing)
        qu = _extract(usda)

        penalty = 0.0
        bonus = 0.0
        for axis in set(qi) | set(qu):
            a = qi.get(axis, set())
            b = qu.get(axis, set())
            w = _W.get(axis, 2.0)
            if a and b:
                if a & b:
                    bonus += 0.4 * w / 2.5
                else:
                    if all((axis, x, y) in _SOFT for x in a for y in b):
                        penalty += 0.2 * w
                    else:
                        penalty += w
            elif a and not b:
                # ingredient specifies a qualifier the USDA entry is silent on
                if axis in ("flavor", "state", "plant_part", "milk_base", "process"):
                    if axis == "state" and a <= {"fresh", "frozen", "cooked"}:
                        continue
                    if axis == "plant_part" and a <= {"seed"} and "oil" not in b:
                        continue
                    penalty += 0.6 * w
            elif b and not a:
                # USDA adds a qualifier unspecified by recipe: usually fine, mild for strong ones
                if axis in ("flavor", "process", "milk_base"):
                    penalty += 0.4 * w
                elif axis == "plant_part" and "oil" in b:
                    penalty += 0.8 * w
                elif axis == "state" and b & {"canned", "dried"}:
                    penalty += 0.3 * w

        score = score + bonus - penalty
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
