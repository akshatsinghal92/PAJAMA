import re
import math

SYNONYMS = {
    "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed",
    "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander",
    "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo",
    "pinyon": "pine", "pinon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine",
    "ox": "beef", "calf": "veal", "para": "brazil", "innard": "giblet", "yoghurt": "yogurt", "fava": "broadbean",
    "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup",
}
BASE_OF_VARIETY = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato",
                   "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VARIETIES_BY_BASE = {"grape": {"concord", "muscadine", "thompson", "american", "red", "green"}, "squash": {"butternut", "hubbard", "acorn", "winter", "summer", "spaghetti"},
                     "apple": {"fuji", "gala", "granny", "mcintosh", "golden", "delicious"}, "potato": {"russet", "yukon", "red"}, "orange": {"navel", "valencia", "blood"}}
FILLER = frozenset("""thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed
    melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs
    regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild
    mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank
    loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious
    style domesticated new fluid white sliced atlantic pacific alaska american""".split())
STATE_WORDS = frozenset("cooked boiled baked braised simmered broiled roasted steamed toasted grilled sauteed poached stewed heat dried canned frozen smoked pickled fried ground powdered batter lowfat nonfat reduced light lite skim sweetened unsweetened flavored diet".split())
TRANSFORM_NOUNS = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf icecream".split())


def tokenize(s):
    out = []
    for w in re.findall(r"[a-z]+", s.lower().replace("-", " ")):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYNONYMS.get(w, w))
    return out


def strip_brand(raw):
    return " ".join(w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))


def features(ingredient, usda_match):
    u_raw = strip_brand(str(usda_match or ""))
    paren = tokenize(" ".join(re.findall(r"\(([^)]*)\)", u_raw)))
    i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
    i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
    u_txt = re.sub(r"\([^)]*\)", " ", u_raw.lower())
    i_main = i_txt.split(",")[0]
    imain, iall = tokenize(i_main), tokenize(i_txt)
    usegs = [tokenize(s) for s in u_txt.split(",") if s.strip()]
    if not imain or not usegs:
        return None
    uflat = [t for s in usegs for t in s]
    uset = set(uflat) | set(paren)
    iset = set(iall)
    core = [t for t in imain if t not in FILLER and t not in STATE_WORDS] or [t for t in imain if t not in FILLER] or imain
    core_b = [BASE_OF_VARIETY.get(t, t) for t in core]
    f = {}
    f["coverage"] = sum(1 for t in core_b if (t in uset or any(BASE_OF_VARIETY.get(u, u) == t for u in uset))) / float(len(core_b))
    f["head_present"] = 1.0 if (core_b[-1] in uset or any(BASE_OF_VARIETY.get(u, u) == core_b[-1] for u in uset)) else 0.0
    f["head_first_seg"] = 1.0 if core_b[-1] in usegs[0] else 0.0
    # variety conflict: ingredient names a variety, USDA names another variety of the same base
    conflict = 0.0
    for t in core:
        if t in BASE_OF_VARIETY:
            base = BASE_OF_VARIETY[t]
            others = VARIETIES_BY_BASE.get(base, set()) - {t}
            if t not in uset and (uset & others):
                conflict = 1.0
    f["variety_conflict"] = conflict
    # added qualifiers (USDA only)
    def has(rx, s):
        return 1.0 if re.search(rx, s) else 0.0
    soft = 1.0 if (re.search(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt) else 0.0
    f["q_sodium"] = has(r"low ?sodium|reduced sodium|no salt added|sodium free", u_txt) * (1 - has(r"low ?sodium|reduced sodium|no salt", i_txt))
    fatq = has(r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", u_txt) * (1 - has(r"fat|light|lite|skim|lean|diet", i_txt))
    f["q_fat"] = fatq * (0.35 if soft else 1.0)
    f["q_sugar"] = has(r"sugar ?free|unsweetened|sweetened|with sugar", u_txt) * (1 - has(r"sweet|sugar", i_txt))
    f["q_salt"] = has(r"with salt|\bsalted\b|salt added", u_txt) * (1 - has(r"salt", i_txt))
    f["q_addedfat"] = has(r"fat added|added fat|made with oil", u_txt) * (1 - has(r"saut|fried|butter|oil|fat", i_txt))
    f["q_lactose_caf_diet"] = has(r"lactose|decaf|\bdiet\b|low calorie", u_txt) * (1 - has(r"lactose|decaf|diet", i_txt))
    f["q_mixin"] = has(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", u_txt) * (1 - has(r"\bwith\b|\band\b", i_main))
    f["q_recipe"] = has(r"made (with|from)|prepared (with|from)|from mix|dry mix", u_txt) * (1 - has(r"made|prepared|mix", i_txt)) * (0.5 if "vegan" in i_txt or "plant" in i_txt else 1.0)
    f["q_origin"] = has(r"new zealand|northern plains|hawaii|beaked|native", u_txt)
    f["q_deli"] = has(r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ](bake|fry|serve)", u_txt) * (1 - has(r"deli|lunch|sliced", i_txt))
    f["q_coating"] = has(r"breaded|battered|coated|glazed|candied", u_txt) * (1 - has(r"bread|batter|coated|glazed|candied|crispy", i_txt))
    f["q_ratio"] = has(r"\d+% lean|\d+% fat", u_txt) * (1 - has(r"\d+%", i_txt))
    flav = re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt)
    f["q_flavour"] = 1.0 if any(not re.search(r"\b" + x, i_txt) for x in flav) else 0.0
    # stated-qualifier drop (ingredient says it, USDA lacks)
    f["drop_stated"] = 1.0 if (re.search(r"unsalted|unsweetened|low ?fat|nonfat|fat ?free|sugar ?free|reduced", i_txt) and not re.search(r"unsalted|unsweetened|low ?fat|nonfat|fat ?free|sugar ?free|reduced|light|lite", u_txt)) else 0.0
    # state events
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
    f["cook_usda_only"] = 1.0 if (uc and not ic and not re.search(r"\braw\b", u_txt)) else 0.0
    f["cook_ing_only"] = 1.0 if (ic and not uc) else 0.0
    di = bool(re.search(r"\b(dried|dehydrated)\b", i_txt)) and not ic
    du = bool(re.search(r"\b(dried|dehydrated)\b", u_txt)) and "from dried" not in u_txt
    default_dry = bool(set(core) & {"pine", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"})
    f["dried_mismatch"] = 1.0 if (di != du and not (du and default_dry)) else 0.0
    f["pickled_smoked"] = 1.0 if any((w in i_txt) != (w in u_txt) for w in ("pickled", "smoked")) else 0.0
    cn = bool(re.search(r"\bcanned\b", u_txt))
    f["canned_mismatch"] = 1.0 if (bool(re.search(r"\bcanned\b", i_txt)) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"})) else 0.0
    f["ground_mismatch"] = 1.0 if (bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt))) else 0.0
    f["part_mismatch"] = 1.0 if set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", u_txt)) else 0.0
    f["transform_noun"] = 1.0 if ((set(usegs[0]) & TRANSFORM_NOUNS) - iset) else 0.0
    f["front_state"] = 1.0 if (usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset) else 0.0
    f["brand_restaurant"] = has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt)
    return f


WEIGHTS = {"coverage": 5.0, "head_present": 1.8, "head_first_seg": 0.5, "variety_conflict": -2.2,
           "q_sodium": -2.0, "q_fat": -1.9, "q_sugar": -1.6, "q_salt": -1.2, "q_addedfat": -1.2, "q_lactose_caf_diet": -1.8,
           "q_mixin": -2.0, "q_recipe": -1.3, "q_origin": -1.4, "q_deli": -1.1, "q_coating": -1.8, "q_ratio": -1.5, "q_flavour": -1.2,
           "drop_stated": -0.9, "cook_usda_only": -2.2, "cook_ing_only": -1.3, "dried_mismatch": -2.4, "pickled_smoked": -2.4,
           "canned_mismatch": -1.7, "ground_mismatch": -1.2, "part_mismatch": -2.6, "transform_noun": -3.2, "front_state": -2.5,
           "brand_restaurant": -3.5}


def judging_function(ingredient, usda_match):
    try:
        f = features(ingredient, usda_match)
        if f is None:
            return 0.0
        z = 2.0 + sum(WEIGHTS[k] * v for k, v in f.items())
        return float(z)
    except Exception:
        return 0.0
