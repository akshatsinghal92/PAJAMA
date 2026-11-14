import re
from difflib import SequenceMatcher

# =====================================================================================
# Forgiving matcher + polarity veto. Stage A resolves "is this the same food" leniently
# (aliases, hierarchy, parentheses, brand-category rule, fuzzy spelling). Stage B subtracts
# penalties for opposite poles and for one-sided qualifiers a diner would notice.
# =====================================================================================

ALIAS_PAIRS = [("clementine", "tangerine"), ("mandarin", "tangerine"), ("satsuma", "tangerine"), ("filbert", "hazelnut"), ("linseed", "flaxseed"),
               ("crawfish", "crayfish"), ("prawn", "shrimp"), ("garbanzo", "chickpea"), ("scallion", "onion"), ("cilantro", "coriander"),
               ("aubergine", "eggplant"), ("courgette", "zucchini"), ("rocket", "arugula"), ("maize", "corn"), ("bison", "buffalo"),
               ("pinyon", "pinenut"), ("pinon", "pinenut"), ("dehydrated", "dried"), ("uncooked", "raw"), ("unroasted", "raw"), ("poultry", "chicken"),
               ("yoghurt", "yogurt"), ("fava", "broadbean"), ("ox", "beef"), ("calf", "veal"), ("innard", "giblet"), ("cos", "romaine"), ("granada", "pomegranate"),
               ("swede", "rutabaga"), ("beetroot", "beet"), ("capsicum", "pepper"), ("treacle", "molasses"), ("catsup", "ketchup"), ("mutton", "lamb"),
               ("puree", "sauce"), ("purée", "sauce")]
ALIAS = dict(ALIAS_PAIRS)
GENERIC_HEADS = {"fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "cereal", "fruit", "vegetable", "game", "organ", "sausage", "bread", "cracker", "tortilla", "granola"}
FILL = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american breakfast lunch".split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained)$")
VARIETY_BASE = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
OPPOSITES = [(r"\bunsalted\b|\bwithout salt\b|\bno salt\b|\bno added salt\b|\bsalt[- ]free\b", r"\bsalted\b|\bwith salt\b|\bsalt added\b"),
             (r"\bunsweetened\b|\bsugar[- ]free\b|\bno added sugar\b|\bno sugar\b", r"\bsweetened\b|\bwith sugar\b|\bsugar added\b|\badded sugar\b"),
             (r"\bno added fat\b|\bfat[- ]free\b|\bnon ?fat\b|\bwithout fat\b", r"\bfat added\b|\badded fat\b|\bwith fat\b|\bbuttered\b"),
             (r"\bskinless\b|\bwithout skin\b|\bskin removed\b|\bmeat only\b", r"\bwith skin\b|\bskin[- ]on\b|\bmeat and skin\b"),
             (r"\bboneless\b|\bbone removed\b|\bwithout bone\b", r"\bbone[- ]in\b|\bwith bone\b"),
             (r"\bseedless\b|\bwithout seeds?\b|\bpitted\b", r"\bwith seeds?\b|\bseeded\b"),
             (r"\bhulled\b|\bshelled\b|\bdehulled\b", r"\bunhulled\b|\bin the shell\b|\bin shell\b|\bwith shells?\b"),
             (r"\bdecaffeinated\b|\bdecaf\b|\bcaffeine[- ]free\b", r"\bcaffeinated\b(?<!de)"),
             (r"\bunheated\b|\braw\b|\buncooked\b", r"\bcooked\b|\bboiled\b|\bbaked\b|\bbroiled\b|\bsimmered\b|\bbraised\b"),
             (r"\bfresh\b", r"\bdried\b|\bcanned\b|\bpickled\b")]


def stem_tokens(s):
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(ALIAS.get(w, w))
    return out


def fuzzy_in(word, pool):
    if word in pool:
        return 1.0
    if len(word) >= 5:
        for x in pool:
            if len(x) >= 5 and x[:3] == word[:3] and SequenceMatcher(None, word, x).ratio() >= 0.87:
                return 0.9
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        u_nobrand = " ".join(w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        branded = u_nobrand != raw
        par_toks = set(stem_tokens(" ".join(re.findall(r"\(([^)]*)\)", u_nobrand))))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", u_nobrand).lower()
        i_main = i_txt.split(",")[0]
        imain = stem_tokens(i_main)
        usegs = [stem_tokens(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uset = set(t for s in usegs for t in s) | par_toks
        iset = set(stem_tokens(i_txt))
        core = [t for t in imain if t not in FILL and not STATE_RX.match(t)] or [t for t in imain if t not in FILL] or imain
        core = [VARIETY_BASE.get(t, t) for t in core]
        uset_b = uset | set(VARIETY_BASE.get(t, t) for t in uset)
        # ------------------------------------------------------------ stage A: forgiving identity
        matched = [fuzzy_in(t, uset_b) for t in core]
        cov = sum(matched) / float(len(core))
        head_m = matched[-1]
        ident = 4.6 * cov + 2.0 * head_m - (1.4 if head_m == 0 else 0.0)
        # hierarchy: first USDA segment a bare generic category, ingredient head found in later segments => fine
        if usegs[0] and all(t in GENERIC_HEADS for t in usegs[0]) and head_m:
            ident += 0.4
        # branded packaged goods: ingredient names the category word of the entry
        if branded and set(core) & {"cereal", "cracker", "tortilla", "granola"} and set(core) & set(usegs[0]):
            ident = max(ident, 6.0)
        # ------------------------------------------------------------ stage B: polarity and qualifiers
        pen = 0.0
        for a_rx, b_rx in OPPOSITES:
            ia, ib = bool(re.search(a_rx, i_txt)), bool(re.search(b_rx, i_txt))
            ua, ub = bool(re.search(a_rx, u_txt)), bool(re.search(b_rx, u_txt))
            if (ia and ub and not ua) or (ib and ua and not ub):
                pen += 2.8 if a_rx.startswith(r"\bunheated") or a_rx.startswith(r"\bfresh") else 3.8
        # one-sided qualifiers a diner notices (USDA adds, ingredient silent)
        soft_dairy = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        q = [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
             (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
             (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
             (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
             (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant", 1.3),
             (r"new zealand|northern plains|hawaii|beaked|native|shoshone|\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced|new zealand", 1.3),
             (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8)]
        for u_rx, i_rx, w in q:
            if re.search(u_rx, u_txt) and not re.search(i_rx, i_txt):
                pen += w
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_txt)), bool(re.search(cook, u_txt))
        if uc and not ic and not re.search(r"\braw\b", u_txt):
            pen += 2.2
        if ic and not uc and not re.search(r"\braw\b", u_txt):
            pen += 1.0
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
            pen += 1.2
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.6
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(usegs[0]) & forms) - iset - set(core):
            pen += 3.2
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            pen += 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.5
        return float(ident - 0.95 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
