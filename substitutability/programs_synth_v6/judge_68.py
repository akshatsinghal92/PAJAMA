import re
import math

# Committee judge: three independent "members" each emit a belief in [0,1] that the pair is
# substitutable, looking at a different aspect only:
#   identity member   : do both strings name the same food (aliases, hierarchy, parentheses)?
#   method member     : are cooking / preservation methods compatible?
#   qualifier member  : does the USDA entry add qualifiers the ingredient never stated?
# The committee output blends their beliefs (weighted mean) with a weakest-member term.

def _s(txt):
    return txt.split()


A = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
         scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
         dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
         cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", flat="wing",
         golden="yellow", wrap="tortilla")
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})
NOISE = frozenset(_s("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional "
                     "boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten "
                     "free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib "
                     "segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart delicious style domesticated new fluid white sliced atlantic pacific "
                     "alaska american lunch snack soft buttery crispy ready eat"))
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
GENERIC = frozenset(_s("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed"))
DISH = frozenset(_s("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf"))
ORGANS = frozenset(_s("liver kidney tongue heart giblet tripe brain gizzard organ"))
DRIED_OK = frozenset(_s("pinenut brazil hazelnut raisin fig date apricot prune agar seaweed mushroom"))
CANNED_OK = frozenset(_s("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine"))
METHOD_RX = [("smoked", r"\b(smoked|cured|lox)\b"), ("pickled", r"\b(pickled|brined|fermented)\b"), ("dried", r"\b(dried|dehydrated|freeze-dried)\b"),
             ("fat", r"\b(fried|deep-fried|pan-fried|sauteed|sautéed|stir-fried|battered|breaded)\b"),
             ("dry", r"\b(baked|roasted|toasted|grilled|broiled|barbecued|seared|dry heat|charbroiled|pan-broiled|panbroiled)\b"),
             ("moist", r"\b(boiled|steamed|simmered|poached|microwaved|blanched|stewed|braised|moist heat)\b"),
             ("generic", r"\b(cooked|heated)\b"), ("canned", r"\b(canned|jarred|bottled)\b"), ("raw", r"\b(raw|uncooked|unheated|unroasted|fresh)\b")]
# cost between methods (symmetric via helper)
MCOST = {}


def _mc(a, b, c):
    MCOST[(a, b)] = MCOST[(b, a)] = c


for _name in ("none", "raw", "moist", "dry", "fat", "smoked", "pickled", "dried", "canned", "generic"):
    _mc(_name, _name, 0.0)
for a, b, c in [("none", "raw", 0), ("none", "generic", 1.0), ("none", "moist", 2.2), ("none", "dry", 2.3), ("none", "fat", 3.0), ("none", "smoked", 3.2), ("none", "pickled", 3.2), ("none", "dried", 3.0), ("none", "canned", 1.6),
                ("raw", "moist", 2.2), ("raw", "dry", 2.3), ("raw", "fat", 3.0), ("raw", "smoked", 3.2), ("raw", "pickled", 3.2), ("raw", "dried", 3.0), ("raw", "canned", 1.8), ("raw", "generic", 2.0),
                ("moist", "dry", 1.0), ("moist", "fat", 1.8), ("moist", "smoked", 2.2), ("moist", "pickled", 2.4), ("moist", "dried", 2.6), ("moist", "canned", 1.0), ("moist", "generic", 0.4),
                ("dry", "fat", 1.4), ("dry", "smoked", 1.8), ("dry", "pickled", 2.4), ("dry", "dried", 2.4), ("dry", "canned", 1.8), ("dry", "generic", 0.4),
                ("fat", "smoked", 2.4), ("fat", "pickled", 2.8), ("fat", "dried", 2.8), ("fat", "canned", 2.4), ("fat", "generic", 1.0),
                ("smoked", "pickled", 2.4), ("smoked", "dried", 1.8), ("smoked", "canned", 2.0), ("smoked", "generic", 1.6), ("pickled", "dried", 2.6), ("pickled", "canned", 1.0), ("pickled", "generic", 2.0),
                ("dried", "canned", 2.8), ("dried", "generic", 2.2), ("canned", "generic", 1.0)]:
    _mc(a, b, c)
ORDER = ("smoked", "pickled", "dried", "fat", "dry", "moist", "generic", "canned", "raw")


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("skin-on", "withskin").replace("skin on", "withskin").replace("meat and skin", "withskin")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(A.get(w, w))
    return out


def method_of(text, is_ing):
    found = [n for n, rx in METHOD_RX if re.search(rx, text)]
    if "from dried" in text:
        found = [f for f in found if f != "dried"]
    if is_ing and "dried" in found and {"moist", "dry", "generic"} & set(found):
        found.remove("dried")
    if not found:
        return "none"
    for n in ORDER:
        if n in found and not (n == "raw" and len(found) > 1):
            return n
    return found[0]


def prep(ingredient, usda):
    raw = " ".join(str(usda or "").split())
    keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
    nb = " ".join(keep)
    par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
    i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
    i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
    u = re.sub(r"\([^)]*\)", " ", nb).lower()
    return i, u, par


# ---------------------------------------------------------------- member 1: identity
def member_identity(i, u, par):
    imain = toks(i.split(",")[0])
    segs = [toks(s) for s in u.split(",") if s.strip()]
    if not imain or not segs:
        return None
    flat = [t for s in segs for t in s]
    uset = set(flat) | set(toks(par))
    ub = uset | set(CULT.get(t, t) for t in uset)
    core = [t for t in imain if t not in NOISE and not STATE_RX.match(t)] or [t for t in imain if t not in NOISE] or imain
    hits = [1.0 if (CULT.get(t, t) in ub or t in ub) else 0.0 for t in core]
    cov = sum(hits) / float(len(core))
    head = hits[-1]
    extras = [t for t in segs[0] if t not in core and t not in set(toks(i)) and t not in NOISE and not STATE_RX.match(t) and t not in GENERIC]
    belief = 0.55 * cov + 0.3 * head + 0.15 * (1.0 if not extras else max(0.0, 1.0 - 0.34 * len(extras)))
    for base, vs in CULT_SETS.items():
        named = vs & set(core)
        if named and base in uset and not (named & uset) and (vs & uset):
            belief *= 0.4
    if len(core) >= 2 and re.search(r"\band\b", i.split(",")[0]) and not re.search(r"\band\b", u) and cov < 1.0:
        belief *= 0.6
    return belief, core, uset, segs


# ---------------------------------------------------------------- member 2: method
def member_method(i, u, par, core, segs, iset):
    si, su = method_of(i, True), method_of(u + " " + par, False)
    c = MCOST.get((si, su), 2.0)
    if su == "dried" and si != "dried" and set(core) & DRIED_OK:
        c = min(c, 0.4)
    if su == "canned" and si != "canned" and set(core) & CANNED_OK:
        c = min(c, 0.3)
    if si == "canned" and su in ("none", "raw", "generic") and set(core) & CANNED_OK:
        c = min(c, 0.3)
    if segs[0][:1] == ["frozen"] and "frozen" not in iset:
        c += 2.4
    return math.exp(-0.55 * c)


# ---------------------------------------------------------------- member 3: qualifiers
def member_qualifier(i, u, par, core, segs, iset, uset):
    soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", u)) and "cheese" not in u
    organ = bool(set(core) & ORGANS) or "organ" in uset or "variety meat" in u
    rows = [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
            (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft else 1.0)),
            (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
            (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
            (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
            (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
            (r"\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced", 1.1), (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
            (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2),
            (r"\bkernel\b", r"kernel", 1.5)]
    cost = 0.0
    for ru, ri, w in rows:
        if re.search(ru, u) and not re.search(ri, i):
            cost += w
    if [x for x in re.findall(r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", u) if not re.search(r"\b" + x, i)]:
        cost += 1.1
    if re.search(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", i) and not re.search(r"garlic|seasoned|marinated", u):
        cost += 1.7
    if bool(re.search(r"\b(ground|powdered|powder)\b", i)) != bool(re.search(r"\b(ground|powdered|powder)\b", u)):
        cost += 2.0 if set(core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
    if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", u)):
        cost += 2.5
    if (set(segs[0]) & DISH) - iset - set(core):
        cost += 3.0
    if re.search(r"\bstew (meat|beef|lamb|pork)\b", i) and "stew" in segs[0]:
        cost += 3.0
    if re.search(r"\bbone[- ]in\b", i) and not re.search(r"\bbone\b", u):
        cost += 1.2
    if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
        cost += 3.3
    return math.exp(-0.5 * min(cost, 8.0))


def judging_function(ingredient, usda_match):
    try:
        i, u, par = prep(ingredient, usda_match)
        r = member_identity(i, u, par)
        if r is None:
            return 0.0
        b_id, core, uset, segs = r
        iset = set(toks(i))
        b_m = member_method(i, u, par, core, segs, iset)
        b_q = member_qualifier(i, u, par, core, segs, iset, uset)
        mean = 0.45 * b_id + 0.25 * b_m + 0.30 * b_q
        weakest = min(b_id, b_m, b_q)
        return float(10.0 * (0.6 * mean + 0.4 * weakest) + 0.3 * b_id)
    except Exception:
        return 0.0
