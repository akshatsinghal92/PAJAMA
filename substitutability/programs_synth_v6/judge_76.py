import re
import math

# =============================================================================================
# Bidirectional explanation F-measure judge.
#   RECALL    : how much of the ingredient's weighted detail the USDA entry explains
#   PRECISION : how much of the USDA entry's weighted content the ingredient explains
# Token weights depend on class (head food, other food, lexicon qualifier, unknown modifier) and
# on position (USDA first segment counts fully, hierarchy tail words 0.3 unless they are
# qualifiers). The weighted F1 is multiplied by exp(-penalty) for contradictions, state/method
# mismatches and form changes.
# =============================================================================================

NOTE_WORDS = re.compile(r"\b(optional|to taste|for garnish|for serving|for decoration|for dusting|as needed|divided|plus more|about|approximately|or more|if desired|if needed|room temperature)\b")
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
TYPE_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"},
                 dressing={"italian", "french", "ranch", "caesar", "thousand", "greek", "russian"}, cheese={"cheddar", "swiss", "mozzarella", "provolone", "brie", "camembert", "gouda", "colby", "parmesan"})
QUALIFIERS = frozenset(("raw cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted fried dried canned frozen smoked pickled cured ground powdered whole flaked crumbled "
                        "lowfat nonfat reduced light skim sweetened unsweetened unsalted salted decaffeinated lean vanilla chocolate strawberry peach blueberry raspberry banana cinnamon maple lemon cherry mint garlic").split())
STATE_GROUPS = [set("cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted heat".split()), {"dried"}, {"raw", "fresh", "unheated"}, {"canned", "drained", "jarred"}, {"smoked", "cured"}, {"pickled", "brined"}, {"fried", "battered", "breaded"}, {"frozen", "thawed"}]
NEUTRAL = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat round steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed fresh lump granulated".split())
CATEGORY = frozenset("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed".split())
HEAD_NOUNS = frozenset("butter sugar oil paste flour milk cream juice syrup sauce vinegar yogurt powder extract starch meal bread".split())
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
DRIED_OK = frozenset("pinenut brazil hazelnut raisin fig date apricot prune agar seaweed mushroom".split())
CANNED_OK = frozenset("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine".split())
BASEALT = ("soy", "almond", "oat", "coconut", "cashew", "vegan", "tofu")
OPP = [({"raw", "fresh", "unheated"}, set("cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed heat fried".split())), ({"dried"}, {"raw", "fresh"}), ({"salted"}, {"unsalted"}), ({"sweetened"}, {"unsweetened"}), ({"whole"}, {"ground", "powdered"})]


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


def same_state(a, b):
    for g in STATE_GROUPS:
        if a in g and b in g:
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        par_u = set(toks(" ".join(re.findall(r"\(([^)]*)\)", nb)).lower()))
        u = re.sub(r"\([^)]*\)", " ", nb).lower()
        i_all = NOTE_WORDS.sub(" ", re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower()))
        par_i = set(toks(" ".join(re.findall(r"\(([^)]*)\)", i_all))))
        i = re.sub(r"\([^)]*\)", " ", i_all)
        main = toks(i.split(",")[0])
        tail = toks(",".join(i.split(",")[1:]))
        segs = [toks(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        uflat = [t for s in segs for t in s]
        uset = set(uflat) | par_u
        iset = set(main) | set(tail) | par_i
        ub = uset | set(CULT.get(t, t) for t in uset)
        ib = iset | set(CULT.get(t, t) for t in iset)
        full_i = i + " " + " ".join(par_i)
        # ----------------------------------------------------- recall (ingredient detail explained by USDA)
        food_main = [t for t in main if (t not in NEUTRAL and t not in QUALIFIERS) or t in HEAD_NOUNS] or [t for t in main if t not in QUALIFIERS] or main
        head = food_main[-1]
        r_num = r_den = 0.0
        for t in dict.fromkeys(main + tail):
            if t in NEUTRAL:
                continue
            if t == head:
                w = 3.2
            elif t in food_main:
                w = 2.0
            elif t in QUALIFIERS:
                w = 1.2 if t in main else 0.8
            else:
                w = 0.3                       # unknown modifier / instruction word
            ok = (t in ub) or (CULT.get(t, t) in ub) or (t in QUALIFIERS and any(same_state(t, x) for x in uset))
            if not ok and t == head and head in par_u:
                ok = True                     # exact-head alias in USDA parentheses
            if not ok and t == head and (par_i & uset):
                ok = True                     # exact-head alias in the ingredient's own parentheses
            r_den += w
            r_num += w if ok else 0.0
        recall = r_num / r_den if r_den else 0.0
        # ----------------------------------------------------- precision (USDA content explained by ingredient)
        p_num = p_den = 0.0
        first_len = len(segs[0])
        for k, t in enumerate(uflat):
            if t in NEUTRAL:
                continue
            first = k < first_len
            if t in CATEGORY:
                w = 0.4
            elif t in QUALIFIERS:
                w = 1.0
            else:
                w = 1.5 if first else 0.3
            ok = (t in ib) or (CULT.get(t, t) in ib) or (t in QUALIFIERS and any(same_state(t, x) for x in iset))
            if t in ("raw", "fresh"):
                ok = True                      # raw/plain is the neutral default of a USDA entry
            p_den += w
            p_num += w if ok else 0.0
        precision = p_num / p_den if p_den else 1.0
        f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        # ----------------------------------------------------- penalties
        pen = 0.0
        for ing_set, usda_set in OPP:
            for (a, b) in ((ing_set, usda_set), (usda_set, ing_set)):
                if (a & iset) and (b & uset) and not (a & uset) and not (b & iset):
                    pen += 1.8
                    break
        for base, vs in TYPE_SETS.items():
            named = vs & iset
            if named and (base in uset or base in ("dressing", "cheese")) and not (named & uset) and (vs & uset):
                pen += 2.0
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = "organ" in uset or bool(set(food_main) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard"})
        for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 1.8), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.7 * (0.3 if soft else 1.0)),
                          (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.4), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.6),
                          (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 1.8),
                          (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.1),
                          (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.2), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.0),
                          (r"\d+% lean|\d+% fat", r"\d+%", 1.4), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 0.9), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.1), (r"\bkernel\b", r"kernel", 1.4)]:
            if has(ru, u) and not has(ri, full_i):
                pen += w
        ia, ua = set(x for x in BASEALT if x in iset), set(x for x in BASEALT if x in uset)
        if (ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua)):
            pen += 1.4
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = has(cook, full_i), has(cook, u)
        if uc and not ic and not has(r"\braw\b", u):
            pen += 1.9
        if ic and not uc:
            pen += 1.7 if has(r"toasted|roasted|grilled|fried", full_i) else 1.0
        di = has(r"\b(dried|dehydrated)\b", full_i) and not ic
        du = has(r"\b(dried|dehydrated)\b", u) and "from dried" not in u
        if di != du and not (du and set(food_main) & DRIED_OK):
            pen += 2.0
        for w in ("pickled", "smoked"):
            if (w in full_i) != (w in u):
                pen += 2.0
        cn = has(r"\bcanned\b", u)
        if has(r"\bcanned\b", full_i) != cn and not (cn and set(food_main) & CANNED_OK):
            pen += 1.4
        if has(r"\b(ground|powdered|powder)\b", full_i) != has(r"\b(ground|powdered|powder)\b", u):
            pen += 1.7
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", full_i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)):
            pen += 2.2
        if (set(segs[0]) & DISH) - iset - set(food_main):
            pen += 2.8
        if has(r"\bstew (meat|beef|lamb|pork)\b", full_i) and "stew" in segs[0]:
            pen += 2.8
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            pen += 2.2
        if has(r"\bbone[- ]in\b", full_i) and not has(r"\bbone\b", u):
            pen += 1.0
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            pen += 3.0
        if len(food_main) >= 2 and has(r"\band\b", i.split(",")[0]) and not has(r"\band\b", u) and recall < 0.95:
            pen += 1.3
        head_gate = 1.0 if (head in ub or CULT.get(head, head) in ub or head in par_u or (par_i & uset)) else 0.35
        return float(10.0 * f1 * head_gate * math.exp(-0.28 * min(pen, 10.0)) + 0.3 * recall)
    except Exception:
        return 0.0
