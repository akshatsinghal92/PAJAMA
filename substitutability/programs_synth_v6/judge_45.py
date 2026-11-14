import re
import unicodedata

_ALIAS = {"aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper", "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "filbert": "hazelnut", "linseed": "flaxseed", "clementine": "tangerine", "mandarin": "tangerine", "yoghurt": "yogurt", "bison": "buffalo", "pinyon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "puree": "sauce", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "ox": "beef", "calf": "veal", "fava": "broadbean", "innard": "giblet", "flat": "wing"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_NONFOOD = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style lean light lowfat nonfat reduced sweetened unsweetened flavored".split())
_STATEW = {"dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter"} | _COOK
# nouns that make the leading food a modifier of something else (product-type heads)
_PRODUCT_HEADS = {"milk": 3.5, "juice": 3.5, "oil": 3.5, "sauce": 3.2, "soup": 3.5, "pie": 3.5, "cake": 3.5, "cookie": 3.5, "candy": 3.5, "syrup": 3.2, "pudding": 3.5, "jam": 3.0, "jelly": 3.0, "bread": 2.8, "muffin": 3.5, "cracker": 3.0, "chip": 3.0, "cereal": 2.8, "flour": 3.0, "butter": 2.6, "yogurt": 2.6, "ice": 3.0, "icecream": 3.2, "salad": 3.0, "dressing": 3.2, "sandwich": 3.5, "taco": 3.5, "entree": 3.5, "stew": 3.0, "loaf": 3.0, "drink": 3.2, "beverage": 3.2, "tea": 2.5, "extract": 3.0, "paste": 1.5, "puree": 1.5, "vinegar": 3.0, "powder": 1.6, "flavored": 2.0, "seasoning": 3.0, "spice": 2.5, "frankfurter": 3.0, "sausage": 2.0, "nectar": 3.2, "pretzel": 3.5, "bar": 3.0, "snack": 3.2}
_CATEGORY_FIRST = set("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean cereal fruit vegetable sausage game mollusk organ snack candy spice oil syrup sauce soup bread cracker beverage".split())

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

def _food_words(tokens):
    return [t for t in tokens if t not in _NONFOOD and t not in _STATEW]

def _usda_primary(segs):
    """primary food of a USDA entry: the head (last food word) of segment 0, unless segment 0 is a bare
    category word, in which case the head of segment 1 is the primary food (Beef, chuck ...)"""
    f0 = _food_words(segs[0])
    if not f0:
        return None, []
    if len(f0) == 1 and f0[0] in _CATEGORY_FIRST and len(segs) > 1:
        f1 = _food_words(segs[1])
        if f1:
            return f1[-1], f0 + f1
    return f0[-1], f0

def judging_function(ingredient, usda_match):
    try:
        u_nb = _nobrand(str(usda_match or ""))
        paren = _w(" ".join(re.findall(r"\(([^)]*)\)", u_nb)))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u_clean = re.sub(r"\([^)]*\)", " ", u_nb.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        segs = [_w(s) for s in u_clean.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        iset = set(it)
        ut = [t for s in segs for t in s] + paren
        uset = set(ut)
        i_food = _food_words(main)
        if not i_food:
            i_food = [t for t in main if t not in _NONFOOD] or main
        i_head = i_food[-1]
        u_head, u_lead = _usda_primary(segs)
        if u_head is None:
            return 0.0
        score = 0.0
        # position of ingredient head within USDA
        if i_head == u_head:
            score += 5.0
        elif i_head in u_lead:
            # present in the leading phrase but not as the head => demoted to modifier
            score += 1.0 - _PRODUCT_HEADS.get(u_head, 1.5)
        elif i_head in uset:
            score += 1.5
        else:
            score -= 1.5
        # ingredient modifiers must appear somewhere
        for t in i_food[:-1]:
            if t in uset:
                score += 1.2
            else:
                score -= 1.6
        # USDA leading modifiers that the ingredient lacks (extra defining words before head)
        extra_lead = [t for t in u_lead if t != u_head and t not in iset and t not in _CATEGORY_FIRST]
        score -= 0.8 * min(len(extra_lead), 3)
        # ingredient head is itself a product-type head (cream, cheese...) -> USDA head must equal
        if i_head in _PRODUCT_HEADS and i_head != u_head and i_head not in uset:
            score -= 2.0
        # states
        ic, uc = bool(iset & _COOK), bool(set(ut) & _COOK)
        if uc and not ic and "raw" not in uset:
            score -= 2.2
        if ic and not uc:
            score -= 1.2
        if ("dried" in iset and not ic) != ("dried" in uset and "from" not in uset):
            score -= 2.5
        for st in ("pickled", "smoked"):
            if (st in iset) != (st in uset):
                score -= 2.5
        if ("canned" in iset) != ("canned" in uset) and not ("canned" in uset and (set(i_food) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"})):
            score -= 1.8
        if ("ground" in iset) != ("ground" in uset) or ("powdered" in iset) != ("powdered" in uset):
            score -= 1.3
        if {"leaf", "leave", "bone", "peel", "stem", "shell"} & (iset ^ uset):
            score -= 2.7
        if segs[0] and segs[0][0] in ("frozen", "dried", "canned", "smoked") and segs[0][0] not in iset:
            score -= 2.6
        dn = len((uset & {"lowfat", "nonfat", "reduced", "light", "lite", "skim", "lactose", "sodium", "decaffeinated", "diet", "sweetened", "unsweetened", "flavored", "fortified", "hydrogenated"}) - iset)
        score -= 0.9 * min(dn, 3)
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_clean):
            score -= 3.5
        return float(score + 2.0)
    except Exception:
        return 0.0
