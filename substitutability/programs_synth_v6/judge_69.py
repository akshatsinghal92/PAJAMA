import re

# ======================================================================================
# Part-and-cut judge built from closure "experts" combined by a weighted HARMONIC mean.
# The part expert is the focus: ingredient part vs USDA part, with equivalence groups
# (chuck ~ shoulder ~ blade; flats ~ wings; heart/innards ...), unspecified = neutral.
# ======================================================================================

PART_GROUPS = {
    "breast": "breast", "thigh": "leg", "drumstick": "leg", "leg": "leg", "wing": "wing", "flat": "wing", "drum": "leg", "back": "back", "neck": "neck", "tail": "tail",
    "loin": "loin", "tenderloin": "loin", "sirloin": "loin", "shoulder": "shoulder", "chuck": "shoulder", "blade": "shoulder", "rib": "rib", "ribeye": "rib", "brisket": "brisket",
    "flank": "flank", "round": "round", "rump": "round", "shank": "shank", "crosscut": "shank", "belly": "belly", "ham": "leg", "hock": "shank", "foot": "foot", "feet": "foot",
    "liver": "liver", "heart": "heart", "kidney": "kidney", "tongue": "tongue", "giblet": "giblet", "gizzard": "giblet", "tripe": "tripe", "brain": "brain", "skin": "skin", "bone": "bone",
    "fillet": "fillet", "filet": "fillet", "steak": "steak", "chop": "chop", "yolk": "yolk", "white": "white", "leaf": "leaf", "leave": "leaf", "green": "leaf", "root": "root", "stem": "stem",
    "stalk": "stem", "seed": "seed", "flower": "flower", "floret": "flower", "peel": "peel", "zest": "peel", "rind": "peel", "bulb": "bulb", "pod": "pod", "kernel": "kernel", "pulp": "pulp",
    "juice": "juice", "shell": "shell", "head": "head", "heartland": "heart",
}
# groups that are interchangeable for diners
COMPAT_GROUPS = [{"shoulder", "chuck", "blade"}, {"loin", "steak", "chop"}, {"leg", "round"}, {"giblet", "heart", "liver", "gizzard"}, {"kernel", "seed"}, {"peel"}, {"fillet", "steak", "loin"}]
PLANT_PARTS = {"leaf", "root", "stem", "seed", "flower", "peel", "bulb", "pod", "kernel", "pulp", "head"}
EDIBLE_SEED_FOODS = frozenset("pomegranate amaranth flaxseed sesame chia sunflower poppy pumpkin sunflower".split())
AL = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp", garbanzo="chickpea",
          scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn", bison="buffalo", pinyon="pinenut", pinon="pinenut",
          dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt", fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet",
          cos="romaine", granada="pomegranate", swede="rutabaga", beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", golden="yellow", wrap="tortilla")
SKIPW = frozenset(("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional "
                   "boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature variety flavor other than not eaten "
                   "free range farmed wild mixed species commercial all strong brewed round meat by product added moist segment piece strip wedge chunk cube kernel without salt fat fresh "
                   "raw whole delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat").split())
STATE_RX = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
DISHNOUN = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
CULT = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado", portobello="mushroom", cremini="mushroom")
CULT_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"}, potato={"russet", "yukon"}, orange={"navel", "valencia"})


def toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan").replace("skin-on", "withskin").replace("skin on", "withskin").replace("meat and skin", "withskin")
    s = s.replace("variety meats and by-products", "organ").replace("variety meats", "organ")
    out = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        out.append(AL.get(w, w))
    return out


def parts_in(tokens, skip_core=()):
    found = []
    for t in tokens:
        g = PART_GROUPS.get(t)
        if g and t not in skip_core:
            found.append(g)
    return found


def compatible(a, b):
    if a == b:
        return True
    return any(a in g and b in g for g in COMPAT_GROUPS)


def has(rx, s):
    return bool(re.search(rx, s))


class Ctx(object):
    pass


def build(ingredient, usda):
    c = Ctx()
    raw = " ".join(str(usda or "").split())
    keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper() and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
    nb = " ".join(keep)
    c.par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
    i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
    c.i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
    c.u = re.sub(r"\([^)]*\)", " ", nb).lower()
    c.i_main = c.i.split(",")[0]
    c.imain = toks(c.i_main)
    c.segs = [toks(s) for s in c.u.split(",") if s.strip()]
    c.ok = bool(c.imain and c.segs)
    if not c.ok:
        return c
    c.iset = set(toks(c.i))
    c.uflat = [t for s in c.segs for t in s]
    c.uset = set(c.uflat) | set(toks(c.par))
    c.core_all = [t for t in c.imain if t not in SKIPW and not STATE_RX.match(t)] or [t for t in c.imain if t not in SKIPW] or c.imain
    # the part words of the ingredient are NOT identity words (they are handled by the part expert)
    c.core = [t for t in c.core_all if t not in PART_GROUPS] or c.core_all
    c.i_parts = parts_in(c.imain + toks(c.i.split(",", 1)[1]) if "," in c.i else c.imain)
    c.u_parts = parts_in(c.uflat + toks(c.par))
    return c


def expert_identity(c):
    ub = c.uset | set(CULT.get(t, t) for t in c.uset)
    hits = [1.0 if (t in ub or CULT.get(t, t) in ub) else 0.0 for t in c.core]
    cov = sum(hits) / float(len(c.core))
    extras = [t for t in c.segs[0] if t not in c.core_all and t not in c.iset and t not in SKIPW and not STATE_RX.match(t) and t not in PART_GROUPS
              and t not in ("fish", "beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "nut", "seed", "cheese", "lettuce", "crustacean", "fruit", "vegetable", "game", "organ", "sausage", "cereal", "seaweed")]
    b = 0.55 * cov + 0.30 * hits[-1] + 0.15 * (1.0 if not extras else max(0.0, 1.0 - 0.34 * len(extras)))
    for base, vs in CULT_SETS.items():
        named = vs & set(c.core)
        if named and base in c.uset and not (named & c.uset) and (vs & c.uset):
            b *= 0.4
    if len(c.core) >= 2 and has(r"\band\b", c.i_main) and not has(r"\band\b", c.u) and cov < 1.0:
        b *= 0.6
    return b


def expert_part(c):
    ip, up = set(c.i_parts), set(c.u_parts)
    # parts that ARE the food (pomegranate seeds, artichoke hearts) are not conflicts
    if c.core and set(c.core) & EDIBLE_SEED_FOODS:
        ip.discard("seed")
        up.discard("seed")
    # hearts of lettuce/palm/artichoke are vegetable parts, not organs
    if "heart" in ip and set(c.core) & {"romaine", "lettuce", "artichoke", "palm", "celery"}:
        ip.discard("heart")
        up.discard("heart")
    # 'skin' only matters as a stated component; fillet/steak/chop are cuts of the same flesh
    if "withskin" in c.imain or "withskin" in c.uflat:
        ip.add("skin") if "withskin" in c.imain else None
        up.add("skin") if "withskin" in c.uflat else None
    if not ip and not up:
        return 0.95
    if ip and up:
        if any(compatible(a, b) for a in ip for b in up):
            return 0.95
        # plant-part conflicts are severe; animal cut conflicts moderate
        sev = 0.08 if (ip | up) & PLANT_PARTS and not ((ip | up) - PLANT_PARTS) else 0.18
        return sev
    if up and not ip:
        # USDA names a part the unqualified ingredient did not: organ/plant parts are different foods
        sev_set = up & ({"liver", "heart", "kidney", "tongue", "giblet", "tripe", "brain", "skin", "bone", "foot", "leaf", "root", "stem", "peel", "flower", "seed", "yolk", "white"})
        return 0.30 if sev_set else 0.85
    # ingredient names a part, USDA is silent (whole animal/plant entry)
    sev_set = ip & {"liver", "heart", "kidney", "tongue", "giblet", "tripe", "brain", "skin", "bone", "foot", "leaf", "root", "stem", "peel", "flower", "seed", "yolk", "white", "neck"}
    return 0.30 if sev_set else 0.80


def make_penalty_expert(rows, scale):
    def expert(c):
        soft = has(r"\b(yogurt|kefir|milk)\b", c.u) and "cheese" not in c.u
        organ = bool(set(c.core_all) & {"liver", "kidney", "tongue", "heart", "giblet", "tripe", "brain", "gizzard", "organ"}) or "organ" in c.uset
        cost = 0.0
        for ru, ri, w in rows:
            w = w * (0.2 if (soft and "fat" in ru) else 1.0)
            if "new zealand" in ru and organ:
                w *= 0.3
            if has(ru, c.u) and not has(ri, c.i):
                cost += w
        return cost
    return expert


QUAL_ROWS = [(r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
             (r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9),
             (r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), (r"decaf|lactose|\bdiet\b|low calorie|reduced calorie", r"decaf|lactose|diet|calorie", 1.8),
             (r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
             (r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
             (r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 1.3), (r"\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced", 1.1),
             (r"\d+% lean|\d+% fat", r"\d+%", 1.5), (r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0), (r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2),
             (r"\bkernel\b", r"kernel", 1.5), (r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b", r"strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint", 1.1)]
qual_cost = make_penalty_expert(QUAL_ROWS, 0.5)


def state_cost(c):
    cost = 0.0
    ic, uc = has(r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b", c.i), has(r"\b(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat)\b", c.u)
    if uc and not ic and not has(r"\braw\b", c.u):
        cost += 2.1
    if ic and not uc:
        cost += 1.9 if has(r"toasted|roasted|grilled|fried", c.i) else 1.1
    di = has(r"\b(dried|dehydrated)\b", c.i) and not ic
    du = has(r"\b(dried|dehydrated)\b", c.u) and "from dried" not in c.u
    if di != du and not (du and set(c.core) & {"pinenut", "brazil", "hazelnut", "raisin", "fig", "date", "apricot", "prune", "agar", "seaweed", "mushroom"}):
        cost += 2.3
    for w in ("pickled", "smoked"):
        if (w in c.i) != (w in c.u):
            cost += 2.3
    cn = has(r"\bcanned\b", c.u)
    if has(r"\bcanned\b", c.i) != cn and not (cn and set(c.core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "tangerine"}):
        cost += 1.6
    if has(r"\b(ground|powdered|powder)\b", c.i) != has(r"\b(ground|powdered|powder)\b", c.u):
        cost += 2.0 if set(c.core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
    if (set(c.segs[0]) & DISHNOUN) - c.iset - set(c.core):
        cost += 3.0
    if has(r"\bstew (meat|beef|lamb|pork)\b", c.i_main) and "stew" in c.segs[0]:
        cost += 3.0
    if c.segs[0][:1] in (["frozen"], ["dried"], ["canned"], ["smoked"]) and c.segs[0][0] not in c.iset:
        cost += 2.4
    if has(r"\bbone[- ]in\b", c.i) and not has(r"\bbone\b", c.u):
        cost += 1.2
    if has(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", c.u):
        cost += 3.3
    return cost


def judging_function(ingredient, usda_match):
    try:
        c = build(ingredient, usda_match)
        if not c.ok:
            return 0.0
        e_id = max(expert_identity(c), 0.02)
        e_part = max(expert_part(c), 0.02)
        e_q = max(2.718281828 ** (-0.5 * min(qual_cost(c), 8.0)), 0.02)
        e_s = max(2.718281828 ** (-0.5 * min(state_cost(c), 8.0)), 0.02)
        ws = (0.38, 0.22, 0.22, 0.18)
        es = (e_id, e_part, e_q, e_s)
        harmonic = sum(ws) / sum(w / e for w, e in zip(ws, es))
        return float(10.0 * (0.7 * harmonic + 0.3 * min(es)) + 0.3 * e_id)
    except Exception:
        return 0.0
