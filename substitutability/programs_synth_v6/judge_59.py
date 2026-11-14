import re

# ============================================================================================
# Multiple-readings judge. A USDA description is ambiguous about which segments name the food and
# which are descriptors (USDA: category, subtype, cut, state, ...). We build several READINGS of
# the entry, score the ingredient's identity against each one, keep the best identity score,
# and then apply entry-level penalties (qualifiers, states, forms, brand) once.
# ============================================================================================

ALIASES = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp",
           "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn",
           "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt",
           "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet", "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga",
           "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing", "wrap": "tortilla"}
VARIETY_BASE = {"concord": "grape", "thompson": "grape", "bing": "cherry", "rainier": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "valencia": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VARIETY_SETS = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny", "mcintosh"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}, "yam": {"mountain", "sweet"}}
DROPWORDS = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
TYPE_KEEP = {"breakfast", "italian", "greek", "mexican", "chinese", "polish", "swiss", "cream", "sour"}
HEAD_GENERIC = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal"}
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}


def tk(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIASES.get(w, w))
    return out


def readings(segs):
    """candidate (identity-word-list) readings of a USDA entry"""
    r = []
    if not segs:
        return r
    r.append(segs[0])                                           # primary segment only
    if len(segs) > 1:
        r.append(segs[0] + segs[1])                             # category + subtype
        r.append(segs[1] + segs[0])                             # subtype-first natural order ("pine nut")
    if len(segs) > 2:
        r.append(segs[0] + segs[1] + segs[2])
        r.append(segs[2] + segs[1])                             # cut/organ words
    r.append([w for s in segs for w in s])                      # everything
    return r


def identity_score(core, reading):
    pool = set(reading)
    pool_b = pool | set(VARIETY_BASE.get(t, t) for t in pool)
    matched = [1.0 if (t in pool_b or VARIETY_BASE.get(t) in pool_b) else 0.0 for t in core]
    cov = sum(matched) / float(len(core))
    head = matched[-1]
    # precision: reading words not explained by the ingredient (a more specific different food)
    extra = [t for t in reading if t not in core and t not in DROPWORDS and not STATE_RX.match(t) and t not in HEAD_GENERIC]
    prec_pen = 0.55 * min(len(extra), 3)
    return 4.6 * cov + 2.0 * head - (1.4 if not head else 0.0) - prec_pen, cov, head


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        kept = []
        for w in raw_u.split():
            letters = re.sub(r"[^A-Za-z]", "", w)
            if len(letters) >= 3 and letters.isupper() and letters.lower() not in ("nfs", "usda"):
                continue
            kept.append(w)
        raw_nb = " ".join(kept)
        par = " ".join(re.findall(r"\(([^)]*)\)", raw_nb))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_nb).lower()
        imain = tk(i_txt.split(",")[0])
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        iset = set(tk(i_txt))
        core = [t for t in imain if (t not in DROPWORDS or t in TYPE_KEEP) and not STATE_RX.match(t)] or [t for t in imain if t not in DROPWORDS] or imain
        # parenthetical aliases become an extra reading
        rds = readings(usegs)
        if par:
            rds.append(tk(par) + usegs[0])
        best, best_cov, best_head = -99.0, 0.0, 0.0
        for rd in rds:
            sc, cov, head = identity_score(core, rd)
            if sc > best:
                best, best_cov, best_head = sc, cov, head
        uset = set(t for s in usegs for t in s) | set(tk(par))
        # variety conflict
        conflict = 0.0
        for base, vs in VARIETY_SETS.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                conflict = 2.2
        pen = 0.0
        soft_dairy = has(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                              (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.3),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]:
            if has(u_rx, u_txt) and not has(i_rx, i_txt):
                pen += w
        if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not has(r"garlic|seasoned|marinated", u_txt):
            pen += 1.8
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = has(cook, i_txt), has(cook, u_txt)
        if uc and not ic and not has(r"\braw\b", u_txt):
            pen += 2.2
        if ic and not uc:
            pen += 2.0 if has(r"toasted|roasted|grilled|fried", i_txt) else 1.2
        di = has(r"\b(dried|dehydrated)\b", i_txt) and not ic
        du = has(r"\b(dried|dehydrated)\b", u_txt) and "from dried" not in u_txt
        if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            pen += 2.4
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                pen += 2.4
        cn = has(r"\bcanned\b", u_txt)
        if has(r"\bcanned\b", i_txt) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            pen += 1.7
        if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
            pen += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.4
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.6
        if (set(usegs[0]) & FORMS) - iset - set(core):
            pen += 3.2
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.5
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.5
        if has(r"\band\b", i_txt.split(",")[0]) and not has(r"\band\b", u_txt) and len(core) >= 2 and best_cov < 1.0:
            pen += 1.5
        return float(best - conflict - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
