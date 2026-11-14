import re
import math

# Culinary role lexicon: keyword -> {role: weight}
_ROLE_LEXICON = {
    # fats
    "oil": {"fat": 1.0}, "butter": {"fat": 0.9, "dairy": 0.3}, "lard": {"fat": 1.0},
    "shortening": {"fat": 1.0}, "ghee": {"fat": 1.0}, "margarine": {"fat": 1.0},
    "tallow": {"fat": 1.0},
    # sweeteners
    "sugar": {"sweetener": 1.0}, "honey": {"sweetener": 1.0}, "syrup": {"sweetener": 0.9},
    "molasses": {"sweetener": 1.0}, "agave": {"sweetener": 1.0}, "sweetener": {"sweetener": 1.0},
    "jam": {"sweetener": 0.6, "condiment": 0.5}, "jelly": {"sweetener": 0.6, "condiment": 0.5},
    # thickeners / binders
    "flour": {"thickener": 0.7, "starch_base": 0.6}, "cornstarch": {"thickener": 1.0},
    "starch": {"thickener": 1.0}, "gelatin": {"thickener": 0.8, "binder": 0.4},
    "egg": {"binder": 0.9, "protein": 0.4}, "eggs": {"binder": 0.9, "protein": 0.4},
    "flax": {"binder": 0.8}, "flaxseed": {"binder": 0.8}, "chia": {"binder": 0.7, "seed": 0.5},
    "breadcrumbs": {"binder": 0.8}, "arrowroot": {"thickener": 1.0}, "tapioca": {"thickener": 0.9},
    "pectin": {"thickener": 1.0}, "agar": {"thickener": 1.0},
    # aromatics
    "garlic": {"aromatic": 1.0}, "onion": {"aromatic": 0.8, "vegetable": 0.4},
    "onions": {"aromatic": 0.8, "vegetable": 0.4}, "shallot": {"aromatic": 1.0},
    "shallots": {"aromatic": 1.0}, "ginger": {"aromatic": 1.0}, "leek": {"aromatic": 0.7, "vegetable": 0.5},
    "scallion": {"aromatic": 0.9}, "chives": {"aromatic": 0.9}, "lemongrass": {"aromatic": 1.0},
    "celery": {"aromatic": 0.6, "vegetable": 0.6},
    # seasonings / spices / herbs
    "salt": {"seasoning": 1.0}, "pepper": {"seasoning": 0.7, "vegetable": 0.3},
    "spices": {"seasoning": 1.0}, "cinnamon": {"seasoning": 1.0}, "cumin": {"seasoning": 1.0},
    "paprika": {"seasoning": 1.0}, "oregano": {"seasoning": 1.0}, "basil": {"seasoning": 0.9},
    "thyme": {"seasoning": 1.0}, "parsley": {"seasoning": 0.8}, "cilantro": {"seasoning": 0.8},
    "coriander": {"seasoning": 1.0}, "nutmeg": {"seasoning": 1.0}, "turmeric": {"seasoning": 1.0},
    "vanilla": {"seasoning": 0.8, "sweetener": 0.2}, "mustard": {"condiment": 0.8, "seasoning": 0.4},
    "rosemary": {"seasoning": 1.0}, "dill": {"seasoning": 1.0}, "cloves": {"seasoning": 1.0},
    # liquids / condiments
    "sauce": {"condiment": 1.0}, "ketchup": {"condiment": 1.0}, "vinegar": {"acid": 1.0},
    "lemon": {"acid": 0.6, "fruit": 0.5}, "lime": {"acid": 0.6, "fruit": 0.5},
    "juice": {"liquid": 1.0}, "broth": {"liquid": 0.9, "stock": 1.0}, "stock": {"liquid": 0.9, "stock": 1.0},
    "water": {"liquid": 1.0}, "wine": {"liquid": 0.8, "acid": 0.3}, "beer": {"liquid": 0.9},
    "soy": {"condiment": 0.7, "protein": 0.3}, "mayonnaise": {"condiment": 1.0, "fat": 0.4},
    "dressing": {"condiment": 1.0}, "salsa": {"condiment": 1.0}, "paste": {"condiment": 0.5},
    # dairy
    "milk": {"dairy": 1.0, "liquid": 0.4}, "cream": {"dairy": 1.0, "fat": 0.3},
    "cheese": {"dairy": 1.0, "protein": 0.3}, "yogurt": {"dairy": 1.0}, "brie": {"dairy": 1.0},
    "cheddar": {"dairy": 1.0}, "mozzarella": {"dairy": 1.0}, "parmesan": {"dairy": 1.0},
    "ricotta": {"dairy": 1.0}, "feta": {"dairy": 1.0}, "half": {"dairy": 0.2},
    # proteins
    "beef": {"protein": 1.0}, "pork": {"protein": 1.0}, "chicken": {"protein": 1.0},
    "turkey": {"protein": 1.0}, "lamb": {"protein": 1.0}, "fish": {"protein": 1.0},
    "salmon": {"protein": 1.0}, "tuna": {"protein": 1.0}, "shrimp": {"protein": 1.0},
    "tofu": {"protein": 1.0}, "sausage": {"protein": 0.8, "processed": 0.8},
    "frankfurter": {"protein": 0.6, "processed": 1.0}, "bacon": {"protein": 0.7, "processed": 0.7, "fat": 0.3},
    "ham": {"protein": 0.8, "processed": 0.6}, "patty": {"processed": 1.0, "protein": 0.5},
    "nuggets": {"processed": 1.0}, "veal": {"protein": 1.0}, "duck": {"protein": 1.0},
    # starch bases
    "rice": {"starch_base": 1.0}, "pasta": {"starch_base": 1.0}, "noodles": {"starch_base": 1.0},
    "spaghetti": {"starch_base": 1.0}, "gnocchi": {"starch_base": 1.0}, "bread": {"starch_base": 0.9},
    "potato": {"starch_base": 0.6, "vegetable": 0.6}, "potatoes": {"starch_base": 0.6, "vegetable": 0.6},
    "oats": {"starch_base": 0.8, "binder": 0.3}, "quinoa": {"starch_base": 1.0}, "couscous": {"starch_base": 1.0},
    "tortilla": {"starch_base": 0.9}, "yam": {"starch_base": 0.6, "vegetable": 0.6},
    # legumes
    "beans": {"legume": 1.0}, "broadbeans": {"legume": 1.0}, "favas": {"legume": 1.0},
    "fava": {"legume": 1.0}, "lentils": {"legume": 1.0}, "chickpeas": {"legume": 1.0},
    "peas": {"legume": 0.6, "vegetable": 0.5},
    # vegetables
    "carrot": {"vegetable": 1.0}, "carrots": {"vegetable": 1.0}, "tomato": {"vegetable": 0.9},
    "tomatoes": {"vegetable": 0.9}, "spinach": {"vegetable": 1.0}, "broccoli": {"vegetable": 1.0},
    "cabbage": {"vegetable": 1.0}, "zucchini": {"vegetable": 1.0}, "squash": {"vegetable": 1.0},
    "mushrooms": {"vegetable": 1.0}, "lettuce": {"vegetable": 1.0}, "kale": {"vegetable": 1.0},
    "eggplant": {"vegetable": 1.0}, "cucumber": {"vegetable": 1.0}, "corn": {"vegetable": 0.8},
    "vegetable": {"vegetable": 0.7}, "vegetables": {"vegetable": 0.7},
    # fruits
    "apple": {"fruit": 1.0}, "apples": {"fruit": 1.0}, "banana": {"fruit": 1.0},
    "cherries": {"fruit": 1.0}, "berries": {"fruit": 1.0}, "strawberries": {"fruit": 1.0},
    "blueberries": {"fruit": 1.0}, "orange": {"fruit": 1.0}, "peach": {"fruit": 1.0},
    "pear": {"fruit": 1.0}, "grapes": {"fruit": 1.0}, "mango": {"fruit": 1.0},
    "pineapple": {"fruit": 1.0}, "raisins": {"fruit": 0.8, "sweetener": 0.3}, "plum": {"fruit": 0.8},
    # nuts/seeds
    "almonds": {"nut": 1.0}, "walnuts": {"nut": 1.0}, "pecans": {"nut": 1.0},
    "peanuts": {"nut": 1.0}, "cashews": {"nut": 1.0}, "seeds": {"seed": 1.0}, "sesame": {"seed": 1.0},
}

# Physical form categories; incompatible pairs force a recipe change.
_FORM_WORDS = {
    "ground": "ground", "powder": "ground", "powdered": "ground", "meal": "ground",
    "whole": "whole", "chopped": "cut", "diced": "cut", "cubed": "cut", "sliced": "cut",
    "minced": "cut", "shredded": "cut", "grated": "cut", "crushed": "cut",
    "paste": "paste", "puree": "paste", "pureed": "paste",
    "juice": "liquid", "fluid": "liquid", "liquid": "liquid",
    "dried": "dried", "dehydrated": "dried", "fresh": "fresh", "raw": "fresh",
    "canned": "preserved", "pickled": "preserved",
    "gel": "gel",
}

_HARD_FORM_CONFLICTS = {
    frozenset(["ground", "whole"]), frozenset(["ground", "fresh"]), frozenset(["liquid", "ground"]),
    frozenset(["paste", "whole"]), frozenset(["gel", "ground"]), frozenset(["liquid", "whole"]),
    frozenset(["dried", "fresh"]),
}

_COOK_WORDS = {"cooked", "boiled", "baked", "roasted", "fried", "braised", "steamed",
               "grilled", "broiled", "stewed", "simmered", "microwaved", "drained"}
_RAW_WORDS = {"raw", "uncooked", "fresh"}

# USDA modifiers that change behaviour/composition noticeably
_ALTERATION_WORDS = {"low": 1.0, "reduced": 1.0, "fat-free": 1.2, "nonfat": 1.0, "lite": 1.0,
                     "light": 0.7, "imitation": 1.5, "substitute": 1.3, "diet": 1.0,
                     "sodium": 0.4, "sweetened": 0.4, "unsweetened": 0.3, "flavored": 0.8,
                     "breaded": 1.2, "battered": 1.2, "prepared": 0.4, "dehydrated": 0.8}

_STATE = {"frozen", "thawed", "fresh", "chopped", "diced", "cubed", "sliced", "minced",
          "shredded", "grated", "crushed", "peeled", "large", "small", "medium", "finely",
          "roughly", "thinly", "raw", "cooked", "dried", "whole", "ripe", "boneless", "skinless"}

_STOP = {"and", "or", "with", "without", "of", "the", "a", "an", "for", "to", "in", "from",
         "optional", "serving", "taste", "plus", "more", "about", "into", "added", "salt",
         "ns", "nfs", "as", "made", "type", "style", "all", "purpose", "ready", "serve"}


def _tokens(text):
    return [t for t in re.findall(r"[a-z][a-z\-]*", text.lower()) if t]


def _clean_ingredient(ing):
    s = ing.lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?|cups?|tbsp|tsp)?\b", " ", s)
    head, _, tail = s.partition(",")
    return head.strip(), tail.strip()


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _role_vector(tokens):
    vec = {}
    for t in tokens:
        roles = _ROLE_LEXICON.get(t) or _ROLE_LEXICON.get(_stem(t))
        if not roles:
            continue
        for r, w in roles.items():
            vec[r] = vec.get(r, 0.0) + w
    return vec


def _cosine(a, b):
    if not a or not b:
        return None
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return None
    return dot / (na * nb)


def _forms(tokens):
    return {_FORM_WORDS[t] for t in tokens if t in _FORM_WORDS}


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        head, tail = _clean_ingredient(ingredient)
        ing_head_toks = [t for t in _tokens(head) if t not in _STOP]
        ing_all_toks = ing_head_toks + [t for t in _tokens(tail) if t not in _STOP]
        usda_parts = [p.strip() for p in usda_match.lower().split(",") if p.strip()]
        if not usda_parts:
            return 0.0
        usda_primary = [t for t in _tokens(" ".join(usda_parts[:2])) if t not in _STOP]
        usda_all = [t for t in _tokens(usda_match) if t not in _STOP]

        # 1. Role similarity (core of the heuristic), driven by head nouns
        ing_vec = _role_vector(ing_head_toks)
        _cats = {"spices", "spice", "vegetable", "vegetables", "sauce", "beverages", "fruit"}
        usda_vec = _role_vector([t for t in usda_all if t not in _cats]) or _role_vector(usda_all)
        role_sim = _cosine(ing_vec, usda_vec)

        # 2. Identity anchor: is the ingredient's key item present in USDA text?
        ing_stems = {_stem(t) for t in ing_head_toks if t not in _STATE} or {_stem(t) for t in ing_head_toks}
        usda_stems = {_stem(t) for t in usda_all}
        primary_stems = {_stem(t) for t in usda_primary}
        anchor = len(ing_stems & usda_stems) / max(1, len(ing_stems))
        primary_hit = 1.0 if (ing_stems & primary_stems) else 0.0
        # ingredient-specific terms missing from USDA description (e.g. "tip", "shank")
        missing = len(ing_stems - usda_stems)

        if role_sim is None:
            role_component = 0.5 * anchor + 0.2 * primary_hit
        else:
            role_component = role_sim

        score = 40.0 * role_component + 25.0 * anchor + 12.0 * primary_hit

        # Processed vs whole cut mismatch (e.g. shank -> frankfurter)
        if usda_vec.get("processed", 0) > 0 and ing_vec.get("processed", 0) == 0:
            score -= 22.0

        # 3. Form / texture conflicts that would force a recipe change
        ing_forms = _forms(ing_all_toks)
        usda_forms = _forms(usda_all)
        for f1 in ing_forms:
            for f2 in usda_forms:
                if f1 != f2 and frozenset([f1, f2]) in _HARD_FORM_CONFLICTS:
                    score -= 15.0

        # 4. Cooking state: raw ingredient cut/used fresh vs pre-cooked USDA
        ing_set = set(ing_all_toks)
        usda_set = set(usda_all)
        ing_cooked = bool(ing_set & _COOK_WORDS)
        usda_cooked = bool(usda_set & _COOK_WORDS)
        if usda_cooked and not ing_cooked and ing_forms & {"cut", "whole"}:
            score -= 8.0
        elif usda_cooked and not ing_cooked:
            score -= 2.0
        elif ing_cooked and usda_cooked:
            score += 4.0
        elif not ing_cooked and (usda_set & _RAW_WORDS):
            score += 3.0

        # 5. Composition alterations in USDA not requested by ingredient
        alter = 0.0
        for w, pen in _ALTERATION_WORDS.items():
            if w in usda_set and w not in ing_set:
                alter += pen
        score -= 4.0 * min(alter, 2.0)

        # 6. Over-specific USDA (many descriptors) dilutes interchangeability
        extra_desc = max(0, len(usda_parts) - 3)
        score -= 1.0 * min(extra_desc, 4)
        score -= 3.0 * min(missing, 3)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
