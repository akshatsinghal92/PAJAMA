import re

NEG_PREFIX = re.compile(r"\b(?:no|without|non|not|zero|sans)\s+(?:added\s+)?([a-z]+)")
NEG_SUFFIX = re.compile(r"\b([a-z]+?)[- ](?:free|less)\b")
NEG_UN = re.compile(r"\b(un|de|non)([a-z]{4,})\b")
UN_WHITELIST = {"salted", "sweetened", "cooked", "heated", "roasted", "hulled", "shelled", "peeled", "seasoned", "flavored", "caffeinated", "boned", "skinned", "pitted", "fortified", "enriched", "sulfured", "bleached", "processed", "cured", "seeded", "scented", "toasted"}
CANON = {"salted": "salt", "salt": "salt", "sweetened": "sugar", "sugar": "sugar", "sugars": "sugar", "sweet": "sugar", "fat": "fat", "fatty": "fat", "oil": "fat",
         "boneless": "bone", "boned": "bone", "bone": "bone", "skinless": "skin", "skinned": "skin", "skin": "skin", "seedless": "seed", "seeded": "seed", "seed": "seed", "seeds": "seed", "pitted": "pit",
         "shelled": "shell", "hulled": "hull", "shell": "shell", "hull": "hull", "caffeinated": "caffeine", "caffeine": "caffeine", "lactose": "lactose", "gluten": "gluten", "sodium": "sodium",
         "cooked": "heat", "heated": "heat", "roasted": "roast", "toasted": "roast", "seasoned": "season", "flavored": "flavor", "flavor": "flavor", "fortified": "fortify", "enriched": "fortify",
         "added": "added", "sulfured": "sulfite", "cured": "cure", "processed": "process", "peeled": "peel", "peel": "peel", "moisture": "moisture", "dairy": "dairy", "milk": "dairy"}
NEUTRAL_FILL = set("thawed chopped diced minced shredded grated cubed crushed halved torn crumbled rinsed warmed melted softened ripe large small medium finely optional and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american".split())
ALIASES = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet", "cos": "romaine"}


def signed_facts(text):
    """extract {attribute: polarity} where polarity=-1 means explicitly absent, +1 explicitly present"""
    t = " " + text.lower().replace("-", " ") + " "
    facts = {}
    for m in NEG_PREFIX.finditer(t):
        a = CANON.get(m.group(1), m.group(1))
        facts[a] = -1
    t2 = t
    for m in re.finditer(r"\b([a-z]+?) (?:free|less)\b", t2):
        a = CANON.get(m.group(1), m.group(1))
        facts[a] = -1
    for m in NEG_UN.finditer(t):
        stem = m.group(2)
        if stem in UN_WHITELIST or stem.endswith("ed"):
            facts[CANON.get(stem, stem)] = -1
    for w in re.findall(r"[a-z]+", t):
        if w in CANON and CANON[w] not in facts:
            if w in ("boneless", "skinless", "seedless", "unsalted", "unsweetened"):
                continue
            facts[CANON[w]] = 1
    for w, a in (("boneless", "bone"), ("skinless", "skin"), ("seedless", "seed"), ("unsalted", "salt"), ("unsweetened", "sugar"), ("decaffeinated", "caffeine")):
        if re.search(r"\b" + w + r"\b", t):
            facts[a] = -1
    # explicit presence phrases override
    for pat, a in ((r"\b(?:with|has|including|contains) (?:added )?(salt|sugars?|fat|oil|skin|bone|seeds?)\b", None), (r"\b(salt|sugars?|fat|oil)s? added\b", None), (r"\bskin[- ]on\b", "skin"), (r"\bbone[- ]in\b", "bone"), (r"\bin (?:the )?shell\b", "shell"), (r"\bmeat and skin\b", "skin")):
        for m in re.finditer(pat, t):
            key = a or CANON.get(m.group(1), m.group(1))
            facts[key] = 1
    return facts


def toks(s):
    out = []
    for w in re.findall(r"[a-z]+", s.replace("-", " ")):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIASES.get(w, w))
    return out


def judging_function(ingredient, usda_match):
    try:
        u_raw = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        par = " ".join(re.findall(r"\(([^)]*)\)", u_raw))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", u_raw).lower()
        imain = toks(i_txt.split(",")[0])
        usegs = [toks(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uset = set(t for s in usegs for t in s) | set(toks(par))
        iset = set(toks(i_txt))
        fi, fu = signed_facts(i_txt), signed_facts(u_txt + " " + par)
        conflicts = [a for a in fi if a in fu and fi[a] != fu[a]]
        # one-sided: USDA states a quality the ingredient does not mention (asymmetric)
        usda_only = [a for a in fu if a not in fi]
        ing_only = [a for a in fi if a not in fu]
        weights_u = {"salt": 1.2, "sugar": 1.5, "fat": 1.2, "sodium": 1.9, "caffeine": 1.7, "lactose": 1.7, "gluten": 1.2, "flavor": 1.1, "fortify": 0.5, "season": 1.2, "heat": 0.0, "roast": 0.0, "dairy": 0.4, "added": 0.0}
        sc_conf = 3.6 * len(conflicts)
        sc_u = sum(weights_u.get(a, 0.2) for a in usda_only)
        sc_i = 0.5 * sum(weights_u.get(a, 0.2) for a in ing_only)
        core = [t for t in imain if t not in NEUTRAL_FILL and not re.match(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|diet|unsalted|salted|skinless|boneless|seedless)$", t)] or [t for t in imain if t not in NEUTRAL_FILL] or imain
        head = core[-1]
        cov = sum(1 for t in core if t in uset) / float(len(core))
        score = 5.0 * cov + (1.8 if head in uset else -1.4) + (0.5 if head in usegs[0] else 0.0)
        score -= 0.95 * (sc_conf + sc_u + sc_i)
        # fat/lean percentage specs and fat level words
        if re.search(r"\d+% (lean|fat)|milkfat", u_txt) and not re.search(r"\d+%", i_txt):
            score -= 1.4
        if re.search(r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b", u_txt) and not re.search(r"fat|light|lite|skim|lean|diet", i_txt):
            score -= 1.9 * (0.35 if (re.search(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt) else 1.0)
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
        if uc and not ic and not re.search(r"\braw\b", u_txt):
            score -= 2.2
        if ic and not uc:
            score -= 1.3
        di = bool(re.search(r"\b(dried|dehydrated)\b", i_txt)) and not ic
        du = bool(re.search(r"\b(dried|dehydrated)\b", u_txt)) and "from dried" not in u_txt
        if di != du and not (du and set(core) & {"pine", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            score -= 2.4
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                score -= 2.4
        cn = bool(re.search(r"\bcanned\b", u_txt))
        if bool(re.search(r"\bcanned\b", i_txt)) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            score -= 1.7
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt)):
            score -= 1.2
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(usegs[0]) & forms) - iset:
            score -= 3.2
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            score -= 2.5
        if re.search(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b|made (with|from)|prepared (with|from)|from mix|dry mix", u_txt) and not re.search(r"\bwith\b|\band\b|made|prepared|mix|vegan|plant", i_txt):
            score -= 1.6
        if re.search(r"new zealand|northern plains|hawaii|beaked|native|\bdeli\b|luncheon|prepackaged|shelf stable", u_txt):
            score -= 1.1
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            score -= 3.5
        return float(score + 2.0)
    except Exception:
        return 0.0
