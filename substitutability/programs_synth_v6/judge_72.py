import re
import math

# ============================================================================================
# Product-of-experts judge with a decorator registry. Every expert returns a belief in (0, 1];
# the final score is the weighted geometric mean (sum of weighted logs), so any one expert that
# strongly objects drags the product down multiplicatively. The part/cut expert is the focus.
# ============================================================================================

EXPERTS = []


def expert(weight):
    def deco(fn):
        EXPERTS.append((fn.__name__, weight, fn))
        return fn
    return deco


class Pair(object):
    pass


CUT_FAMILY = {}
for fam, words in {
    "breast": "breast tender", "leg": "thigh drumstick drum leg", "wing": "wing flat drumette", "back": "back carcass frame",
    "shoulder": "chuck blade shoulder arm picnic butt clod", "loin": "loin sirloin tenderloin strip porterhouse chop steak filet mignon",
    "rib": "rib ribeye spareribs", "round": "round rump ham tip", "shank": "shank crosscut hock", "plate": "brisket flank plate belly",
    "offal": "liver heart kidney tongue giblet gizzard tripe brain organ", "extremity": "neck foot feet tail", "skin": "skin", "bone": "bone",
    "yolk": "yolk", "eggwhite": "white", "leaf": "leaf leave green sprout", "root": "root bulb tuber", "stem": "stem stalk shoot", "seed": "seed kernel pod",
    "flower": "flower floret head bud", "peel": "peel zest rind", "pulp": "pulp", "fish_fillet": "fillet roe",
}.items():
    for w in words.split():
        CUT_FAMILY[w] = fam
SAME_BELIEF = {}


def _sb(a, b, v):
    SAME_BELIEF[(a, b)] = SAME_BELIEF[(b, a)] = v


for a in set(CUT_FAMILY.values()):
    _sb(a, a, 0.97)
for pair, v in [(("loin", "rib"), 0.55), (("loin", "round"), 0.45), (("loin", "shoulder"), 0.4), (("rib", "shoulder"), 0.5), (("round", "shoulder"), 0.45), (("shank", "plate"), 0.5), (("shank", "shoulder"), 0.45),
                (("breast", "leg"), 0.3), (("leg", "wing"), 0.4), (("breast", "wing"), 0.3), (("stem", "leaf"), 0.25), (("flower", "stem"), 0.3), (("seed", "pulp"), 0.2), (("peel", "pulp"), 0.15), (("round", "plate"), 0.4), (("loin", "plate"), 0.35)]:
    _sb(pair[0], pair[1], v)
EDIBLE_PART_FOOD = frozenset("pomegranate amaranth flaxseed sesame chia sunflower poppy romaine lettuce artichoke palm celery crayfish shrimp lobster crab prawn".split())
EDIBLE_FAMS_WHEN_FOOD = {"seed", "flower", "stem", "extremity", "root"}

AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla")
NOISE = frozenset(("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional "
                   "boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten "
                   "free range farmed wild mixed species commercial all strong brewed round meat by product added moist segment piece strip wedge chunk cube without salt fat fresh "
                   "raw whole delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat white lump").split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
GENERIC = frozenset("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game organ sausage cereal seaweed".split())
DISHN = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})
BASEALT = ("soy", "almond", "oat", "coconut", "cashew", "vegan", "tofu")


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    s = s.replace("bottom sirloin", "bottomsirloin").replace("top sirloin", "topsirloin").replace("tri-tip", "tritip")
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


def make_pair(ingredient, usda):
    p = Pair()
    raw = " ".join(str(usda or "").split())
    keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
    nb = " ".join(keep)
    p.par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
    i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
    p.i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
    p.u = re.sub(r"\([^)]*\)", " ", nb).lower()
    p.i_main = p.i.split(",")[0]
    p.imain = toks(p.i_main)
    p.segs = [toks(s) for s in p.u.split(",") if s.strip()]
    p.ok = bool(p.imain and p.segs)
    if not p.ok:
        return p
    p.iset = set(toks(p.i))
    p.uflat = [t for s in p.segs for t in s]
    p.uset = set(p.uflat) | set(toks(p.par))
    p.core_all = [t for t in p.imain if t not in NOISE and not STATE_RX.match(t)] or [t for t in p.imain if t not in NOISE] or p.imain
    p.core = [t for t in p.core_all if t not in CUT_FAMILY] or p.core_all
    p.food_edible_parts = bool(set(p.core) & EDIBLE_PART_FOOD)
    p.i_parts = [CUT_FAMILY[t] for t in dict.fromkeys(p.imain + (toks(p.i.split(",", 1)[1]) if "," in p.i else [])) if t in CUT_FAMILY and t not in p.core]
    p.u_parts = [CUT_FAMILY[t] for t in dict.fromkeys(p.uflat + toks(p.par)) if t in CUT_FAMILY and t not in p.core]
    return p


@expert(0.34)
def identity(p):
    ub = p.uset | set(CULT.get(t, t) for t in p.uset)
    hits = [1.0 if (t in ub or CULT.get(t, t) in ub) else 0.0 for t in p.core]
    cov = sum(hits) / float(len(p.core))
    extras = [t for t in p.segs[0] if t not in p.core_all and t not in p.iset and t not in NOISE and not STATE_RX.match(t) and t not in CUT_FAMILY and t not in GENERIC]
    b = 0.55 * cov + 0.30 * hits[-1] + 0.15 * (1.0 if not extras else max(0.0, 1.0 - 0.34 * len(extras)))
    for base, vs in CULT_SETS.items():
        named = vs & set(p.core)
        if named and base in p.uset and not (named & p.uset) and (vs & p.uset):
            b *= 0.4
    if len(p.core) >= 2 and has(r"\band\b", p.i_main) and not has(r"\band\b", p.u) and cov < 1.0:
        b *= 0.6
    ia, ua = set(x for x in BASEALT if x in p.iset), set(x for x in BASEALT if x in p.uset)
    if (ua - ia) or ((ia - ua) and not ({"vegan", "tofu"} & ua)):
        b *= 0.55
    if "tritip" in p.uset and "tritip" not in p.iset and ("sirloin" in p.iset or "tip" in p.iset):
        b *= 0.5
    return b


@expert(0.24)
def part_cut(p):
    ip, up = list(dict.fromkeys(p.i_parts)), list(dict.fromkeys(p.u_parts))
    if p.food_edible_parts:
        ip = [x for x in ip if x not in EDIBLE_FAMS_WHEN_FOOD]
        up = [x for x in up if x not in EDIBLE_FAMS_WHEN_FOOD]
    if has(r"skin[- ]on|meat and skin", p.i):
        ip.append("skin")
    if has(r"with skin|meat and skin", p.u):
        up.append("skin")
    if not ip and not up:
        return 0.95
    if ip and up:
        worst = 1.0
        for a in ip:
            best = max(SAME_BELIEF.get((a, b), 0.08 if (a in ("offal", "extremity", "skin", "bone") or b in ("offal", "extremity", "skin", "bone")) else 0.2) for b in up)
            worst = min(worst, best)
        return worst
    only = set(ip or up)
    if only & {"offal", "extremity", "skin", "bone", "leaf", "root", "stem", "seed", "flower", "peel", "yolk", "eggwhite"}:
        return 0.3
    return 0.85


@expert(0.22)
def qualifiers(p):
    soft = has(r"\b(yogurt|kefir|milk)\b", p.u) and "cheese" not in p.u
    organ = "organ" in p.uset or "offal" in p.i_parts
    cost = 0.0
    for ru, ri, w in [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
                      (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.3 if soft else 1.0)),
                      (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
                      (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
                      (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
                      (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
                      (r"\bdeli\b|luncheon|prepackaged|shelf stable|ready[- ]to[- ]bake", r"deli|lunch|sliced", 1.1), (r"\d+% lean|\d+% fat", r"\d+%", 1.5),
                      (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2),
                      (r"\bkernel\b", r"kernel", 1.5), (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint", 1.1)]:
        if has(ru, p.u) and not has(ri, p.i):
            cost += w
    if has(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", p.i) and not has(r"garlic|seasoned|marinated", p.u):
        cost += 1.7
    return math.exp(-0.5 * min(cost, 8.0))


@expert(0.20)
def state(p):
    cost = 0.0
    cook = r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b"
    ic, uc = has(cook, p.i), has(cook, p.u)
    if uc and not ic and not has(r"\braw\b", p.u):
        cost += 2.2
    if ic and not uc:
        cost += 1.9 if has(r"toasted|roasted|grilled|fried", p.i) else 1.1
    di = has(r"\b(dried|dehydrated)\b", p.i) and not ic
    du = has(r"\b(dried|dehydrated)\b", p.u) and "from dried" not in p.u
    if di != du and not (du and set(p.core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}):
        cost += 2.3
    for w in ("pickled", "smoked"):
        if (w in p.i) != (w in p.u):
            cost += 2.3
    cn = has(r"\bcanned\b", p.u)
    if has(r"\bcanned\b", p.i) != cn and not (cn and set(p.core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
        cost += 1.6
    if has(r"\b(ground|powdered|powder)\b", p.i) != has(r"\b(ground|powdered|powder)\b", p.u):
        cost += 2.0 if set(p.core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice", "bean"} else 1.3
        if p.u_parts and not p.i_parts and not has(r"\bground\b", p.i):
            cost += 0.6
    if (set(p.segs[0]) & DISHN) - p.iset - set(p.core):
        cost += 3.0
    if has(r"\bstew (meat|beef|lamb|pork)\b", p.i_main) and "stew" in p.segs[0]:
        cost += 3.0
    if p.segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and p.segs[0][0] not in p.iset:
        cost += 2.4
    if has(r"\bbone[- ]in\b", p.i) and not has(r"\bbone\b", p.u):
        cost += 1.2
    if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", p.u):
        cost += 3.3
    return math.exp(-0.5 * min(cost, 8.0))


def judging_function(ingredient, usda_match):
    try:
        p = make_pair(ingredient, usda_match)
        if not p.ok:
            return 0.0
        total_w = sum(w for _, w, _ in EXPERTS)
        logsum = 0.0
        beliefs = []
        for name, w, fn in EXPERTS:
            b = max(min(fn(p), 1.0), 0.02)
            beliefs.append(b)
            logsum += (w / total_w) * math.log(b)
        geo = math.exp(logsum)
        return float(10.0 * (0.75 * geo + 0.25 * min(beliefs)) + 0.3 * beliefs[0])
    except Exception:
        return 0.0
