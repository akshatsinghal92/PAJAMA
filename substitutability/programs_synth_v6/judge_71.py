import re
from collections import namedtuple

# ===========================================================================================
# Frame-comparison judge. Each food string is parsed into a Frame with slots
#     species (animal/plant word), part, grind, method, quals (frozenset), product, pack
# and two frames are compared slot by slot with per-slot compatibility functions. The part slot
# keeps a list so lists of parts ("neck and gizzard") are compared by their WORST member.
# ===========================================================================================

Frame = namedtuple("Frame", "species part grind method quals product pack core")

SPECIES_WORDS = frozenset(("beef veal pork lamb mutton chicken turkey duck goose buffalo rabbit goat deer salmon tuna cod fish shrimp crab lobster crayfish egg apple pear peach plum cherry grape "
                           "orange tangerine lemon lime grapefruit mango papaya banana pomegranate pineapple melon berry raspberry strawberry blueberry blackberry cranberry coconut fig date "
                           "potato yam carrot beet radish turnip onion garlic leek tomato pepper cucumber squash zucchini eggplant pumpkin broccoli cauliflower cabbage kale spinach lettuce "
                           "romaine celery mushroom olive corn bean pea lentil chickpea broadbean soy peanut almond walnut pecan hazelnut pistachio cashew pinenut brazil flaxseed sesame "
                           "rice wheat oat barley quinoa amaranth cocoa tea coffee").split())
PART_SETS = [("breast", {"breast", "tender"}), ("leg", {"thigh", "drumstick", "drum", "leg", "ham", "round", "rump", "tip"}), ("wing", {"wing", "flat", "drumette"}),
             ("shoulder", {"chuck", "blade", "shoulder", "arm", "picnic", "butt"}), ("loin", {"loin", "sirloin", "tenderloin", "strip", "chop", "steak", "porterhouse"}),
             ("rib", {"rib", "ribeye", "spareribs"}), ("shank", {"shank", "crosscut", "hock", "brisket", "flank", "plate", "belly"}), ("offal", {"liver", "heart", "kidney", "tongue", "giblet", "gizzard", "tripe", "brain", "organ"}),
             ("extremity", {"neck", "tail", "foot", "feet", "back"}), ("skin", {"skin"}), ("bone", {"bone"}), ("yolk", {"yolk"}), ("whiteegg", {"white"}),
             ("leaf", {"leaf", "leave", "green", "sprout"}), ("root", {"root", "bulb"}), ("stem", {"stem", "stalk", "shoot"}), ("seed", {"seed", "kernel", "pod"}), ("flower", {"flower", "floret", "head"}),
             ("peel", {"peel", "zest", "rind"}), ("pulp", {"pulp"}), ("fillet", {"fillet", "filet", "roe"})]
PART_OF = {}
for _k, _ws in PART_SETS:
    for _w in _ws:
        PART_OF[_w] = _k
# cost between part classes when both present
PART_COST = {}


def _pc(a, b, c):
    PART_COST[(a, b)] = PART_COST[(b, a)] = c


FLESH = ["breast", "leg", "wing", "shoulder", "loin", "rib", "shank", "fillet"]
for a_ in FLESH:
    for b_ in FLESH:
        _pc(a_, b_, 0.0 if a_ == b_ else 2.2)
_pc("loin", "shoulder", 1.6)
_pc("leg", "loin", 1.6)
_pc("leg", "shoulder", 1.6)
_pc("rib", "loin", 1.4)
_pc("shank", "shoulder", 1.4)
for off in ("offal", "extremity", "skin", "bone"):
    for f_ in FLESH + ["offal", "extremity", "skin", "bone"]:
        if f_ != off:
            _pc(off, f_, 3.0)
    _pc(off, off, 0.0)
PLANTP = ["leaf", "root", "stem", "seed", "flower", "peel", "pulp", "yolk", "whiteegg"]
for a_ in PLANTP:
    for b_ in PLANTP:
        _pc(a_, b_, 0.0 if a_ == b_ else 3.0)
_pc("stem", "leaf", 2.4)
_pc("flower", "stem", 2.4)
EDIBLE_PART = frozenset("pomegranate amaranth flaxseed sesame chia sunflower poppy romaine lettuce artichoke palm celery".split())

AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla")
NOISE = frozenset(("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional "
                   "boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten "
                   "free range farmed wild mixed species commercial all strong brewed round meat by product added moist segment piece strip wedge chunk cube without salt fat fresh "
                   "raw whole delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat").split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
PRODUCTS = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf yogurt cheese bread cereal cracker tortilla".split())
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})
METHODS = [("smoked", r"\b(smoked|cured|lox)\b"), ("pickled", r"\b(pickled|brined|fermented)\b"), ("dried", r"\b(dried|dehydrated)\b"), ("fat", r"\b(fried|deep-fried|pan-fried|sauteed|sautéed|battered|breaded)\b"),
           ("dry", r"\b(baked|roasted|toasted|grilled|broiled|barbecued|seared|dry heat|pan-broiled)\b"), ("moist", r"\b(boiled|steamed|simmered|poached|microwaved|stewed|braised|moist heat)\b"),
           ("generic", r"\b(cooked|heated)\b"), ("canned", r"\b(canned|jarred|bottled)\b"), ("raw", r"\b(raw|uncooked|unheated|fresh)\b")]
M_COST = {}


def _mc(a, b, c):
    M_COST[(a, b)] = M_COST[(b, a)] = c


for _n in ("none", "raw", "moist", "dry", "fat", "smoked", "pickled", "dried", "canned", "generic"):
    _mc(_n, _n, 0.0)
for a_, b_, c_ in [("none", "raw", 0), ("none", "generic", 1.0), ("none", "moist", 2.2), ("none", "dry", 2.3), ("none", "fat", 3.0), ("none", "smoked", 3.2), ("none", "pickled", 3.2), ("none", "dried", 3.0), ("none", "canned", 1.6),
                   ("raw", "moist", 2.2), ("raw", "dry", 2.3), ("raw", "fat", 3.0), ("raw", "smoked", 3.2), ("raw", "pickled", 3.2), ("raw", "dried", 3.0), ("raw", "canned", 1.8), ("raw", "generic", 2.0),
                   ("moist", "dry", 1.0), ("moist", "fat", 1.8), ("moist", "smoked", 2.2), ("moist", "pickled", 2.4), ("moist", "dried", 2.6), ("moist", "canned", 1.0), ("moist", "generic", 0.4),
                   ("dry", "fat", 1.4), ("dry", "smoked", 1.8), ("dry", "pickled", 2.4), ("dry", "dried", 2.4), ("dry", "canned", 1.8), ("dry", "generic", 0.4), ("fat", "smoked", 2.4), ("fat", "pickled", 2.8),
                   ("fat", "dried", 2.8), ("fat", "canned", 2.4), ("fat", "generic", 1.0), ("smoked", "pickled", 2.4), ("smoked", "dried", 1.8), ("smoked", "canned", 2.0), ("smoked", "generic", 1.6),
                   ("pickled", "dried", 2.6), ("pickled", "canned", 1.0), ("pickled", "generic", 2.0), ("dried", "canned", 2.8), ("dried", "generic", 2.2), ("canned", "generic", 1.0)]:
    _mc(a_, b_, c_)
M_ORDER = ("smoked", "pickled", "dried", "fat", "dry", "moist", "generic", "canned", "raw")
QUALS = [("sodium", r"low ?sodium|reduced sodium|no salt added|sodium free", 2.0), ("fat", r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", 1.9),
         ("sugar", r"sugar ?free|unsweetened|sweetened", 1.6), ("diet", r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", 1.8), ("mixin", r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", 2.0),
         ("recipe", r"made (with|from)|prepared (with|from)|from mix|dry mix", 1.2), ("origin", r"new zealand|northern plains|hawaii|beaked|native|shoshone", 1.3), ("deli", r"\bdeli\b|luncheon|prepackaged|shelf stable", 1.1),
         ("ratio", r"\d+% lean|\d+% fat", 1.5), ("coating", r"breaded|battered|coated|glazed|candied", 1.0), ("fatadded", r"fat added|added fat", 1.2), ("kernel", r"\bkernel\b", 1.5),
         ("flavour", r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", 1.1)]
Q_LICENSE = {"sodium": r"sodium", "fat": r"fat|light|lite|skim|lean|diet", "sugar": r"sweet|sugar", "diet": r"decaf|lactose|diet|calorie", "mixin": r"\bwith\b|\band\b", "recipe": r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread",
             "origin": r"new zealand|hawaii", "deli": r"deli|lunch|sliced", "ratio": r"\d+%", "coating": r"bread|batter|coated|glazed|candied|crispy", "fatadded": r"saut|fried|butter|oil|fat", "kernel": r"kernel",
             "flavour": r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint"}


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


def parse(text, tokens, is_ing):
    m = [n for n, rx in METHODS if re.search(rx, text)]
    if "from dried" in text:
        m = [x for x in m if x != "dried"]
    if is_ing and "dried" in m and {"moist", "dry", "generic"} & set(m):
        m.remove("dried")
    method = "none"
    for n in M_ORDER:
        if n in m and not (n == "raw" and len(m) > 1):
            method = n
            break
    species = [t for t in tokens if t in SPECIES_WORDS]
    core = [t for t in tokens if t not in NOISE and not STATE_RX.match(t) and t not in PART_OF] or [t for t in tokens if t not in NOISE]
    parts = list(dict.fromkeys(PART_OF[t] for t in tokens if t in PART_OF and t not in core))
    quals = frozenset(k for k, rx, w in QUALS if re.search(rx, text))
    grind = bool(re.search(r"\b(ground|powdered|powder)\b", text))
    product = frozenset(t for t in tokens if t in PRODUCTS)
    pack = bool(re.search(r"\bcanned\b", text))
    return Frame(species=frozenset(species), part=parts, grind=grind, method=method, quals=quals, product=product, pack=pack, core=core)


def has(rx, s):
    return bool(re.search(rx, s))


def judging_function(ingredient, usda_match):
    try:
        raw = " ".join(str(usda_match or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
        i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
        u = re.sub(r"\([^)]*\)", " ", nb).lower()
        i_main = i.split(",")[0]
        imain = toks(i_main)
        segs = [toks(s) for s in u.split(",") if s.strip()]
        if not imain or not segs:
            return 0.0
        iall = toks(i)
        uflat = [t for s in segs for t in s] + toks(par)
        fi, fu = parse(i, iall, True), parse(u + " " + par, uflat, False)
        iset, uset = set(iall), set(uflat)
        ub = uset | set(CULT.get(t, t) for t in uset)
        core = fi.core or imain
        hits = [1.0 if (t in ub or CULT.get(t, t) in ub) else 0.0 for t in core]
        cov = sum(hits) / float(len(core))
        score = 2.0 + 4.6 * cov + 2.0 * (1.0 if hits[-1] else -0.7)
        extras = [t for t in segs[0] if t not in core and t not in iset and t not in NOISE and not STATE_RX.match(t) and t not in PART_OF
                  and t not in ("fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal", "seaweed")]
        score -= 0.5 * min(len(extras), 3)
        for base, vs in CULT_SETS.items():
            named = vs & set(core)
            if named and base in uset and not (named & uset) and (vs & uset):
                score -= 2.2
        if len(core) >= 2 and has(r"\band\b", i_main) and not has(r"\band\b", u) and cov < 1.0:
            score -= 1.4
        # ---------------- slot: part (worst member)
        ip, up = list(fi.part), list(fu.part)
        if set(core) & EDIBLE_PART:
            ip = [p for p in ip if p not in ("seed", "flower", "stem")]
            up = [p for p in up if p not in ("seed", "flower", "stem")]
        if has(r"skin[- ]on|meat and skin", i):
            ip.append("skin")
        if has(r"with skin|meat and skin", u):
            up.append("skin")
        pcost = 0.0
        if ip and up:
            pcost = max(min(PART_COST.get((a, b), 1.2 if a != b else 0.0) for b in up) for a in ip)
        elif ip or up:
            only = set(ip or up)
            pcost = 2.0 if only & {"offal", "extremity", "skin", "bone", "leaf", "root", "stem", "seed", "flower", "peel", "yolk", "whiteegg"} else 0.3
        # ground vs cut: ground is a form of the whole cut
        if fi.grind != fu.grind:
            pcost += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice", "bean"} else 1.3
            if fu.part and not fi.part and not fi.grind:
                pcost += 0.6
        score -= 1.15 * pcost
        # ---------------- slot: method
        mc = M_COST.get((fi.method, fu.method), 2.0)
        if fu.method == "dried" and fi.method != "dried" and set(core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}:
            mc = min(mc, 0.4)
        if fu.method == "canned" and fi.method != "canned" and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}:
            mc = min(mc, 0.3)
        if fi.method == "canned" and fu.method in ("none", "raw", "generic") and set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}:
            mc = min(mc, 0.3)
        if segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and segs[0][0] not in iset:
            mc += 2.4
        score -= 1.05 * mc
        # ---------------- slot: qualifiers (asymmetric)
        soft = has(r"\b(yogurt|kefir|milk)\b", u) and "cheese" not in u
        qcost = 0.0
        for k, rx, w in QUALS:
            if k in fu.quals and not has(Q_LICENSE[k], i):
                ww = w
                if k == "fat" and soft:
                    ww *= 0.3
                if k == "origin" and "organ" in uset:
                    ww *= 0.3
                qcost += ww
        if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i) and not has(r"garlic|seasoned|marinated", u):
            qcost += 1.7
        score -= 0.9 * min(qcost, 8.0)
        # ---------------- slot: product / form
        if (set(segs[0]) & PRODUCTS) - iset - set(core) - {"yogurt", "cheese", "bread", "cereal", "cracker", "tortilla"}:
            score -= 2.7
        if has(r"\bstew (meat|beef|lamb|pork)\b", i_main) and "stew" in segs[0]:
            score -= 2.7
        if has(r"\bbone[- ]in\b", i) and not has(r"\bbone\b", u):
            score -= 1.1
        if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
