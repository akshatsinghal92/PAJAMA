import re

# ---------------------------------------------------------------------------------------------
# Commercial-level agreement judge.
#   * commercial markers on the USDA side:   brand tokens, 'commercially prepared', 'ready-to-eat',
#     'single serving', 'enriched', 'ready-to-serve', numeric pack sizes ...
#   * commercial markers on the ingredient:  'store-bought', 'bagged', 'packaged', 'instant', 'canned'...
# A packaged-goods ingredient (cereal, crackers, dressing...) legitimately matches commercial entries;
# a plain whole-food ingredient should not be matched to a flavoured / plant-based branded product.
# ---------------------------------------------------------------------------------------------

NOT_BRANDS = {"nfs", "ns", "usda", "uht", "msg", "bbq", "gmo", "dha", "rtd", "rtu"}
BRAND_WORDS = {"ritz", "oreo", "cheerios", "kelloggs", "quaker", "nabisco", "pillsbury", "heinz", "hersheys", "silk", "chobani", "dannon", "yoplait", "lifeway", "post", "mission", "kraft",
               "nestle", "campbells", "powerade", "gatorade", "goya", "bertolli", "hellmanns", "smuckers", "knorr", "lipton", "tyson", "triscuit", "goldfish", "nutella", "jif", "skippy", "welchs",
               "gerber", "oikos", "fage", "stonyfield", "morningstar", "boca", "gardein", "beyond", "impossible", "thins", "valley", "foods"}
COMMERCIAL_USDA = [r"commercially prepared", r"ready[- ]to[- ](eat|serve|bake|fry)", r"single serving", r"enriched", r"fortified", r"shelf stable", r"\bcommercial\b", r"\bprepackaged\b", r"\bassorted brands\b", r"\bstore brand\b", r"restaurant|fast food"]
COMMERCIAL_ING = [r"store[- ]bought", r"\bbagged\b", r"\bpackaged\b", r"\binstant\b", r"\bbottled\b", r"\bjarred\b", r"\bcanned\b", r"from (a )?(tube|jar|can|box|bag)", r"\bmicrowave\b", r"\bready\b"]
PACKAGED_TYPES = ("cereal", "cracker", "tortilla", "cookie", "granola", "syrup", "chip", "pasta", "noodle", "beverage", "drink", "dressing", "popcorn", "pretzel", "mayonnaise", "ketchup", "mustard", "sauce", "bread", "jerky", "bar", "yogurt", "oatmeal", "wrap", "marinara")
FLAVOURS = ("vanilla", "chocolate", "strawberry", "peach", "blueberry", "raspberry", "banana", "cinnamon", "maple", "caramel", "honey", "lemon", "cherry", "mint", "coconut", "mocha", "pumpkin", "butter", "garlic")
PLANT_BASE = ("soy", "almond", "oat", "coconut", "rice", "cashew", "pea", "vegan", "tofu", "plant")
ALIAS = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet", "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "wrap": "tortilla"}
FILL = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat store bought bagged packaged instant microwave tube jar".split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")


def tk(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIAS.get(w, w))
    return out


def brand_tokens(raw):
    found, kept = [], []
    for w in raw.split():
        letters = re.sub(r"[^A-Za-z]", "", w)
        low = letters.lower()
        is_caps = len(letters) >= 3 and letters.isupper() and low not in NOT_BRANDS
        if is_caps or low in BRAND_WORDS or re.match(r"^[A-Z][a-z]+'s$", w.strip(",()")):
            found.append(low)
        else:
            kept.append(w)
    return found, " ".join(kept)


def rx_any(patterns, s):
    return sum(1 for p in patterns if re.search(p, s))


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        brands, generic_u = brand_tokens(raw_u)
        for m in re.finditer(r"\(([A-Z][A-Za-z' ]{2,})\)", raw_u):
            if m.group(1).split()[0].lower() in BRAND_WORDS:
                brands.append(m.group(1).lower())
        par = " ".join(re.findall(r"\(([^)]*)\)", generic_u))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", generic_u).lower()
        imain = tk(i_txt.split(",")[0])
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uset = set(t for s in usegs for t in s) | set(tk(par))
        iset = set(tk(i_txt))
        core = [t for t in imain if t not in FILL and not STATE_RX.match(t)] or [t for t in imain if t not in FILL] or imain
        head = core[-1]
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head_hit = head in uset
        # --- commercial level
        u_level = len(brands) + rx_any(COMMERCIAL_USDA, u_txt + " " + par.lower())
        i_level = rx_any(COMMERCIAL_ING, i_txt)
        packaged_i = bool(set(core) & set(PACKAGED_TYPES))
        packaged_u = bool(set(t for t in uset) & set(PACKAGED_TYPES))
        # commercial entry for a plain whole-food ingredient is a (mild) mismatch; for packaged ingredient it is expected
        if u_level and not packaged_i and not i_level:
            comm = -0.9 * min(u_level, 2)
        elif u_level and (packaged_i or i_level):
            comm = 0.8
        else:
            comm = 0.0
        # --- flavour / base consistency (matters most for branded goods)
        i_fl = set(f for f in FLAVOURS if re.search(r"\b" + f, i_txt))
        u_fl = set(f for f in FLAVOURS if re.search(r"\b" + f, u_txt))
        fl_pen = 1.3 * len(u_fl - i_fl) + 1.0 * len(i_fl - u_fl)
        if brands and (u_fl & i_fl):
            fl_pen = max(0.0, fl_pen - 1.0)
        pb_u = set(b for b in PLANT_BASE if re.search(r"\b" + b, u_txt))
        pb_i = set(b for b in PLANT_BASE if re.search(r"\b" + b, i_txt))
        base_pen = 2.2 if (pb_u ^ pb_i) and not (pb_u & pb_i) and not ({"vegan", "plant"} & (pb_u | pb_i) and {"vegan", "plant"} & (pb_u | pb_i) and (pb_u | pb_i) & {"soy", "tofu", "vegan"}) else 0.0
        ident = 4.6 * cov + 2.0 * (1.0 if head_hit else -0.7)
        # product-type rule for brands: generic type word in ingredient equals generic part of entry
        if brands and packaged_i and (set(core) & set(usegs[0])):
            ident = max(ident, 6.4)
        # --- qualifiers and states
        pen = 0.0
        soft_dairy = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                              (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.3),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]:
            if re.search(u_rx, u_txt) and not re.search(i_rx, i_txt):
                pen += w
        if re.search(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not re.search(r"garlic|seasoned|marinated", u_txt):
            pen += 1.8
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
        if uc and not ic and not re.search(r"\braw\b", u_txt):
            pen += 2.2
        if ic and not uc:
            pen += 2.0 if re.search(r"toasted|roasted|grilled|fried", i_txt) else 1.2
        di = bool(re.search(r"\b(dried|dehydrated)\b", i_txt)) and not ic
        du = bool(re.search(r"\b(dried|dehydrated)\b", u_txt)) and "from dried" not in u_txt
        if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            pen += 2.4
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                pen += 2.4
        cn = bool(re.search(r"\bcanned\b", u_txt))
        if bool(re.search(r"\bcanned\b", i_txt)) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
            pen += 1.7
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_txt)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_txt)):
            pen += 1.4
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.6
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(usegs[0]) & forms) - iset - set(core):
            pen += 3.2
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.5
        return float(ident + comm - fl_pen - base_pen - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
