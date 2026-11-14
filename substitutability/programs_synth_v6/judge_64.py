import re
import math

# =============================================================================================
# Naive-Bayes-style log-odds judge. The pair is converted into a bag of symbolic evidence tokens
# ("cook:usda_only", "qual:fat", "type:S>D", ...). A dictionary of log-likelihood-ratio weights
# (positive = substitutable evidence) is summed; the sum is squashed with a logistic function.
# =============================================================================================

LLR = {
    "ident:full": 2.6, "ident:most": 0.9, "ident:half": -0.8, "ident:none": -3.2,
    "head:hit": 1.6, "head:miss": -2.2, "head:first": 0.5,
    "first:explained": 0.8, "first:extra1": -0.6, "first:extra2": -1.3, "first:extra3": -1.9,
    "type:S>D": -3.2, "type:D>S": -2.6, "type:S>L": -1.4, "type:L>S": -1.4, "type:S>M": -1.8, "type:D>D": 0.5, "type:L>L": 0.4,
    "form:new_noun": -3.0, "form:front_state": -2.4, "form:restaurant": -3.3, "form:stew_idiom": -3.0,
    "qual:sodium": -1.9, "qual:fat": -1.8, "qual:fat_soft": -0.6, "qual:sugar": -1.5, "qual:diet": -1.7, "qual:mixin": -1.9, "qual:recipe": -1.2,
    "qual:origin": -1.2, "qual:origin_organ": -0.3, "qual:deli": -1.0, "qual:ratio": -1.4, "qual:coating": -1.7, "qual:flavour": -1.1, "qual:seasoned_dropped": -1.7,
    "cook:usda_only": -2.1, "cook:ing_only_hard": -1.9, "cook:ing_only_soft": -1.1, "dry:mismatch": -2.3, "pickle_smoke": -2.3, "can:mismatch": -1.6,
    "grind:hard": -2.0, "grind:soft": -1.2, "part:mismatch": -2.5, "bone_in:dropped": -1.2, "variety:conflict": -2.2,
    "brand:category_rule": 2.2, "brand:present": 0.3, "alias:paren": 1.2,
}
BIAS = -1.0

SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
       "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
       "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
VB = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
GEN = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal"}
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
ORGANS = {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard", "organ"}
DISH = r"\b(entree|dinner|casserole|sandwich|burrito|taco|pizza|pie|soup|salad|curry|stir[- ]fry|lasagna|stuffed|in (a )?(sauce|gravy)|topped|filled)\b|\bstew\b(?! meat| beef)"
IDIOM = r"half and half|salt and pepper|meat and skin|skin and bone|equal parts milk and cream|half & half"


def tk(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("dairy free", "vegan")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYN.get(w, w))
    return out


def struct_type(text):
    t = re.sub(IDIOM, " ", text.lower())
    if re.search(DISH, t):
        return "D"
    if re.search(r"\b(mix|blend|mixture|assorted|medley)\b", t):
        return "M"
    if re.search(r"\b(and|with|plus|&)\b", t.split(",")[0]):
        return "L"
    return "S"


def evidence(ingredient, usda_match):
    ev = []
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
        return None, 0.0
    iset = set(tk(i_txt))
    uset = set(t for s in usegs for t in s) | set(tk(par))
    ub = uset | set(VB.get(t, t) for t in uset)
    core = [t for t in imain if t not in SKIP and not STATE.match(t)] or [t for t in imain if t not in SKIP] or imain
    matched = [1.0 if (t in ub or VB.get(t) in ub) else 0.0 for t in core]
    cov = sum(matched) / float(len(core))
    ev.append("ident:full" if cov >= 0.99 else "ident:most" if cov >= 0.66 else "ident:half" if cov >= 0.33 else "ident:none")
    ev.append("head:hit" if matched[-1] else "head:miss")
    if core[-1] in usegs[0]:
        ev.append("head:first")
    if set(usegs[0]) <= (iset | set(core) | GEN | {"raw", "fluid"}):
        ev.append("first:explained")
    extra = [t for t in usegs[0] if t not in iset and t not in core and t not in SKIP and not STATE.match(t) and t not in GEN]
    if extra:
        ev.append("first:extra%d" % min(len(extra), 3))
    ti, tu = struct_type(i_main), struct_type(u_txt)
    if ti != tu:
        ev.append("type:%s>%s" % (ti, tu))
    elif ti in ("D", "L"):
        ev.append("type:%s>%s" % (ti, tu))
    if (set(usegs[0]) & FORMS) - set(core) - iset:
        ev.append("form:new_noun")
    if re.search(r"\bstew (meat|beef|lamb|pork)\b", i_main) and "stew" in usegs[0] and not re.search(r"\bstew (meat|beef)\b", u_txt):
        ev.append("form:stew_idiom")
    if usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
        ev.append("form:front_state")
    if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
        ev.append("form:restaurant")
    soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
    organ = bool(set(core) & ORGANS) or "organ" in uset or "variety meat" in u_txt
    def has(rx, s):
        return bool(re.search(rx, s))
    if has(r"low ?sodium|reduced sodium|no salt added|sodium free", u_txt) and not has(r"sodium", i_txt):
        ev.append("qual:sodium")
    if has(r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", u_txt) and not has(r"fat|light|lite|skim|lean|diet", i_txt):
        ev.append("qual:fat_soft" if soft else "qual:fat")
    if has(r"sugar ?free|unsweetened|sweetened", u_txt) and not has(r"sweet|sugar", i_txt):
        ev.append("qual:sugar")
    if has(r"decaf|lactose|\bdiet\b|low calorie", u_txt) and not has(r"decaf|lactose|diet", i_txt):
        ev.append("qual:diet")
    if has(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", u_txt) and not has(r"\bwith\b|\band\b", i_txt):
        ev.append("qual:mixin")
    if has(r"made (with|from)|prepared (with|from)|from mix|dry mix", u_txt) and not has(r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", i_txt):
        ev.append("qual:recipe")
    if has(r"new zealand|northern plains|hawaii|beaked|native|shoshone", u_txt) and not has(r"new zealand|hawaii", i_txt):
        ev.append("qual:origin_organ" if organ else "qual:origin")
    if has(r"\bdeli\b|luncheon|prepackaged|shelf stable", u_txt) and not has(r"deli|lunch|sliced", i_txt):
        ev.append("qual:deli")
    if has(r"\d+% lean|\d+% fat", u_txt) and not has(r"\d+%", i_txt):
        ev.append("qual:ratio")
    if has(r"breaded|battered|coated|glazed|candied", u_txt) and not has(r"bread|batter|coated|glazed|candied|crispy", i_txt):
        ev.append("qual:coating")
    if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt) if not re.search(r"\b" + x, i_txt)]:
        ev.append("qual:flavour")
    if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not has(r"garlic|seasoned|marinated", u_txt):
        ev.append("qual:seasoned_dropped")
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = has(cook, i_txt), has(cook, u_txt)
    if uc and not ic and not has(r"\braw\b", u_txt):
        ev.append("cook:usda_only")
    if ic and not uc:
        ev.append("cook:ing_only_hard" if has(r"toasted|roasted|grilled|fried", i_txt) else "cook:ing_only_soft")
    di = has(r"\b(dried|dehydrated)\b", i_txt) and not ic
    du = has(r"\b(dried|dehydrated)\b", u_txt) and "from dried" not in u_txt
    if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
        ev.append("dry:mismatch")
    for w in ("pickled", "smoked"):
        if (w in i_txt) != (w in u_txt):
            ev.append("pickle_smoke")
    cn = has(r"\bcanned\b", u_txt)
    if has(r"\bcanned\b", i_txt) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
        ev.append("can:mismatch")
    if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
        ev.append("grind:hard" if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else "grind:soft")
    if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
        ev.append("part:mismatch")
    if has(r"\bbone[- ]in\b", i_txt) and not has(r"\bbone\b", u_txt):
        ev.append("bone_in:dropped")
    for base, vs in VSET.items():
        named = vs & set(core)
        if named and base in uset and not (named & uset) and (vs & uset):
            ev.append("variety:conflict")
    if branded:
        ev.append("brand:present")
        if set(core) & {"cereal", "cracker", "tortilla", "granola"} and set(core) & set(usegs[0]):
            ev.append("brand:category_rule")
    if par and core[-1] in set(tk(par)) and core[-1] not in set(t for s in usegs for t in s):
        ev.append("alias:paren")
    return ev, cov


def judging_function(ingredient, usda_match):
    try:
        ev, cov = evidence(ingredient, usda_match)
        if ev is None:
            return 0.0
        z = BIAS + sum(LLR.get(e, 0.0) for e in ev) + 0.4 * cov
        return float(1.0 / (1.0 + math.exp(-z / 2.0)))
    except Exception:
        return 0.0
