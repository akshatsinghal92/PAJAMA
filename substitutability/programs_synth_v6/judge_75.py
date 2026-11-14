import re
import math
from difflib import SequenceMatcher

# ===========================================================================================
# Soft-minimum aggregation judge. Five aspect scores (each in [0, 1]) are combined with a
# temperature-controlled SOFT-MIN: smin = -T * ln( mean( exp(-s_k / T) ) ). Small T behaves like
# min (veto), large T like a plain mean. Aspects use the WHOLE ingredient string:
#   food      head noun and food words, fuzzy spelling and parenthetical aliases (either side)
#   detail    lexicon qualifiers (state / form / diet / flavour / variety) covered vs contradicted
#   added     unstated qualifiers on the USDA side
#   method    cooking / preservation compatibility
#   shape     part, form noun and product-type consistency
# ===========================================================================================

NOTES = re.compile(r"\b(optional|to taste|for garnish|for serving|for decoration|for dusting|as needed|divided|plus more|about|approximately|or more|if desired|if needed|room temperature)\b")
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla", flat="wing")
CULT_BASE = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
TYPE_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"},
                 dressing={"italian", "french", "ranch", "caesar", "thousand", "greek", "russian"}, cheese={"cheddar", "swiss", "mozzarella", "provolone", "brie", "camembert", "gouda", "colby", "parmesan"})
HEAD_NOUNS = frozenset("butter sugar oil paste flour milk cream juice syrup sauce vinegar cheese yogurt powder extract starch meal bread".split())
QUAL = {"state": "raw cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted fried dried canned frozen smoked pickled cured",
        "form": "ground powdered whole flaked crumbled", "diet": "lowfat nonfat reduced light skim sweetened unsweetened unsalted salted decaffeinated lean",
        "flavour": "vanilla chocolate strawberry peach blueberry raspberry banana cinnamon maple lemon cherry mint garlic"}
QLEX = {w: k for k, ws in QUAL.items() for w in ws.split()}
STATE_GROUPS = [set("cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed toasted heat".split()), {"dried"}, {"raw", "fresh", "unheated"}, {"canned", "drained", "jarred"}, {"smoked", "cured"}, {"pickled", "brined"}, {"fried", "battered", "breaded"}, {"frozen", "thawed"}]
OPP = [({"raw", "fresh", "unheated"}, set("cooked boiled baked roasted steamed simmered braised broiled grilled sauteed poached stewed heat fried".split())), ({"dried"}, {"raw", "fresh"}), ({"salted"}, {"unsalted"}), ({"sweetened"}, {"unsweetened"}), ({"whole"}, {"ground", "powdered"})]
NOISE = frozenset("thawed chopped diced cubed crushed peeled halved torn rinsed warmed melted softened ripe finely boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety other than not eaten free range farmed mixed species commercial all strong brewed meat by product added moist segment piece wedge cube without salt fat delicious style domesticated new fluid sliced shredded minced atlantic pacific alaska american lunch snack soft buttery crispy ready eat round steak chop fillet tail wing breast thigh shank loin roast rib floret strip chunk kernel heart white seed".split())
DISH = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
DRIED_OK = frozenset("pinenut brazil hazelnut raisin fig date apricot prune agar seaweed mushroom".split())
CANNED_OK = frozenset("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine".split())
BASEALT = ("soy", "almond", "oat", "coconut", "cashew", "vegan", "tofu")
METHOD_PATTERNS = [("smoked", r"\b(smoked|cured|lox)\b"), ("pickled", r"\b(pickled|brined|fermented)\b"), ("dried", r"\b(dried|dehydrated)\b"), ("fat", r"\b(fried|deep-fried|pan-fried|sauteed|sautéed|battered|breaded)\b"),
                   ("dry", r"\b(baked|roasted|toasted|grilled|broiled|barbecued|seared|dry heat|pan-broiled)\b"), ("moist", r"\b(boiled|steamed|simmered|poached|microwaved|stewed|braised|moist heat)\b"),
                   ("generic", r"\b(cooked|heated)\b"), ("canned", r"\b(canned|jarred|bottled)\b"), ("raw", r"\b(raw|uncooked|unheated|fresh)\b")]
MCOST = {}


def _mc(a, b, c):
    MCOST[(a, b)] = MCOST[(b, a)] = c


for _n in ("none", "raw", "moist", "dry", "fat", "smoked", "pickled", "dried", "canned", "generic"):
    _mc(_n, _n, 0.0)
for a_, b_, c_ in [("none", "raw", 0), ("none", "generic", 1.2), ("none", "moist", 2.2), ("none", "dry", 2.3), ("none", "fat", 3.0), ("none", "smoked", 3.2), ("none", "pickled", 3.2), ("none", "dried", 3.0), ("none", "canned", 1.6),
                   ("raw", "moist", 2.2), ("raw", "dry", 2.3), ("raw", "fat", 3.0), ("raw", "smoked", 3.2), ("raw", "pickled", 3.2), ("raw", "dried", 3.0), ("raw", "canned", 1.8), ("raw", "generic", 2.0),
                   ("moist", "dry", 1.0), ("moist", "fat", 1.8), ("moist", "smoked", 2.2), ("moist", "pickled", 2.4), ("moist", "dried", 2.6), ("moist", "canned", 1.0), ("moist", "generic", 0.4),
                   ("dry", "fat", 1.4), ("dry", "smoked", 1.8), ("dry", "pickled", 2.4), ("dry", "dried", 2.4), ("dry", "canned", 1.8), ("dry", "generic", 0.4), ("fat", "smoked", 2.4), ("fat", "pickled", 2.8),
                   ("fat", "dried", 2.8), ("fat", "canned", 2.4), ("fat", "generic", 1.0), ("smoked", "pickled", 2.4), ("smoked", "dried", 1.8), ("smoked", "canned", 2.0), ("smoked", "generic", 1.6),
                   ("pickled", "dried", 2.6), ("pickled", "canned", 1.0), ("pickled", "generic", 2.0), ("dried", "canned", 2.8), ("dried", "generic", 2.2), ("canned", "generic", 1.0)]:
    _mc(a_, b_, c_)
M_ORDER = ("smoked", "pickled", "dried", "fat", "dry", "moist", "generic", "canned", "raw")


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def has(rx, s):
    return bool(re.search(rx, s))


def near(w, pool):
    if w in pool:
        return 1.0
    if len(w) >= 5:
        for x in pool:
            if len(x) >= 5 and x[:3] == w[:3] and SequenceMatcher(None, w, x).ratio() >= 0.87:
                return 0.9
    return 0.0


def soft_min(vals, T):
    return -T * math.log(sum(math.exp(-v / T) for v in vals) / len(vals))


def method_symbol(text, is_ing):
    m = [n for n, rx in METHOD_PATTERNS if re.search(rx, text)]
    if "from dried" in text:
        m = [x for x in m if x != "dried"]
    if is_ing and "dried" in m and {"moist", "dry", "generic"} & set(m):
        m.remove("dried")
    for n in M_ORDER:
        if n in m and not (n == "raw" and len(m) > 1):
            return n
    return "none"


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        par_u = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
        u = re.sub(r"\([^)]*\)", " ", nb).lower()
        i_all = NOTES.sub(" ", re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", str(ingredient or "").lower()))
        par_i = " ".join(re.findall(r"\(([^)]*)\)", i_all))
        i = re.sub(r"\([^)]*\)", " ", i_all)
        main = toks(i.split(",")[0])
        tail = toks(",".join(i.split(",")[1:]))
        segs = [toks(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        uflat = [t for s in segs for t in s]
        pi, pu = set(toks(par_i)), set(toks(par_u))
        uset = set(uflat) | pu
        iset = set(main) | set(tail) | pi
        ub = uset | set(CULT_BASE.get(t, t) for t in uset)
        # head product nouns always remain core words
        core = [t for t in main if (t not in NOISE and t not in QLEX) or t in HEAD_NOUNS] or [t for t in main if t not in QLEX] or main
        # ---------------------------------------------------------- aspect 1: food
        hits = [max(near(t, ub), near(CULT_BASE.get(t, t), ub)) for t in core]
        cov = sum(hits) / float(len(core))
        head = hits[-1]
        # parenthetical alias on the ingredient (shungiku) or USDA (Pomegranates ... (granada)) can rescue the head
        if head == 0.0 and (pi & uset or set(core) & pu):
            head = 0.8
            cov = max(cov, 0.8)
        extras = [t for t in segs[0] if t not in core and t not in iset and t not in NOISE and t not in QLEX and t not in ("fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal", "seaweed")]
        food = 0.55 * cov + 0.30 * head + 0.15 * (1.0 if not extras else max(0.0, 1.0 - 0.34 * len(extras)))
        for base, vs in TYPE_SETS.items():
            named = vs & iset
            if named and (base in uset or base in ("dressing", "cheese")) and not (named & uset) and (vs & uset):
                food *= 0.4
        if len(core) >= 2 and has(r"\band\b", i.split(",")[0]) and not has(r"\band\b", u) and cov < 1.0:
            food *= 0.6
        ia, ua = set(x for x in BASEALT if x in iset), set(x for x in BASEALT if x in uset)
        if (ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua)):
            food *= 0.6
        # ---------------------------------------------------------- aspect 2: detail
        cov_q = contra_q = miss_q = 0
        for t in dict.fromkeys(main + tail):
            if t not in QLEX:
                continue
            gi = [k for k, g in enumerate(STATE_GROUPS) if t in g]
            if t in uset or (gi and any(x in STATE_GROUPS[gi[0]] for x in uset)):
                cov_q += 1
            elif any((t in a and (b & uset)) or (t in b and (a & uset)) for a, b in OPP):
                contra_q += 1
            else:
                miss_q += 1 if QLEX[t] in ("diet", "flavour") else 0.5
        detail = math.exp(-0.9 * contra_q - 0.35 * miss_q) * (1.0 if (cov_q + contra_q + miss_q) else 0.95)
        # ---------------------------------------------------------- aspect 3: added qualifiers
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        organ = "organ" in uset or bool(set(core) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard"})
        full_i = i + " " + par_i
        cost = 0.0
        for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0), (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                          (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                          (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                          (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                          (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3), (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1),
                          (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2), (r"\bkernel\b", r"kernel", 1.5)]:
            if has(ru, u) and not has(ri, full_i):
                cost += w
        if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, full_i)]:
            cost += 1.1
        added = math.exp(-0.5 * min(cost, 8.0))
        # ---------------------------------------------------------- aspect 4: method
        si, su = method_symbol(full_i, True), method_symbol(u + " " + par_u, False)
        mc = MCOST.get((si, su), 2.0)
        if su == "dried" and si != "dried" and set(core) & DRIED_OK:
            mc = min(mc, 0.4)
        if su == "canned" and si != "canned" and set(core) & CANNED_OK:
            mc = min(mc, 0.3)
        if si == "canned" and su in ("none", "raw", "generic") and set(core) & CANNED_OK:
            mc = min(mc, 0.3)
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            mc += 2.4
        method = math.exp(-0.55 * mc)
        # ---------------------------------------------------------- aspect 5: shape
        sc = 0.0
        if (set(segs[0]) & DISH) - iset - set(core):
            sc += 3.0
        if has(r"\bstew (meat|beef|lamb|pork)\b", full_i) and "stew" in segs[0]:
            sc += 3.0
        if has(r"\b(ground|powdered|powder)\b", full_i) != has(r"\b(ground|powdered|powder)\b", u):
            sc += 1.8
        if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", full_i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)):
            sc += 2.4
        if has(r"\bbone[- ]in\b", full_i) and not has(r"\bbone\b", u):
            sc += 1.1
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            sc += 3.3
        shape = math.exp(-0.5 * min(sc, 8.0))
        aspects = [food, detail, added, method, shape]
        weights = [0.36, 0.12, 0.2, 0.18, 0.14]
        mean = sum(w * a for w, a in zip(weights, aspects))
        smin = soft_min(aspects, 0.25)
        return float(10.0 * (0.5 * mean + 0.5 * smin) + 0.3 * food)
    except Exception:
        return 0.0
