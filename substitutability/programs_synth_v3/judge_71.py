import re

# Culinary role lexicon: stem -> (role, species/identity key)
_ROLE_LEXICON = {
    # proteins (identity matters: species/animal)
    "beef": ("protein_red", "beef"), "steak": ("protein_red", "beef"), "veal": ("protein_red", "veal"),
    "lamb": ("protein_red", "lamb"), "mutton": ("protein_red", "lamb"), "pork": ("protein_red", "pork"),
    "ham": ("protein_cured", "pork"), "bacon": ("protein_cured", "pork"), "sausage": ("protein_cured", "sausage"),
    "frankfurter": ("protein_cured", "frank"), "hot dog": ("protein_cured", "frank"),
    "chicken": ("protein_poultry", "chicken"), "turkey": ("protein_poultry", "turkey"),
    "duck": ("protein_poultry", "duck"), "fish": ("protein_sea", "fish"), "salmon": ("protein_sea", "salmon"),
    "tuna": ("protein_sea", "tuna"), "cod": ("protein_sea", "cod"), "shrimp": ("protein_sea", "shrimp"),
    "egg": ("binder", "egg"), "tofu": ("protein_plant", "tofu"),
    "liver": ("offal", "liver"), "kidney": ("offal", "kidney"), "heart": ("offal", "heart"),
    "tongue": ("offal", "tongue"),
    # legumes / starches
    "bean": ("legume", "bean"), "lentil": ("legume", "lentil"), "chickpea": ("legume", "chickpea"),
    "pea": ("legume", "pea"), "rice": ("starch", "rice"), "pasta": ("starch", "pasta"),
    "noodle": ("starch", "noodle"), "potato": ("starch", "potato"), "bread": ("starch", "bread"),
    "oat": ("starch", "oat"), "quinoa": ("starch", "quinoa"),
    "flour": ("thickener", "flour"), "cornstarch": ("thickener", "cornstarch"), "starch": ("thickener", "starch"),
    "flax": ("binder", "flax"), "chia": ("binder", "chia"), "gelatin": ("binder", "gelatin"),
    # fats
    "oil": ("fat", "oil"), "butter": ("fat", "butter"), "margarine": ("fat", "butter"),
    "lard": ("fat", "lard"), "ghee": ("fat", "butter"), "shortening": ("fat", "shortening"),
    # dairy
    "milk": ("dairy_liquid", "milk"), "cream": ("dairy_liquid", "cream"), "yogurt": ("dairy_soft", "yogurt"),
    "cheese": ("dairy_cheese", "cheese"), "cottage": ("dairy_soft", "cottage"),
    # sweeteners
    "sugar": ("sweetener", "sugar"), "honey": ("sweetener", "honey"), "syrup": ("sweetener", "syrup"),
    "molasses": ("sweetener", "molasses"),
    # aromatics / seasonings
    "garlic": ("aromatic", "garlic"), "onion": ("aromatic", "onion"), "shallot": ("aromatic", "shallot"),
    "ginger": ("aromatic", "ginger"), "leek": ("aromatic", "leek"), "scallion": ("aromatic", "scallion"),
    "sage": ("herb", "sage"), "basil": ("herb", "basil"), "thyme": ("herb", "thyme"),
    "oregano": ("herb", "oregano"), "parsley": ("herb", "parsley"), "cilantro": ("herb", "cilantro"),
    "rosemary": ("herb", "rosemary"), "mint": ("herb", "mint"), "dill": ("herb", "dill"),
    "pepper": ("seasoning", "pepper"), "salt": ("seasoning", "salt"), "cumin": ("seasoning", "cumin"),
    "cinnamon": ("seasoning", "cinnamon"), "paprika": ("seasoning", "paprika"), "vanilla": ("flavoring", "vanilla"),
    # vegetables
    "carrot": ("veg_bulk", "carrot"), "celery": ("veg_bulk", "celery"), "tomato": ("veg_bulk", "tomato"),
    "spinach": ("veg_leafy", "spinach"), "lettuce": ("veg_leafy", "lettuce"), "kale": ("veg_leafy", "kale"),
    "cabbage": ("veg_leafy", "cabbage"), "broccoli": ("veg_bulk", "broccoli"), "zucchini": ("veg_bulk", "zucchini"),
    "mushroom": ("veg_bulk", "mushroom"), "corn": ("veg_bulk", "corn"), "squash": ("veg_bulk", "squash"),
    "sauerkraut": ("veg_bulk", "sauerkraut"),
    # fruits
    "apple": ("fruit", "apple"), "banana": ("fruit", "banana"), "papaya": ("fruit", "papaya"),
    "mango": ("fruit", "mango"), "tamarind": ("acid_fruit", "tamarind"), "lemon": ("acid_fruit", "lemon"),
    "lime": ("acid_fruit", "lime"), "orange": ("fruit", "orange"), "berry": ("fruit", "berry"),
    # nuts
    "almond": ("nut", "almond"), "walnut": ("nut", "walnut"), "peanut": ("nut", "peanut"),
    # liquids
    "broth": ("liquid", "broth"), "stock": ("liquid", "broth"), "water": ("liquid", "water"),
    "vinegar": ("acid_fruit", "vinegar"), "wine": ("liquid", "wine"),
}

# Roles that are near-interchangeable in function
_ROLE_FAMILY = {
    "protein_red": "meat", "protein_poultry": "meat", "protein_cured": "meat_cured",
    "protein_sea": "seafood", "protein_plant": "plant_protein", "offal": "offal",
    "legume": "legume", "starch": "starch", "thickener": "thickener", "binder": "binder",
    "fat": "fat", "dairy_liquid": "dairy", "dairy_soft": "dairy", "dairy_cheese": "dairy",
    "sweetener": "sweet", "aromatic": "aromatic", "herb": "herb", "seasoning": "seasoning",
    "flavoring": "seasoning", "veg_bulk": "veg", "veg_leafy": "veg", "fruit": "fruit",
    "acid_fruit": "fruit", "nut": "nut", "liquid": "liquid",
}

# Physical forms that change how an ingredient behaves
_FORM_GROUPS = {
    "dry_powder": {"ground", "powder", "powdered", "dried", "dehydrated", "flakes", "granulated"},
    "fresh": {"fresh", "raw", "uncooked"},
    "cooked": {"cooked", "fried", "pan-fried", "roasted", "boiled", "baked", "grilled", "braised",
               "stewed", "broiled", "steamed", "canned"},
    "processed": {"patty", "nugget", "breaded", "battered", "loaf", "spread", "paste", "puree"},
    "whole_shape": {"whole", "sliced", "diced", "chopped", "minced", "cubed"},
}

_MIXTURE_MARKERS = re.compile(r"\b(with|and|or|in|sandwich|dish|salad|soup|casserole|stew|mixture|style)\b")
_FLAVOR_ADDITIVES = re.compile(r"\b(with vegetables|with fruit|with sauce|with cheese|with gravy|sweetened|flavored|seasoned)\b")
_GENERIC_OK = {"nfs", "ns", "plain", "regular", "raw", "fresh"}


def _norm(text):
    try:
        t = str(text or "").lower()
    except Exception:
        return ""
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    t = t.replace("hot dogs", "hot dog")
    return re.sub(r"\s+", " ", t).strip()


def _stem(w):
    for suf in ("ies", "oes", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "oes":
                return w[:-2]
            return w[:-len(suf)] if suf == "s" else w[:-1] if w.endswith("ses") else w[:-2] if w[-3] in "sxz" or w.endswith(("ches", "shes")) else w[:-1]
    return w


def _tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z][a-z\-]*", text)]


def _roles(text, toks):
    """Return list of (position, role, identity) found in text."""
    found = []
    joined = " " + " ".join(toks) + " "
    for key, (role, ident) in _ROLE_LEXICON.items():
        if " " in key:
            idx = (" " + text + " ").find(" " + key)
            if idx >= 0:
                found.append((idx, role, ident))
        else:
            for i, t in enumerate(toks):
                if t == key:
                    found.append((i * 10, role, ident))
                    break
    found.sort()
    return found


def _forms(toks_set, text):
    out = set()
    for g, words in _FORM_GROUPS.items():
        if toks_set & words or any(w in text for w in words if "-" in w):
            out.add(g)
    return out


def _head_role(roles, toks):
    """Pick the role that dominates the item.

    For recipe text the head noun tends to be last; for USDA the primary food is first.
    """
    return roles


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        if not ing or not usda:
            return 0.0

        ing_main = ing.split(",")[0].strip()
        usda_parts = [p.strip() for p in usda.split(",") if p.strip()]
        usda_primary = usda_parts[0] if usda_parts else usda

        ing_toks = _tokens(ing_main)
        usda_toks = _tokens(usda)
        prim_toks = _tokens(usda_primary)
        ing_set, usda_set = set(ing_toks), set(usda_toks)

        ing_roles = _roles(ing_main, ing_toks)
        usda_roles = _roles(usda, usda_toks)
        prim_roles = _roles(usda_primary, prim_toks)

        # ---- Stage 1: functional role of each side ----
        # Ingredient: a role-word that is the head (rightmost lexicon hit) defines function;
        # a modifier lexicon hit (e.g. "beef" in "beef kidney") defines identity.
        ing_head = ing_roles[-1] if ing_roles else None
        ing_idents = {r[2] for r in ing_roles}
        usda_head = prim_roles[0] if prim_roles else (usda_roles[0] if usda_roles else None)
        usda_idents = {r[2] for r in usda_roles}
        # Offal/organ words dominate function whatever position
        for r in ing_roles:
            if r[1] == "offal":
                ing_head = r
        for r in usda_roles:
            if r[1] == "offal":
                usda_head = r

        # role compatibility on a 0..1 scale
        if ing_head and usda_head:
            if ing_head[1] == usda_head[1]:
                role_fit = 1.0
            elif _ROLE_FAMILY.get(ing_head[1]) == _ROLE_FAMILY.get(usda_head[1]):
                role_fit = 0.6
            else:
                role_fit = 0.05
        elif ing_head or usda_head:
            role_fit = 0.35
        else:
            role_fit = 0.45

        # ---- Stage 2: identity preservation within the role ----
        if ing_idents and usda_idents:
            shared_ident = ing_idents & usda_idents
            missing = ing_idents - usda_idents
            extra = usda_idents - ing_idents
            ident_fit = len(shared_ident) / float(len(ing_idents))
            if ing_head and ing_head[2] not in usda_idents:
                ident_fit *= 0.4
            # species clash among proteins (beef vs lamb) changes taste noticeably
            if missing and extra and ing_head and ing_head[1].startswith(("protein", "offal")):
                ident_fit *= 0.5
        else:
            # lexical fallback: content-word overlap with primary food
            stop = {"of", "the", "a", "fresh", "raw", "sliced", "diced", "chopped", "plain", "lean", "only"}
            a = {t for t in ing_toks if t not in stop and len(t) > 2}
            b = {t for t in prim_toks if t not in stop and len(t) > 2}
            ident_fit = (len(a & b) / float(len(a))) if a else 0.3
            ident_fit = max(ident_fit, 0.15)

        # ---- Stage 3: behavioral form (texture/state) agreement ----
        ing_forms = _forms(set(_tokens(ing)), ing)
        usda_forms = _forms(usda_set, usda)
        form_mult = 1.0
        head_role = ing_head[1] if ing_head else ""
        if head_role in ("herb", "aromatic"):
            # fresh leafy herb vs dried/ground powder behaves differently
            if "dry_powder" in usda_forms and "dry_powder" not in ing_forms:
                form_mult *= 0.35
            if "processed" in ing_forms and "processed" not in usda_forms:
                form_mult *= 0.6
        if "processed" in usda_forms and "processed" not in ing_forms:
            form_mult *= 0.45
        if "cooked" in usda_forms and not (ing_forms & {"cooked"}) and head_role.startswith(("protein", "offal")):
            form_mult *= 0.55
        if "dry_powder" in ing_forms and "fresh" in usda_forms and head_role in ("herb", "aromatic", "seasoning"):
            form_mult *= 0.5

        # ---- Stage 4: composition integrity (mixtures / additions alter behavior) ----
        comp_mult = 1.0
        usda_tail = " ".join(usda_parts[1:]) if len(usda_parts) > 1 else ""
        if _FLAVOR_ADDITIVES.search(usda) and not _FLAVOR_ADDITIVES.search(ing):
            # flavoured yogurt for a flavoured yogurt is fine
            if not ("flavor" in usda and ing_set & {"vanilla", "flavored", "strawberry", "chocolate"}):
                comp_mult *= 0.4
        mix_hits = _MIXTURE_MARKERS.findall(usda_primary)
        if mix_hits:
            comp_mult *= 0.45 ** min(len(mix_hits), 2)
        # extra roles in USDA entry that ingredient lacks (e.g. "and sauerkraut")
        usda_role_set = {r[1] for r in usda_roles}
        ing_role_set = {r[1] for r in ing_roles}
        alien = usda_role_set - ing_role_set
        alien_families = {_ROLE_FAMILY.get(r) for r in alien} - {_ROLE_FAMILY.get(r) for r in ing_role_set}
        if alien_families:
            comp_mult *= 0.75 ** min(len(alien_families), 3)

        # generic/NFS entries are a fine stand-in when role & identity line up
        bonus = 0.0
        if usda_set & _GENERIC_OK and role_fit >= 1.0 and ident_fit >= 0.99:
            bonus = 0.08

        # ---- Combine: geometric blend so any failed stage drags score down ----
        core = (max(role_fit, 1e-3) ** 0.45) * (max(ident_fit, 1e-3) ** 0.35)
        score = core * form_mult * comp_mult + bonus
        score = max(0.0, min(1.0, score))
        return round(score * 10.0, 4)
    except Exception:
        return 0.0
