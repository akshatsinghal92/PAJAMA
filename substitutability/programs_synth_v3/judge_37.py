import re

# Dimension ledger: each qualifier word maps to (dimension, value).
# Values marked as the "default" for a dimension are what an unqualified
# ingredient implicitly assumes.
_DIMENSIONS = {
    "state": {
        "default": "fresh",
        "values": {
            "raw": "fresh", "fresh": "fresh", "uncooked": "fresh", "frozen": "fresh",
            "thawed": "fresh", "dried": "dried", "dehydrated": "dried", "dry": "dried",
            "chips": "dried", "powder": "dried", "powdered": "dried", "freeze-dried": "dried",
            "cooked": "cooked", "braised": "cooked", "roasted": "cooked", "boiled": "cooked",
            "baked": "cooked", "fried": "cooked", "grilled": "cooked", "stewed": "cooked",
            "simmered": "cooked", "steamed": "cooked", "broiled": "cooked", "sauteed": "cooked",
            "canned": "canned", "jarred": "canned", "pickled": "pickled", "brined": "pickled",
        },
    },
    "flavor": {
        "default": "plain",
        "values": {
            "smoked": "smoked", "spicy": "spicy", "hot": "spicy", "sweetened": "sweet",
            "unsweetened": "plain", "salted": "salted", "unsalted": "plain", "honey": "sweet",
            "candied": "sweet", "glazed": "sweet", "seasoned": "seasoned", "flavored": "seasoned",
            "marinated": "seasoned", "plain": "plain", "garlic": None, "barbecue": "seasoned",
            "bbq": "seasoned", "cured": "smoked",
        },
    },
    "grade": {
        "default": "regular",
        "values": {
            "extra": "premium", "virgin": "premium", "organic": "regular", "lowfat": "light",
            "low-fat": "light", "nonfat": "light", "fat-free": "light", "light": "light",
            "reduced": "light", "lite": "light", "skim": "light", "whole": "regular",
            "full-fat": "regular", "diet": "light", "low": "light",
        },
    },
    "form": {
        "default": "whole",
        "values": {
            "loaf": "composite", "patty": "composite", "patties": "composite",
            "sausage": "composite", "nuggets": "composite", "breaded": "composite",
            "mix": "composite", "pie": "composite", "salad": "composite", "soup": "composite",
            "sauce": "composite", "paste": "paste", "puree": "paste", "pureed": "paste",
            "juice": "juice", "ground": "ground", "minced": "whole", "diced": "whole",
            "sliced": "whole", "chopped": "whole", "seeds": "whole", "hearts": "whole",
        },
    },
    "skin": {
        "default": None,
        "values": {
            "skin-on": "skin", "skin": "skin", "skinless": "noskin", "lean": "noskin",
            "boneless": None,
        },
    },
}

_PREP_ONLY = {
    "diced", "chopped", "sliced", "minced", "trimmed", "peeled", "halved", "cubed",
    "julienned", "shredded", "grated", "crushed", "rinsed", "drained", "washed",
    "thawed", "softened", "melted", "beaten", "large", "small", "medium", "of",
    "visible", "fat", "and", "or", "the", "a", "to", "from", "tube", "into", "cut",
    "pieces", "piece", "fine", "finely", "roughly", "coarsely", "thinly", "thick",
}

_USDA_BOILERPLATE = {
    "raw", "or", "and", "frozen", "fresh", "ns", "as", "to", "nfs", "with", "without",
    "separable", "only", "choice", "select", "prime", "all", "grades", "trimmed",
    "fat", "by-products", "variety", "meats", "broilers", "fryers", "cos", "100%",
    "includes", "commercial", "prepared", "made", "from", "type", "of", "in",
}

_SYNONYMS = {
    "romaine": "lettuce", "cos": "lettuce", "chuck": "beef", "shank": "beef",
    "sirloin": "beef", "brisket": "beef", "steak": "beef", "mutton": "lamb",
    "pomegranate": "pomegranate", "scallion": "onion", "scallions": "onion",
    "cilantro": "coriander", "zucchini": "squash", "courgette": "squash",
    "aubergine": "eggplant", "prawn": "shrimp", "prawns": "shrimp",
}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|lbs|cups?|tbsp|tsp)?\b", " ", text)
    text = re.sub(r"\d+(/\d+)?\"?", " ", text)
    raw = re.findall(r"[a-z%]+(?:-[a-z]+)*", text)
    out = []
    for t in raw:
        out.append(t)
        if "-" in t:
            out.extend(t.split("-"))
    return out


def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("es") and t[-3] in "sxz":
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _profile(tokens):
    prof = {}
    for dim, spec in _DIMENSIONS.items():
        found = set()
        for t in tokens:
            if t in spec["values"] and spec["values"][t] is not None:
                found.add(spec["values"][t])
        prof[dim] = found
    return prof


def _nouns(tokens, drop):
    qual_words = set()
    for spec in _DIMENSIONS.values():
        qual_words.update(spec["values"].keys())
    res = set()
    for t in tokens:
        if t in drop or t in qual_words:
            continue
        s = _stem(t)
        res.add(_SYNONYMS.get(s, _SYNONYMS.get(t, s)))
    return res


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0

        # Separate the post-comma state of the ingredient; it still counts.
        ing_tokens = _tokens(ing)
        usda_parts = [p.strip() for p in usda.lower().split(",") if p.strip()]
        usda_tokens = _tokens(usda)
        primary_tokens = _tokens(usda_parts[0]) if usda_parts else []

        if not ing_tokens or not usda_tokens:
            return 0.0

        # --- 1. Qualifier-ledger alignment per dimension ---
        ip = _profile(ing_tokens)
        up = _profile(usda_tokens)
        dim_weight = {"state": 3.0, "flavor": 2.5, "grade": 1.5, "form": 2.5, "skin": 1.0}
        ledger = 0.0
        for dim, w in dim_weight.items():
            default = _DIMENSIONS[dim]["default"]
            iv = ip[dim] or ({default} if default else set())
            uv = up[dim] or ({default} if default else set())
            if not ip[dim] and not up[dim]:
                ledger += 0.3 * w            # both unqualified: generic alignment
            elif iv & uv:
                ledger += w                  # same specificity on this axis
            elif not ip[dim] and up[dim]:
                ledger -= w                  # USDA adds a qualifier not implied
            elif ip[dim] and not up[dim]:
                ledger -= 0.8 * w            # USDA drops a qualifier the recipe asked for
            else:
                ledger -= 1.2 * w            # conflicting variants

        # --- 2. Core identity: does the USDA primary food cover the ingredient head? ---
        ing_nouns = _nouns(ing_tokens, _PREP_ONLY)
        usda_nouns = _nouns(usda_tokens, _USDA_BOILERPLATE)
        prim_nouns = _nouns(primary_tokens, _USDA_BOILERPLATE)
        if ing_nouns:
            cover = len(ing_nouns & usda_nouns) / float(len(ing_nouns))
        else:
            cover = 0.0
        head_hit = 1.0 if (prim_nouns & ing_nouns) else 0.0

        # --- 3. Extra unexplained USDA descriptors (specificity drift) ---
        extras = usda_nouns - ing_nouns
        drift = min(len(extras), 6) / 6.0

        score = 50.0
        score += 4.0 * ledger
        score += 20.0 * cover
        score += 10.0 * head_hit
        score -= 12.0 * drift
        if not (ing_nouns & usda_nouns):
            score -= 25.0
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
