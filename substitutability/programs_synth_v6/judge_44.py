import re
import unicodedata

_ALIAS = {
    "aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper",
    "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "calamari": "squid", "filbert": "hazelnut", "linseed": "flaxseed",
    "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "pawpaw": "papaya", "yoghurt": "yogurt", "catsup": "ketchup", "mayo": "mayonnaise", "treacle": "molasses",
    "cornflour": "cornstarch", "wholemeal": "wholewheat", "bison": "buffalo", "pinyon": "pine", "pinon": "pine", "pignoli": "pine", "poultry": "chicken", "dehydrated": "dried", "uncooked": "raw",
    "puree": "sauce", "flat": "wing", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "icing": "powdered", "caster": "granulated", "porridge": "oatmeal", "polenta": "cornmeal",
    "innard": "giblet", "ox": "beef", "calf": "veal", "mutton": "lamb", "kumara": "sweetpotato", "chicory": "endive", "lite": "light", "skim": "nonfat", "lowfat": "light", "reduced": "light", "fava": "broadbean", "faba": "broadbean",
    "concord": "grape", "bing": "cherry", "navel": "orange", "russet": "potato", "gala": "apple", "fuji": "apple", "bartlett": "pear", "roma": "tomato", "butternut": "squash", "portobello": "mushroom", "cremini": "mushroom", "shiitake": "mushroom",
}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_DIETW = set("light nonfat sodium lactose decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk organ".split())
_STATEW = {"dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter"}
_INEDIBLE = {"leaf", "leave", "bone", "peel", "stem", "shell", "rind"}

def _ascii(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("us"):
        return t[:-1]
    return t

def _w(s):
    s = _ascii(s.lower()).replace("-", " ")
    return [_ALIAS.get(_stem(t), _stem(t)) for t in re.findall(r"[a-z]+", s)]

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _units(segs):
    """unordered bigram units inside a segment plus across the first two segments (hierarchy: category, subtype)"""
    units = set()
    sig = [[t for t in s if t not in _BENIGN] for s in segs]
    for s in sig:
        for a, b in zip(s, s[1:]):
            units.add(frozenset((a, b)))
    if len(sig) >= 2:
        for a in sig[0]:
            for b in sig[1]:
                units.add(frozenset((a, b)))
    return units

def judging_function(ingredient, usda_match):
    try:
        u_nb = _nobrand(str(usda_match or ""))
        paren = " ".join(re.findall(r"\(([^)]*)\)", u_nb))
        ing_raw = re.sub(r"\([^)]*\)", " ", str(ingredient or ""))
        ing_raw = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing_raw.lower())
        u_clean = re.sub(r"\([^)]*\)", " ", u_nb.lower())
        main = _w(ing_raw.split(",")[0])
        it = _w(ing_raw)
        segs = [_w(s) for s in u_clean.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        pal = _w(paren)
        ut = [t for s in segs for t in s] + pal
        uset, iset, first = set(ut), set(it), segs[0]
        core = [t for t in main if t not in _BENIGN and t not in _COOK and t not in _DIETW and t not in _STATEW and t not in _INEDIBLE and t not in ("light",)] or [t for t in main if t not in _BENIGN] or main
        head = core[-1]
        # unigram evidence
        uni = sum(1 for t in core if t in uset) / float(len(core))
        # bigram units on the ingredient core (ordered adjacency) vs unordered units of USDA
        iu = set(frozenset((a, b)) for a, b in zip(core, core[1:]))
        uu = _units(segs + ([pal] if pal else []))
        bi = (len(iu & uu) / float(len(iu))) if iu else uni
        score = 3.8 * uni + 2.0 * bi + (1.5 if head in uset else -1.3)
        # specificity direction: USDA first-segment words that are not in ingredient (USDA more specific) vs ingredient words missing in USDA (USDA more generic)
        more_specific = [t for t in first if t not in iset and t not in _BENIGN and t not in _TAXA and t not in _COOK and t not in _STATEW and t not in _DIETW and t not in core]
        more_generic = [t for t in core if t not in uset]
        score -= 0.6 * min(len(more_specific), 3) + 1.0 * min(len(more_generic), 3)
        # rule table
        rules = [
            ((set(first) & _FORMS) - iset, -3.3),
            ((iset & _FORMS) - uset, -1.4),
            ([1] if (first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset) else [], -2.6),
            ([1] if (set(ut) & _COOK and not (iset & _COOK) and "raw" not in uset) else [], -2.2),
            ([1] if ((iset & _COOK) and not (uset & _COOK)) else [], -1.2),
            ([1] if (("dried" in iset and not (iset & _COOK)) != ("dried" in uset and "from" not in uset)) else [], -2.5),
            ([1] if ("pickled" in iset) != ("pickled" in uset) else [], -2.5),
            ([1] if ("smoked" in iset) != ("smoked" in uset) else [], -2.5),
            ([1] if (("canned" in iset) != ("canned" in uset) and not ("canned" in uset and (set(core) & {"applesauce", "olive", "sauce", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple", "peach", "pear"}))) else [], -1.8),
            ([1] if (("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset)) else [], -1.3),
            (list(_INEDIBLE & (iset ^ uset)), -2.7),
            ([1] if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_clean) else [], -3.5),
        ]
        for hit, delta in rules:
            if hit:
                score += delta
        nd = len((uset & _DIETW) - iset) + 0.5 * len((iset & _DIETW) - uset)
        score -= 0.95 * min(nd, 3.0)
        return float(score + 1.5)
    except Exception:
        return 0.0
