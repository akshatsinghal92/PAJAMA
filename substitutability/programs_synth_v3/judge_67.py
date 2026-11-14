import re

# Culinary role lexicon: role -> keywords
_ROLES = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "acid": ["vinegar", "lemon juice", "lime juice", "verjuice"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "nectar", "stevia", "sweetener"],
    "aromatic": ["garlic", "onion", "shallot", "ginger", "leek", "scallion", "chive", "lemongrass"],
    "spice": ["spices", "pepper", "cumin", "cinnamon", "paprika", "nutmeg", "clove", "turmeric",
              "oregano", "basil", "thyme", "rosemary", "seasoning", "salt", "curry"],
    "thickener": ["starch", "flour", "arrowroot", "gelatin", "pectin", "agar", "tapioca", "roux"],
    "binder": ["egg", "flax", "chia", "breadcrumb", "bread crumbs"],
    "protein": ["chicken", "beef", "pork", "turkey", "lamb", "fish", "salmon", "tuna", "shrimp",
                "tofu", "tempeh", "duck", "veal", "sausage", "ham", "bacon"],
    "legume": ["beans", "bean", "lentil", "lentils", "peas", "chickpea", "chickpeas"],
    "grain": ["rice", "farina", "oats", "oat", "barley", "wheat", "cereals", "quinoa", "couscous",
              "pasta", "noodles", "cornmeal", "grits", "bulgur"],
    "baked": ["bread", "cornbread", "muffin", "biscuit", "roll", "cracker", "cake", "tortilla"],
    "dairy": ["cheese", "milk", "cream", "yogurt", "kefir"],
    "fruit": ["cherries", "cherry", "grapes", "grape", "apple", "pear", "peach", "plum", "berries",
              "jackfruit", "durian", "mango", "banana", "orange", "grapefruit", "tangelo", "ugli",
              "fruit", "melon", "pineapple", "apricot", "fig", "date"],
    "vegetable": ["carrot", "celery", "cucumber", "tomato", "potato", "spinach", "cabbage",
                  "broccoli", "squash", "zucchini", "lettuce", "kale", "pepper, sweet", "eggplant"],
    "liquid": ["broth", "stock", "wine", "juice", "water", "beer"],
}

# Physical form classes (texture / behavior)
_FORMS = {
    "ground": ["ground", "powder", "powdered", "meal", "flour", "dry mix"],
    "paste": ["paste", "puree", "pureed", "mashed", "spread", "butter"],
    "liquid": ["juice", "liquid", "syrup", "broth", "oil", "vinegar", "milk"],
    "chopped": ["chopped", "diced", "minced", "sliced", "segments", "shredded", "grated", "pulp"],
    "whole": ["whole", "raw", "fresh"],
    "gel": ["gel", "jelly", "gelled"],
}

# Compatible roles (role pair families that can sometimes stand in)
_ROLE_NEIGHBORS = {
    ("thickener", "grain"): 0.5,
    ("binder", "thickener"): 0.4,
    ("aromatic", "spice"): 0.4,
    ("legume", "protein"): 0.2,
    ("acid", "liquid"): 0.3,
    ("fruit", "vegetable"): 0.1,
    ("grain", "baked"): 0.2,
}

# Words that imply a composite dish rather than a single ingredient
_DISH_MARKERS = ["made with", "salad", "mixture", "prepared from", "casserole", "soup", "sandwich",
                 "dish", "with sauce", "patty", "stew", "recipe", "frozen dinner", "entree", "mix"]

# Words that modify behavior/composition in ways a cook would notice
_ALTERING = ["low sodium", "reduced fat", "fat free", "nonfat", "low fat", "light", "lite",
             "sugar free", "imitation", "substitute", "artificial", "diet", "unsalted"]

_PREP_STOP = {"g", "fresh", "frozen", "thawed", "chopped", "diced", "minced", "sliced", "raw",
              "cooked", "uncooked", "and", "or", "of", "the", "a", "with", "from", "to", "in",
              "quick", "cooking", "toasted", "large", "small", "medium", "pieces", "segments",
              "pulp", "processed", "prepared", "dry", "enriched", "assorted", "brands",
              "including", "minutes", "plain", "whole", "ground", "s"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\(([^)]*)\)", r" \1 ", t)
    t = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"[^a-z0-9,\- ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _has(text, kw):
    return re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text) is not None


def _roles(text, primary_only=None):
    found = {}
    for role, kws in _ROLES.items():
        for kw in kws:
            if _has(text, kw):
                w = 1.0
                if primary_only is not None and _has(primary_only, kw):
                    w = 2.0
                found[role] = max(found.get(role, 0.0), w)
    return found


def _forms(text):
    out = set()
    for form, kws in _FORMS.items():
        for kw in kws:
            if _has(text, kw):
                out.add(form)
                break
    return out


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and not w.endswith("ses"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _content_words(text):
    return {_stem(w) for w in re.findall(r"[a-z]+", text) if w not in _PREP_STOP and len(w) > 1}


def _role_score(r_ing, r_usda):
    if not r_ing or not r_usda:
        return 0.35
    best = 0.0
    for a, wa in r_ing.items():
        for b, wb in r_usda.items():
            if a == b:
                s = 1.0 * min(wa, wb) / 2.0 + 0.5
            else:
                s = _ROLE_NEIGHBORS.get((a, b), _ROLE_NEIGHBORS.get((b, a), 0.0))
            best = max(best, s)
    return min(best, 1.0)


def _form_score(f_ing, f_usda):
    if not f_ing or not f_usda:
        return 0.8
    if f_ing & f_usda:
        return 1.0
    conflicting = [("ground", "whole"), ("paste", "whole"), ("liquid", "ground"),
                   ("gel", "ground"), ("liquid", "whole"), ("paste", "ground")]
    for a, b in conflicting:
        if (a in f_ing and b in f_usda) or (b in f_ing and a in f_usda):
            return 0.35
    return 0.7


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_primary = usda_parts[0] if usda_parts else usda
        ing_main = ing.split(",")[0].strip()

        # 1. Culinary role agreement (primary of USDA weighted)
        r_ing = _roles(ing_main, primary_only=ing_main)
        r_usda = _roles(usda, primary_only=usda_primary)
        role = _role_score(r_ing, r_usda)

        # 2. Texture/form behavior
        form = _form_score(_forms(ing), _forms(usda))

        # 3. Identity anchor: does USDA primary food name appear in the ingredient?
        ing_words = _content_words(ing_main)
        prim_words = _content_words(usda_primary)
        usda_words = _content_words(usda)
        anchor = 0.0
        if prim_words:
            anchor = len(prim_words & ing_words) / float(len(prim_words))
        coverage = len(ing_words & usda_words) / float(len(ing_words)) if ing_words else 0.0

        # 4. Variety/qualifier conflict: ingredient qualifiers missing while USDA names a
        #    different qualifier for same primary (e.g. concord vs muscadine)
        extra_ing = ing_words - usda_words
        extra_usda = (usda_words - ing_words) - _content_words(" ".join(_ALTERING))
        variety_conflict = 0.0
        if anchor > 0 and extra_ing and extra_usda:
            variety_conflict = min(1.0, 0.35 * min(len(extra_ing), len(extra_usda)))

        # 5. Composite dish penalty (the match changes role from ingredient to dish)
        dish_hits = sum(1 for m in _DISH_MARKERS if _has(usda, m) and not _has(ing, m))
        dish_pen = min(1.0, 0.45 * dish_hits)

        # 6. Behavior-altering processing absent from ingredient
        alter_hits = sum(1 for m in _ALTERING if _has(usda, m) and not _has(ing, m))
        alter_pen = min(1.0, 0.4 * alter_hits)

        score = (
            3.2 * role
            + 1.6 * form
            + 3.0 * anchor
            + 1.4 * coverage
            - 2.0 * variety_conflict
            - 2.6 * dish_pen
            - 1.8 * alter_pen
        )
        if anchor == 0.0 and role < 1.0:
            score -= 1.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
