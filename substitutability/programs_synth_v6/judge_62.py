import re

# =========================================================================================
# Component-alignment judge. Each side is decomposed into COMPONENTS (foods joined by 'and',
# 'with', 'in', 'mixed with', 'plus'). Components are aligned greedily (best overlap first).
# Aligned components give identity; unaligned USDA components are additions (the USDA entry is
# a dish containing more than the ingredient) and unaligned ingredient components are omissions.
# =========================================================================================

SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
       "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
       "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
VB = {"concord": "grape", "thompson": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot of the a for from nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
GENERIC = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal"}
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
JOINERS = r"\band\b|\bwith\b|\bplus\b|\bmixed with\b|\bin\b|&|\+"
IDIOMS = [("half and half", "halfandhalf"), ("half & half", "halfandhalf"), ("equal parts milk and cream", "halfandhalf"), ("salt and pepper", "saltpepper"), ("mac and cheese", "macncheese"), ("meat and skin", "withskin"), ("skin and bone", "skinbone")]


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


def components(text):
    t = text.lower()
    for a, b in IDIOMS:
        t = t.replace(a, b)
    parts = re.split(JOINERS, t)
    comps = []
    for p in parts:
        ws = [w for w in tk(p) if w not in SKIP and not STATE.match(w)]
        if ws:
            comps.append(ws)
    return comps


def align(ic, uc):
    """greedy alignment on token overlap; returns (aligned_score_sum, matched_i_idx, matched_u_idx)"""
    pairs = []
    for a, ia in enumerate(ic):
        for b, ub in enumerate(uc):
            sa, sb = set(ia), set(ub | set(VB.get(t, t) for t in ub)) if isinstance(ub, set) else set(ub)
            sb = sb | set(VB.get(t, t) for t in sb)
            inter = len([t for t in ia if t in sb or VB.get(t) in sb])
            if inter:
                pairs.append((inter / float(len(ia)), a, b))
    pairs.sort(reverse=True)
    used_i, used_u, tot = set(), set(), 0.0
    for sc, a, b in pairs:
        if a in used_i or b in used_u:
            continue
        used_i.add(a)
        used_u.add(b)
        tot += sc
    return tot, used_i, used_u


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda")))
        par = " ".join(re.findall(r"\(([^)]*)\)", raw_u))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_u).lower()
        i_main = i_txt.split(",")[0]
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        imain = tk(i_main)
        if not imain or not usegs:
            return 0.0
        iset = set(tk(i_txt))
        uset = set(t for s in usegs for t in s) | set(tk(par))
        ic = components(i_main)
        # USDA components: the first segment's components plus 'with X' style segments; hierarchy segments merge into one component
        uc = []
        first_comps = components(u_txt.split(",")[0])
        uc.extend(first_comps)
        hier = [w for s in u_txt.split(",")[1:] for w in tk(s) if w not in SKIP and not STATE.match(w)]
        if hier:
            uc.append(hier)
        # hierarchical words also help the first component (category first, subtype later)
        uc_sets = [set(c) for c in uc]
        if uc_sets:
            uc_sets[0] = uc_sets[0] | set(hier)
        uc_sets.extend([set(tk(par))] if par else [])
        if not ic:
            ic = [imain]
        tot, ui, uu = align(ic, uc_sets)
        n_i = len(ic)
        ident = 6.6 * (tot / float(n_i)) if n_i else 0.0
        # head presence of the last ingredient component
        last = ic[-1]
        head_hit = last[-1] in uset or VB.get(last[-1]) in uset
        ident += 1.8 if head_hit else -1.2
        omit = [i for i in range(n_i) if i not in ui]
        added = [j for j in range(len(first_comps)) if j not in uu]
        comp_pen = 1.6 * min(len(omit), 3) + 1.5 * min(len(added), 3)
        if re.search(r"\b(with|in)\b", u_txt.split(",")[0]) and not re.search(r"\bwith\b|\bin\b", i_main):
            comp_pen += 0.8
        # variety conflict
        for base, vs in VSET.items():
            named = vs & set(imain)
            if named and base in uset and not (named & uset) and (vs & uset):
                comp_pen += 2.2
        pen = 0.0
        soft_dairy = has(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                              (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]:
            if has(u_rx, u_txt) and not has(i_rx, i_txt):
                pen += w
        if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt) if not re.search(r"\b" + x, i_txt)]:
            pen += 1.1
        if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not has(r"garlic|seasoned|marinated", u_txt):
            pen += 1.7
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        icook, ucook = has(cook, i_txt), has(cook, u_txt)
        if ucook and not icook and not has(r"\braw\b", u_txt):
            pen += 2.1
        if icook and not ucook:
            pen += 1.9 if has(r"toasted|roasted|grilled|fried", i_txt) else 1.1
        di = has(r"\b(dried|dehydrated)\b", i_txt) and not icook
        du = has(r"\b(dried|dehydrated)\b", u_txt) and "from dried" not in u_txt
        if di != du and not (du and set(imain) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            pen += 2.3
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                pen += 2.3
        cn = has(r"\bcanned\b", u_txt)
        if has(r"\bcanned\b", i_txt) != cn and not (cn and set(imain) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            pen += 1.6
        if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
            pen += 2.0 if set(imain) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.5
        core_i = set(t for c in ic for t in c)
        form_new = (set(usegs[0]) & FORMS) - core_i
        if form_new - iset or ("stew" in form_new and re.search(r"\bstew (meat|beef|lamb|pork)\b", i_main)):
            pen += 3.0
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.4
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.3
        return float(ident - comp_pen - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
