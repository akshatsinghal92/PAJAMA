import re

# ===========================================================================================
# Detail-ledger judge. The WHOLE ingredient string (main phrase, post-comma text and parentheses,
# minus gram weights and recipe notes) is cut into detail units. Each unit is typed
# (food / variety / form / state / flavour / part / diet / note) and weighted. Units are then
# settled against the USDA entry: COVERED (same word or an equivalent), CONTRADICTED (an opposite
# value present) or UNCOVERED. The score is the covered weight share, minus contradictions and
# uncovered material qualifiers, minus unstated USDA qualifiers.
# ===========================================================================================

NOTE_RX = re.compile(r"\b(optional|to taste|for garnish|for serving|for decoration|for dusting|as needed|divided|plus more|about|approximately|or more|if desired|if needed|fresh or frozen|room temperature|at room temp|store[- ]bought|homemade)\b")
UNIT_WEIGHT = {"food": 3.0, "variety": 1.6, "form": 1.4, "state": 1.6, "flavour": 1.5, "part": 1.8, "diet": 1.4, "size": 0.2}
FORM_WORDS = frozenset("whole ground powdered flaked sliced shredded chunk crumbled crumble minced paste puree juice wedge ring round strip stick".split())
STATE_EQ = [frozenset("cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed heat toasted".split()), frozenset(["dried", "dehydrated"]), frozenset(["raw", "fresh", "uncooked", "unheated", "unroasted"]),
            frozenset(["canned", "jarred", "bottled", "drained"]), frozenset(["smoked", "cured"]), frozenset(["pickled", "brined"]), frozenset(["fried", "battered", "breaded"]), frozenset(["frozen", "thawed"])]
STATE_WORDS = frozenset().union(*STATE_EQ)
DIET_WORDS = frozenset("lowfat nonfat reduced light lite skim sweetened unsweetened unsalted salted lean decaffeinated sugar-free".split())
FLAVOURS = frozenset("vanilla chocolate strawberry peach blueberry raspberry banana cinnamon maple caramel honey lemon cherry mint coconut mocha pumpkin butter garlic".split())
PART_WORDS = frozenset("leaf leave root stem seed bone skin peel zest yolk white liver heart kidney tongue giblet neck wing thigh breast drumstick shank".split())
SIZE_WORDS = frozenset("large small medium big baby mini jumbo thin thick fine coarse".split())
VARIETY_WORDS = frozenset("concord bing fuji gala granny bartlett russet yukon roma navel valencia hass portobello cremini shiitake butternut acorn italian greek mexican swiss dutch french wild sweet".split())
OPPOSITE = [({"cooked", "boiled", "baked", "roasted", "steamed", "simmered", "braised", "broiled", "grilled", "sauteed", "poached", "stewed", "heat", "toasted", "fried"}, {"raw", "uncooked", "unheated", "unroasted"}), ({"dried", "dehydrated"}, {"fresh", "raw", "canned"}),
            ({"salted"}, {"unsalted"}), ({"sweetened"}, {"unsweetened"}), ({"whole"}, {"ground", "powdered", "minced"}), ({"frozen"}, {"fresh"})]
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
STOP = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
CULT_BASE = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def classify(w, head_zone):
    if w in STATE_WORDS:
        return "state"
    if w in DIET_WORDS:
        return "diet"
    if w in FLAVOURS:
        return "flavour"
    if w in PART_WORDS:
        return "part"
    if w in FORM_WORDS:
        return "form"
    if w in SIZE_WORDS:
        return "size"
    if w in VARIETY_WORDS:
        return "variety"
    return "food"


def equivalent(w, pool):
    if w in pool:
        return True
    for grp in STATE_EQ:
        if w in grp and (grp & pool):
            return True
    if w in CULT_BASE and CULT_BASE[w] in pool:
        return True
    return False


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        par_u = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
        u = re.sub(r"\([^)]*\)", " ", nb).lower()
        # ingredient: whole string, notes removed, gram weight removed, parentheses kept
        i_full = str(ingredient or "").lower()
        i_full = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_full)
        i_full = NOTE_RX.sub(" ", i_full)
        i_full = re.sub(r"\(\s*\)", " ", i_full)
        i_main_txt = i_full.split(",")[0]
        main = toks(re.sub(r"[()]", " ", i_main_txt))
        full = toks(re.sub(r"[()]", " ", i_full))
        segs = [toks(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        uflat = [t for s in segs for t in s]
        uset = set(uflat) | set(toks(par_u))
        iset = set(full)
        ub = uset | set(CULT_BASE.get(t, t) for t in uset)
        # ---------------- build the detail units
        units = []
        seen = set()
        head_idx = None
        for k, w in enumerate(full):
            if w in STOP or w in seen:
                continue
            seen.add(w)
            typ = classify(w, k < len(main))
            units.append((w, typ, k < len(main)))
        if not units:
            units = [(w, "food", True) for w in main]
        food_units = [x for x in units if x[1] == "food"]
        # ---------------- settle each unit
        covered = 0.0
        total = 0.0
        uncovered_mat = 0.0
        contradiction = 0.0
        for w, typ, in_main in units:
            wt = UNIT_WEIGHT[typ] * (1.0 if in_main else 0.7)
            total += wt
            if equivalent(w, ub) or (w in CULT_BASE and CULT_BASE[w] in ub):
                covered += wt
                continue
            # contradiction: USDA states an opposite value of this unit
            contra = False
            for a_set, b_set in OPPOSITE:
                if (w in a_set and (b_set & uset)) or (w in b_set and (a_set & uset)):
                    contra = True
            if contra:
                contradiction += wt
            elif typ in ("state", "variety", "part", "flavour", "diet") and in_main:
                uncovered_mat += wt
            elif typ in ("state", "variety", "part", "flavour", "diet", "form"):
                uncovered_mat += 0.5 * wt
        share = covered / total if total else 0.0
        head = food_units[-1][0] if food_units else main[-1]
        head_hit = equivalent(head, ub)
        score = 6.0 * share + (1.8 if head_hit else -1.6) - 1.3 * min(contradiction, 4.0) - 0.9 * min(uncovered_mat, 4.0)
        # variety conflict
        for base, vs in CULT_SETS.items():
            named = vs & iset
            if named and base in uset and not (named & uset) and (vs & uset):
                score -= 2.0
        # ---------------- unstated USDA qualifiers (reverse direction)
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = has(r"variety meat|organ", u) or bool(iset & {"liver", "heart", "kidney", "tongue", "giblet"})
        qcost = 0.0
        full_txt = i_full
        for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                          (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                          (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                          (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                          (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                          (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
                          (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1), (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
                          (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2),
                          (r"\bkernel\b", r"kernel", 1.5)]:
            if has(ru, u) and not has(ri, full_txt):
                qcost += w
        flav_u = [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, full_txt)]
        if flav_u:
            qcost += 1.1
        score -= 0.9 * min(qcost, 8.0)
        # ---------------- state / form events beyond the ledger
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = has(cook, full_txt), has(cook, u)
        if uc and not ic and not has(r"\braw\b", u):
            score -= 1.9
        di = has(r"\b(dried|dehydrated)\b", full_txt) and not ic
        du = has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        if di != du and not (du and iset & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}):
            score -= 2.1
        for w in ("pickled", "smoked"):
            if (w in full_txt) != (w in u):
                score -= 2.1
        cn = has(r"\bcanned\b", u)
        if has(r"\bcanned\b", full_txt) != cn and not (cn and iset & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            score -= 1.4
        if has(r"\b(ground|powdered|powder)\b", full_txt) != has(r"\b(ground|powdered|powder)\b", u):
            score -= 1.7
        if (set(segs[0]) & DISH) - iset:
            score -= 2.7
        if has(r"\bstew (meat|beef|lamb|pork)\b", full_txt) and "stew" in segs[0]:
            score -= 2.7
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            score -= 2.2
        if has(r"\bbone[- ]in\b", full_txt) and not has(r"\bbone\b", u):
            score -= 1.1
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score + 2.0)
    except Exception:
        return 0.0
