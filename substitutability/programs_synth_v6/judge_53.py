import re

# attribute -> (pattern for the POSITIVE-presence pole, pattern for the NEGATED/absent pole)
_ATTRS = {
    "salt": (r"\bwith salt\b|\bsalted\b|\bsalt added\b|\badded salt\b|\bsalt\b", r"\bunsalted\b|\bwithout salt\b|\bno salt\b|\bsalt free\b|\bno added salt\b|\bsalt[- ]free\b"),
    "sugar": (r"\bsweetened\b|\bwith sugar\b|\bsugars? added\b|\badded sugar\b", r"\bunsweetened\b|\bsugar ?free\b|\bno sugar\b|\bwithout sugar\b|\bno added sugar\b"),
    "fat": (r"\bfat added\b|\badded fat\b|\bwith fat\b|\bwith oil\b|\bbuttered\b|\bfried\b", r"\bno added fat\b|\bfat ?free\b|\bwithout fat\b|\bnon ?fat\b|\bno fat\b|\bfat[- ]free\b"),
    "skin": (r"\bwith skin\b|\bskin[- ]on\b|\bmeat and skin\b|\bskin included\b", r"\bskinless\b|\bwithout skin\b|\bskin removed\b|\bmeat only\b|\bskin not eaten\b|\bpeeled\b"),
    "bone": (r"\bbone[- ]in\b|\bwith bone\b|\bbone\b(?! removed)", r"\bboneless\b|\bbone removed\b|\bwithout bone\b|\bde-?boned\b"),
    "seed": (r"\bwith seeds?\b|\bseeded\b|\bseed in\b", r"\bseedless\b|\bwithout seeds?\b|\bseeds? removed\b|\bpitted\b|\bdeseeded\b"),
    "hull": (r"\bunhulled\b|\bhulled\b(?!.*less)|\bwith hulls?\b|\bin shell\b|\bin the shell\b", r"\bhulled\b|\bshelled\b|\bdehulled\b|\bwithout shell\b"),
    "caffeine": (r"\bcaffeinated\b(?<!de)|\bregular\b", r"\bdecaffeinated\b|\bdecaf\b|\bcaffeine[- ]free\b"),
    "lactose": (r"\bmilk\b|\blactose\b(?! reduced| free)", r"\blactose[- ]free\b|\blactose[- ]reduced\b|\bdairy[- ]free\b|\bnon[- ]dairy\b"),
    "gluten": (r"\bwheat\b|\bwith gluten\b", r"\bgluten[- ]free\b|\bwithout gluten\b"),
    "sodium": (r"\bsodium\b(?! free)|\bregular sodium\b", r"\blow ?sodium\b|\breduced sodium\b|\bsodium free\b|\bno sodium\b|\bunsalted\b"),
    "cooked": (r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|fried)\b", r"\braw\b|\buncooked\b|\bunheated\b|\bunroasted\b"),
    "dried": (r"\bdried\b|\bdehydrated\b|\bdry\b", r"\bfresh\b|\bwet\b|\bnot dried\b|\bmoist\b"),
    "frozen": (r"\bfrozen\b", r"\bfresh\b|\bunfrozen\b|\bthawed\b"),
    "sweet_fruit": (r"\bsweet\b", r"\bunsweetened\b|\bsour\b|\btart\b"),
    "fat_level": (r"\bwhole\b|\bfull[- ]fat\b|\bregular\b|\bhi[- ]fat\b", r"\blow ?fat\b|\bnon ?fat\b|\bfat[- ]free\b|\breduced fat\b|\bskim\b|\blite\b|\blight\b|\blean\b"),
}
# attributes whose one-sided mention is also mildly penalised (taste/composition visible to a diner)
_ONE_SIDED = {"salt": 0.8, "sugar": 1.0, "fat": 0.7, "sodium": 1.2, "caffeine": 1.4, "lactose": 0.8, "fat_level": 0.5, "skin": 0.5, "seed": 0.5}
_CONTRADICTION = {"salt": 4.0, "sugar": 4.0, "fat": 3.8, "skin": 3.5, "bone": 3.5, "seed": 3.0, "hull": 3.0, "caffeine": 3.5, "lactose": 2.5, "gluten": 3.5, "sodium": 3.5, "cooked": 3.2, "dried": 3.5, "frozen": 0.8, "sweet_fruit": 2.0, "fat_level": 3.0}
_FILL = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style domesticated new fluid white sliced atlantic pacific alaska american".split())
_STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted)$")
_ALIAS = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet", "cos": "romaine"}


def _poles(text):
    """return {attr: +1 (presence pole) / -1 (negated pole) / 0 absent} ; negated pole wins if both fire"""
    res = {}
    for a, (pos_rx, neg_rx) in _ATTRS.items():
        pos = re.search(pos_rx, text)
        neg = re.search(neg_rx, text)
        if neg:
            res[a] = -1
        elif pos:
            res[a] = 1
        else:
            res[a] = 0
    return res


def _toks(s):
    out = []
    for w in re.findall(r"[a-z]+", s.replace("-", " ")):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(_ALIAS.get(w, w))
    return out


def judging_function(ingredient, usda_match):
    try:
        u_raw = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        u_par = " ".join(re.findall(r"\(([^)]*)\)", u_raw))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", u_raw).lower()
        i_main = i_txt.split(",")[0]
        imain = _toks(i_main)
        usegs = [_toks(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uset = set(t for s in usegs for t in s) | set(_toks(u_par))
        iset = set(_toks(i_txt))
        # ---- polarity channel
        pi = _poles(i_txt)
        pu = _poles(u_txt + " " + u_par.lower())
        contra = 0.0
        agree = 0.0
        onesided = 0.0
        for a in _ATTRS:
            x, y = pi[a], pu[a]
            if x and y:
                if x != y:
                    contra += _CONTRADICTION[a]
                else:
                    agree += 0.25
            elif x or y:
                if a in ("cooked", "dried"):
                    # one-sided cooked/dried: ingredient unmarked is raw; USDA 'raw' counts as explicit
                    if y == 1 and not x:
                        onesided += 2.2 if a == "cooked" else 2.4
                    elif x == 1 and not y:
                        onesided += 1.3 if a == "cooked" else 2.4
                else:
                    onesided += _ONE_SIDED.get(a, 0.0) * (1.0 if y else 0.6)
        # ---- identity channel
        core = [t for t in imain if t not in _FILL and not _STATE_RX.match(t)] or [t for t in imain if t not in _FILL] or imain
        head = core[-1]
        cov = sum(1 for t in core if t in uset) / float(len(core))
        ident = 5.0 * cov + (1.8 if head in uset else -1.4) + (0.5 if head in usegs[0] else 0.0)
        # ---- form/other events
        other = 0.0
        pk = re.search(r"\bcanned\b", u_txt)
        if bool(re.search(r"\bcanned\b", i_txt)) != bool(pk) and not (pk and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            other += 1.7
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                other += 2.4
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt)):
            other += 1.2
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            other += 2.6
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(usegs[0]) & forms) - iset:
            other += 3.2
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            other += 2.5
        if re.search(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b|made (with|from)|prepared (with|from)|from mix|dry mix", u_txt) and not re.search(r"\bwith\b|\band\b|made|prepared|mix|vegan|plant", i_txt):
            other += 1.6
        if re.search(r"new zealand|northern plains|hawaii|beaked|native|\bdeli\b|luncheon|prepackaged|shelf stable|\d+% lean", u_txt):
            other += 1.2
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            other += 3.5
        return float(ident + agree - 0.95 * min(contra, 8.0) - 0.9 * onesided - 0.9 * other + 2.0)
    except Exception:
        return 0.0
