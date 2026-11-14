import re

# =============================================================================================
# Composite-dish detector. Both strings are scored for "compositeness": how many distinct food
# nouns they combine, plus dish markers (with, and, in sauce, stuffed, salad, soup, mix, blend,
# entree, prepared ...). The judge rewards equal compositeness (single-single or dish-dish) and
# penalises a single ingredient matched against a dish that merely CONTAINS it, or the reverse.
# =============================================================================================

FOOD_NOUNS = set("""beef pork lamb veal chicken turkey duck goose buffalo ham bacon sausage liver kidney tongue heart fish salmon tuna cod shrimp crab lobster crayfish egg
cheese yogurt milk cream butter tofu bean pea lentil chickpea broadbean corn rice pasta noodle flour bread tortilla cracker oat wheat potato yam carrot onion garlic tomato pepper
cucumber squash zucchini lettuce spinach kale cabbage broccoli cauliflower celery mushroom olive radish beet apple pear peach plum cherry grape berry orange tangerine lemon lime
mango papaya banana pomegranate coconut pineapple melon nut almond walnut pecan hazelnut peanut cashew pistachio seed sesame flaxseed vegetable fruit sugar honey syrup oil vinegar
salt cocoa chocolate vanilla cinnamon ginger parsley basil coriander mint sage thyme sauce gravy dressing mayonnaise ketchup mustard""".split())
DISH_MARKERS = [r"\bwith\b", r"\band\b", r"\bin (a )?(sauce|gravy|juice|syrup|brine|oil|water)\b", r"\bstuffed\b", r"\bsalad\b", r"\bsoup\b", r"\bcasserole\b", r"\bsandwich\b", r"\bmix(ed|ture)?\b",
                r"\bblend\b", r"\bdinner\b", r"\bprepared\b", r"\bentree\b", r"\bstew\b", r"\bpie\b", r"\bpizza\b", r"\btaco\b", r"\bburrito\b", r"\bcurry\b", r"\bstir[- ]fry\b", r"\bmade (with|from)\b", r"\bfilled\b", r"\btopped\b"]
SPECIAL_JOIN = [r"half and half", r"salt and pepper", r"bread and butter", r"mac(aroni)? and cheese"]
AL = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion",
      "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
      "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
      "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing"}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
GENERIC = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal"}
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}


def tk(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def compositeness(text, tokens_by_seg):
    """return (n_food_nouns, n_dish_markers) after protecting idiomatic joins like 'half and half'"""
    t = text.lower()
    for sj in SPECIAL_JOIN:
        t = re.sub(sj, " ", t)
    markers = sum(1 for p in DISH_MARKERS if re.search(p, t))
    flat = [w for s in tokens_by_seg for w in s]
    foods = set(w for w in flat if w in FOOD_NOUNS and w not in GENERIC)
    return len(foods), markers


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda")))
        par = " ".join(re.findall(r"\(([^)]*)\)", raw_u))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_u).lower()
        i_main = i_txt.split(",")[0]
        imain = tk(i_main)
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        iset = set(tk(i_txt))
        uset = set(t for s in usegs for t in s) | set(tk(par))
        core = [t for t in imain if t not in SKIP and not STATE.match(t)] or [t for t in imain if t not in SKIP] or imain
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = core[-1] in uset
        # ------------------------------------------------ compositeness
        i_foods, i_marks = compositeness(i_main, [imain])
        u_foods, u_marks = compositeness(u_txt, usegs)
        i_comp = i_foods + 1.2 * i_marks
        u_comp = u_foods + 1.2 * u_marks
        gap = u_comp - i_comp
        comp_pen = 0.0
        if gap > 0.9:                # USDA is a dish / mixture the ingredient is not
            comp_pen = 1.4 * min(gap, 3.0)
        elif gap < -0.9:             # ingredient is a mixture, USDA is a single food
            comp_pen = 1.1 * min(-gap, 3.0)
        # extra foods named by USDA but absent in ingredient are the additions that change the dish
        added_foods = [w for w in set(w for s in usegs for w in s) if w in FOOD_NOUNS and w not in GENERIC and w not in iset and w not in core]
        comp_pen += 0.7 * min(len(added_foods), 3)
        missing_foods = [w for w in set(imain) if w in FOOD_NOUNS and w not in GENERIC and w not in uset]
        comp_pen += 0.9 * min(len(missing_foods), 3)
        ident = 4.6 * cov + 2.0 * (1.0 if head else -0.7)
        # ------------------------------------------------ qualifiers and states (shared table)
        pen = 0.0
        soft_dairy = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]:
            if re.search(u_rx, u_txt) and not re.search(i_rx, i_txt):
                pen += w
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
        if uc and not ic and not re.search(r"\braw\b", u_txt):
            pen += 2.1
        if ic and not uc:
            pen += 1.9 if re.search(r"toasted|roasted|grilled|fried", i_txt) else 1.1
        di = bool(re.search(r"\b(dried|dehydrated)\b", i_txt)) and not ic
        du = bool(re.search(r"\b(dried|dehydrated)\b", u_txt)) and "from dried" not in u_txt
        if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            pen += 2.3
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                pen += 2.3
        cn = bool(re.search(r"\bcanned\b", u_txt))
        if bool(re.search(r"\bcanned\b", i_txt)) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            pen += 1.6
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt)):
            pen += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.5
        # 'stew meat' is a cut, 'Stew, beef' is a dish: treat the form noun as new unless ingredient is a dish too
        form_new = (set(usegs[0]) & FORMS) - set(core)
        if "stew" in form_new and re.search(r"\bstew (meat|beef|lamb|pork)\b", i_main):
            pen += 3.0
        elif form_new - iset:
            pen += 3.0
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.4
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.3
        if re.search(r"\bbone[- ]in\b", i_txt) and not re.search(r"\bbone\b", u_txt):
            pen += 1.2
        return float(ident - comp_pen - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
