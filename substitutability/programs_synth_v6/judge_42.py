import re
import unicodedata

# variety / cultivar -> base food (generic knowledge)
_VARIETY = {
    "concord": "grape", "thompson": "grape", "muscat": "grape", "bing": "cherry", "rainier": "cherry", "morello": "cherry",
    "fuji": "apple", "gala": "apple", "granny": "apple", "mcintosh": "apple", "honeycrisp": "apple", "braeburn": "apple", "pippin": "apple",
    "bartlett": "pear", "anjou": "pear", "bosc": "pear", "comice": "pear",
    "russet": "potato", "yukon": "potato", "fingerling": "potato", "idaho": "potato",
    "roma": "tomato", "beefsteak": "tomato", "cherry tomato": "tomato", "plum tomato": "tomato", "heirloom": "tomato",
    "vidalia": "onion", "shallot": "onion", "walla": "onion",
    "navel": "orange", "valencia": "orange", "seville": "orange", "blood orange": "orange",
    "meyer": "lemon", "key lime": "lime", "persian lime": "lime",
    "hass": "avocado", "fuerte": "avocado",
    "kabocha": "squash", "butternut": "squash", "acorn": "squash", "delicata": "squash", "spaghetti squash": "squash",
    "cremini": "mushroom", "portobello": "mushroom", "shiitake": "mushroom", "button": "mushroom", "oyster mushroom": "mushroom", "baby bella": "mushroom",
    "basmati": "rice", "jasmine": "rice", "arborio": "rice", "sushi rice": "rice",
    "cheddar": "cheddar", "colby": "colby", "monterey jack": "jack",
    "sirloin": "beef", "ribeye": "beef", "brisket": "beef", "chuck": "beef", "flank": "beef", "tenderloin": "beef", "porterhouse": "beef",
    "drumstick": "chicken", "gizzard": "giblet", "innard": "giblet",
    "ox": "beef", "calf": "veal", "mutton": "lamb", "venison": "deer",
}
_WORDSYN = {
    "aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper",
    "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "calamari": "squid", "filbert": "hazelnut", "linseed": "flaxseed",
    "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "pomelo": "grapefruit", "pawpaw": "papaya", "rockmelon": "cantaloupe", "kumara": "sweetpotato",
    "yoghurt": "yogurt", "yogourt": "yogurt", "catsup": "ketchup", "mayo": "mayonnaise", "treacle": "molasses", "wholemeal": "wholewheat", "cornflour": "cornstarch",
    "aubergines": "eggplant", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "pignoli": "pinenut",
    "purée": "puree", "puree": "sauce", "flat": "wing", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "chicory": "endive", "swiss": "swiss",
    "icing": "powdered", "confectioner": "powdered", "caster": "granulated", "castor": "granulated", "porridge": "oatmeal", "semolina": "farina", "polenta": "cornmeal",
}
_PHRASE = [("pine nut", "pinenut"), ("pine kernel", "pinenut"), ("sweet potato", "sweetpotato"), ("green onion", "onion"), ("spring onion", "onion"), ("half and half", "halfandhalf"), ("half-and-half", "halfandhalf"),
           ("brazil nut", "brazilnut"), ("para nut", "brazilnut"), ("bean curd", "tofu"), ("corn syrup", "cornsyrup"), ("garbanzo bean", "chickpea"), ("chick pea", "chickpea"), ("fava bean", "broadbean"), ("faba bean", "broadbean"),
           ("broad bean", "broadbean"), ("fava", "broadbean"), ("butter bean", "limabean"), ("lima bean", "limabean"), ("bell pepper", "bellpepper"), ("sweet pepper", "bellpepper"), ("chinese cabbage", "napa"), ("napa cabbage", "napa"), ("bok choy", "bokchoy"), ("pak choi", "bokchoy"),
           ("ice cream", "icecream"), ("cottage cheese", "cottagecheese"), ("cream cheese", "creamcheese"), ("sour cream", "sourcream"), ("apple sauce", "applesauce"), ("apple puree", "applesauce"), ("apple purée", "applesauce"),
           ("glass noodle", "cellophanenoodle"), ("cellophane noodle", "cellophanenoodle"), ("bean thread", "cellophanenoodle"), ("long rice", "cellophanenoodle"),
           ("hot dog", "frankfurter"), ("wiener", "frankfurter"), ("summer sausage", "cervelat"), ("thuringer", "cervelat"), ("variety meats", "organ"), ("by-products", "organ"), ("by products", "organ"), ("organ meat", "organ"), ("giblets", "giblet"),
           ("plant-based", "vegan"), ("plant based", "vegan"), ("dairy-free", "vegan"), ("non-dairy", "vegan"), ("made with tofu", "vegan"), ("skin-on", "withskin"), ("meat and skin", "withskin"), ("equal parts milk and cream", "halfandhalf"),
           ("high fructose", "highfructose"), ("high-fructose", "highfructose"), ("stew meat", "stewmeat"), ("cocoa butter", "cocoabutter"), ("peanut butter", "peanutbutter"), ("almond butter", "almondbutter"), ("pecan butter", "pecanbutter")]
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf icecream".split())
_DIETW = set("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk organ".split())
_INEDIBLE = {"leaf", "leave", "bone", "peel", "stem", "shell", "rind"}

def _ascii(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def _prep(s):
    s = _ascii(s.lower())
    for a, b in _PHRASE:
        s = s.replace(_ascii(a), b)
    return s

def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("us"):
        return t[:-1]
    return t

def _w(s):
    out = []
    for t in re.findall(r"[a-z]+", s):
        t = _stem(t)
        t = _WORDSYN.get(t, t)
        out.append(t)
    return out

def _variety(tokens):
    """map cultivar words to base food, keep the cultivar word too"""
    base = []
    for t in tokens:
        if t in _VARIETY:
            base.append(_VARIETY[t])
    return base

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def judging_function(ingredient, usda_match):
    try:
        u_nb = _nobrand(str(usda_match or ""))
        paren_alias = " ".join(re.findall(r"\(([^)]*)\)", u_nb))
        ing = re.sub(r"\([^)]*\)", " ", _prep(str(ingredient or "")))
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u_clean = re.sub(r"\([^)]*\)", " ", _prep(u_nb))
        main = _w(ing.split(",")[0])
        it = _w(ing)
        segs = [_w(s) for s in u_clean.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        alias_u = _w(_prep(paren_alias))
        iset = set(it) | set(_variety(it))
        uset = set(ut) | set(alias_u) | set(_variety(ut)) | set(_variety(alias_u))
        first = segs[0]
        # identity: ingredient's core words, cultivar words resolved to base foods
        core = []
        for t in main:
            if t in _BENIGN or t in _COOK or t in _DIETW or t in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter") or t in _INEDIBLE:
                continue
            if t in _VARIETY:
                core.append(_VARIETY[t])
            else:
                core.append(t)
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        head = core[-1]
        matched = [t for t in core if t in uset]
        cov = len(matched) / float(len(core))
        score = 5.0 * cov + (1.6 if head in uset else -1.3)
        # alias-only bonus: head found only via parenthetical alias
        if head in set(alias_u) and head not in set(ut):
            score += 0.8
        # events
        if (set(first) & _FORMS) - iset:
            score -= 3.3
        if (iset & _FORMS) - uset:
            score -= 1.4
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
            score -= 2.6
        ic, uc = bool(iset & _COOK), bool(uset & _COOK)
        if uc and not ic and "raw" not in uset:
            score -= 2.0
        if ic and not uc:
            score -= 1.2
        if ("dried" in iset and not ic) != ("dried" in uset and "from" not in uset):
            score -= 2.5
        for st, p in (("pickled", 2.5), ("smoked", 2.5), ("canned", 2.1)):
            if (st in iset) != (st in uset):
                score -= p
        if ("fried" in iset) != ("fried" in uset) and not (ic and uc):
            score -= 1.3
        if ("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset):
            score -= 1.3
        if _INEDIBLE & (iset ^ uset):
            score -= 2.7
        if ("whole" in iset) != ("whole" in uset) and ("ground" in iset or "ground" in uset):
            score -= 0.8
        score -= 0.95 * min(len((uset & _DIETW) - iset) + 0.5 * len((iset & _DIETW) - uset), 3.0)
        colors = {"red", "green", "yellow", "white", "black", "brown", "orange", "purple"}
        ci, cu = iset & colors, uset & colors
        if ci and cu and not (ci & cu):
            score -= 1.6
        extra = [t for t in first if t not in iset and t not in _BENIGN and t not in _DIETW and t not in core and t not in _TAXA and t not in _COOK and t not in colors and t not in _VARIETY and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground")]
        score -= 0.55 * min(len(extra), 3)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_clean):
            score -= 3.5
        return float(score + 1.5)
    except Exception:
        return 0.0
