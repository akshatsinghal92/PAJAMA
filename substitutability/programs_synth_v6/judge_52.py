import re
import math

# ----------------------------------------------------------------------------------------------
# Evidence-ledger judge: positive evidence (same food) and negative evidence (unstated qualifiers,
# state/form changes) are accumulated in two separate ledgers and combined by a soft difference.
# ----------------------------------------------------------------------------------------------

_ALIASES = [
    ("clementine", "tangerine"), ("mandarin", "tangerine"), ("satsuma", "tangerine"), ("filbert", "hazelnut"),
    ("linseed", "flaxseed"), ("crawfish", "crayfish"), ("prawn", "shrimp"), ("garbanzo", "chickpea"),
    ("scallion", "onion"), ("cilantro", "coriander"), ("aubergine", "eggplant"), ("courgette", "zucchini"),
    ("rocket", "arugula"), ("maize", "corn"), ("bison", "buffalo"), ("pinyon", "pinenut"), ("pinon", "pinenut"),
    ("dehydrated", "dried"), ("uncooked", "raw"), ("poultry", "chicken"), ("yoghurt", "yogurt"), ("fava", "broadbean"),
    ("swede", "rutabaga"), ("beetroot", "beet"), ("capsicum", "pepper"), ("treacle", "molasses"), ("catsup", "ketchup"),
    ("innard", "giblet"), ("para nut", "brazil nut"),
]
_PACKAGED_CATEGORIES = {"cereal": r"\bcereals?\b", "cracker": r"\bcrackers?\b", "tortilla": r"\btortillas?\b",
                        "granola": r"\bgranola\b", "syrup": r"\bsyrups?\b", "beverage": r"\b(beverage|drink)\b"}
_WS = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style domesticated new fluid white sliced atlantic pacific alaska american".split())
_STATE_TOK = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet)$")


def _norm_text(s):
    s = s.lower().replace("-", " ")
    for a, b in _ALIASES:
        s = re.sub(r"\b" + a + r"s?\b", b, s)
    return s


def _toks(s):
    out = []
    for w in re.findall(r"[a-z]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(w)
    return out


def judging_function(ingredient, usda_match):
    try:
        u_raw = " ".join(w for w in str(usda_match or "").split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))
        had_brand = u_raw != " ".join(str(usda_match or "").split())
        paren = _toks(_norm_text(" ".join(re.findall(r"\(([^)]*)\)", u_raw))))
        i_txt = _norm_text(re.sub(r"\([^)]*\)", " ", str(ingredient or "")))
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = _norm_text(re.sub(r"\([^)]*\)", " ", u_raw))
        i_main = i_txt.split(",")[0]
        imain = _toks(i_main)
        usegs = [_toks(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        uflat = [t for s in usegs for t in s]
        uset = set(uflat) | set(paren)
        iset = set(_toks(i_txt))
        core = [t for t in imain if t not in _WS and not _STATE_TOK.match(t)] or [t for t in imain if t not in _WS] or imain
        head = core[-1]

        pos = []   # positive evidence ledger
        neg = []   # negative evidence ledger

        # --- positive evidence
        matched = [t for t in core if t in uset]
        pos.append(("coverage", 5.0 * len(matched) / float(len(core))))
        if head in uset:
            pos.append(("head", 1.8))
            if head in usegs[0]:
                pos.append(("head_first", 0.5))
        if set(usegs[0]) and set(usegs[0]) <= (iset | set(core) | {"raw", "fluid", "nfs"}):
            pos.append(("first_segment_explained", 1.2))
        if head in set(paren) and head not in set(uflat):
            pos.append(("paren_alias", 2.0))
        # packaged-goods category rule: generic ingredient word names the category of a branded USDA entry
        for cat, rx in _PACKAGED_CATEGORIES.items():
            if re.search(rx, i_main) and re.search(rx, u_txt.split(",")[0]) and had_brand:
                pos.append(("brand_category_" + cat, 2.5))
        # exact set equality on the ingredient phrase and the USDA first segment
        if set(core) == set(t for t in usegs[0] if t not in _WS and not _STATE_TOK.match(t)):
            pos.append(("exact_phrase", 1.0))

        # --- negative evidence
        def has(rx, s):
            return bool(re.search(rx, s))
        soft_dairy = has(r"\b(yogurt|kefir|milk)\b", u_txt) and "cheese" not in u_txt
        meat = has(r"\b(beef|pork|lamb|veal|chicken|turkey|buffalo)\b", u_txt) or "variety meat" in u_txt
        table = [
            (r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
            (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft_dairy else 1.0)),
            (r"sugar ?free|unsweetened|sweetened|with sugar", r"sweet|sugar", 1.6),
            (r"with salt|\bsalted\b|salt added", r"salt", 1.2),
            (r"fat added|added fat|made with oil", r"saut|fried|butter|oil|fat", 1.2),
            (r"lactose|decaf|\bdiet\b|low calorie", r"lactose|decaf|diet", 1.8),
            (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
            (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant", 1.3),
            (r"new zealand|northern plains|hawaii|beaked|native", r"new zealand|hawaii|native", 1.4 * (0.5 if meat else 1.0)),
            (r"\bimported\b", r"imported", 0.7 * (0.4 if meat else 1.0)),
            (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ](bake|fry|serve)", r"deli|lunch|sliced", 1.1),
            (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.8),
            (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
        ]
        for u_rx, i_rx, w in table:
            if has(u_rx, u_txt) and not has(i_rx, i_txt):
                neg.append((u_rx[:12], w))
        flav = re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt)
        if any(not has(r"\b" + x, i_txt) for x in flav):
            neg.append(("flavour", 1.2))
        if has(r"unsalted|unsweetened|low ?fat|nonfat|fat ?free|sugar ?free|reduced", i_txt) and not has(r"unsalted|unsweetened|low ?fat|nonfat|fat ?free|sugar ?free|reduced|light|lite", u_txt):
            neg.append(("stated_dropped", 0.9))
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = has(cook, i_txt), has(cook, u_txt)
        if uc and not ic and not has(r"\braw\b", u_txt):
            neg.append(("cook_usda_only", 2.2))
        if ic and not uc:
            neg.append(("cook_ing_only", 1.3))
        di = has(r"\b(dried|dehydrated)\b", i_txt) and not ic
        du = has(r"\b(dried|dehydrated)\b", u_txt) and "from dried" not in u_txt
        if di != du and not (du and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune"}):
            neg.append(("dried", 2.4))
        for w in ("pickled", "smoked"):
            if (w in i_txt) != (w in u_txt):
                neg.append((w, 2.4))
        cn = has(r"\bcanned\b", u_txt)
        if has(r"\bcanned\b", i_txt) != cn and not (cn and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            neg.append(("canned", 1.7))
        if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
            neg.append(("ground", 1.2))
        if set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", u_txt)):
            neg.append(("part", 2.6))
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
        if (set(usegs[0]) & forms) - iset:
            neg.append(("transform", 3.2))
        if usegs[0] and usegs[0][0] in ("frozen", "dried", "canned", "smoked") and usegs[0][0] not in iset:
            neg.append(("front_state", 2.5))
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            neg.append(("restaurant", 3.5))
        # modifier absence
        for t in core[:-1]:
            if t not in uset:
                neg.append(("modifier_missing", 1.0))

        p = sum(v for _, v in pos)
        n = sum(v for _, v in neg)
        return float(p - 0.95 * min(n, 7.0) + 1.0)
    except Exception:
        return 0.0
