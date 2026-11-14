import re

# unstated-qualifier patterns on the USDA side: (regex, weight, 'dairy-soft' flag)
_Q_PATTERNS = [
    (r"\blow ?sodium\b|\breduced sodium\b|\bno salt added\b|\bsodium free\b", 2.0),
    (r"\bfat ?free\b|\bnon ?fat\b|\bskim\b", 2.0),
    (r"\blow ?fat\b|\breduced fat\b|\blite\b|\blight\b|\b\d% milkfat\b|\b2% milkfat\b|\b1% milkfat\b", 1.9),
    (r"\bsugar ?free\b|\bno sugar added\b|\bunsweetened\b", 1.7),
    (r"\bsweetened\b|\bwith sugar\b|\bsugars added\b", 1.6),
    (r"\bwith salt\b|\bsalted\b|\bsalt added\b", 1.3),
    (r"\bfat added\b|\badded fat\b|\bmade with oil\b|\bwith oil\b", 1.3),
    (r"\bflavored\b|\bflavor\b", 1.2),
    (r"\bfortified\b|\benriched\b|\bwith added vitamin|\bvitamin d\b|\bvitamin a\b", 0.6),
    (r"\blactose[- ]reduced\b|\blactose free\b", 1.8),
    (r"\bdecaffeinated\b|\bdecaf\b|\bcaffeine free\b", 1.8),
    (r"\bdiet\b|\blow calorie\b", 1.8),
    (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", 2.0),
    (r"\bmade (with|from)\b|\bprepared (with|from)\b|\bfrom mix\b|\bdry mix\b", 1.4),
    (r"\bimported\b|\bnew zealand\b|\bnorthern plains\b|\bhawaii\b|\bbeaked\b|\bnative\b", 1.4),
    (r"\bdeli\b|\bluncheon\b|\bprepackaged\b|\bshelf stable\b|\bready[- ]to[- ](bake|fry|eat|serve)\b", 1.1),
    (r"\bhydrogenated\b|\bcommercial(ly)? prepared\b|\bhome recipe\b", 0.8),
    (r"\bbreaded\b|\bbattered\b|\bcoated\b|\bglazed\b|\bcandied\b", 1.8),
    (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|honey|maple|garlic|lemon|mint)\b", 1.2),
]
_SOFT_DAIRY = re.compile(r"\b(yogurt|yoghurt|kefir|milk)\b")
_FOODISH_STOP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style lean domesticated new fluid white sliced".split())
_STEMS = {"yoghurt": "yogurt", "clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "maize": "corn", "bison": "buffalo", "pinyon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine", "ox": "beef", "calf": "veal", "para": "brazil", "innard": "giblet", "rocket": "arugula"}


def _clean_ing(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    return re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", s)


def _brandless(raw):
    return " ".join(w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()))


def _toks(s):
    out = []
    for w in re.findall(r"[a-z]+", s.replace("-", " ")):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(_STEMS.get(w, w))
    return out


def _added_qualifier_load(ing_text, usda_text):
    """sum of weights for qualifier patterns present in USDA but NOT in the ingredient text"""
    load = 0.0
    soft = bool(_SOFT_DAIRY.search(usda_text)) and "cheese" not in usda_text
    for pat, w in _Q_PATTERNS:
        in_u = re.search(pat, usda_text)
        in_i = re.search(pat, ing_text)
        if in_u and not in_i:
            ww = w
            if soft and ("fat" in pat or "lite" in pat or "milkfat" in pat):
                ww = w * 0.35          # dairy-drink fat level is rarely noticed
            if "flavored|flavor" in pat and "flavor" in ing_text:
                ww = 0.0
            load += ww
    return load


def judging_function(ingredient, usda_match):
    try:
        i_text = _clean_ing(str(ingredient or ""))
        u_text = re.sub(r"\([^)]*\)", " ", _brandless(str(usda_match or "")).lower())
        i_main = i_text.split(",")[0]
        itok = _toks(i_main)
        utok_segs = [_toks(s) for s in u_text.split(",") if s.strip()]
        if not itok or not utok_segs:
            return 0.0
        uflat = [t for s in utok_segs for t in s]
        uset = set(uflat)
        core = [t for t in itok if t not in _FOODISH_STOP and not re.match(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|dried|canned|frozen|smoked|pickled|fried|ground|powdered|lowfat|nonfat|reduced|light|sweetened|unsweetened|flavored|diet|batter|butter)$", t)] or [t for t in itok if t not in _FOODISH_STOP] or itok
        head = core[-1]
        coverage = sum(1 for t in core if t in uset) / float(len(core))
        load = _added_qualifier_load(i_text, u_text)
        score = 5.0 * coverage + (1.6 if head in uset else -1.4) - 0.95 * min(load, 6.0)
        # reverse direction: qualifiers stated by the ingredient that USDA drops (lesser)
        stated_drop = 0.0
        for pat, w in _Q_PATTERNS:
            if re.search(pat, i_text) and not re.search(pat, u_text):
                stated_drop += 0.45 * w
        score -= min(stated_drop, 2.0)
        # states
        cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
        ic, uc = bool(re.search(cook, i_text)), bool(re.search(cook, u_text))
        if uc and not ic and not re.search(r"\braw\b", u_text):
            score -= 2.2
        if ic and not uc:
            score -= 1.3
        dry_i = bool(re.search(r"\b(dried|dehydrated)\b", i_text)) and not ic
        dry_u = bool(re.search(r"\b(dried|dehydrated)\b", u_text)) and "from dried" not in u_text
        if dry_i != dry_u:
            score -= 2.4
        for w in ("pickled", "smoked"):
            if (w in i_text) != (w in u_text):
                score -= 2.4
        if bool(re.search(r"\bcanned\b", i_text)) != bool(re.search(r"\bcanned\b", u_text)) and not (re.search(r"\bcanned\b", u_text) and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"}):
            score -= 1.7
        if bool(re.search(r"\b(ground|powdered|powder)\b", i_text)) != bool(re.search(r"\b(ground|powdered|powder)\b", u_text)):
            score -= 1.2
        if set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", i_text)) != set(re.findall(r"\b(leaf|leaves|bone|peel|stem|shell)\b", u_text)):
            score -= 2.6
        first = utok_segs[0]
        forms = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf", "icecream"}
        if (set(first) & forms) - set(_toks(i_text)):
            score -= 3.2
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in i_text:
            score -= 2.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_text):
            score -= 3.5
        return float(score + 2.0)
    except Exception:
        return 0.0
