import re

_LABELS = {
    "animal": "beef pork lamb veal ham bacon sausage chicken turkey duck goose buffalo bison liver kidney tongue heart giblet fish salmon tuna cod swordfish herring pollock bass shrimp crab lobster crayfish crawfish crustacean oyster clam mussel scallop squid lox whitefish trout meat poultry",
    "dairy": "cheese yogurt yoghurt kefir milk cream butter buttermilk cheddar brie camembert mozzarella parmesan asadero queso",
    "plant_protein": "bean lentil pea chickpea tofu soy tempeh broadbean fava hummus",
    "grain": "flour bread cracker tortilla cornbread cereal oat oatmeal granola farina bran cornmeal pasta noodle rice quinoa amaranth barley wheat popcorn",
    "nutseed": "nut almond walnut pecan hazelnut pistachio cashew peanut seed flaxseed sesame chia sunflower pine",
    "produce": "lettuce spinach kale chard romaine escarole cabbage greens potato yam carrot beet radish turnip onion garlic leek tomato pepper cucumber zucchini squash eggplant pumpkin olive broccoli cauliflower asparagus celery mushroom artichoke borage apple pear peach plum apricot fig date orange tangerine lemon lime grapefruit berry blueberry strawberry raspberry blackberry cranberry grape cherry mango papaya pineapple banana pomegranate coconut kiwi guava tamarind durian melon watermelon fruit vegetable corn",
    "seasoning": "parsley basil cilantro coriander mint sage thyme oregano rosemary dill cinnamon cumin paprika ginger turmeric nutmeg clove cocoa spice herb extract vanilla",
    "fat": "oil shortening lard margarine mayonnaise ghee",
    "sweet": "sugar honey molasses syrup candy jam jelly chocolate",
    "liquid": "tea coffee juice nectar wine beer beverage drink broth stock vinegar water",
    "prepared": "sauce ketchup salsa mustard dressing soup stew entree sandwich taco cookie cake pie pudding snack",
}
_LAB = {}
for _l, _ws in _LABELS.items():
    for _w in _ws.split():
        _LAB.setdefault(_w, set()).add(_l)

_NOISE = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a with in for from or nfs regular plain type separable trimmed choice select grade only mature variety flavor other than not eaten without salt added lean fat free range farmed wild mixed species commercial".split())
_STATE_GROUPS = [("raw", "uncooked"), ("cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "fried"), ("dried", "dehydrated"), ("canned",), ("smoked", "cured"), ("pickled",)]
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "maize": "corn", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "granada": "pomegranate", "crawfish": "crayfish"}

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _sig(tokens):
    s = set()
    for t in tokens:
        s |= _LAB.get(t, set())
    return s

def _gstate(tokens):
    out = set()
    for gi, g in enumerate(_STATE_GROUPS):
        if any(t in g for t in tokens):
            out.add(gi)
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _w(ing.split(",")[0])
        iall = _w(ing)
        uf = _w(u.split(",")[0])
        ut = _w(u)
        if not it or not ut:
            return 0.0
        si, su = _sig(it), _sig(uf)
        if not su:
            su = _sig(ut)
        # category signal: only a gate. Overlap of label sets.
        if si and su:
            j = len(si & su) / float(len(si | su))
            cat = -2.5 if not (si & su) else (0.4 + 1.2 * j)
        else:
            cat = 0.0
        # exact first-segment identity bonus
        core_i = [t for t in it if t not in _NOISE and t not in ("raw", "cooked", "dried", "canned", "frozen", "toasted", "ground", "whole")]
        core_u = [t for t in uf if t not in _NOISE and t not in ("raw", "cooked", "dried", "canned", "frozen", "toasted", "ground", "whole")]
        exact = 3.0 if (core_i and set(core_i) == set(core_u)) else 0.0
        uset = set(ut)
        cov = sum(1 for t in core_i if t in uset) / float(len(core_i)) if core_i else 0.0
        head = 1.5 if core_i and core_i[-1] in uset else 0.0
        # extra defining words in USDA first segment
        extra = [t for t in core_u if t not in set(iall)]
        extra_pen = 0.7 * len(extra)
        # prepared-form words only in USDA
        prep_pen = 2.8 if ("prepared" in su and "prepared" not in si) else 0.0
        # state group agreement
        gi, gu = _gstate(iall), _gstate(ut)
        if 0 in gi:
            gi = gi - {0}
        if 0 in gu:
            gu = gu - {0}
        state_pen = 0.0
        if gi != gu:
            state_pen = 1.6 if (gi and gu) else 1.1
            if gi - {1} == gu - {1} and not (gi ^ gu) - {1}:
                state_pen = 0.5
        mods = set("lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated".split())
        mod_pen = 0.9 * len((uset & mods) - set(iall))
        score = cat + exact + 3.5 * cov + head - extra_pen - prep_pen - state_pen - mod_pen
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
