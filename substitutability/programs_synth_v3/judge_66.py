import re

# Culinary role lexicon: role -> keywords
_ROLES = {
    "fat": ["oil", "butter", "lard", "shortening", "ghee", "margarine", "tallow", "drippings"],
    "sweetener": ["sugar", "honey", "syrup", "molasses", "agave", "stevia", "sweetener", "nectar"],
    "thickener": ["flour", "starch", "cornstarch", "arrowroot", "tapioca", "gelatin", "pectin", "xanthan"],
    "binder": ["egg", "eggs", "flax", "chia", "breadcrumbs", "crumbs"],
    "aromatic": ["garlic", "onion", "shallot", "ginger", "leek", "scallion", "chive", "lemongrass"],
    "spice": ["pepper", "cumin", "paprika", "cinnamon", "nutmeg", "spice", "spices", "clove", "oregano",
              "basil", "thyme", "rosemary", "seasoning", "curry", "turmeric", "salt"],
    "protein": ["chicken", "beef", "pork", "turkey", "lamb", "fish", "salmon", "tuna", "shrimp", "tofu",
                "sausage", "ham", "bacon", "cervelat", "thuringer", "salami", "meat", "veal", "duck"],
    "dairy": ["milk", "cream", "yogurt", "cheese", "kefir", "buttermilk", "sour"],
    "starch_base": ["bread", "rice", "pasta", "spaghetti", "noodle", "noodles", "potato", "tortilla",
                    "dumpling", "dumplings", "wonton", "bun", "roll", "oats", "cereal"],
    "bulk_veg": ["squash", "carrot", "cabbage", "spinach", "kale", "broccoli", "zucchini", "pumpkin",
                 "tomato", "lettuce", "pepper", "beans", "peas", "celery", "eggplant", "seaweed",
                 "kombu", "laver", "nori", "mushroom", "mushrooms", "cauliflower", "veggie", "vegetable"],
    "fruit": ["orange", "mandarin", "clementine", "tangerine", "apple", "berry", "strawberry",
              "banana", "grape", "lemon", "lime", "peach", "pear", "mango", "cherry", "fruit"],
    "nut_seed": ["pecan", "pecans", "almond", "almonds", "walnut", "walnuts", "cashew", "peanut",
                 "peanuts", "hazelnut", "seed", "seeds", "pistachio"],
    "sauce": ["sauce", "gravy", "dressing", "ketchup", "salsa", "paste", "condiment", "vinegar"],
}

# Physical form classes -> keywords; values define functional behaviour
_FORMS = {
    "spread": ["butter", "paste", "spread", "puree", "pureed", "jam", "mashed"],
    "liquid": ["juice", "oil", "milk", "broth", "stock", "syrup", "liquid", "sauce"],
    "powder": ["ground", "powder", "powdered", "flour", "meal"],
    "pieces": ["chopped", "diced", "sliced", "minced", "shredded", "grated", "cubed", "crumbled"],
    "dried": ["dried", "dry", "dehydrated"],
    "gel": ["gel", "jelly", "gelatin"],
}

# Pairs of forms that change behaviour substantially (penalty weight)
_FORM_CONFLICT = {
    frozenset(["spread", "whole"]): 3.5,
    frozenset(["spread", "pieces"]): 2.5,
    frozenset(["spread", "powder"]): 2.5,
    frozenset(["liquid", "powder"]): 3.0,
    frozenset(["liquid", "whole"]): 2.5,
    frozenset(["gel", "powder"]): 3.0,
    frozenset(["dried", "fresh"]): 2.5,
    frozenset(["powder", "whole"]): 0.8,
    frozenset(["pieces", "whole"]): 0.4,
}

# Known interchangeable item groups (same culinary role, imperceptible swap)
_EQUIV = [
    {"mandarin", "clementine", "tangerine", "satsuma"},
    {"cervelat", "thuringer", "summer"},
    {"dumpling", "dumplings", "wonton", "potsticker", "pot", "sticker"},
    {"scallion", "scallions", "green", "spring"},
    {"garbanzo", "chickpea", "chickpeas"},
    {"cilantro", "coriander"},
    {"zucchini", "courgette"},
    {"veggie", "vegetable", "no"},
]

# Distinct varieties within a family: sharing the family but differing variety is a change
_VARIETY_FAMILIES = {
    "squash": {"butternut", "hubbard", "acorn", "spaghetti", "delicata", "kabocha", "summer", "zucchini"},
    "seaweed": {"kombu", "laver", "nori", "wakame", "kelp", "dulse", "agar"},
    "kombu": {"kombu", "laver", "nori", "wakame", "kelp", "dulse"},
    "rice": {"white", "brown", "wild", "basmati", "jasmine", "arborio"},
    "onion": {"red", "yellow", "white", "sweet", "green"},
}

_STOP = {"and", "or", "with", "of", "the", "a", "an", "nfs", "ns", "raw", "fresh", "plain",
         "from", "tube", "for", "to", "in", "uncooked", "cooked", "prepared", "type", "style"}

_PREP_NOISE = {"thawed", "softened", "melted", "room", "temperature", "drained", "rinsed",
               "divided", "packed", "peeled", "trimmed", "optional", "large", "small", "medium"}


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"^\s*[\d.,/]+\s*(g|gr|grams?|kg|ml|l|oz)?\b", " ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    return [t for t in text.split() if t]


def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("es") and t[-3] in "sxz":
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _roles(tokens):
    found = {}
    tset = set(tokens) | {_stem(t) for t in tokens}
    for role, kws in _ROLES.items():
        hits = sum(1 for k in kws if k in tset or _stem(k) in tset)
        if hits:
            found[role] = hits
    return found


def _forms(tokens, is_usda):
    tset = set(tokens)
    out = set()
    for form, kws in _FORMS.items():
        if any(k in tset for k in kws):
            out.add(form)
    # 'butter' as fat vs nut butter: only a spread if preceded by nut/seed word
    if "butter" in tset:
        nutty = any(_stem(t) in {"pecan", "peanut", "almond", "cashew", "walnut", "hazelnut",
                                 "seed", "apple", "pistachio"} for t in tokens)
        if not nutty and "spread" in out and not (tset & {"paste", "spread", "puree", "jam", "mashed"}):
            out.discard("spread")
    if "oil" in tset and "liquid" in out and len(out) == 1:
        pass
    if not out:
        out.add("whole")
    if "raw" in tset or "fresh" in tset:
        out.add("fresh")
    return out


def _primary_ing(tokens):
    content = [t for t in tokens if t not in _STOP and t not in _PREP_NOISE]
    return _stem(content[-1]) if content else ""


def _primary_usda(desc):
    first = desc.lower().split(",")[0]
    toks = _tokens(first)
    toks = [t for t in toks if t not in _STOP]
    return [_stem(t) for t in toks]


def _equiv_hit(a, b):
    for grp in _EQUIV:
        g = {_stem(x) for x in grp}
        if (a & g) and (b & g) and (a & g) != (b & g):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        ing_main = ingredient.split(",")[0]
        ing_tok = _tokens(ing_main)
        usda_tok = _tokens(usda_match)
        if not ing_tok or not usda_tok:
            return 0.0

        ing_set = {_stem(t) for t in ing_tok if t not in _STOP and t not in _PREP_NOISE}
        usda_set = {_stem(t) for t in usda_tok if t not in _STOP}

        score = 5.0

        # 1. Role agreement (core of the rubric)
        r_ing = _roles(ing_tok)
        r_usda = _roles(usda_tok)
        if r_ing and r_usda:
            shared = set(r_ing) & set(r_usda)
            union = set(r_ing) | set(r_usda)
            role_sim = len(shared) / float(len(union))
            score += 3.0 * role_sim
            if not shared:
                score -= 2.5
        elif r_ing or r_usda:
            score -= 0.3

        # 2. Primary item identity
        head = _primary_ing(ing_tok)
        uprim = set(_primary_usda(usda_match))
        if head and head in uprim:
            score += 2.0
        elif head and head in usda_set:
            score += 1.0
        elif _equiv_hit(ing_set, usda_set):
            score += 2.0
        else:
            score -= 1.0

        # token coverage of the ingredient by USDA
        if ing_set:
            cov = len(ing_set & usda_set) / float(len(ing_set))
            score += 1.5 * cov

        # 3. Form / texture behaviour
        f_ing = _forms(ing_tok, False)
        f_usda = _forms(usda_tok, True)
        penalty = 0.0
        for a in f_ing:
            for b in f_usda:
                if a == b:
                    continue
                penalty = max(penalty, _FORM_CONFLICT.get(frozenset([a, b]), 0.0))
        # ingredient is a spread (e.g. nut butter, paste) but USDA lacks it -> function changes
        if "spread" in f_ing and "spread" not in f_usda:
            penalty = max(penalty, 3.0)
        # dried ingredient but USDA entry raw/fresh
        if "dried" in f_ing and "dried" not in f_usda and ("fresh" in f_usda or "raw" in usda_tok):
            penalty = max(penalty, 2.5)
        score -= penalty

        # 4. Variety conflict within a family
        for fam, varieties in _VARIETY_FAMILIES.items():
            if fam in ing_set or fam in usda_set or (ing_set & varieties and usda_set & varieties):
                vi = ing_set & varieties
                vu = usda_set & varieties
                if vi and vu and not (vi & vu):
                    score -= 3.0
                    break
                if vi and not vu and fam in usda_set and len(usda_set) > 1:
                    # USDA describes a specific different variant not named in ingredient
                    extra = usda_set - ing_set - {fam}
                    if extra & set().union(*_VARIETY_FAMILIES.values()):
                        score -= 2.0
                        break

        # 5. Extra unexplained USDA descriptors (mild, signals a different product)
        neutral = {"frozen", "fried", "toasted", "nonfat", "brand", "fruit", "bottom", "unroasted",
                   "roasted", "meat", "no", "with", "beef", "pork", "summer", "greek"}
        extra = [t for t in usda_set - ing_set if t not in neutral and len(t) > 2]
        score -= min(1.5, 0.25 * len(extra))

        # cooking-state agreement (fried, toasted, etc.)
        states = {"fried", "toasted", "roasted", "baked", "boiled", "grilled", "smoked"}
        si = ing_set & states
        su = usda_set & states
        if si and su:
            score += 0.8 if si & su else -0.8
        elif si and not su:
            score -= 0.5

        return round(max(0.0, min(15.0, score)) * (100.0 / 15.0), 3)
    except Exception:
        return 0.0
