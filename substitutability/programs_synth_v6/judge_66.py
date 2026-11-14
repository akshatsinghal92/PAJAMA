import re

# ===========================================================================================
# Processing-intensity axis judge. Cooking/processing words are placed on ONE numeric axis:
#   0 raw / fresh        1 gentle moist heat (boiled, steamed, simmered, poached, microwaved)
#   2 dry heat (baked, roasted, toasted, grilled, broiled)      3 fat cooking (fried, sauteed)
#   4 cured / smoked / pickled      5 dried / dehydrated        1.5 'cooked' (unspecified heat)
# Method agreement = closeness on the axis (absolute difference), with unstated methods treated as
# 0 (raw) for the ingredient and as 'neutral' (compatible with 0 and 1.5) for the USDA entry.
# Identity is the longest-common-subsequence ratio of core words (ordered) so word order helps.
# ===========================================================================================

AXIS_WORDS = [
    (0.0, ["raw", "fresh", "uncooked", "unheated", "unroasted"]),
    (1.0, ["boiled", "steamed", "simmered", "poached", "microwaved", "blanched", "stewed", "braised", "moist heat"]),
    (1.5, ["cooked", "heated", "prepared"]),
    (2.0, ["baked", "roasted", "toasted", "grilled", "broiled", "barbecued", "seared", "dry heat", "charbroiled", "pan-broiled", "panbroiled"]),
    (3.0, ["fried", "deep-fried", "pan-fried", "sauteed", "sautéed", "stir-fried", "battered", "breaded"]),
    (4.0, ["smoked", "cured", "pickled", "brined", "fermented", "salted"]),
    (5.0, ["dried", "dehydrated", "freeze-dried"]),
]
CANNED_RX = re.compile(r"\b(canned|jarred|bottled)\b")
SYN = {"clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea",
       "scallion": "onion", "cilantro": "coriander", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "maize": "corn", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut",
       "dehydrated": "dried", "uncooked": "raw", "unroasted": "raw", "poultry": "chicken", "yoghurt": "yogurt", "fava": "broadbean", "para": "brazil", "ox": "beef", "calf": "veal", "innard": "giblet",
       "cos": "romaine", "granada": "pomegranate", "swede": "rutabaga", "beetroot": "beet", "capsicum": "pepper", "treacle": "molasses", "catsup": "ketchup", "mutton": "lamb", "flat": "wing", "wrap": "tortilla"}
VB = {"concord": "grape", "bing": "cherry", "fuji": "apple", "gala": "apple", "bartlett": "pear", "russet": "potato", "roma": "tomato", "navel": "orange", "hass": "avocado", "portobello": "mushroom", "cremini": "mushroom"}
VSET = {"grape": {"concord", "muscadine", "thompson", "american"}, "squash": {"butternut", "hubbard", "acorn", "spaghetti"}, "apple": {"fuji", "gala", "granny"}, "potato": {"russet", "yukon"}, "orange": {"navel", "valencia"}}
SKIP = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat".split())
STATE = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
FORMS = {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "sandwich", "taco", "entree", "cookie", "syrup", "sauce", "frankfurter", "loaf"}
ORGANS = {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard", "organ"}
DEFAULT_DRIED = {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}
DEFAULT_CANNED = {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}


def tk(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("skin-on", "withskin").replace("skin on", "withskin").replace("meat and skin", "withskin")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(SYN.get(w, w))
    return out


def axis_levels(text):
    lv = []
    for val, words in AXIS_WORDS:
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", text):
                lv.append(val)
                break
    return lv


def lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] + 1 if a[i - 1] == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw_u = " ".join(str(usda_match or "").split())
        kept = [w for w in raw_u.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        raw_nb = " ".join(kept)
        par = " ".join(re.findall(r"\(([^)]*)\)", raw_nb))
        i_txt = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i_txt = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i_txt)
        u_txt = re.sub(r"\([^)]*\)", " ", raw_nb).lower()
        i_main = i_txt.split(",")[0]
        imain = tk(i_main)
        usegs = [tk(s) for s in u_txt.split(",") if s.strip()]
        if not imain or not usegs:
            return 0.0
        iset = set(tk(i_txt))
        flat = [t for s in usegs for t in s]
        uset = set(flat) | set(tk(par))
        ub = uset | set(VB.get(t, t) for t in uset)
        core = [t for t in imain if t not in SKIP and not STATE.match(t)] or [t for t in imain if t not in SKIP] or imain
        core_b = [VB.get(t, t) for t in core]
        # ---------- identity: ordered LCS in two USDA orders, plus set coverage
        rev = [t for s in reversed(usegs) for t in s]
        lcs = max(lcs_len(core_b, [VB.get(t, t) for t in flat]), lcs_len(core_b, [VB.get(t, t) for t in rev]))
        cov = sum(1 for t in core_b if t in ub or t in uset) / float(len(core_b))
        head = core_b[-1] in ub or core_b[-1] in uset
        ident = 2.2 * (lcs / float(len(core_b))) + 2.6 * cov + 2.0 * (1.0 if head else -0.8)
        # ---------- method axis
        i_lv = axis_levels(i_txt)
        u_lv = axis_levels(u_txt + " " + par.lower())
        if "from dried" in u_txt:
            u_lv = [v for v in u_lv if v != 5.0]
        if 5.0 in i_lv and any(v in (1.0, 1.5, 2.0) for v in i_lv):
            i_lv = [v for v in i_lv if v != 5.0]          # reconstituted dried
        i_pos = max(i_lv) if i_lv else 0.0
        if not u_lv:
            u_pos = None
        else:
            u_pos = max(u_lv)
            if 0.0 in u_lv and len(u_lv) > 1:
                u_pos = max(v for v in u_lv if v != 0.0)
        if u_pos is None:
            # generic entry: compatible with raw, mildly costly for processed ingredient
            mpen = 0.5 * i_pos if i_pos >= 2.0 else 0.0
            if i_pos == 1.5 or i_pos == 1.0:
                mpen = 0.4
            if i_pos >= 2.0 and re.search(r"toasted|roasted|grilled|fried|smoked", i_txt):
                mpen = max(mpen, 2.0)
        else:
            gap = abs(i_pos - u_pos)
            mpen = 1.0 * gap if gap <= 1.0 else 1.0 + 1.1 * (gap - 1.0)
            if not i_lv and u_pos > 0.0:
                mpen = max(mpen, 2.1)         # ingredient unmarked (raw) against cooked/processed entry
            if (i_pos >= 4.0) != (u_pos >= 4.0):
                mpen += 0.6                    # crossing into cured/dried territory is not reversible
            if 5.0 in u_lv and 5.0 not in i_lv and set(core) & DEFAULT_DRIED:
                mpen = min(mpen, 0.4)
        if CANNED_RX.search(i_txt) != CANNED_RX.search(u_txt) and not (CANNED_RX.search(u_txt) and set(core) & DEFAULT_CANNED):
            mpen += 1.5
        if ("frozen" in u_txt.split(",")[0].split()[:1]) and "frozen" not in iset:
            mpen += 2.4
        # ---------- supporting penalties
        pen = 0.0
        soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u_txt)) and "cheese" not in u_txt
        organ = bool(set(core) & ORGANS) or "organ" in uset or "variety meat" in u_txt
        for u_rx, i_rx, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                              (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft else 1.0)),
                              (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
                              (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                              (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                              (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
                              (r"\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced", 1.1),
                              (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0),
                              (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2)]:
            if has(u_rx, u_txt) and not has(i_rx, i_txt):
                pen += w
        if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u_txt) if not re.search(r"\b" + x, i_txt)]:
            pen += 1.1
        if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i_txt) and not has(r"garlic|seasoned|marinated", u_txt):
            pen += 1.7
        if has(r"\b(ground|powdered|powder)\b", i_txt) != has(r"\b(ground|powdered|powder)\b", u_txt):
            pen += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i_txt)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u_txt)):
            pen += 2.5
        if (set(usegs[0]) & FORMS) - iset - set(core):
            pen += 3.0
        if has(r"\bstew (meat|beef|lamb|pork)\b", i_main) and "stew" in usegs[0]:
            pen += 3.0
        if has(r"\bbone[- ]in\b", i_txt) and not has(r"\bbone\b", u_txt):
            pen += 1.2
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_txt):
            pen += 3.3
        conflict = 0.0
        for base, vs in VSET.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                conflict = 2.2
        return float(ident - 1.05 * mpen - conflict - 0.9 * min(pen, 9.0) + 2.0)
    except Exception:
        return 0.0
