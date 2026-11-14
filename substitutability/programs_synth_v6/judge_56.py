import re

# ======================================================================================
# Profile-distance judge. Each food string is converted into a PROFILE (a dict of
# categorical attributes). Distance between profiles is an asymmetric, weighted
# mismatch sum; identity is the profile's "food" slot compared by overlap.
# ======================================================================================

SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish",
       "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini",
       "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "dehydrated": "dried", "uncooked": "raw",
       "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb"}
VARIETY = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti", "winter", "summer"},
           "apple": {"fuji", "gala", "granny", "mcintosh", "golden", "delicious"}, "potato": {"russet", "yukon", "sweet"}, "orange": {"navel", "valencia", "blood"},
           "pepper": {"bell", "jalapeno", "chili", "sweet"}, "yam": {"mountain", "sweet"}, "mushroom": {"portobello", "cremini", "shiitake", "button"}}
TYPE_QUALIFIERS = {"breakfast", "italian", "greek", "mexican", "chinese", "smoked", "polish", "swiss"}
FILL = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch".split())
STATE_WORDS = set("cooked boiled baked braised simmered broiled roasted steamed toasted grilled sauteed poached stewed heat dried canned frozen smoked pickled fried ground powdered batter lowfat nonfat reduced light lite skim sweetened unsweetened flavored diet unsalted salted skinless boneless seedless crispy drained".split())
GENERIC = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "bread", "cracker", "tortilla", "cereal", "granola"}


def toks(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYN.get(w, w))
    return out


def has(rx, s):
    return bool(re.search(rx, s))


def make_profile(text, is_usda):
    raw = " ".join(text.split())
    if is_usda:
        raw = " ".join(w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
    par = " ".join(re.findall(r"\(([^)]*)\)", raw))
    body = re.sub(r"\([^)]*\)", " ", raw).lower()
    if not is_usda:
        body = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", body)
    segs = [toks(s) for s in body.split(",") if s.strip()]
    allt = set(t for s in segs for t in s) | set(toks(par))
    p = {"body": body, "segs": segs, "tokens": allt, "paren": set(toks(par))}
    cook_rx = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    p["cooked"] = has(cook_rx, body)
    p["raw"] = has(r"\braw\b|\buncooked\b|\bunheated\b", body)
    p["dried"] = has(r"\b(dried|dehydrated)\b", body) and "from dried" not in body
    p["canned"] = has(r"\bcanned\b", body)
    p["smoked"] = has(r"\bsmoked\b", body)
    p["pickled"] = has(r"\bpickled\b", body)
    p["ground"] = has(r"\b(ground|powdered|powder)\b", body)
    p["salt_pos"] = has(r"\bwith salt\b|\bsalted\b|\bsalt added\b", body)
    p["salt_neg"] = has(r"\bunsalted\b|\bwithout salt\b|\bno salt\b|\bsalt[- ]free\b|\bno added salt\b", body)
    p["sugar_pos"] = has(r"\bsweetened\b|\bwith sugar\b|\bsugar added\b", body)
    p["sugar_neg"] = has(r"\bunsweetened\b|\bsugar[- ]free\b|\bno added sugar\b", body)
    p["fat_pos"] = has(r"\bfat added\b|\badded fat\b|\bbuttered\b|\bsauteed\b|\bfried\b|\bmade with oil\b", body)
    p["fat_neg"] = has(r"\bno added fat\b|\bfat[- ]free\b|\bnon ?fat\b", body)
    p["fatlevel"] = has(r"\blow ?fat\b|\breduced fat\b|\blite\b|\blight\b|\bskim\b|\bmilkfat\b", body)
    p["skin_pos"] = has(r"\bwith skin\b|\bskin[- ]on\b|\bmeat and skin\b", body)
    p["skin_neg"] = has(r"\bskinless\b|\bwithout skin\b|\bmeat only\b|\bskin removed\b", body)
    p["bone_pos"] = has(r"\bbone[- ]in\b|\bwith bone\b", body)
    p["bone_neg"] = has(r"\bboneless\b|\bbone removed\b|\bwithout bone\b", body)
    p["decaf"] = has(r"\bdecaf", body)
    p["caffeinated"] = has(r"\bcaffeinated\b", body) and not has(r"decaffeinated", body)
    p["sodium_low"] = has(r"low ?sodium|reduced sodium|no salt added|sodium free", body)
    p["lactose"] = has(r"lactose", body)
    p["diet"] = has(r"\bdiet\b|low calorie", body)
    p["mixin"] = has(r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", body)
    p["recipe"] = has(r"made (with|from)|prepared (with|from)|from mix|dry mix|home recipe", body)
    p["origin"] = has(r"new zealand|northern plains|hawaii|beaked|native|shoshone", body)
    p["deli"] = has(r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ](bake|fry|serve)", body)
    p["ratio"] = has(r"\d+% lean|\d+% fat", body)
    p["coating"] = has(r"breaded|battered|coated|glazed|candied", body)
    p["flavours"] = set(re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", body))
    p["restaurant"] = has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", body)
    return p


def food_slot(profile):
    if not profile["segs"]:
        return []
    first = profile["segs"][0]
    return [t for t in first if t not in FILL and t not in STATE_WORDS]


def distance(ip, up, core):
    d = 0.0
    # states
    if up["cooked"] and not ip["cooked"] and not up["raw"]:
        d += 2.2
    if ip["cooked"] and not up["cooked"]:
        d += 1.0 if up["raw"] else 1.3
    idr = ip["dried"] and not ip["cooked"]
    if idr != up["dried"] and not (up["dried"] and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
        d += 2.4
    d += 2.4 * (ip["smoked"] != up["smoked"]) + 2.4 * (ip["pickled"] != up["pickled"])
    if ip["canned"] != up["canned"] and not (up["canned"] and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
        d += 1.7
    d += 1.2 * (ip["ground"] != up["ground"])
    # polarity pairs: contradiction is heavy; one-sided USDA addition is moderate
    for pos, neg, one in (("salt_pos", "salt_neg", 1.2), ("sugar_pos", "sugar_neg", 1.6), ("fat_pos", "fat_neg", 1.2), ("skin_pos", "skin_neg", 0.6), ("bone_pos", "bone_neg", 0.8)):
        if (ip[pos] and up[neg]) or (ip[neg] and up[pos]):
            d += 3.8
        elif up[pos] and not ip[pos] and not ip[neg]:
            if pos == "fat_pos" and (ip["cooked"] or has(r"saut|fried|butter", ip["body"])):
                continue
            d += one
        elif up[neg] and not ip[neg] and neg in ("salt_neg", "sugar_neg", "fat_neg"):
            d += one * 0.9
    if up["decaf"] != ip["decaf"] or (ip["caffeinated"] and up["decaf"]) or (up["caffeinated"] and ip["decaf"]):
        d += 1.8
    soft_dairy = has(r"\b(yogurt|kefir|milk)\b", up["body"]) and "cheese" not in up["body"]
    if up["fatlevel"] and not ip["fatlevel"] and not has(r"fat|light|lite|skim|lean|diet", ip["body"]):
        d += 1.9 * (0.35 if soft_dairy else 1.0)
    if up["sodium_low"] and not ip["sodium_low"] and "sodium" not in ip["body"]:
        d += 2.0
    d += 1.8 * (up["lactose"] and not ip["lactose"]) + 1.8 * (up["diet"] and not ip["diet"])
    d += 2.0 * (up["mixin"] and not has(r"\bwith\b|\band\b", ip["body"]))
    bakedgood = bool(set(core) & {"bread", "cornbread", "cake", "cookie", "muffin", "pie", "pizza", "dumpling", "dressing", "mayonnaise", "tapenade"})
    if up["recipe"] and not (ip["recipe"] or has(r"vegan|plant", ip["body"]) or bakedgood):
        d += 1.3
    d += 1.3 * (up["origin"] and not ip["origin"]) + 1.1 * (up["deli"] and not has(r"deli|lunch|sliced", ip["body"]))
    d += 1.5 * (up["ratio"] and not has(r"\d+%", ip["body"]))
    d += 1.8 * (up["coating"] and not has(r"bread|batter|coated|glazed|candied|crispy", ip["body"]))
    if up["flavours"] and any(not has(r"\b" + f, ip["body"]) for f in up["flavours"]):
        d += 1.2
    d += 3.5 * up["restaurant"]
    return d


def judging_function(ingredient, usda_match):
    try:
        ip = make_profile(str(ingredient or ""), False)
        up = make_profile(str(usda_match or ""), True)
        if not ip["segs"] or not up["segs"]:
            return 0.0
        imain = toks(ip["body"].split(",")[0])
        core = [t for t in imain if t not in FILL and t not in STATE_WORDS] or [t for t in imain if t not in FILL] or imain
        # type qualifiers (breakfast sausage, Greek yogurt) matter: re-add them as core words
        extras = [t for t in imain if t in TYPE_QUALIFIERS and t not in core]
        core = core + extras if not core[-1:] == extras[-1:] else core
        head = [t for t in core if t not in TYPE_QUALIFIERS][-1] if [t for t in core if t not in TYPE_QUALIFIERS] else core[-1]
        utoks = up["tokens"]
        cov_items = [1.0 if t in utoks else 0.0 for t in core]
        # variety conflict test
        conflict = 0.0
        for base, vs in VARIETY.items():
            named = vs & set(core)
            if named and base in utoks and not (named & utoks) and (vs & utoks):
                conflict = 1.0
        cov = sum(cov_items) / float(len(core))
        head_hit = 1.0 if head in utoks else 0.0
        food_u = food_slot(up)
        extra_u = [t for t in food_u if t not in ip["tokens"] and t not in GENERIC and t not in core]
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        form_pen = 3.2 if (set(up["segs"][0]) & forms) - ip["tokens"] - set(core) else 0.0
        front = 2.5 if (up["segs"][0][0] in ("frozen", "dried", "canned", "smoked") and up["segs"][0][0] not in ip["tokens"]) else 0.0
        part = 2.6 if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", ip["body"])) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", up["body"])) else 0.0
        ident = 4.6 * cov + 2.0 * head_hit - (1.4 if not head_hit else 0.0) - 2.2 * conflict - 0.55 * min(len(extra_u), 3)
        return float(ident - 0.95 * min(distance(ip, up, core) + form_pen + front + part, 10.0) + 2.0)
    except Exception:
        return 0.0
