import re

# =====================================================================================
# Brand-aware strategy judge. Step 1 decides whether the USDA entry is a BRANDED product.
# Branded entries are scored by product-type agreement (generic part of the name) and
# flavour/base agreement; generic entries are scored by the standard identity+qualifier path.
# =====================================================================================

KNOWN_BRANDS = {"ritz", "oreo", "cheerios", "kellogg", "kelloggs", "quaker", "nabisco", "pillsbury", "betty", "crocker", "heinz", "hershey", "hersheys", "silk", "chobani", "dannon",
                "yoplait", "lifeway", "post", "mission", "kraft", "nestle", "campbell", "campbells", "mcdonalds", "powerade", "gatorade", "pepsi", "coca", "cola", "wonder", "pringles",
                "doritos", "lays", "tostitos", "goya", "bertolli", "hellmann", "hellmanns", "smucker", "smuckers", "knorr", "lipton", "folgers", "starbucks", "oscar", "mayer", "tyson",
                "wheat thins", "triscuit", "cheez", "goldfish", "pop", "tarts", "nutella", "jif", "skippy", "welch", "welchs", "sunkist", "dole", "ocean", "spray", "gerber", "enfamil", "similac", "oikos", "fage", "stonyfield"}
FLAVOURS = ("vanilla", "chocolate", "strawberry", "peach", "blueberry", "raspberry", "banana", "cinnamon", "maple", "caramel", "honey", "lemon", "cherry", "mint", "coconut", "mocha", "pumpkin", "apple", "orange")
BASE_ALTS = ("soy", "almond", "oat", "coconut", "rice", "cashew", "pea", "vegan", "tofu", "plant")
PRODUCT_TYPES = ("cereal", "cracker", "tortilla", "cookie", "yogurt", "granola", "syrup", "bar", "chip", "bread", "pasta", "noodle", "beverage", "drink", "sauce", "dressing", "soup", "juice", "cheese", "sausage", "jerky", "popcorn", "pretzel", "mayonnaise", "ketchup", "mustard", "butter", "oil", "cream", "milk")
ALIAS = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet", "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb"}
FILL = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american breakfast lunch snack soft buttery crispy ready eat".split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")


def toks(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIAS.get(w, w))
    return out


def detect_brand(raw):
    """return (is_branded, generic_text_without_brand_tokens)"""
    words = raw.split()
    brand_hit = False
    kept = []
    for w in words:
        letters = re.sub(r"[^A-Za-z]", "", w)
        low = letters.lower()
        if (len(letters) >= 3 and letters.isupper()) or low in KNOWN_BRANDS or re.match(r"^[A-Z][a-z]+'s$", w.strip(",()")):
            brand_hit = True
            continue
        kept.append(w)
    # parenthetical capitalised proper name e.g. "(Ritz)"
    for m in re.finditer(r"\(([A-Z][A-Za-z' ]+)\)", raw):
        if m.group(1).strip().lower() in KNOWN_BRANDS or m.group(1)[:1].isupper():
            brand_hit = True
    generic = " ".join(kept)
    return brand_hit, generic


def has(rx, s):
    return bool(re.search(rx, s))


def standard_penalties(i_txt, u_txt, core, iset, uset, usegs):
    p = 0.0
    soft_dairy = has(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt
    table = [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
             (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
             (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
             (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
             (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo", 1.3),
             (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
             (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]
    for u_rx, i_rx, w in table:
        if has(u_rx, u_txt) and not has(i_rx, i_txt):
            p += w
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = has(cook, i_txt), has(cook, u_txt)
    if uc and not ic and not has(r"\braw\b", u_txt):
        p += 2.2
    if ic and not uc and not has(r"\braw\b", u_txt):
        p += 1.0
    di = has(r"\b(dried|dehydrated)\b", i_txt) and not ic
    du = has(r"\b(dried|dehydrated)\b", u_txt) and "from dried" not in u_txt
    if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
        p += 2.4
    for w in ("pickled", "smoked"):
        if (w in i_txt) != (w in u_txt):
            p += 2.4
    cn = has(r"\bcanned\b", u_txt)
    if has(r"\bcanned\b", i_txt) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
        p += 1.7
    if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
        p += 1.4
    if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
        p += 2.6
    forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
    if (set(usegs[0]) & forms) - iset - set(core):
        p += 3.2
    if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
        p += 2.5
    if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
        p += 3.5
    return p


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        branded, generic_u = detect_brand(raw_u)
        paren = " ".join(re.findall(r"\(([^)]*)\)", generic_u))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", generic_u).lower()
        imain = toks(i_txt.split(",")[0])
        usegs = [toks(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uset = set(t for s in usegs for t in s) | set(toks(paren))
        iset = set(toks(i_txt))
        core = [t for t in imain if t not in FILL and not STATE_RX.match(t)] or [t for t in imain if t not in FILL] or imain
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = core[-1]
        head_hit = head in uset
        base = 4.6 * cov + 2.0 * (1.0 if head_hit else 0.0) - (1.4 if not head_hit else 0.0)
        pen = standard_penalties(i_txt, u_txt, core, iset, uset, usegs)
        if not branded:
            return float(base - 0.95 * min(pen, 9.0) + 2.0)
        # ---------------- branded path ----------------
        # product type agreement: the ingredient names a product type that the branded entry also names
        itypes = set(t for t in PRODUCT_TYPES if t in iset)
        utypes = set(t for t in PRODUCT_TYPES if t in uset)
        type_agree = bool(itypes & utypes)
        type_clash = bool(itypes and utypes and not (itypes & utypes))
        # flavour agreement
        i_fl = set(f for f in FLAVOURS if re.search(r"\b" + f, i_txt))
        u_fl = set(f for f in FLAVOURS if re.search(r"\b" + f, u_txt))
        flavour_clash = bool(u_fl - i_fl) and not (u_fl & i_fl) and bool(i_fl or True)
        flavour_missing = bool(i_fl - u_fl)
        base_alt_u = set(b for b in BASE_ALTS if re.search(r"\b" + b, u_txt))
        base_alt_i = set(b for b in BASE_ALTS if re.search(r"\b" + b, i_txt))
        base_clash = bool(base_alt_u - base_alt_i) or bool(base_alt_i - base_alt_u)
        score = 2.0
        if type_agree:
            score += 4.2
        elif type_clash:
            score -= 2.5
        score += 2.0 * cov
        if head_hit:
            score += 1.0
        if flavour_clash and not type_agree:
            score -= 1.2
        elif u_fl - i_fl:
            score -= 1.0 * len(u_fl - i_fl)
        if flavour_missing:
            score -= 1.2 * len(i_fl - u_fl)
        if base_clash:
            score -= 2.2
        score -= 0.5 * min(pen, 7.0)
        return float(score)
    except Exception:
        return 0.0
