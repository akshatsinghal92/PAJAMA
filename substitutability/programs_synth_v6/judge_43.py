import re
import unicodedata
from difflib import SequenceMatcher

_FAMILY = {
    "citrus": "orange tangerine clementine mandarin lemon lime grapefruit pomelo satsuma kumquat citron",
    "brassica": "cabbage broccoli cauliflower kale collard brussels kohlrabi bokchoy napa turnip rutabaga swede mustard radish daikon arugula rocket",
    "allium": "onion scallion shallot leek garlic chive ramp",
    "gourd": "squash zucchini courgette pumpkin cucumber melon cantaloupe watermelon gourd",
    "nightshade": "tomato potato eggplant aubergine pepper capsicum tomatillo",
    "legume": "bean pea lentil chickpea garbanzo broadbean fava lupin soybean edamame peanut",
    "stonefruit": "peach plum apricot cherry nectarine prune",
    "pome": "apple pear quince",
    "berry": "strawberry raspberry blackberry blueberry cranberry currant gooseberry boysenberry loganberry mulberry",
    "pinenut": "pine pinyon pinon pignoli",
    "treenut": "almond walnut pecan hazelnut filbert cashew pistachio macadamia brazil chestnut",
    "gadid": "cod haddock pollock whiting hake",
    "crustacean": "shrimp prawn crab lobster crayfish crawfish langoustine",
    "bovine": "beef veal bison buffalo ox",
    "poultry": "chicken turkey duck goose",
    "greens": "spinach chard kale collard lettuce romaine arugula endive chicory escarole radicchio chrysanthemum shungiku borage",
}
_FAM_OF = {}
for _f, _ws in _FAMILY.items():
    for _w0 in _ws.split():
        _FAM_OF.setdefault(_w0, set()).add(_f)
_EQUIV = {
    "aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper",
    "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "calamari": "squid", "filbert": "hazelnut", "linseed": "flaxseed",
    "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "pawpaw": "papaya", "yoghurt": "yogurt", "catsup": "ketchup", "mayo": "mayonnaise", "treacle": "molasses",
    "cornflour": "cornstarch", "wholemeal": "wholewheat", "bison": "buffalo", "pinyon": "pinenut", "pinon": "pinenut", "pignoli": "pinenut", "poultry": "chicken", "dehydrated": "dried", "uncooked": "raw",
    "puree": "sauce", "flat": "wing", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "icing": "powdered", "caster": "granulated", "porridge": "oatmeal", "polenta": "cornmeal",
    "innard": "giblet", "ox": "beef", "calf": "veal", "mutton": "lamb", "swiss": "swiss",
}
_PHR = [("pine nut", "pinenut"), ("sweet potato", "sweetpotato"), ("green onion", "onion"), ("spring onion", "onion"), ("half and half", "halfandhalf"), ("brazil nut", "brazilnut"), ("para nut", "brazilnut"),
        ("bean curd", "tofu"), ("fava bean", "broadbean"), ("broad bean", "broadbean"), ("fava", "broadbean"), ("butter bean", "limabean"), ("lima bean", "limabean"), ("bell pepper", "bellpepper"), ("sweet pepper", "bellpepper"),
        ("apple sauce", "applesauce"), ("apple puree", "applesauce"), ("glass noodle", "cellophanenoodle"), ("cellophane noodle", "cellophanenoodle"), ("hot dog", "frankfurter"), ("summer sausage", "cervelat"),
        ("variety meats", "organ"), ("by-products", "organ"), ("by products", "organ"), ("plant-based", "vegan"), ("plant based", "vegan"), ("dairy-free", "vegan"), ("made with tofu", "vegan"), ("skin-on", "withskin"),
        ("meat and skin", "withskin"), ("equal parts milk and cream", "halfandhalf"), ("high fructose", "highfructose"), ("stew meat", "stewmeat"), ("cocoa butter", "cocoabutter"), ("peanut butter", "peanutbutter"),
        ("cottage cheese", "cottagecheese"), ("cream cheese", "creamcheese"), ("sour cream", "sourcream"), ("corn syrup", "cornsyrup")]
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_DIETW = set("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk organ".split())
_STATEW = {"dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter"}
_INEDIBLE = {"leaf", "leave", "bone", "peel", "stem", "shell", "rind"}
_DEFAULT_CANNED = {"applesauce", "olive", "sauce", "bean", "tomato", "pumpkin", "corn", "tuna", "sardine", "peach", "pear", "pineapple"}

def _ascii(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def _prep(s):
    s = _ascii(s.lower()).replace("-", " ")
    s = " " + re.sub(r"\s+", " ", s) + " "
    for a, b in _PHR:
        s = s.replace(" " + a.replace("-", " ") + " ", " " + b + " ")
    return s

def _stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("us"):
        return t[:-1]
    return t

def _w(s):
    return [_EQUIV.get(_stem(t), _stem(t)) for t in re.findall(r"[a-z]+", s)]

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _evidence(word, uset, ulist):
    """strength in [0,1] that `word` is named by the USDA entry"""
    if word in uset:
        return 1.0
    best = 0.0
    if len(word) >= 5:
        for x in ulist:
            if len(x) >= 5 and SequenceMatcher(None, word, x).ratio() >= 0.88 and word[:3] == x[:3]:
                best = max(best, 0.9)
    fam = _FAM_OF.get(word, set())
    if fam:
        for x in uset:
            if fam & _FAM_OF.get(x, set()):
                best = max(best, 0.3)   # same botanical/culinary family: weak evidence only
    return best

def judging_function(ingredient, usda_match):
    try:
        u_nb = _nobrand(str(usda_match or ""))
        paren = " ".join(re.findall(r"\(([^)]*)\)", u_nb))
        ing = re.sub(r"\([^)]*\)", " ", _prep(str(ingredient or "")))
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u_clean = re.sub(r"\([^)]*\)", " ", _prep(u_nb))
        main = _w(ing.split(",")[0])
        it = _w(ing)
        segs = [_w(s) for s in u_clean.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        uset = set(ut) | set(_w(_prep(paren)))
        ulist = list(uset)
        iset = set(it)
        first = segs[0]
        core = [t for t in main if t not in _BENIGN and t not in _COOK and t not in _DIETW and t not in _STATEW and t not in _INEDIBLE] or [t for t in main if t not in _BENIGN] or main
        ev = [_evidence(t, uset, ulist) for t in core]
        head_ev = ev[-1]
        ident = (0.65 * sum(ev) / len(ev)) + 0.35 * head_ev
        factor = 1.0
        if (set(first) & _FORMS) - iset:
            factor *= 0.35
        if (iset & _FORMS) - uset:
            factor *= 0.65
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
            factor *= 0.5
        ic, uc = bool(iset & _COOK), bool(uset & _COOK)
        if uc and not ic and "raw" not in uset:
            factor *= 0.6
        if ic and not uc:
            factor *= 0.7
        if ("dried" in iset and not ic) != ("dried" in uset and "from" not in uset):
            factor *= 0.55
        for st, p in (("pickled", 0.55), ("smoked", 0.55), ("canned", 0.7)):
            if (st in iset) != (st in uset):
                if st == "canned" and "canned" in uset and (set(core) & _DEFAULT_CANNED):
                    continue
                factor *= p
        if ("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset):
            factor *= 0.75
        if _INEDIBLE & (iset ^ uset):
            factor *= 0.5
        nd = len((uset & _DIETW) - iset) + 0.5 * len((iset & _DIETW) - uset)
        factor *= 0.8 ** min(nd, 3.0)
        extra = [t for t in first if t not in iset and t not in _BENIGN and t not in _DIETW and t not in core and t not in _TAXA and t not in _COOK and t not in _STATEW and t not in ("red", "green", "yellow", "white", "black", "brown")]
        factor *= 0.9 ** min(len(extra), 3)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_clean):
            factor *= 0.3
        # additive tie-breaker keeps resolution when factor/ident saturate
        return float(10.0 * ident * factor + 1.5 * ident + 0.5 * factor)
    except Exception:
        return 0.0
