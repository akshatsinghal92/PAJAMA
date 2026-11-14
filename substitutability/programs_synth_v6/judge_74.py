import re

# =============================================================================================
# Decision-list judge. Facts about the pair are computed once; then an ORDERED list of rules is
# scanned and the FIRST rule whose guard fires returns the score band (+ a continuous refinement).
# Detail coverage uses the whole ingredient string, but only qualifier words from a lexicon and
# the last food word are mandatory; parenthetical text is an alias source, never a requirement.
# =============================================================================================

NOTES = re.compile(r"\b(optional|to taste|for garnish|for serving|for decoration|for dusting|as needed|divided|plus more|about|approximately|or more|if desired|if needed|room temperature)\b")
QUAL_LEX = {
    "state": ["raw", "cooked", "boiled", "baked", "roasted", "steamed", "simmered", "braised", "broiled", "grilled", "sauteed", "poached", "stewed", "toasted", "fried", "dried", "dehydrated", "canned", "frozen", "smoked", "pickled", "cured"],
    "form": ["ground", "powdered", "whole", "flaked", "crumbled", "paste", "puree", "juice"],
    "diet": ["lowfat", "nonfat", "reduced", "light", "skim", "sweetened", "unsweetened", "unsalted", "salted", "decaffeinated", "lean"],
    "flavour": ["vanilla", "chocolate", "strawberry", "peach", "blueberry", "raspberry", "banana", "cinnamon", "maple", "lemon", "cherry", "mint", "coconut", "garlic", "butter"],
    "variety": ["concord", "bing", "fuji", "gala", "bartlett", "russet", "roma", "navel", "hass", "butternut", "italian", "greek", "mexican", "dutch"],
}
LEX = {w: k for k, ws in QUAL_LEX.items() for w in ws}
STATE_GROUP = {}
for gi, grp in enumerate([("cooked", "boiled", "baked", "roasted", "steamed", "simmered", "braised", "broiled", "grilled", "sauteed", "poached", "stewed", "toasted", "heat"), ("dried", "dehydrated"), ("raw", "fresh", "uncooked", "unheated"), ("canned", "jarred", "drained"), ("smoked", "cured"), ("pickled", "brined"), ("fried", "battered", "breaded"), ("frozen", "thawed")]):
    for w in grp:
        STATE_GROUP[w] = gi
OPP_PAIRS = [({"raw", "fresh", "uncooked", "unheated"}, {"cooked", "boiled", "baked", "roasted", "steamed", "simmered", "braised", "broiled", "grilled", "sauteed", "poached", "stewed", "heat", "fried"}), ({"dried", "dehydrated"}, {"raw", "fresh"}),
             ({"salted"}, {"unsalted"}), ({"sweetened"}, {"unsweetened"}), ({"whole"}, {"ground", "powdered"})]
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
CULT_BASE = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})
NOISE = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat round steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed".split())
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
ORGANS = frozenset("liver kidney tongue heart giblet tripe brain gizzard organ".split())
DRIED_OK = frozenset("pinenut brazil hazelnut raisin fig date apricot prune agar seaweed mushroom".split())
CANNED_OK = frozenset("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine".split())


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


def has(rx, s):
    return bool(re.search(rx, s))


def facts(ingredient, usda):
    f = {}
    raw = " ".join(str(usda or "").split())
    keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
    nb = " ".join(keep)
    par_u = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
    u = re.sub(r"\([^)]*\)", " ", nb).lower()
    i_full = NOTES.sub(" ", re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower()))
    par_i = " ".join(re.findall(r"\(([^)]*)\)", i_full))
    i_noparen = re.sub(r"\([^)]*\)", " ", i_full)
    f.update(u=u, i_full=i_noparen, par_i=par_i)
    f["main"] = toks(i_noparen.split(",")[0])
    f["tail"] = toks(",".join(i_noparen.split(",")[1:]))
    f["segs"] = [toks(s) for s in u.split(",") if s.strip()]
    f["ok"] = bool(f["main"] and f["segs"])
    if not f["ok"]:
        return f
    f["uflat"] = [t for s in f["segs"] for t in s]
    f["uset"] = set(f["uflat"]) | set(toks(par_u))
    f["iset"] = set(f["main"]) | set(f["tail"]) | set(toks(par_i))
    core = [t for t in f["main"] if t not in NOISE and t not in LEX] or [t for t in f["main"] if t not in LEX] or f["main"]
    f["core"] = core
    ub = f["uset"] | set(CULT_BASE.get(t, t) for t in f["uset"])
    hits = [1.0 if (t in ub or CULT_BASE.get(t, t) in ub) else 0.0 for t in core]
    f["cov"] = sum(hits) / float(len(core))
    f["head"] = hits[-1]
    # alias in parentheses on the ingredient side: if the parenthetical word names the USDA food, the head is covered
    f["alias_hit"] = bool(set(toks(par_i)) & f["uset"]) and f["head"] == 0.0
    # lexicon qualifiers of the whole ingredient: covered / contradicted / missing
    qs = [t for t in dict.fromkeys(f["main"] + f["tail"]) if t in LEX]
    cov_q, contra_q, miss_q = 0, 0, 0
    for t in qs:
        kind = LEX[t]
        gi = STATE_GROUP.get(t)
        if t in f["uset"] or (gi is not None and any(STATE_GROUP.get(x) == gi for x in f["uset"])):
            cov_q += 1
        elif any((t in a and (b & f["uset"])) or (t in b and (a & f["uset"])) for a, b in OPP_PAIRS):
            contra_q += 1
        else:
            miss_q += 1 if kind in ("state", "diet", "flavour", "variety") else 0
    f["qn"] = (cov_q, contra_q, miss_q)
    return f


def unstated_cost(f):
    u, i = f["u"], f["i_full"] + " " + f["par_i"]
    soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
    organ = bool(set(f["core"]) & ORGANS) or "organ" in f["uset"]
    cost = 0.0
    for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                      (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                      (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                      (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                      (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1),
                      (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2), (r"\bkernel\b", r"kernel", 1.5)]:
        if has(ru, u) and not has(ri, i):
            cost += w
    if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, i)]:
        cost += 1.1
    return cost


def state_cost(f):
    u, i = f["u"], f["i_full"]
    core = set(f["core"])
    cost = 0.0
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = has(cook, i), has(cook, u)
    if uc and not ic and not has(r"\braw\b", u):
        cost += 2.0
    if ic and not uc:
        cost += 1.8 if has(r"toasted|roasted|grilled|fried", i) else 1.0
    di = has(r"\b(dried|dehydrated)\b", i) and not ic
    du = has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
    if di != du and not (du and core & DRIED_OK):
        cost += 2.2
    for w in ("pickled", "smoked"):
        if (w in i) != (w in u):
            cost += 2.2
    cn = has(r"\bcanned\b", u)
    if has(r"\bcanned\b", i) != cn and not (cn and core & CANNED_OK):
        cost += 1.5
    if has(r"\b(ground|powdered|powder)\b", i) != has(r"\b(ground|powdered|powder)\b", u):
        cost += 1.8
    if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)):
        cost += 2.4
    return cost


def judging_function(ingredient, usda_match):
    try:
        f = facts(ingredient, usda_match)
        if not f["ok"]:
            return 0.0
        u, i = f["u"], f["i_full"]
        segs, core = f["segs"], f["core"]
        cov_q, contra_q, miss_q = f["qn"]
        refine = 0.6 * f["cov"] + 0.2 * f["head"] + 0.05 * cov_q - 0.03 * len(segs)
        # ---- rule 1: restaurant / brand-less dish nouns => reject
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            return float(0.5 + refine)
        # ---- rule 2: head absent and no alias => reject
        if f["head"] == 0.0 and not f["alias_hit"]:
            return float(1.5 + 2.0 * refine)
        # ---- rule 3: USDA entry is another product form of the food
        if (set(segs[0]) & DISH) - f["iset"] - set(core) and not (has(r"\bstew (meat|beef|lamb|pork)\b", i) is False and False):
            return float(2.2 + refine)
        if has(r"\bstew (meat|beef|lamb|pork)\b", i) and "stew" in segs[0]:
            return float(2.4 + refine)
        # ---- rule 4: contradicted qualifier => strong reject
        if contra_q:
            return float(2.8 - 0.4 * (contra_q - 1) + refine)
        # ---- rule 5: cultivar conflict
        for base, vs in CULT_SETS.items():
            named = vs & f["iset"]
            if named and base in f["uset"] and not (named & f["uset"]) and (vs & f["uset"]):
                return float(3.0 + refine)
        # ---- rule 6: front state / part mismatches
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in f["iset"]:
            return float(3.2 + refine)
        # ---- rule 7: graded band with all remaining costs
        cost = unstated_cost(f) + state_cost(f)
        miss_pen = 0.9 * miss_q
        extras = [t for t in segs[0] if t not in core and t not in f["iset"] and t not in NOISE and t not in LEX and t not in ("fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal", "seaweed")]
        extra_pen = 0.5 * min(len(extras), 3)
        part_pen = 0.0
        if has(r"\bbone[- ]in\b", i) and not has(r"\bbone\b", u):
            part_pen += 1.1
        if len(core) >= 2 and has(r"\band\b", i.split(",")[0]) and not has(r"\band\b", u) and f["cov"] < 1.0:
            part_pen += 1.4
        band = 9.0 if f["cov"] >= 0.99 else 6.2 + 2.6 * f["cov"]
        score = band - 0.9 * min(cost, 8.0) - miss_pen - extra_pen - part_pen
        return float(score + refine)
    except Exception:
        return 0.0
