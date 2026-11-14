import re

# =============================================================================================
# Compound-name integrity judge. A compound is a (modifier, head) pair in which the modifier changes
# the food: sweet potato, coconut milk, peanut butter, cocoa butter, sea bass, bell pepper, ice cream,
# apple juice, plum sauce. Compounds come from (1) a lexicon of fixed compounds and (2) a generic
# rule: FOOD-NOUN + PRODUCT-NOUN adjacent words. Integrity asks:
#   * every ingredient compound must reappear in the USDA entry (adjacent, comma-reversed, or
#     within the first two segments such as "Oil, cocoa butter"), otherwise it is BROKEN
#   * a USDA compound the ingredient does not contain is an ADDED modifier (potato -> Sweet potato)
# The rest of the score is a plain feature-weight sum (named features, linear weights).
# =============================================================================================

FIXED_COMPOUNDS = [("sweet", "potato"), ("sea", "bass"), ("bell", "pepper"), ("ice", "cream"), ("cream", "cheese"), ("sour", "cream"), ("cottage", "cheese"), ("green", "tea"), ("black", "tea"),
                   ("pine", "nut"), ("brazil", "nut"), ("water", "chestnut"), ("butter", "bean"), ("lima", "bean"), ("kidney", "bean"), ("snow", "pea"), ("sugar", "snap"), ("corn", "syrup"), ("maple", "syrup"),
                   ("hot", "dog"), ("black", "pepper"), ("soy", "sauce"), ("fish", "sauce"), ("hot", "sauce"), ("baking", "soda"), ("baking", "powder"), ("brown", "sugar"), ("powdered", "sugar"), ("coconut", "sugar"),
                   ("cocoa", "butter"), ("peanut", "butter"), ("almond", "butter"), ("pecan", "butter"), ("apple", "butter"), ("coconut", "milk"), ("almond", "milk"), ("soy", "milk"), ("oat", "milk"), ("rice", "milk"),
                   ("coconut", "cream"), ("coconut", "oil"), ("olive", "oil"), ("sesame", "oil"), ("palm", "oil"), ("palm", "kernel"), ("sunflower", "oil"), ("peanut", "oil"), ("apple", "juice"), ("orange", "juice"),
                   ("tomato", "juice"), ("lemon", "juice"), ("plum", "sauce"), ("apple", "sauce"), ("tomato", "sauce"), ("tomato", "paste"), ("garlic", "paste"), ("fish", "stick"), ("egg", "white"), ("egg", "yolk"),
                   ("cream", "of", "coconut"), ("half", "and", "half"), ("whole", "wheat"), ("sweet", "corn"), ("pearl", "onion"), ("green", "onion"), ("spring", "onion"), ("red", "wine"), ("white", "wine"), ("rice", "vinegar"),
                   ("wine", "vinegar"), ("cider", "vinegar"), ("balsamic", "vinegar"), ("sour", "dough"), ("pot", "roast"), ("hash", "brown"), ("french", "fry"), ("peanut", "brittle"), ("sweet", "pepper")]
FOOD_MODIFIERS = frozenset("sweet sea bell ice cream sour cottage green black pine brazil water butter lima kidney snow corn maple soy fish baking brown powdered coconut cocoa peanut almond pecan apple oat rice palm sunflower olive sesame orange tomato lemon plum garlic egg wheat pearl spring red white wine cider balsamic pot hash french vanilla chocolate strawberry cherry banana honey hazelnut walnut cashew pistachio pumpkin mushroom bean pea potato onion carrot beet turnip squash".split())
PRODUCT_NOUNS = frozenset("milk butter oil juice sauce paste cream cheese yogurt syrup sugar vinegar flour bread cake cookie pie soup jam jelly powder extract starch noodle pasta rice bean pea nut seed leaf root chip".split())
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pine", pinon="pine",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
NOISE = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
QUAL = frozenset("raw cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted fried dried canned frozen smoked pickled cured ground powdered lowfat nonfat reduced light skim sweetened unsweetened unsalted salted decaffeinated lean".split())
CATEGORY = frozenset("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed".split())
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
DRIED_OK = frozenset("pine brazil hazelnut raisin fig date apricot prune agar seaweed mushroom".split())
CANNED_OK = frozenset("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine".split())
BASEALT = ("soy", "almond", "oat", "coconut", "cashew", "vegan", "tofu")
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
TYPE_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"},
                 dressing={"italian", "french", "ranch", "caesar", "thousand", "greek", "russian"}, cheese={"cheddar", "swiss", "mozzarella", "provolone", "brie", "camembert", "gouda", "colby", "parmesan"})


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


def compounds_of(token_segments):
    """set of compounds as frozensets of their words: fixed lexicon matches and generic noun-noun adjacency."""
    found = set()
    flat = [t for s in token_segments for t in s]
    pool = set(flat)
    for comp in FIXED_COMPOUNDS:
        if all(w in pool for w in comp):
            # adjacency inside a segment (any order) or across the first two segments
            ok = False
            for s in token_segments:
                if all(w in s for w in comp):
                    ok = True
            if not ok and len(token_segments) >= 2:
                head2 = set(token_segments[0]) | set(token_segments[1])
                ok = all(w in head2 for w in comp)
            if ok:
                found.add(frozenset(comp))
    for s in token_segments:
        for a, b in zip(s, s[1:]):
            if a in FOOD_MODIFIERS and b in PRODUCT_NOUNS and a != b:
                found.add(frozenset((a, b)))
    return found


def has(rx, s):
    return bool(re.search(rx, s))


def features(ingredient, usda):
    f = {}
    raw = " ".join(str(usda or "").split())
    keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
    nb = " ".join(keep)
    par_u = set(toks(" ".join(re.findall(r"\(([^)]*)\)", nb)).lower()))
    u = re.sub(r"\([^)]*\)", " ", nb).lower()
    i_all = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower())
    par_i = set(toks(" ".join(re.findall(r"\(([^)]*)\)", i_all))))
    i = re.sub(r"\([^)]*\)", " ", i_all)
    main = toks(i.split(",")[0])
    segs = [toks(s) for s in u.split(",") if s.strip()]
    if not main or not segs:
        return None
    iset = set(toks(i)) | par_i
    uflat = [t for s in segs for t in s]
    uset = set(uflat) | par_u
    ub = uset | set(CULT.get(t, t) for t in uset)
    core = [t for t in main if t not in NOISE and t not in QUAL or t in PRODUCT_NOUNS] or [t for t in main if t not in QUAL] or main
    hits = [1.0 if (t in ub or CULT.get(t, t) in ub) else 0.0 for t in core]
    f["cov"] = sum(hits) / float(len(core))
    f["head"] = hits[-1]
    f["head_alias"] = 1.0 if (hits[-1] == 0.0 and (core[-1] in par_u or (par_i & uset))) else 0.0
    i_comps = compounds_of([main])
    u_comps = compounds_of(segs)
    broken = [c for c in i_comps if c not in u_comps and not all(w in uset for w in c)]
    half = [c for c in i_comps if c not in u_comps and all(w in uset for w in c)]   # words present but not adjacent
    added = [c for c in u_comps if c not in i_comps and not (c <= iset)]
    f["compound_intact"] = 1.0 if (i_comps and not broken and not half) else 0.0
    f["compound_scattered"] = float(len(half))
    f["compound_broken"] = float(min(len(broken), 2))
    f["compound_added"] = float(min(len(added), 2))
    f["compound_none"] = 1.0 if not i_comps and not u_comps else 0.0
    extras = [t for t in segs[0] if t not in core and t not in iset and t not in NOISE and t not in QUAL and t not in CATEGORY]
    f["extra_first"] = float(min(len(extras), 3))
    type_conf = 0.0
    for base, vs in TYPE_SETS.items():
        named = vs & iset
        if named and (base in uset or base in ("dressing", "cheese")) and not (named & uset) and (vs & uset):
            type_conf = 1.0
    f["type_conflict"] = type_conf
    ia, ua = set(x for x in BASEALT if x in iset), set(x for x in BASEALT if x in uset)
    f["base_alt"] = 1.0 if ((ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua))) else 0.0
    full_i = i + " " + " ".join(par_i)
    soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
    organ = "organ" in uset or bool(set(core) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard"})
    q = 0.0
    for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                      (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                      (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                      (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                      (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1),
                      (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2), (r"\bkernel\b", r"kernel", 1.5)]:
        if has(ru, u) and not has(ri, full_i):
            q += w
    if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, full_i)]:
        q += 1.1
    f["unstated_quals"] = min(q, 7.0)
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = has(cook, full_i), has(cook, u)
    f["cook_usda_only"] = 1.0 if (uc and not ic and not has(r"\braw\b", u)) else 0.0
    f["cook_ing_only"] = (1.8 if has(r"toasted|roasted|grilled|fried", full_i) else 1.0) if (ic and not uc) else 0.0
    di = has(r"\b(dried|dehydrated)\b", full_i) and not ic
    du = has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
    f["dried_mismatch"] = 1.0 if (di != du and not (du and set(core) & DRIED_OK)) else 0.0
    f["pickle_smoke"] = float(sum(1 for w in ("pickled", "smoked") if (w in full_i) != (w in u)))
    cn = has(r"\bcanned\b", u)
    f["canned_mismatch"] = 1.0 if (has(r"\bcanned\b", full_i) != cn and not (cn and set(core) & CANNED_OK)) else 0.0
    f["ground_mismatch"] = 1.0 if (has(r"\b(ground|powdered|powder)\b", full_i) != has(r"\b(ground|powdered|powder)\b", u)) else 0.0
    f["part_mismatch"] = 1.0 if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", full_i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)) else 0.0
    f["dish_noun"] = 1.0 if ((set(segs[0]) & DISH) - iset - set(core)) else 0.0
    f["stew_idiom"] = 1.0 if (has(r"\bstew (meat|beef|lamb|pork)\b", full_i) and "stew" in segs[0]) else 0.0
    f["front_state"] = 1.0 if (segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset) else 0.0
    f["bone_in_dropped"] = 1.0 if (has(r"\bbone[- ]in\b", full_i) and not has(r"\bbone\b", u)) else 0.0
    f["restaurant"] = 1.0 if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u) else 0.0
    f["compound_and"] = 1.0 if (len(core) >= 2 and has(r"\band\b", i.split(",")[0]) and not has(r"\band\b", u) and f["cov"] < 1.0) else 0.0
    return f


WEIGHTS = {"cov": 4.6, "head": 2.0, "head_alias": 1.6, "compound_intact": 1.8, "compound_scattered": -1.5, "compound_broken": -3.0, "compound_added": -2.6, "compound_none": 0.0,
           "extra_first": -0.5, "type_conflict": -2.0, "base_alt": -1.6, "unstated_quals": -0.9, "cook_usda_only": -2.0, "cook_ing_only": -1.0, "dried_mismatch": -2.2, "pickle_smoke": -2.2,
           "canned_mismatch": -1.5, "ground_mismatch": -1.7, "part_mismatch": -2.4, "dish_noun": -2.8, "stew_idiom": -2.8, "front_state": -2.2, "bone_in_dropped": -1.0, "restaurant": -3.0, "compound_and": -1.4}


def judging_function(ingredient, usda_match):
    try:
        f = features(ingredient, usda_match)
        if f is None:
            return 0.0
        total = 2.0 - 1.6 * (1.0 - f["head"]) * (1.0 - f["head_alias"])
        for k, w in WEIGHTS.items():
            total += w * f.get(k, 0.0)
        return float(total)
    except Exception:
        return 0.0
