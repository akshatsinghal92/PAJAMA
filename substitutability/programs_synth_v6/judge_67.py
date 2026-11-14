import re
import math
from difflib import SequenceMatcher

# Method-compatibility probability judge (object style). A Pair object lazily exposes the facts about
# an ingredient/USDA pair; a registry of small generator functions yields (label, cost) hits.

COMPAT = {}


def _link(a, b, p):
    COMPAT[(a, b)] = COMPAT[(b, a)] = p


_STATES = ("none", "raw", "moist", "dry", "fat", "smoked", "pickled", "dried", "canned", "generic")
for _s in _STATES:
    _link(_s, _s, 0.95)
for _a, _b, _p in [("none", "raw", .95), ("none", "generic", .55), ("none", "moist", .18), ("none", "dry", .16), ("none", "fat", .08), ("none", "smoked", .07),
                   ("none", "pickled", .07), ("none", "dried", .08), ("none", "canned", .35), ("raw", "moist", .15), ("raw", "dry", .14), ("raw", "fat", .06),
                   ("raw", "smoked", .06), ("raw", "pickled", .06), ("raw", "dried", .07), ("raw", "canned", .3), ("raw", "generic", .2), ("moist", "dry", .55),
                   ("moist", "fat", .35), ("moist", "smoked", .2), ("moist", "pickled", .15), ("moist", "dried", .12), ("moist", "canned", .55), ("moist", "generic", .8),
                   ("dry", "fat", .45), ("dry", "smoked", .3), ("dry", "pickled", .15), ("dry", "dried", .2), ("dry", "canned", .35), ("dry", "generic", .8),
                   ("fat", "smoked", .2), ("fat", "pickled", .1), ("fat", "dried", .1), ("fat", "canned", .2), ("fat", "generic", .55), ("smoked", "pickled", .15),
                   ("smoked", "dried", .3), ("smoked", "canned", .3), ("smoked", "generic", .4), ("pickled", "dried", .12), ("pickled", "canned", .5),
                   ("pickled", "generic", .3), ("dried", "canned", .1), ("dried", "generic", .2), ("canned", "generic", .5)]:
    _link(_a, _b, _p)

_PATTERNS = (("smoked", r"\b(smoked|cured|lox)\b"), ("pickled", r"\b(pickled|brined|fermented)\b"), ("dried", r"\b(dried|dehydrated|freeze-dried)\b"),
             ("fat", r"\b(fried|deep-fried|pan-fried|sauteed|sautéed|stir-fried|battered|breaded)\b"),
             ("dry", r"\b(baked|roasted|toasted|grilled|broiled|barbecued|seared|dry heat|charbroiled|pan-broiled|panbroiled)\b"),
             ("moist", r"\b(boiled|steamed|simmered|poached|microwaved|blanched|stewed|braised|moist heat)\b"),
             ("generic", r"\b(cooked|heated|prepared)\b"), ("canned", r"\b(canned|jarred|bottled)\b"), ("raw", r"\b(raw|uncooked|unheated|unroasted|fresh)\b"))
_ORDER = ("smoked", "pickled", "dried", "fat", "dry", "moist", "generic", "canned", "raw")

_ALIASES = dict(clementine="tangerine", mandarin="tangerine", satsuma="tangerine", filbert="hazelnut", linseed="flaxseed", crawfish="crayfish", prawn="shrimp",
                garbanzo="chickpea", scallion="onion", cilantro="coriander", aubergine="eggplant", courgette="zucchini", rocket="arugula", maize="corn",
                bison="buffalo", pinyon="pinenut", pinon="pinenut", dehydrated="dried", uncooked="raw", unroasted="raw", poultry="chicken", yoghurt="yogurt",
                fava="broadbean", para="brazil", ox="beef", calf="veal", innard="giblet", cos="romaine", granada="pomegranate", swede="rutabaga",
                beetroot="beet", capsicum="pepper", treacle="molasses", catsup="ketchup", mutton="lamb", flat="wing")
_CULTIVAR = dict(concord="grape", bing="cherry", fuji="apple", gala="apple", bartlett="pear", russet="potato", roma="tomato", navel="orange", hass="avocado",
                 portobello="mushroom", cremini="mushroom")
_CULTIVAR_SETS = dict(grape={"concord", "muscadine", "thompson", "american"}, squash={"butternut", "hubbard", "acorn", "spaghetti"}, apple={"fuji", "gala", "granny"},
                      potato={"russet", "yukon"}, orange={"navel", "valencia"})
_NOISE = frozenset(("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium "
                    "finely optional boneless skinless cold hot and of the a in for from or with nfs ns regular type separable trimmed choice select grade only mature "
                    "variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round meat by product added moist steak "
                    "chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole "
                    "heart delicious style domesticated new fluid white sliced atlantic pacific alaska american lunch snack soft buttery crispy ready eat").split())
_STATE_TOKEN = re.compile(r"^(cooked|boiled|baked|braised|simmered|broiled|roasted|steamed|toasted|grilled|sauteed|poached|stewed|heat|dried|canned|frozen|smoked|pickled|fried|ground|powdered|batter|lowfat|nonfat|reduced|light|lite|skim|sweetened|unsweetened|flavored|diet|unsalted|salted|skinless|boneless|seedless|crispy|drained|sulfured)$")
_DISH_NOUNS = frozenset("oil juice flour jerky nectar soup stew candy cake pudding snack sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_ORGAN_WORDS = frozenset("liver kidney tongue heart giblet tripe brain gizzard organ".split())
_DRIED_BY_DEFAULT = frozenset("pinenut brazil hazelnut raisin fig date apricot prune agar seaweed mushroom".split())
_CANNED_BY_DEFAULT = frozenset("applesauce olive bean tomato pumpkin corn tuna pineapple tangerine".split())
_FLAVOURS = r"\b(strawberry|peach|blueberry|raspberry|cherry|banana|chocolate|cinnamon|maple|garlic|lemon|mint)\b"


def _toks(s):
    s = s.replace("dairy-free", "vegan").replace("plant-based", "vegan")
    res = []
    for w in re.findall(r"[a-zé]+", s.replace("-", " ")):
        w = w.replace("é", "e")
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
            w = w[:-1]
        res.append(_ALIASES.get(w, w))
    return res


def _symbol(text, ingredient_side):
    hits = [n for n, rx in _PATTERNS if re.search(rx, text)]
    if "from dried" in text:
        hits = [h for h in hits if h != "dried"]
    if ingredient_side and "dried" in hits and {"moist", "dry", "generic"} & set(hits):
        hits.remove("dried")
    if not hits:
        return "none"
    for n in _ORDER:
        if n in hits and not (n == "raw" and len(hits) > 1):
            return n
    return hits[0]


def _near(word, pool):
    if word in pool:
        return 1.0
    if len(word) >= 5:
        for x in pool:
            if len(x) >= 5 and x[:3] == word[:3] and SequenceMatcher(None, word, x).ratio() >= 0.87:
                return 0.9
    return 0.0


class Pair(object):
    def __init__(self, ingredient, usda):
        raw = " ".join(str(usda or "").split())
        keep = [w for w in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and re.sub(r"[^A-Za-z]", "", w).isupper()
                                              and re.sub(r"[^A-Za-z]", "", w).lower() not in ("nfs", "usda"))]
        nb = " ".join(keep)
        self.par = " ".join(re.findall(r"\(([^)]*)\)", nb)).lower()
        i = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).lower()
        self.i = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", i)
        self.u = re.sub(r"\([^)]*\)", " ", nb).lower()
        self.i_main = self.i.split(",")[0]
        self.imain = _toks(self.i_main)
        self.segs = [_toks(s) for s in self.u.split(",") if s.strip()]
        self.iset = set(_toks(self.i))
        self.uset = set(t for s in self.segs for t in s) | set(_toks(self.par))
        self.core = ([t for t in self.imain if t not in _NOISE and not _STATE_TOKEN.match(t)]
                     or [t for t in self.imain if t not in _NOISE] or self.imain)

    def valid(self):
        return bool(self.imain and self.segs)

    def f(self, rx_u, rx_i=None):
        a = bool(re.search(rx_u, self.u))
        return a and (rx_i is None or not re.search(rx_i, self.i))


def hits(p):
    """generator of (label, cost) penalty hits"""
    soft = bool(re.search(r"\b(yogurt|kefir|milk)\b", p.u)) and "cheese" not in p.u
    organ = bool(set(p.core) & _ORGAN_WORDS) or "organ" in p.uset or "variety meat" in p.u
    rows = [("sodium", r"low ?sodium|reduced sodium|no salt added|sodium free", r"sodium", 2.0),
            ("fat", r"fat ?free|non ?fat|skim|low ?fat|reduced fat|\blite\b|\blight\b|milkfat", r"fat|light|lite|skim|lean|diet", 1.9 * (0.35 if soft else 1.0)),
            ("sugar", r"sugar ?free|unsweetened|sweetened", r"sweet|sugar", 1.6), ("diet", r"decaf|lactose|\bdiet\b|low calorie", r"decaf|lactose|diet", 1.8),
            ("mixin", r"\bwith (vegetables|oats|meat|cheese|fruit|nuts|granola|honey|beans|tomato|cream)\b", r"\bwith\b|\band\b", 2.0),
            ("recipe", r"made (with|from)|prepared (with|from)|from mix|dry mix", r"made|prepared|mix|vegan|plant|bread|cake|dressing|mayo|cornbread", 1.2),
            ("origin", r"new zealand|northern plains|hawaii|beaked|native|shoshone", r"new zealand|hawaii", 0.4 if organ else 1.3),
            ("deli", r"\bdeli\b|luncheon|prepackaged|shelf stable", r"deli|lunch|sliced", 1.1), ("ratio", r"\d+% lean|\d+% fat", r"\d+%", 1.5),
            ("coating", r"breaded|battered|coated|glazed|candied", r"bread|batter|coated|glazed|candied|crispy", 1.0),
            ("fatadded", r"fat added|added fat", r"saut|fried|butter|oil|fat", 1.2)]
    for label, ru, ri, w in rows:
        if p.f(ru, ri):
            yield label, w
    if [x for x in re.findall(_FLAVOURS, p.u) if not re.search(r"\b" + x, p.i)]:
        yield "flavour", 1.1
    if re.search(r"\bwith garlic\b|\broasted with\b|\bseasoned\b|\bmarinated\b", p.i) and not re.search(r"garlic|seasoned|marinated", p.u):
        yield "seasoned_dropped", 1.7
    g_i, g_u = bool(re.search(r"\b(ground|powdered|powder)\b", p.i)), bool(re.search(r"\b(ground|powdered|powder)\b", p.u))
    if g_i != g_u:
        yield "grind", 2.0 if set(p.core) & {"seed", "flaxseed", "pecan", "almond", "walnut", "oat", "grain", "wheat", "rice"} else 1.3
    if set(re.findall(r"\b(leaf|leaves|peel|stem)\b", p.i)) != set(re.findall(r"\b(leaf|leaves|peel|stem)\b", p.u)):
        yield "part", 2.5
    if (set(p.segs[0]) & _DISH_NOUNS) - p.iset - set(p.core):
        yield "dish_noun", 3.0
    if re.search(r"\bstew (meat|beef|lamb|pork)\b", p.i_main) and "stew" in p.segs[0]:
        yield "stew_idiom", 3.0
    if re.search(r"\bbone[- ]in\b", p.i) and not re.search(r"\bbone\b", p.u):
        yield "bone_in", 1.2
    if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", p.u):
        yield "restaurant", 3.3
    for base, vs in _CULTIVAR_SETS.items():
        named = vs & set(p.core)
        if named and base in p.uset and not (named & p.uset) and (vs & p.uset):
            yield "cultivar", 2.2


def judging_function(ingredient, usda_match):
    try:
        p = Pair(ingredient, usda_match)
        if not p.valid():
            return 0.0
        ub = p.uset | set(_CULTIVAR.get(t, t) for t in p.uset)
        marks = [_near(_CULTIVAR.get(t, t), ub) for t in p.core]
        ident = 4.6 * (sum(marks) / float(len(p.core))) + 2.0 * (1.0 if marks[-1] > 0 else -0.7)
        si, su = _symbol(p.i, True), _symbol(p.u + " " + p.par, False)
        prob = COMPAT.get((si, su), 0.3)
        if su == "dried" and si != "dried" and set(p.core) & _DRIED_BY_DEFAULT:
            prob = max(prob, 0.7)
        if su == "canned" and si != "canned" and set(p.core) & _CANNED_BY_DEFAULT:
            prob = max(prob, 0.7)
        if si == "canned" and su in ("none", "raw", "generic") and set(p.core) & _CANNED_BY_DEFAULT:
            prob = max(prob, 0.7)
        if p.segs[0][:1] == ["frozen"] and "frozen" not in p.iset:
            prob *= 0.15
        total_pen = sum(c for _, c in hits(p))
        return float(ident + 3.0 * math.log(max(prob, 0.02)) - 0.9 * min(total_pen, 9.0) + 2.0)
    except Exception:
        return 0.0
