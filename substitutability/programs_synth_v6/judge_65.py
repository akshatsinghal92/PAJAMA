import re

# ===========================================================================================
# Cooking-method graph judge. Method words are mapped to families, families have pairwise
# distances (symmetrical), unstated methods are compatible with raw/generic. The method distance
# is the main term; identity and a short qualifier list play supporting roles.
# ===========================================================================================

FAMILY = {
    "raw": ["raw", "fresh", "uncooked", "unheated", "unroasted", "unprepared"],
    "dry": ["baked", "roasted", "broiled", "grilled", "toasted", "barbecued", "seared", "dry heat", "oven", "charbroiled", "pan-broiled", "panbroiled"],
    "moist": ["boiled", "steamed", "simmered", "braised", "poached", "stewed", "moist heat", "blanched", "microwaved"],
    "fat": ["fried", "deep-fried", "pan-fried", "sauteed", "sautéed", "stir-fried", "stir fried", "battered", "breaded"],
    "dried": ["dried", "dehydrated", "freeze-dried", "powdered"],
    "cured": ["smoked", "cured", "pickled", "brined", "salted", "fermented"],
    "canned": ["canned", "jarred", "bottled", "drained"],
    "frozen": ["frozen", "thawed"],
    "generic": ["cooked", "prepared", "heated"],
}
DIST = {("raw", "dry"): 2.2, ("raw", "moist"): 2.0, ("raw", "fat"): 3.2, ("raw", "dried"): 3.2, ("raw", "cured"): 3.0, ("raw", "canned"): 2.0, ("raw", "frozen"): 0.5, ("raw", "generic"): 2.0,
        ("dry", "moist"): 1.2, ("dry", "fat"): 1.6, ("dry", "dried"): 2.4, ("dry", "cured"): 2.0, ("dry", "canned"): 1.8, ("dry", "frozen"): 2.0, ("dry", "generic"): 0.4,
        ("moist", "fat"): 1.8, ("moist", "dried"): 2.6, ("moist", "cured"): 2.2, ("moist", "canned"): 0.8, ("moist", "frozen"): 2.0, ("moist", "generic"): 0.4,
        ("fat", "dried"): 3.0, ("fat", "cured"): 2.6, ("fat", "canned"): 2.4, ("fat", "frozen"): 2.4, ("fat", "generic"): 0.8,
        ("dried", "cured"): 1.8, ("dried", "canned"): 2.8, ("dried", "frozen"): 3.0, ("dried", "generic"): 2.2,
        ("cured", "canned"): 1.8, ("cured", "frozen"): 2.6, ("cured", "generic"): 1.4, ("canned", "frozen"): 1.6, ("canned", "generic"): 0.8, ("frozen", "generic"): 1.6}
FAM_RX = {f: re.compile(r"\b(" + "|".join(re.escape(w) for w in ws) + r")\b") for f, ws in FAMILY.items()}

SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
       "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
       "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
VB = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
DEFAULT_DRIED = {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}
DEFAULT_CANNED = {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}


def tk(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYN.get(w, w))
    return out


def families_of(text):
    return {f for f, rx in FAM_RX.items() if rx.search(text)}


def method_distance(i_fams, u_fams, defaults):
    """distance between two sets of method families. empty set on ingredient = raw-compatible; empty set on USDA = generic"""
    a = set(i_fams) or {"raw"}
    b = set(u_fams) or {"generic"}
    # 'unstated' on one side is compatible with raw and generic
    if not i_fams and not u_fams:
        return 0.0
    if not i_fams:
        # ingredient silent: raw plus 'frozen/thawed/canned default' acceptable
        best = min(DIST.get(tuple(sorted((x, y))), 0.0) if x != y else 0.0 for x in ("raw",) for y in b)
        return best if "raw" not in b else 0.0
    if not u_fams:
        # USDA silent: generic entry; cooked ingredient pays a small price, cured/dried/fried ingredient more
        worst = max(DIST.get(tuple(sorted((x, "raw"))), 0.0) for x in a if x != "raw") if a - {"raw"} else 0.0
        return 0.45 * worst
    best = 99.0
    for x in a:
        for y in b:
            d = 0.0 if x == y else DIST.get(tuple(sorted((x, y))), 2.0)
            best = min(best, d)
    # dried default exemption
    if "dried" in b and "dried" not in a and defaults & DEFAULT_DRIED:
        best = min(best, 0.4)
    if "canned" in b and "canned" not in a and defaults & DEFAULT_CANNED:
        best = min(best, 0.3)
    return best


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        kept = [w for w in raw_u.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
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
        # ---- cooking method term
        i_fams = families_of(i_txt) - {"frozen"} if families_of(i_txt) - {"frozen"} else set()
        u_fams = families_of(u_txt + " " + par.lower()) - {"frozen"} if families_of(u_txt + " " + par.lower()) - {"frozen"} else set()
        # "from dried" cooked beans are cooked, not dried
        if "from dried" in u_txt:
            u_fams.discard("dried")
        # a reconstituted dried ingredient ("cooked dried favas") is cooked
        if "dried" in i_fams and ("moist" in i_fams or "dry" in i_fams or "generic" in i_fams):
            i_fams.discard("dried")
        mdist = method_distance(i_fams, u_fams, set(core))
        # ---- supporting penalties
        pen = 0.0
        soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                              (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0),
                              (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2)]:
            if has(u_rx, u_txt) and not has(i_rx, i_txt):
                pen += w
        if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt) if not re.search(r"\b" + x, i_txt)]:
            pen += 1.1
        if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not has(r"garlic|seasoned|marinated", u_txt):
            pen += 1.7
        if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
            pen += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.5
        if (set(usegs[0]) & FORMS) - iset - set(core):
            pen += 3.0
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.4
        if has(r"\bbone[- ]in\b", i_txt) and not has(r"\bbone\b", u_txt):
            pen += 1.2
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.3
        conflict = 0.0
        for base, vs in VSET.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                conflict = 2.2
        return float(ident - 1.15 * mdist - conflict - 0.9 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
