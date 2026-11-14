import re

# =============================================================================================
# Type-matrix judge: every food string is classified into a structural TYPE
#     S  single ingredient          L  list of foods ('X and Y', 'X, Y')
#     D  prepared dish              M  mix / blend / dry mix
#     B  branded packaged product   R  restaurant item
# A compatibility matrix gives the structural score; a fully table-driven rule list (regexes on the
# USDA side that are not licensed by the ingredient side) supplies the qualifier/state penalties.
# =============================================================================================

DISH_RX = r"\b(entree|dinner|casserole|sandwich|burrito|taco|pizza|pie|stew|soup|salad|curry|stir[- ]fry|lasagna|macaroni and cheese|stuffed|in (a )?(sauce|gravy)|topped|filled)\b"
MIX_RX = r"\b(mix|blend|mixture|assorted|combination|medley|dry mix)\b"
LIST_RX = r"\b(and|with|plus|&)\b"
IDIOM_RX = r"half and half|salt and pepper|meat and skin|skin and bone|equal parts milk and cream|half & half"
RESTAURANT_RX = r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food|kfc|subway"

TYPE_MATRIX = {("S", "S"): 0.0, ("S", "L"): -1.6, ("S", "D"): -3.2, ("S", "M"): -2.0, ("S", "B"): -0.2, ("S", "R"): -3.5,
               ("L", "S"): -1.6, ("L", "L"): 0.4, ("L", "D"): -1.0, ("L", "M"): -0.6, ("L", "B"): -0.6, ("L", "R"): -3.0,
               ("D", "S"): -3.0, ("D", "L"): -1.0, ("D", "D"): 0.8, ("D", "M"): -0.8, ("D", "B"): -0.4, ("D", "R"): -1.0,
               ("M", "S"): -1.8, ("M", "L"): -0.6, ("M", "D"): -1.0, ("M", "M"): 0.6, ("M", "B"): -0.2, ("M", "R"): -2.5,
               ("B", "S"): -0.2, ("B", "L"): -0.6, ("B", "D"): -0.6, ("B", "M"): -0.2, ("B", "B"): 0.4, ("B", "R"): -2.0}

SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
       "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
       "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
VB = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "candy", "cake", "pudding", "snack", "cookie", "syrup", "sauce", "frankfurter", "loaf"}

# table rows: (regex that must match the USDA text, regex that if found in the ingredient licenses it, weight)
RULES = [
    (r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
    (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9),
    (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6),
    (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
    (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
    (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
    (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
    (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
    (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8),
    (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint", 1.1),
]


def tk(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYN.get(w, w))
    return out


def classify(text, branded=False):
    t = re.sub(IDIOM_RX, " ", text.lower())
    if re.search(RESTAURANT_RX, t):
        return "R"
    if re.search(DISH_RX, t):
        return "D"
    if re.search(MIX_RX, t):
        return "M"
    if branded:
        return "B"
    first = t.split(",")[0]
    if re.search(LIST_RX, first):
        return "L"
    return "S"


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        kept = [w for w in raw_u.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        branded = len(kept) < len(raw_u.split())
        raw_nb = " ".join(kept)
        par = " ".join(re.findall(r"\(([^)]*)\)", raw_nb))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_nb).lower()
        i_main = i_txt.split(",")[0]
        imain = tk(i_main)
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        iset = set(tk(i_txt))
        uset = set(t for s in usegs for t in s) | set(tk(par))
        ub = uset | set(VB.get(t, t) for t in uset)
        core = [t for t in imain if t not in SKIP and not STATE.match(t)] or [t for t in imain if t not in SKIP] or imain
        matched = [1.0 if (t in ub or VB.get(t) in ub) else 0.0 for t in core]
        cov = sum(matched) / float(len(core))
        ident = 4.6 * cov + 2.0 * (1.0 if matched[-1] else -0.7)
        # ---- structural type compatibility
        ti = classify(i_main)
        tu = classify(u_txt, branded)
        struct = TYPE_MATRIX.get((ti, tu), 0.0)
        # a dish ingredient word equal on both sides cancels the dish penalty (soup for soup)
        if ti == "S" and tu in ("D", "M", "L") and not (set(core) & set(t for s in usegs[:1] for t in s)):
            struct -= 0.4
        # ---- data-driven qualifier rules
        pen = 0.0
        soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        for u_rx, lic, w in RULES:
            if re.search(u_rx, u_txt) and not re.search(lic, i_txt):
                pen += w * (0.35 if (soft and "fat" in u_rx) else 1.0)
        # ---- state rules as (condition, weight)
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
        dflt_dry = bool(set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"})
        dflt_can = bool(set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"})
        di = bool(re.search(r"\b(dried|dehydrated)\b", i_txt)) and not ic
        du = bool(re.search(r"\b(dried|dehydrated)\b", u_txt)) and "from dried" not in u_txt
        seedy = bool(set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"})
        state_rules = [
            (uc and not ic and not re.search(r"\braw\b", u_txt), 2.1),
            (ic and not uc and bool(re.search(r"toasted|roasted|grilled|fried", i_txt)), 1.9),
            (ic and not uc and not re.search(r"toasted|roasted|grilled|fried", i_txt), 1.1),
            (di != du and not (du and dflt_dry), 2.3),
            (("pickled" in i_txt) != ("pickled" in u_txt), 2.3), (("smoked" in i_txt) != ("smoked" in u_txt), 2.3),
            (bool(re.search(r"\bcanned\b", i_txt)) != bool(re.search(r"\bcanned\b", u_txt)) and not (re.search(r"\bcanned\b", u_txt) and dflt_can), 1.6),
            (bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt)), 2.0 if seedy else 1.3),
            (set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)), 2.5),
            (bool((set(usegs[0]) & FORMS) - iset), 3.0),
            (bool(usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset), 2.4),
            (bool(re.search(r"\bbone[- ]in\b", i_txt)) and not re.search(r"\bbone\b", u_txt), 1.2),
        ]
        for cond, w in state_rules:
            if cond:
                pen += w
        conflict = 0.0
        for base, vs in VSET.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                conflict = 2.2
        return float(ident + struct - conflict - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
