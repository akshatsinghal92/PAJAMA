import re

_ROLE_WORDS = {
    "fat": "oil shortening lard margarine butter ghee mayonnaise tallow",
    "sweetener": "sugar honey syrup molasses",
    "aromatic": "onion garlic leek shallot scallion ginger",
    "herbspice": "parsley basil cilantro coriander mint sage thyme oregano rosemary dill cinnamon cumin paprika turmeric nutmeg clove spice herb vanilla extract",
    "starch": "flour bread cracker tortilla cornbread cereal oat oatmeal granola farina bran cornmeal pasta noodle rice quinoa amaranth barley wheat potato yam popcorn gnocchi",
    "protein": "beef pork lamb veal ham bacon sausage chicken turkey duck buffalo liver kidney tongue fish salmon tuna cod swordfish herring pollock bass shrimp crab lobster crayfish oyster clam egg tofu tempeh",
    "legume": "bean lentil pea chickpea broadbean hummus",
    "nutseed": "nut almond walnut pecan hazelnut pistachio cashew peanut seed flaxseed sesame chia sunflower pine",
    "dairy": "cheese yogurt kefir milk cream buttermilk",
    "veg": "lettuce spinach kale chard romaine escarole cabbage greens carrot beet radish tomato pepper cucumber zucchini squash eggplant pumpkin olive broccoli cauliflower asparagus celery mushroom artichoke corn borage",
    "fruit": "apple pear peach plum apricot fig date orange tangerine lemon lime grapefruit berry blueberry strawberry raspberry blackberry cranberry grape cherry mango papaya pineapple banana pomegranate coconut kiwi guava tamarind durian melon watermelon fruit",
    "liquid": "tea coffee juice nectar wine beer broth stock vinegar water beverage drink",
    "condiment": "sauce ketchup salsa mustard dressing marinara gravy",
}
_ROLE = {}
for _r, _ws in _ROLE_WORDS.items():
    for _x in _ws.split():
        _ROLE.setdefault(_x, _r)
_ROLE_GROUP = {"fat": "fat", "sweetener": "sweet", "aromatic": "flavor", "herbspice": "flavor", "starch": "bulk", "protein": "main", "legume": "main", "nutseed": "crunch", "dairy": "dairy", "veg": "produce", "fruit": "produce", "liquid": "liquid", "condiment": "sauce"}
_TEX = [("powder", "ground powder powdered flour meal dust"), ("paste", "paste puree sauce butter spread cream mayonnaise syrup juice oil nectar dressing gravy"), ("whole", "whole seed kernel leaf leave nut bean pea slice floret"), ("ground", "crumble crumbles minced mince grated shredded patty")]
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "fava": "broadbean", "maize": "corn", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "dehydrated": "dried", "granada": "pomegranate", "cos": "romaine", "uncooked": "raw", "poultry": "chicken", "purée": "puree"}
_BENIGN = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten lean free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel meat by product raw fat without salt added dry heat moist steak chop fillet heart tail neck wing breast thigh leg shank loin roast rib flat".split())
_BEHAVE = set("lowfat nonfat reduced light diet lactose sodium decaffeinated skim sweetened salted flavored breaded battered seasoned prepared mix deli luncheon imported beaked fortified hydrogenated strawberry peach chocolate oat vegetable".split())
_STATES = {"cooked": "k", "boiled": "k", "baked": "k", "braised": "k", "simmered": "k", "broiled": "k", "roasted": "k", "steamed": "k", "toasted": "k", "fried": "f", "dried": "d", "canned": "c", "smoked": "s", "pickled": "p", "frozen": "z"}

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _role(tokens):
    for t in reversed(tokens):
        if t in _ROLE:
            return _ROLE[t]
    return None

def _texture(tokens):
    s = set(tokens)
    for name, ws in _TEX:
        if s & set(ws.split()):
            return name
    return "whole"

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        ut = _w(u)
        uf = _w(u.split(",")[0])
        if not main or not ut:
            return 0.0
        iset, uset = set(it), set(ut)
        ri = _role(main)
        ru = _role(uf) or _role(ut)
        # role consistency
        if ri and ru:
            if ri == ru:
                role = 2.0
            elif _ROLE_GROUP[ri] == _ROLE_GROUP[ru]:
                role = 1.2
            else:
                role = -3.0
        else:
            role = 0.0
        # texture / shape consistent
        ti, tu = _texture(main), _texture(uf)
        tex = 0.0
        if ti != tu:
            if {ti, tu} == {"whole", "powder"} or {ti, tu} == {"paste", "powder"}:
                tex = -2.0
            elif {ti, tu} == {"whole", "paste"}:
                tex = -1.2
            else:
                tex = -0.6
        # identity
        core = [t for t in main if t not in _BENIGN and t not in _STATES and t not in _BEHAVE and t not in ("ground", "whole")]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = 1.5 if core[-1] in uset else -1.0
        # behaviour modifiers present only on one side change function (low fat, flavored, sweetened ...)
        beh = len((uset & _BEHAVE) - iset) + 0.5 * len((iset & _BEHAVE) - uset)
        # state changes that alter behaviour
        fi = set(_STATES[t] for t in iset if t in _STATES)
        fu = set(_STATES[t] for t in uset if t in _STATES)
        sp = 1.3 * len((fi ^ fu) - {"z"})
        front = 2.0 if (uf and uf[0] in ("frozen", "dried", "canned", "smoked") and uf[0] not in iset) else 0.0
        trans = 2.5 if (set(uf) & {"oil", "juice", "flour", "jerky", "nectar", "soup", "stew", "candy", "cake", "pudding", "snack", "spice", "sandwich", "taco", "entree", "cookie", "syrup", "frankfurter"}) - iset else 0.0
        score = role + tex + 4.5 * cov + head - 1.0 * min(beh, 3.5) - sp - front - trans
        pi = set(t for t in iset if t in ("seed", "leaf", "leave", "bone", "peel", "stem", "shell"))
        pu = set(t for t in uset if t in ("seed", "leaf", "leave", "bone", "peel", "stem", "shell"))
        score -= 1.8 * len(pi ^ pu)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score + 2.0)
    except Exception:
        return 0.0
