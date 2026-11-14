import re
import math

# Culinary role lexicon: each role maps to cue words. A food may carry several roles.
_ROLE_CUES = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "sweetener", "confectioner",
                  "confectioners", "powdered", "stevia", "dextrose"],
    "confection": ["candy", "candies", "coating", "chocolate", "fudge", "toffee", "caramel",
                   "butterscotch", "marshmallow", "frosting", "icing"],
    "dairy": ["milk", "cream", "yogurt", "cheese", "kefir", "buttermilk", "creamer"],
    "protein": ["beef", "chicken", "pork", "turkey", "lamb", "veal", "fish", "salmon", "tuna",
                "shrimp", "egg", "eggs", "tofu", "tempeh", "sirloin", "breast", "thigh", "steak",
                "ham", "bacon", "sausage", "patty"],
    "starch": ["flour", "bread", "cornbread", "rice", "pasta", "noodle", "noodles", "oats",
               "cornmeal", "potato", "potatoes", "tortilla", "cracker", "crackers"],
    "thickener": ["cornstarch", "starch", "gelatin", "agar", "arrowroot", "tapioca", "pectin",
                  "chia", "flax", "flaxseed", "xanthan"],
    "aromatic": ["garlic", "onion", "onions", "shallot", "ginger", "leek", "scallion",
                 "spices", "spice", "herb", "herbs", "basil", "oregano", "cumin", "pepper",
                 "cinnamon", "paprika", "thyme"],
    "fruit": ["apple", "applesauce", "berry", "blackberry", "strawberry", "durian", "banana",
              "mango", "peach", "pear", "cherry", "grape", "orange", "lemon", "lime", "coconut",
              "pineapple", "raspberry", "blueberry"],
    "vegetable": ["tomato", "carrot", "celery", "spinach", "kale", "broccoli", "cabbage",
                  "lettuce", "zucchini", "squash", "pepper", "peppers", "vegetable", "vegetables",
                  "beans", "peas", "corn"],
    "liquid": ["juice", "broth", "stock", "water", "milk", "beverage", "drink", "nectar"],
    "condiment": ["dressing", "sauce", "ketchup", "mustard", "mayonnaise", "vinegar", "salsa",
                  "relish", "dip"],
}

# Physical-form classes; mismatched form forces a change in preparation.
_FORM_CUES = {
    "puree": ["puree", "purée", "pureed", "sauce", "applesauce", "mashed", "paste"],
    "ground": ["ground", "powder", "powdered", "minced", "meal", "flour", "granulated"],
    "whole": ["whole", "raw", "fresh", "roast", "steak", "fillet", "breast", "leaves"],
    "liquid": ["juice", "liquid", "drink", "beverage", "broth", "milk"],
    "solid_coat": ["coating", "bar", "chips", "candies", "candy"],
}

# Formulation modifiers that alter taste/behaviour (diet versions etc.).
_FORMULATION = {
    "reduced": "light", "low": "light", "lite": "light", "light": "light", "calorie": "light",
    "sodium": "light", "fat-free": "light", "diet": "light",
    "sweetened": "sweet", "unsweetened": "unsweet",
    "salted": "salt", "unsalted": "nosalt",
}

_NEUTRAL_USDA = {"raw", "or", "frozen", "made", "from", "home", "recipe", "regular", "canned",
                 "prepared", "commercial", "ns", "as", "to", "and", "with", "without",
                 "includes", "plain", "separable", "lean", "fat", "trimmed", "choice", "select",
                 "uncooked", "cooked", "fruit", "on", "bottom"}

_PREP = {"sifted", "thawed", "chopped", "diced", "sliced", "minced", "drained", "rinsed",
         "softened", "melted", "divided", "packed", "peeled", "beaten", "room", "temperature",
         "cut", "into", "pieces", "for", "serving", "optional", "taste", "the", "a", "of",
         "dairy-free", "tube", "jar"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = t.replace("é", "e").replace("'", "")
    return t


def _tokens(text):
    return [w for w in re.findall(r"[a-z][a-z\-]*", text) if len(w) > 1]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _profile(tokens, lexicon):
    vec = {}
    stems = set(_stem(t) for t in tokens) | set(tokens)
    for role, cues in lexicon.items():
        hits = 0
        for c in cues:
            c2 = c.replace("é", "e")
            if c2 in stems or _stem(c2) in stems:
                hits += 1
        if hits:
            vec[role] = hits
    return vec


def _cosine(a, b):
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Separate the ingredient's head (before comma) from the state clause.
        ing_head = ing.split(",")[0]
        ing_tok = [t for t in _tokens(ing_head) if t not in _PREP]
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_tok = _tokens(usda)
        primary_tok = _tokens(usda_parts[0]) if usda_parts else []

        if not ing_tok or not usda_tok:
            return 1.0

        # 1. Culinary role agreement (dominant feature).
        r_ing = _profile(ing_tok, _ROLE_CUES)
        r_usda = _profile(usda_tok, _ROLE_CUES)
        r_primary = _profile(primary_tok, _ROLE_CUES)
        role_sim = _cosine(r_ing, r_usda)
        # A role that the USDA *primary* food has but the ingredient lacks signals a shift
        # in function (e.g. sugar -> candy coating).
        foreign_roles = [r for r in r_primary if r not in r_ing]
        if not r_ing and not r_usda:
            role_sim = 0.5

        # 2. Physical form compatibility.
        f_ing = set(_profile(ing_tok, _FORM_CUES))
        f_usda = set(_profile(usda_tok, _FORM_CUES))
        form_pen = 0.0
        if f_ing and f_usda and not (f_ing & f_usda):
            form_pen = 1.5
        if "puree" in f_ing and ("puree" in f_usda):
            form_pen -= 0.5

        # 3. Identity anchoring: does the ingredient's head noun appear in USDA primary?
        ing_stems = set(_stem(t) for t in ing_tok)
        prim_stems = set(_stem(t) for t in primary_tok)
        all_stems = set(_stem(t) for t in usda_tok)
        head = _stem(ing_tok[-1])
        anchor = 0.0
        if head in prim_stems:
            anchor = 2.0
        elif head in all_stems:
            anchor = 1.2
        elif any(head[:4] == p[:4] for p in prim_stems if len(p) >= 4 and len(head) >= 4):
            anchor = 0.8
        coverage = len(ing_stems & all_stems) / max(1, len(ing_stems))

        # 4. Formulation conflicts: USDA diet/light variants the recipe didn't ask for.
        ing_form = {_FORMULATION[t] for t in _tokens(ing) if t in _FORMULATION}
        usda_form = {_FORMULATION[t] for t in usda_tok if t in _FORMULATION}
        extra_form = usda_form - ing_form
        form_conflict = 0.0
        if "light" in extra_form:
            form_conflict += 2.0
        if ("sweet" in ing_form and "unsweet" in usda_form) or \
           ("unsweet" in ing_form and "sweet" in usda_form):
            form_conflict += 2.0

        # 5. Specificity drift: USDA cut/variety descriptors absent from the ingredient that
        # change behaviour (e.g. a specific cut of meat vs another).
        unexplained = [t for t in usda_tok
                       if _stem(t) not in ing_stems and t not in _NEUTRAL_USDA
                       and not t.isupper() and len(t) > 2]
        drift = 0.0
        if "protein" in r_ing:
            drift = 0.45 * len(unexplained)
        else:
            drift = 0.15 * max(0, len(unexplained) - 2)

        score = 4.0 * role_sim + anchor + 2.0 * coverage
        score -= 1.5 * len(foreign_roles)
        score -= form_pen + form_conflict + min(drift, 3.0)
        score = 5.0 + score - 3.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
