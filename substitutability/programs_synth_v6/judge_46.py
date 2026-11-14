import re
import unicodedata

_ALIAS = {"aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper", "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "filbert": "hazelnut", "linseed": "flaxseed", "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "yoghurt": "yogurt", "bison": "buffalo", "pinyon": "pine", "pinon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "puree": "sauce", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "ox": "beef", "calf": "veal", "fava": "broadbean", "innard": "giblet", "flat": "wing", "para": "brazil", "concord": "grape", "bing": "cherry", "navel": "orange", "gala": "apple", "fuji": "apple", "russet": "potato", "roma": "tomato", "portobello": "mushroom", "cremini": "mushroom", "shiitake": "mushroom"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_NOISE = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style lean light lowfat nonfat reduced sweetened unsweetened flavored domesticated imported zealand new".split())
_STATEW = {"dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter"} | _COOK
# product nouns: when they follow or lead the ingredient food they demote it
_PRODUCT = set("milk juice oil sauce soup pie cake cookie candy syrup pudding jam jelly muffin cracker chip cereal flour butter yogurt icecream salad dressing sandwich taco entree stew loaf drink beverage extract vinegar seasoning nectar pretzel bar snack frankfurter cheese cream tea coffee wine beer broth stock gravy dip spread bread noodle pasta".split())
_TAXON = set("fish beef pork lamb veal chicken turkey duck nut seed lettuce crustacean fruit vegetable game mollusk organ sausage".split())

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

def _demotion(head, segs, ing_tokens):
    """0 = head leads / stands alone; >0 = head demoted to modifier of a product noun"""
    pen = 0.0
    flat = [t for s in segs for t in s]
    for si, s in enumerate(segs):
        for k, t in enumerate(s):
            if t != head:
                continue
            # followed by a product noun inside the same segment: "almond milk", "tomato soup"
            nxt = [x for x in s[k + 1:] if x in _PRODUCT and x not in ing_tokens]
            if nxt:
                pen = max(pen, 3.2)
            # product noun leads the USDA name: "Oil, hazelnut", "Juice, watermelon", "Flour, amaranth", "Sauce, plum"
            if si > 0 and segs[0] and segs[0][0] in _PRODUCT and segs[0][0] not in ing_tokens:
                pen = max(pen, 3.2)
            if si == 0 and k > 0 and s[0] in _PRODUCT and s[0] not in ing_tokens:
                pen = max(pen, 3.0)
    return pen

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
        ut = [t for s in segs for t in s]
        uset = set(ut) | set(paren)
        core = [t for t in main if t not in _NOISE and t not in _STATEW] or [t for t in main if t not in _NOISE] or main
        head = core[-1]
        # the ingredient may itself be a product noun (cream cheese, olive oil): then the product noun is expected
        iprod = set(t for t in core if t in _PRODUCT)
        score = 0.0
        # presence and first-position of every core word
        for idx, t in enumerate(core):
            wgt = 2.6 if t == head else 1.3
            pos = None
            for si, s in enumerate(segs):
                if t in s:
                    pos = si
                    break
            if pos is None:
                if t in set(paren):
                    score += 0.8 * wgt
                else:
                    score -= 0.9 * wgt
            else:
                score += wgt * (1.0 if pos == 0 else (0.85 if pos == 1 else 0.7))
        score -= _demotion(head, segs, iset)
        # product nouns USDA has but ingredient lacks anywhere in segment 0
        lead_prod = [t for t in segs[0] if t in _PRODUCT and t not in iset and t != head]
        if lead_prod and head not in _PRODUCT:
            score -= 1.0
        # USDA extra food words in the leading segment (a different, more specific food)
        extra = [t for t in segs[0] if t not in iset and t not in _NOISE and t not in _STATEW and t not in _TAXON and t not in _PRODUCT and t not in core]
        score -= 0.6 * min(len(extra), 3)
        # states and parts (same strengths as best prior programs)
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
        if ("canned" in iset) != ("canned" in uset) and not ("canned" in uset and (set(core) & {"applesauce", "olive", "bean", "tomato", "pumpkin", "corn", "tuna", "pineapple"})):
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
        return float(score + 3.0)
    except Exception:
        return 0.0
