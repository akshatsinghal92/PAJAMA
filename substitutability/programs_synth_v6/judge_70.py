import re

# =============================================================================================
# Cut-tree judge. Animal cuts and plant parts are nodes of a small taxonomy (parent links). A part
# mismatch costs by tree distance: same node 0, parent/child 0.4, siblings 1.2, different primal 2.4,
# animal flesh vs organ/offal 3.2, plant part vs different plant part 3.0. Everything else is an
# additive score (identity + method/qualifier penalties) in a plain linear layout.
# =============================================================================================

PARENT = {}


def tree(parent, *children):
    for ch in children:
        PARENT[ch] = parent


tree("poultry_flesh", "breast", "leg", "wing", "back", "tender")
tree("leg", "thigh", "drumstick", "drum")
tree("wing", "flat", "drumette", "wingette")
tree("beef_primal", "chuck", "rib", "loin", "round", "brisket", "flank", "shank", "plate", "sirloin_tip")
tree("chuck", "blade", "shoulder", "arm")
tree("rib", "ribeye", "prime_rib")
tree("loin", "sirloin", "tenderloin", "strip", "porterhouse", "tbone", "chop", "steak")
tree("round", "rump", "tip", "eye")
tree("pork_primal", "ham", "belly", "jowl", "butt", "picnic", "spareribs", "hock")
tree("offal", "liver", "heart", "kidney", "tongue", "giblet", "gizzard", "tripe", "brain", "sweetbread", "tail", "neck", "foot", "feet")
tree("plant_part", "leaf", "root", "stem", "stalk", "seed", "flower", "floret", "peel", "zest", "rind", "bulb", "pod", "kernel", "pulp", "head", "sprout", "shoot")
tree("egg_part", "yolk", "white")
tree("fish_part", "fillet", "steak_fish", "belly_fish", "roe")
tree("covering", "skin", "bone", "shell")
ROOT_KIND = {"poultry_flesh": "flesh", "beef_primal": "flesh", "pork_primal": "flesh", "offal": "offal", "plant_part": "plant", "egg_part": "egg", "fish_part": "flesh", "covering": "cover"}
WORD2NODE = {"breast": "breast", "thigh": "thigh", "drumstick": "drumstick", "drum": "drum", "leg": "leg", "wing": "wing", "flat": "flat", "drumette": "drumette", "back": "back", "tender": "tender",
             "chuck": "chuck", "blade": "blade", "shoulder": "shoulder", "arm": "arm", "rib": "rib", "ribeye": "ribeye", "loin": "loin", "sirloin": "sirloin", "tenderloin": "tenderloin", "strip": "strip",
             "round": "round", "rump": "rump", "eye": "eye", "brisket": "brisket", "flank": "flank", "shank": "shank", "crosscut": "shank", "plate": "plate", "chop": "chop", "steak": "steak",
             "ham": "ham", "belly": "belly", "hock": "hock", "butt": "butt", "picnic": "picnic", "liver": "liver", "heart": "heart", "kidney": "kidney", "tongue": "tongue", "giblet": "giblet",
             "gizzard": "gizzard", "tripe": "tripe", "brain": "brain", "tail": "tail", "neck": "neck", "foot": "foot", "feet": "foot", "organ": "giblet", "leaf": "leaf", "leave": "leaf", "green": "leaf",
             "root": "root", "stem": "stem", "stalk": "stalk", "seed": "seed", "flower": "flower", "floret": "floret", "peel": "peel", "zest": "zest", "rind": "rind", "bulb": "bulb", "pod": "pod",
             "kernel": "kernel", "pulp": "pulp", "head": "head", "sprout": "sprout", "yolk": "yolk", "white": "white", "fillet": "fillet", "filet": "fillet", "roe": "roe", "skin": "skin", "bone": "bone", "shell": "shell"}
EDIBLE_PART_FOODS = frozenset("pomegranate amaranth flaxseed sesame chia sunflower poppy pumpkin romaine lettuce artichoke palm celery".split())
INTERCHANGEABLE = [{"chuck", "blade", "shoulder", "arm"}, {"loin", "sirloin", "tenderloin", "strip", "chop", "steak"}, {"ham", "leg", "round"}, {"kernel", "seed"}, {"zest", "peel", "rind"}, {"stem", "stalk"}, {"floret", "flower", "head"}, {"giblet", "gizzard", "organ"}, {"fillet", "steak"}, {"thigh", "drumstick", "drum", "leg"}, {"wing", "flat", "drumette"}, {"shank", "hock"}, {"tip", "round", "rump", "eye"}]


def ancestors(n):
    out = [n]
    while n in PARENT:
        n = PARENT[n]
        out.append(n)
    return out


def tree_cost(a, b):
    if a == b:
        return 0.0
    for g in INTERCHANGEABLE:
        if a in g and b in g:
            return 0.3
    aa, bb = ancestors(a), ancestors(b)
    if a in bb or b in aa:
        return 0.4
    if PARENT.get(a) == PARENT.get(b):
        return 1.2
    ra, rb = aa[-1], bb[-1]
    ka, kb = ROOT_KIND.get(ra), ROOT_KIND.get(rb)
    if ka == kb == "flesh":
        return 2.4
    if "offal" in (ka, kb) and ka != kb:
        return 3.2
    if ka == kb == "plant":
        return 3.0
    return 3.4


AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla")
NOISE = frozenset(("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional "
                   "boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten "
                   "free range farmed wild mixed species commercial all strong brewed round meat by product added moist segment piece strip wedge chunk cube without salt fat fresh "
                   "raw whole delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat").split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})
BASE_ALT = ("soy", "almond", "oat", "coconut", "cashew", "vegan", "tofu")


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ").replace("tri-tip", "tip")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def part_nodes(tokens, core):
    nodes = []
    for t in tokens:
        n = WORD2NODE.get(t)
        if n and t not in core:
            nodes.append(n)
    return nodes


def part_cost(i_nodes, u_nodes, core, i_txt, u_txt):
    if set(core) & EDIBLE_PART_FOODS:
        i_nodes = [n for n in i_nodes if n not in ("seed", "heart", "head", "stem", "stalk")]
        u_nodes = [n for n in u_nodes if n not in ("seed", "heart", "head", "stem", "stalk")]
    if re.search(r"skin[- ]on|meat and skin", i_txt):
        i_nodes = i_nodes + ["skin"]
    if re.search(r"with skin|meat and skin", u_txt):
        u_nodes = u_nodes + ["skin"]
    i_nodes, u_nodes = list(dict.fromkeys(i_nodes)), list(dict.fromkeys(u_nodes))
    if not i_nodes and not u_nodes:
        return 0.0
    if i_nodes and u_nodes:
        # every ingredient part must find a relative in the USDA entry; take the mean of best matches
        costs = [min(tree_cost(a, b) for b in u_nodes) for a in i_nodes]
        return sum(costs) / len(costs) * (1.0 + 0.25 * (len(costs) - 1)) if max(costs) > 0.5 else 0.2 * max(costs)
    nodes = u_nodes or i_nodes
    only = [n for n in nodes if ROOT_KIND.get(ancestors(n)[-1]) in ("offal", "plant", "egg", "cover")]
    return 2.2 if only else 0.3


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
        i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
        u = re.sub(r"\([^)]*\)", " ", nb).lower()
        i_main = i.split(",")[0]
        imain = toks(i_main)
        segs = [toks(s) for s in u.split(",") if s.strip()]
        if not imain or not segs:
            return 0.0
        iset = set(toks(i))
        uflat = [t for s in segs for t in s]
        uset = set(uflat) | set(toks(par))
        core_all = [t for t in imain if t not in NOISE and not STATE_RX.match(t)] or [t for t in imain if t not in NOISE] or imain
        core = [t for t in core_all if t not in WORD2NODE] or core_all
        ub = uset | set(CULT.get(t, t) for t in uset)
        hits = [1.0 if (t in ub or CULT.get(t, t) in ub) else 0.0 for t in core]
        cov = sum(hits) / float(len(core))
        ident = 4.6 * cov + 2.0 * (1.0 if hits[-1] else -0.7)
        extras = [t for t in segs[0] if t not in core_all and t not in iset and t not in NOISE and not STATE_RX.match(t) and t not in WORD2NODE
                  and t not in ("fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal", "seaweed")]
        ident -= 0.5 * min(len(extras), 3)
        for base, vs in CULT_SETS.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                ident -= 2.2
        if len(core) >= 2 and has(r"\band\b", i_main) and not has(r"\band\b", u) and cov < 1.0:
            ident -= 1.4
        # base-alternative check: plant bases must agree
        b_i, b_u = set(b for b in BASE_ALT if b in iset), set(b for b in BASE_ALT if b in uset)
        if (b_u - b_i) or (b_i - b_u and not ({"vegan", "tofu"} & b_u)):
            ident -= 1.6
        i_nodes = part_nodes(imain + (toks(i.split(",", 1)[1]) if "," in i else []), core)
        u_nodes = part_nodes(uflat + toks(par), core)
        pc = part_cost(i_nodes, u_nodes, core, i, u)
        pen = 0.0
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = "giblet" in i_nodes or "liver" in i_nodes or "heart" in i_nodes or "kidney" in i_nodes or "tongue" in i_nodes or "organ" in uset
        for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                          (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                          (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                          (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                          (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                          (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
                          (r"\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced", 1.1), (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
                          (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2),
                          (r"\bkernel\b", r"kernel", 1.5), (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint", 1.1)]:
            if has(ru, u) and not has(ri, i):
                pen += w
        ic = has(r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b", i)
        uc = has(r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b", u)
        if uc and not ic and not has(r"\braw\b", u):
            pen += 2.1
        if ic and not uc:
            pen += 1.9 if has(r"toasted|roasted|grilled|fried", i) else 1.1
        di, du = has(r"\b(dried|dehydrated)\b", i) and not ic, has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}):
            pen += 2.3
        for w in ("pickled", "smoked"):
            if (w in i) != (w in u):
                pen += 2.3
        cn = has(r"\bcanned\b", u)
        if has(r"\bcanned\b", i) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            pen += 1.6
        if has(r"\b(ground|powdered|powder)\b", i) != has(r"\b(ground|powdered|powder)\b", u):
            pen += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
        if (set(segs[0]) & DISH) - iset - set(core):
            pen += 3.0
        if has(r"\bstew (meat|beef|lamb|pork)\b", i_main) and "stew" in segs[0]:
            pen += 3.0
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            pen += 2.4
        if has(r"\bbone[- ]in\b", i) and not has(r"\bbone\b", u):
            pen += 1.2
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            pen += 3.3
        return float(ident - 1.2 * pc - 0.9 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
