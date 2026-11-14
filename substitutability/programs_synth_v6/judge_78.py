import re
import math

# =============================================================================================
# Hypothesis-tournament judge. The ingredient phrase can be read in several ways; each reading is a
# hypothesis about WHAT FOOD is meant, with a built-in cost, and the best-supported hypothesis wins:
#   H_full   the whole noun phrase is one compound food (sweet potato, peanut butter)   cost 0
#   H_head   only the last word is the food, modifiers are decoration                  cost grows when
#            the (modifier, head) pair is a known compound (sweet potato != potato)
#   H_mod    the modifier is the food and the head is a product form (coconut + milk)  cost when the USDA
#            entry names the modifier food only (coconut -> 'Nuts, coconut meat') versus the product
# Support of a hypothesis = how well USDA tokens cover its required words (aliases, fuzzy, hierarchy).
# Entry-level qualifier / state penalties are applied once after the tournament.
# =============================================================================================

KNOWN = {("sweet", "potato"), ("sea", "bass"), ("bell", "pepper"), ("ice", "cream"), ("cream", "cheese"), ("sour", "cream"), ("cottage", "cheese"), ("green", "tea"), ("black", "tea"), ("pine", "nut"), ("brazil", "nut"),
         ("water", "chestnut"), ("butter", "bean"), ("lima", "bean"), ("kidney", "bean"), ("snow", "pea"), ("corn", "syrup"), ("maple", "syrup"), ("hot", "dog"), ("black", "pepper"), ("soy", "sauce"), ("fish", "sauce"),
         ("brown", "sugar"), ("coconut", "sugar"), ("cocoa", "butter"), ("peanut", "butter"), ("almond", "butter"), ("pecan", "butter"), ("apple", "butter"), ("coconut", "milk"), ("almond", "milk"), ("soy", "milk"),
         ("oat", "milk"), ("rice", "milk"), ("coconut", "cream"), ("coconut", "oil"), ("olive", "oil"), ("sesame", "oil"), ("palm", "oil"), ("sunflower", "oil"), ("peanut", "oil"), ("apple", "juice"), ("orange", "juice"),
         ("tomato", "juice"), ("lemon", "juice"), ("plum", "sauce"), ("apple", "sauce"), ("tomato", "sauce"), ("tomato", "paste"), ("garlic", "paste"), ("egg", "white"), ("egg", "yolk"), ("whole", "wheat"), ("sweet", "corn"),
         ("green", "onion"), ("spring", "onion"), ("red", "wine"), ("white", "wine"), ("rice", "vinegar"), ("wine", "vinegar"), ("cider", "vinegar"), ("balsamic", "vinegar"), ("sweet", "pepper"), ("chicken", "ham"),
         ("pork", "sausage"), ("beef", "stew"), ("ground", "beef"), ("hot", "sauce"), ("corn", "bread"), ("pita", "bread"), ("rye", "bread"), ("bean", "sprout"), ("alfalfa", "sprout")}
PRODUCT_FORMS = frozenset("milk butter oil juice sauce paste cream syrup sugar vinegar flour bread cake cookie pie soup jam jelly powder extract starch noodle sausage ham stew wine dressing".split())
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pine", pinon="pine",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
NOISE = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed".split())
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


def has(rx, s):
    return bool(re.search(rx, s))


def support(words, pool, par):
    if not words:
        return 0.0
    got = 0.0
    for w in words:
        if w in pool or CULT.get(w, w) in pool:
            got += 1.0
        elif w in par:
            got += 0.8
    return got / len(words)


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
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
            return 0.0
        iset = set(toks(i)) | par_i
        uflat = [t for s in segs for t in s]
        uset = set(uflat)
        ub = uset | set(CULT.get(t, t) for t in uset)
        core = [t for t in main if t not in NOISE and t not in QUAL] or [t for t in main if t not in QUAL] or main
        head = core[-1]
        mods = core[:-1]
        # ---------------------------------------------------------------- hypotheses
        hyps = []
        # H_full : all core words must be present; compound words are required adjacent-or-reversed
        full_sup = support(core, ub, par_u)
        hyps.append(("full", full_sup, 0.0))
        # H_head : head only; costs 3.0 when (mod, head) is a known compound, 0.6 for other modifiers
        cost_head = 0.0
        for m in mods:
            cost_head += 3.0 if (m, head) in KNOWN else 0.8
        hyps.append(("head", support([head], ub, par_u), cost_head))
        # H_mod : the modifier names the food and head is a product form
        if mods and head in PRODUCT_FORMS:
            m = mods[-1]
            sup_m = support([m], ub, par_u)
            product_present = head in ub
            cost_mod = 0.0 if product_present else 2.4
            hyps.append(("mod", sup_m, cost_mod + (0.0 if (m, head) not in KNOWN else 1.2)))
        # hypothesis score: support in [0,1] -> 0..7 minus cost; add head/gate terms
        best = -99.0
        best_name = "full"
        for name, sup, cost in hyps:
            sc = 7.0 * sup - cost
            if name == "full" and sup >= 0.99:
                sc += 0.8
            if sc > best:
                best, best_name = sc, name
        # compound "added" check: USDA names a known compound that the ingredient lacks (potato -> Sweet potato)
        added = 0.0
        for seg in segs:
            for a, b in zip(seg, seg[1:]):
                if (a, b) in KNOWN and (a not in iset or b not in iset):
                    added += 2.6
            for (a, b) in KNOWN:
                if a in seg and b in seg and a not in iset and b in iset:
                    added += 1.8
        added = min(added, 4.0)
        # product-form head: ingredient head 'butter' must not match only a different butter (cocoa/peanut)
        best += 1.6 if head in ub else -1.4
        extras = [t for t in segs[0] if t not in core and t not in iset and t not in NOISE and t not in QUAL and t not in CATEGORY]
        best -= 0.5 * min(len(extras), 3)
        for base, vs in TYPE_SETS.items():
            named = vs & iset
            if named and (base in uset or base in ("dressing", "cheese")) and not (named & uset) and (vs & uset):
                best -= 2.0
        ia, ua = set(x for x in BASEALT if x in iset), set(x for x in BASEALT if x in uset)
        if (ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua)):
            best -= 1.6
        # ---------------------------------------------------------------- entry-level penalties
        full_i = i + " " + " ".join(par_i)
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = "organ" in uset or bool(set(core) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard"})
        pen = 0.0
        for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                          (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                          (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                          (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                          (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1),
                          (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2), (r"\bkernel\b", r"kernel", 1.5)]:
            if has(ru, u) and not has(ri, full_i):
                pen += w
        if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, full_i)]:
            pen += 1.1
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = has(cook, full_i), has(cook, u)
        if uc and not ic and not has(r"\braw\b", u):
            pen += 2.0
        if ic and not uc:
            pen += 1.8 if has(r"toasted|roasted|grilled|fried", full_i) else 1.0
        di = has(r"\b(dried|dehydrated)\b", full_i) and not ic
        du = has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        if di != du and not (du and set(core) & DRIED_OK):
            pen += 2.2
        for w in ("pickled", "smoked"):
            if (w in full_i) != (w in u):
                pen += 2.2
        cn = has(r"\bcanned\b", u)
        if has(r"\bcanned\b", full_i) != cn and not (cn and set(core) & CANNED_OK):
            pen += 1.5
        if has(r"\b(ground|powdered|powder)\b", full_i) != has(r"\b(ground|powdered|powder)\b", u):
            pen += 1.7
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", full_i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)):
            pen += 2.4
        if (set(segs[0]) & DISH) - iset - set(core):
            pen += 2.8
        if has(r"\bstew (meat|beef|lamb|pork)\b", full_i) and "stew" in segs[0]:
            pen += 2.8
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            pen += 2.2
        if has(r"\bbone[- ]in\b", full_i) and not has(r"\bbone\b", u):
            pen += 1.0
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            pen += 3.0
        if len(core) >= 2 and has(r"\band\b", i.split(",")[0]) and not has(r"\band\b", u) and full_sup < 1.0:
            pen += 1.4
        return float(best - added - 0.9 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
