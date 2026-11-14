import re

# ==========================================================================================
# Additive decision-stump ensemble (boosting style). Step 1 turns the pair into a flat dict of
# numeric features. Step 2 sums the outputs of a hand-built list of stumps (feature, threshold,
# value_if_below, value_if_at_or_above). No stump is a lookup of specific foods.
# ==========================================================================================

AL = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
      "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
      "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
      "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
VB = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
GEN = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal"}
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
ORGANS = {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard", "organ"}


def tk(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def rx(p, s):
    return 1.0 if re.search(p, s) else 0.0


def build_features(ingredient, usda_match):
    raw_u = " ".join(str(usda_match or "").split())
    kept, brand_n = [], 0
    for w in raw_u.split():
        letters = re.sub(r"[^A-Za-z]", "", w)
        if len(letters) >= 3 and letters.isupper() and letters.lower() not in ("nfs", "usda"):
            brand_n += 1
        else:
            kept.append(w)
    raw_nb = " ".join(kept)
    par = " ".join(re.findall(r"\(([^)]*)\)", raw_nb))
    i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
    i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
    u_txt = re.sub(r"\([^)]*\)", " ", raw_nb).lower()
    imain = tk(i_txt.split(",")[0])
    usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
    if not imain or not usegs:
        return None
    iset = set(tk(i_txt))
    uset = set(t for s in usegs for t in s) | set(tk(par))
    ub = uset | set(VB.get(t, t) for t in uset)
    core = [t for t in imain if t not in SKIP and not STATE.match(t)] or [t for t in imain if t not in SKIP] or imain
    matched = [1.0 if (t in ub or VB.get(t) in ub) else 0.0 for t in core]
    f = {}
    f["cov"] = sum(matched) / float(len(core))
    f["head"] = matched[-1]
    f["head_first"] = 1.0 if core[-1] in usegs[0] else 0.0
    f["ncore"] = float(len(core))
    first_extra = [t for t in usegs[0] if t not in core and t not in iset and t not in SKIP and not STATE.match(t) and t not in GEN]
    f["extra_first"] = float(min(len(first_extra), 4))
    f["form_noun"] = 1.0 if ((set(usegs[0]) & FORMS) - iset - set(core)) else 0.0
    f["front_state"] = 1.0 if (usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset) else 0.0
    f["brand_n"] = float(min(brand_n, 3))
    f["restaurant"] = rx(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt)
    soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
    organ = bool(set(core) & ORGANS) or "organ" in uset
    q_sodium = rx(r"low ?sodium|reduced sodium|no salt added|sodium free", u_txt) * (1 - rx(r"sodium", i_txt))
    q_fat = rx(r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", u_txt) * (1 - rx(r"fat|light|lite|skim|lean|diet", i_txt))
    f["q_sodium"] = q_sodium
    f["q_fat_hard"] = q_fat * (0.0 if soft else 1.0)
    f["q_fat_soft"] = q_fat * (1.0 if soft else 0.0)
    f["q_sugar"] = rx(r"sugar ?free|unsweetened|sweetened", u_txt) * (1 - rx(r"sweet|sugar", i_txt))
    f["q_diet"] = rx(r"decaf|lactose|\bdiet\b|low calorie", u_txt) * (1 - rx(r"decaf|lactose|diet", i_txt))
    f["q_mixin"] = rx(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", u_txt) * (1 - rx(r"\bwith\b|\band\b", i_txt))
    f["q_recipe"] = rx(r"made (with|from)|prepared (with|from)|from mix|dry mix", u_txt) * (1 - rx(r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", i_txt))
    f["q_origin"] = rx(r"new zealand|northern plains|hawaii|beaked|native|shoshone", u_txt) * (1 - rx(r"new zealand|hawaii", i_txt)) * (0.3 if organ else 1.0)
    f["q_deli"] = rx(r"\bdeli\b|luncheon|prepackaged|shelf stable", u_txt) * (1 - rx(r"deli|lunch|sliced", i_txt))
    f["q_ratio"] = rx(r"\d+% lean|\d+% fat", u_txt) * (1 - rx(r"\d+%", i_txt))
    f["q_coating"] = rx(r"breaded|battered|coated|glazed|candied", u_txt) * (1 - rx(r"bread|batter|coated|glazed|candied|crispy", i_txt))
    f["q_flavour"] = 1.0 if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt) if not re.search(r"\b" + x, i_txt)] else 0.0
    f["i_seasoned"] = rx(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) * (1 - rx(r"garlic|seasoned|marinated", u_txt))
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = rx(cook, i_txt), rx(cook, u_txt)
    f["cook_usda_only"] = 1.0 if (uc and not ic and not rx(r"\braw\b", u_txt)) else 0.0
    f["cook_ing_only_hard"] = 1.0 if (ic and not uc and rx(r"toasted|roasted|grilled|fried", i_txt)) else 0.0
    f["cook_ing_only_soft"] = 1.0 if (ic and not uc and not rx(r"toasted|roasted|grilled|fried", i_txt)) else 0.0
    di = rx(r"\b(dried|dehydrated)\b", i_txt) * (1 - ic)
    du = rx(r"\b(dried|dehydrated)\b", u_txt) * (0.0 if "from dried" in u_txt else 1.0)
    dflt = bool(set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"})
    f["dried_mismatch"] = 1.0 if (di != du and not (du and dflt)) else 0.0
    f["pick_smoke"] = float(sum(1 for w in ("pickled", "smoked") if (w in i_txt) != (w in u_txt)))
    cn = rx(r"\bcanned\b", u_txt)
    dc = bool(set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"})
    f["canned_mismatch"] = 1.0 if (rx(r"\bcanned\b", i_txt) != cn and not (cn and dc)) else 0.0
    gm = rx(r"\b(ground|powdered|powder)\b", i_txt) != rx(r"\b(ground|powdered|powder)\b", u_txt)
    f["ground_hard"] = 1.0 if (gm and set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"}) else 0.0
    f["ground_soft"] = 1.0 if (gm and not f["ground_hard"]) else 0.0
    seedfood = bool(set(core) & {"pomegranate", "amaranth", "flaxseed", "sesame", "chia", "sunflower", "poppy"})
    pi = set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt))
    pu = set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt))
    f["part_mismatch"] = 1.0 if (pi != pu) else 0.0
    f["compound_and"] = 1.0 if (rx(r"\band\b", i_txt.split(",")[0]) and not rx(r"\band\b", u_txt) and len(core) >= 2 and f["cov"] < 1.0) else 0.0
    conflict = 0.0
    for base, vs in VSET.items():
        named = vs & set(core)
        if named and base in uset and not (named & uset) and (vs & uset):
            conflict = 1.0
    f["variety_conflict"] = conflict
    return f


# stumps: (feature, threshold, value_below, value_at_or_above)
STUMPS = [
    ("cov", 0.5, -1.0, 1.0), ("cov", 0.99, 0.0, 2.2), ("cov", 0.01, -1.6, 0.0),
    ("head", 0.5, -1.4, 2.0), ("head_first", 0.5, 0.0, 0.6),
    ("extra_first", 1.0, 0.0, -0.55), ("extra_first", 2.0, 0.0, -0.55), ("extra_first", 3.0, 0.0, -0.55),
    ("form_noun", 0.5, 0.0, -3.0), ("front_state", 0.5, 0.0, -2.4), ("restaurant", 0.5, 0.0, -3.3),
    ("q_sodium", 0.5, 0.0, -1.9), ("q_fat_hard", 0.5, 0.0, -1.8), ("q_fat_soft", 0.5, 0.0, -0.6), ("q_sugar", 0.5, 0.0, -1.5),
    ("q_diet", 0.5, 0.0, -1.7), ("q_mixin", 0.5, 0.0, -1.9), ("q_recipe", 0.5, 0.0, -1.2), ("q_origin", 0.2, 0.0, -1.2),
    ("q_deli", 0.5, 0.0, -1.0), ("q_ratio", 0.5, 0.0, -1.4), ("q_coating", 0.5, 0.0, -1.7), ("q_flavour", 0.5, 0.0, -1.1),
    ("i_seasoned", 0.5, 0.0, -1.7), ("cook_usda_only", 0.5, 0.0, -2.1), ("cook_ing_only_hard", 0.5, 0.0, -1.9), ("cook_ing_only_soft", 0.5, 0.0, -1.1),
    ("dried_mismatch", 0.5, 0.0, -2.3), ("pick_smoke", 0.5, 0.0, -2.3), ("pick_smoke", 1.5, 0.0, -2.3), ("canned_mismatch", 0.5, 0.0, -1.6),
    ("ground_hard", 0.5, 0.0, -2.0), ("ground_soft", 0.5, 0.0, -1.2), ("part_mismatch", 0.5, 0.0, -2.5), ("compound_and", 0.5, 0.0, -1.4),
    ("variety_conflict", 0.5, 0.0, -2.2), ("brand_n", 0.5, 0.0, 0.0),
]


def judging_function(ingredient, usda_match):
    try:
        f = build_features(ingredient, usda_match)
        if f is None:
            return 0.0
        total = 2.0
        for name, thr, lo, hi in STUMPS:
            total += hi if f[name] >= thr else lo
        # branded packaged goods: brand tokens present and full coverage keeps most of the mass
        if f["brand_n"] >= 1 and f["head"] > 0.5:
            total += 0.6
        # continuous tie-breaker so ensembles of discrete stumps do not collapse to few levels
        total += 0.3 * f["cov"] - 0.02 * f["ncore"]
        return float(total)
    except Exception:
        return 0.0
