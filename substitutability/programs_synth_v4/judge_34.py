import re
import math

# Culinary role lexicon: each role maps to keyword stems that signal it.
_ROLE_LEXICON = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "protein_meat": ["beef", "veal", "lamb", "pork", "ham", "bacon", "sausage", "cervelat", "salami",
                     "turkey", "chicken", "duck", "goose", "tongue", "heart", "liver", "kidney",
                     "meat", "shank", "chuck", "loin", "steak", "patty", "luncheon", "skin"],
    "protein_sea": ["fish", "salmon", "tuna", "cod", "shrimp", "crab", "crawfish", "crayfish",
                    "lobster", "clam", "oyster", "mussel", "crustacean", "scallop", "squid"],
    "protein_plant": ["tofu", "sufu", "fuyu", "tempeh", "bean", "lentil", "chickpea", "soy"],
    "dairy": ["cheese", "milk", "cream", "yogurt", "cottage", "asadero", "queso", "half"],
    "nut_seed": ["nut", "pecan", "almond", "walnut", "pine", "pinyon", "brazil", "cashew",
                 "hazelnut", "pistachio", "seed", "flax", "linseed", "chia", "sesame", "peanut"],
    "fruit": ["apple", "pear", "kumquat", "orange", "tangerine", "mandarin", "clementine",
              "pomegranate", "berry", "grape", "lemon", "lime", "peach", "plum", "cherry",
              "banana", "mango", "fig", "date", "raisin"],
    "vegetable": ["onion", "carrot", "celery", "potato", "tomato", "pepper", "cabbage",
                  "spinach", "lettuce", "kale", "squash", "zucchini", "seaweed", "kombu",
                  "laver", "kelp", "nori", "mushroom", "corn"],
    "starch": ["bread", "cornbread", "flour", "wheat", "rice", "oat", "pasta", "noodle",
               "crumb", "cracker", "muffin", "barley", "cereal"],
    "aromatic": ["garlic", "ginger", "spice", "herb", "basil", "thyme", "cumin", "pepper",
                 "cinnamon", "zest", "peel", "vanilla"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "sweet", "agave"],
    "beverage": ["tea", "coffee", "juice", "soda", "beverage", "drink", "wine", "beer", "iced"],
}

# Physical-form attributes that govern how an ingredient behaves in a recipe.
_FORM_GROUPS = {
    "dry": ["dried", "dehydrated", "dry", "powder", "powdered", "mix", "rings", "low moisture"],
    "liquid": ["juice", "bottled", "beverage", "liquid", "brewed", "iced", "syrup"],
    "rind": ["zest", "peel", "rind"],
    "ground": ["ground", "crumbs", "crumb", "minced", "paste"],
    "toasted": ["toasted", "roasted"],
    "fat_mod": ["reduced fat", "reduced-fat", "lowfat", "low fat", "nonfat", "fat free",
                "1%", "2%", "lactose reduced", "diet", "light"],
}

_NOISE = {"g", "kg", "mg", "ml", "oz", "lb", "fresh", "raw", "and", "or", "of", "the", "a",
          "with", "without", "optional", "sliced", "cubed", "chopped", "diced", "drained",
          "boiled", "cooked", "frozen", "thawed", "canned", "whole", "mixed", "species",
          "wild", "moist", "heat", "includes", "enriched", "uncooked", "only", "imported",
          "variety", "meats", "by", "products", "separable", "choice", "prepackaged", "deli",
          "new", "zealand", "segments", "tails", "pack", "lean", "fat"}

_SYNONYMS = {
    "linseed": "flax", "linseeds": "flax", "flaxseed": "flax",
    "pinyon": "pine", "crawfish": "crayfish", "sufu": "fuyu",
    "clementine": "tangerine", "mandarin": "tangerine",
    "garbanzo": "chickpea", "aubergine": "eggplant", "courgette": "zucchini",
    "coriander": "cilantro", "prawn": "shrimp",
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    return t


def _stem(w):
    w = _SYNONYMS.get(w, w)
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            base = w[: -len(suf)] + ("y" if suf == "ies" else "")
            return _SYNONYMS.get(base, base)
    return _SYNONYMS.get(w, w)


def _tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z%]+", text) if w not in _NOISE and len(w) > 1]


def _role_vector(tokens, raw):
    vec = {}
    for role, keys in _ROLE_LEXICON.items():
        hits = 0.0
        for k in keys:
            for t in tokens:
                if t == k or t.startswith(k) or (len(t) > 3 and k.startswith(t)):
                    hits += 1.0
                    break
        if hits:
            vec[role] = hits
    return vec


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _forms(raw):
    found = set()
    for grp, kws in _FORM_GROUPS.items():
        for kw in kws:
            if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", raw):
                found.add(grp)
                break
    return found


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = _clean(usda_match)
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        ing_tok = _tokens(ing_raw)
        usda_tok = _tokens(usda_raw)
        if not ing_tok or not usda_tok:
            return 5.0

        # 1. Role compatibility (cosine between role-profile vectors)
        role_sim = _cosine(_role_vector(ing_tok, ing_raw), _role_vector(usda_tok, usda_raw))

        # 2. Identity anchor: does the ingredient's head noun appear in the USDA primary food
        usda_primary = _tokens(usda_raw.split(",")[0])
        usda_set = set(usda_tok)
        ing_set = set(ing_tok)
        head = ing_tok[-1]
        head_hit = 1.0 if head in usda_set else 0.0
        primary_hit = 1.0 if any(t in ing_set for t in usda_primary) else 0.0
        jac = len(ing_set & usda_set) / float(len(ing_set | usda_set))

        # 3. Form / behaviour mismatch penalties
        f_ing = _forms(ing_raw)
        f_usda = _forms(usda_raw)
        penalty = 0.0
        for grp, w in (("rind", 3.0), ("liquid", 2.0), ("dry", 1.5),
                       ("ground", 1.0), ("toasted", 1.5), ("fat_mod", 2.0)):
            if (grp in f_ing) != (grp in f_usda):
                penalty += w
        # Explicit "skin not eaten" or "skin" missing when ingredient specifies skin
        if "skin" in ing_set and re.search(r"skin not eaten|without skin", usda_raw):
            penalty += 2.5

        # Unexplained extra modifiers in USDA (different product), mild
        extra = [t for t in usda_set - ing_set if t not in _NOISE]
        penalty += 0.25 * min(len(extra), 6)

        score = (4.0 * role_sim + 3.0 * head_hit + 2.0 * primary_hit + 3.0 * jac) - penalty
        # map roughly to 0..10
        score = 10.0 / (1.0 + math.exp(-(score - 3.5)))
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
