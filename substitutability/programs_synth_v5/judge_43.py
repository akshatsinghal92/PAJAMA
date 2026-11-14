import re

ALIASES = {
    "aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "chickpeas": "chickpea",
    "scallion": "onion", "scallions": "onion", "maize": "corn", "pinyon": "pine", "pignoli": "pine",
    "pinon": "pine", "coriander": "cilantro", "rocket": "arugula", "capsicum": "pepper",
    "confectioners": "powdered", "icing": "powdered", "poultry": "chicken", "flats": "wing",
    "flat": "wing", "drumette": "wing", "prawn": "shrimp", "prawns": "shrimp", "swede": "rutabaga",
    "beetroot": "beet", "mince": "ground", "minced": "ground", "chuck": "chuck", "hazelnut": "filbert",
    "hazelnuts": "filbert", "filberts": "filbert", "filbert": "filbert", "cornflour": "cornstarch",
    "caster": "sugar", "treacle": "molasses", "biscuit": "cookie", "crisps": "chips", "aubergines": "eggplant",
    "zucchini": "zucchini", "squash": "squash", "cilantro": "cilantro", "yoghurt": "yogurt",
    "wheat": "wheat", "porridge": "oatmeal", "gammon": "ham", "pinto": "pinto", "kidney": "kidney",
}
FOODS = set("""pork beef chicken turkey lamb veal duck goose fish salmon tuna cod shrimp sausage ham bacon liver tongue
giblets heart kidney cheese milk cream butter egg yogurt kefir sugar honey flour rice oat corn wheat bean beans pea peas
chickpea lentil nut nuts pecan pecans walnut almond hazelnut filbert cashew peanut peanuts pine pistachio onion garlic
ginger pepper tomato potato carrot celery spinach lettuce cabbage eggplant zucchini squash apple banana orange lemon
lime oil olive vinegar salt cinnamon cilantro parsley basil frankfurter jerky cereal borage cheddar colby mozzarella
parmesan sirloin chuck steak wing breast thigh leg shank skin whitefish molasses chocolate cocoa coffee tea""".split())
STATE = set("""cooked boiled fried roasted baked raw dried canned frozen smoked pickled steamed grilled braised
unheated fresh toasted""".split())
FLAVOR = set("strawberry vanilla chocolate flavored sweetened lowfat nonfat substitute imitation artificial".split())
STOP = set("""a an the and or of with without in for from to g kg oz lb ml cup cups tsp tbsp fresh frozen thawed
chopped sliced diced crumbled shredded minced drained trimmed visible fat parts equal nfs plain separable lean
meat only choice grade usda brand salt added""".split())


def _sing(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _toks(s):
    s = (s or "").lower()
    paren = re.findall(r"\(([^)]*)\)", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|lb|ml)?\b", " ", s)
    words = re.findall(r"[a-z]+", s)
    pw = re.findall(r"[a-z]+", " ".join(paren))
    out = []
    for w in words:
        w = ALIASES.get(w, w)
        out.append(_sing(w))
    return out, [_sing(ALIASES.get(w, w)) for w in pw]


def judging_function(ingredient, usda_match):
    try:
        ing, _ = _toks(ingredient)
        u_main = (usda_match or "").split(",")[0]
        ut, up = _toks(usda_match)
        mt, _ = _toks(u_main)
        if not ing or not ut:
            return 0.0
        ing_set = set(ing)
        u_all = set(ut) | set(up)
        head_set = set(mt) | set(up)
        if not ing_set or not head_set:
            return 0.0
        foods = {_sing(f) for f in FOODS}
        ing_f = {w for w in ing_set if w in foods}
        u_f = {w for w in u_all if w in foods}
        score = 0.0
        # concept resolution: shared food concepts
        if ing_f and u_f:
            inter = ing_f & u_f
            score += 6.0 * len(inter) / len(ing_f | u_f)
            # ingredient food concepts missing from usda
            score -= 2.0 * len(ing_f - u_f) / len(ing_f)
            score -= 1.5 * len(u_f - ing_f) / len(u_f)
            if not inter:
                score -= 3.0
        else:
            c = {w for w in ing_set if w not in STOP}
            d = {w for w in u_all if w not in STOP}
            if c and d:
                score += 5.0 * len(c & d) / len(c | d)
        # head noun match: last content word of ingredient vs first USDA token
        icont = [w for w in ing if w not in STOP and w not in STATE]
        if icont and mt:
            if icont[-1] in set(mt) or icont[-1] in u_all:
                score += 2.0
            if mt[0] == icont[-1]:
                score += 1.0
        # all usda main-phrase words appear in ingredient
        mc = [w for w in mt if w not in STOP]
        if mc and all(w in ing_set for w in mc):
            score += 1.5
        # exact-ish
        if set(w for w in ing if w not in STOP) == set(w for w in ut if w not in STOP):
            score += 2.0
        # penalties: flavored / substitute / state mismatch
        for w in FLAVOR:
            if w in u_all and w not in ing_set:
                score -= 2.5
        ist = ing_set & STATE
        ust = u_all & STATE
        if ist and ust and not (ist & ust):
            score -= 1.0
        if "cooked" in ust and "cooked" not in ist and "raw" not in ist and "fresh" not in ing_set:
            score -= 0.5
        if "canned" in ist and "canned" not in ust:
            score -= 1.0
        # extra unmatched non-stop ingredient words signal different product
        extra = [w for w in ing if w not in STOP and w not in u_all and w not in STATE]
        score -= 0.4 * min(len(extra), 4)
        return float(score)
    except Exception:
        return 0.0
