import re
import math

_CLASSES = {
    "meat": "beef pork lamb veal ham bacon sausage buffalo bison liver kidney tongue heart giblet meat steak roast chop brisket salami cervelat thuringer",
    "poultry": "chicken turkey duck goose poultry",
    "seafood": "fish salmon tuna cod swordfish herring pollock bass shrimp crab lobster crayfish crawfish crustacean oyster clam mussel scallop squid lox whitefish trout",
    "dairy": "cheese yogurt yoghurt kefir milk cream butter buttermilk cheddar brie camembert mozzarella parmesan asadero queso",
    "legume": "bean lentil pea chickpea tofu soy tempeh broadbean fava hummus",
    "grain": "flour bread cracker tortilla cornbread cereal oat oatmeal granola farina bran cornmeal pasta noodle rice quinoa amaranth barley wheat popcorn",
    "nut": "nut almond walnut pecan hazelnut pistachio cashew peanut seed flaxseed sesame chia sunflower pine",
    "veg": "lettuce spinach kale chard romaine escarole cabbage greens potato yam carrot beet radish turnip onion garlic leek tomato pepper cucumber zucchini squash eggplant pumpkin olive broccoli cauliflower asparagus celery mushroom artichoke borage corn chrysanthemum",
    "fruit": "apple pear peach plum apricot fig date orange tangerine lemon lime grapefruit berry blueberry strawberry raspberry blackberry cranberry grape cherry mango papaya pineapple banana pomegranate coconut kiwi guava tamarind durian melon watermelon fruit applesauce",
    "spice": "parsley basil cilantro coriander mint sage thyme oregano rosemary dill cinnamon cumin paprika ginger turmeric nutmeg clove cocoa spice herb extract vanilla",
    "fat": "oil shortening lard margarine mayonnaise ghee",
    "sweet": "sugar honey molasses syrup candy jam jelly chocolate",
    "drink": "tea coffee juice nectar wine beer beverage drink broth stock vinegar",
    "dish": "sauce ketchup salsa mustard dressing soup stew entree sandwich taco cookie cake pie pudding snack",
}
_CIDX = {}
_NAMES = sorted(_CLASSES)
for _n, _ws in _CLASSES.items():
    for _x in _ws.split():
        _CIDX.setdefault(_x, []).append(_n)
_ADJ = {frozenset(a) for a in [("meat", "poultry"), ("meat", "seafood"), ("poultry", "seafood"), ("veg", "fruit"), ("legume", "nut"), ("grain", "legume"), ("fat", "nut"), ("sweet", "fruit"), ("dairy", "fat")]}
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "maize": "corn", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "pinyon": "pine", "linseed": "flaxseed", "bison": "buffalo", "granada": "pomegranate", "crawfish": "crayfish", "dehydrated": "dried", "uncooked": "raw", "cos": "romaine"}
_NEUTRAL = set("fresh thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a with in for from or nfs regular plain type separable trimmed choice select grade only mature variety flavor other than not eaten without salt added lean fat free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing golden navel sweet red dark yellow green white black".split())
_STATEW = set("raw cooked boiled baked braised fried simmered broiled roasted steamed toasted dried canned smoked pickled frozen ground whole".split())
_TRANS = set("oil juice syrup sauce soup pudding cookie cake candy jerky flour snack taco sandwich entree spice stew nectar".split())
_DIET = set("lowfat nonfat reduced low light diet sodium decaffeinated lactose imported deli luncheon prepackaged beaked mountain zealand hawaii hydrogenated".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _vec(tokens, first_w=1.0):
    v = {}
    for k, t in enumerate(tokens):
        for c in _CIDX.get(t, []):
            v[c] = v.get(c, 0.0) + 1.0
    return v

def _cos(a, b):
    if not a or not b:
        return None
    dot = sum(a[k] * b.get(k, 0.0) for k in a)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else None

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _w(ing.split(",")[0])
        iall = _w(ing)
        ut = _w(u)
        uf = _w(u.split(",")[0])
        if not it or not ut:
            return 0.0
        vi = _vec(it)
        vu = _vec(uf) or _vec(ut)
        c = _cos(vi, vu)
        if c is None:
            cat = 0.0
        elif c > 0.5:
            cat = 1.0
        elif c > 0:
            cat = 0.2
        else:
            # check adjacency
            adj = any(frozenset((a, b)) in _ADJ for a in vi for b in vu)
            cat = -0.3 if adj else -2.5
        core = [t for t in it if t not in _NEUTRAL and t not in _STATEW]
        if not core:
            core = [t for t in it if t not in _NEUTRAL] or it
        uset = set(ut)
        score = cat
        score += 4.0 * (sum(1 for t in core if t in uset) / float(len(core)))
        score += 1.5 if core[-1] in uset else -0.5
        # explained USDA first segment
        extra = [t for t in uf if t not in _NEUTRAL and t not in _STATEW and t not in set(iall) and t not in _CIDX]
        score -= 0.8 * len(extra)
        if (set(uf) & _TRANS) - set(iall):
            score -= 3.0
        # states
        si, su = set(iall) & _STATEW, uset & _STATEW
        diff = (si ^ su) - {"raw", "whole", "frozen"}
        # cooked family equivalence
        cookfam = {"cooked", "boiled", "baked", "braised", "fried", "simmered", "broiled", "roasted", "steamed", "toasted"}
        if si & cookfam and su & cookfam:
            diff = diff - cookfam
        score -= 1.1 * len(diff)
        score -= 0.9 * len((uset & _DIET) - set(iall))
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score)
    except Exception:
        return 0.0
