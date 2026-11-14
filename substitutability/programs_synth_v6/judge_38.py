import re
import math

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "bison": "buffalo", "cilantro": "coriander", "maize": "corn", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine", "pinyon": "pine", "purée": "puree", "ox": "beef", "calf": "veal", "mutton": "lamb", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "scallion": "onion", "capsicum": "pepper"}
# weight of a qualifier word when it appears on only one side (symmetric difference)
_QW = {}
def _reg(words, w):
    for x in words.split():
        _QW[x] = w
_reg("cooked boiled baked braised simmered broiled roasted steamed toasted grilled sauteed poached stewed heat", 1.7)
_reg("dried pickled smoked cured salted", 2.2)
_reg("canned frozen jarred bottled", 1.0)
_reg("fried battered breaded batter", 1.8)
_reg("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored", 1.1)
_reg("seasoned prepared mix deli luncheon prepackaged hydrogenated fortified imported beaked mountain", 1.1)
_reg("leaf leave bone peel stem skin shell", 1.8)
_reg("ground powdered", 1.2)
_reg("red green yellow white black brown orange purple", 1.2)
_reg("vanilla chocolate strawberry peach banana lemon garlic cinnamon honey butter", 1.3)
_reg("raw whole fresh", 0.0)
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat".split())
_HEAVYFORM = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk seed".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

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
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        iset, uset = set(it), set(ut)
        first = segs[0]
        # weighted symmetric difference over qualifier words
        cook = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
        qi = {t for t in iset if t in _QW}
        qu = {t for t in uset if t in _QW}
        # cooking family collapses to one qualifier
        ci, cu = bool(qi & cook), bool(qu & cook)
        qi = (qi - cook) | ({"cooked"} if ci else set())
        qu = (qu - cook) | ({"cooked"} if cu else set())
        # 'raw' on USDA balances an unmarked ingredient
        sd = 0.0
        for t in qu - qi:
            w = _QW[t]
            if t in ("canned", "frozen", "ground") and t in iset:
                continue
            sd += w
        for t in qi - qu:
            w = _QW[t]
            sd += 0.8 * w
        if "raw" in uset and ci:
            sd += 0.8
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iset:
            sd += 2.0
        if "ground" in iset and "ground" in uset and (("lean" in uset) != ("lean" in iset)):
            sd += 0.8
        # identity
        core = [t for t in main if t not in _BENIGN and t not in _QW]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = core[-1] in uset
        form = 0.0
        if (set(first) & _HEAVYFORM) - iset:
            form += 3.0
        if (iset & _HEAVYFORM) - uset:
            form += 1.5
        extra = [t for t in first if t not in iset and t not in _BENIGN and t not in _QW and t not in core and t not in _TAXA]
        # compound listing
        comp = 0.8 if (re.search(r"\band\b", ing.split(",")[0]) and len(core) >= 2 and cov < 1.0) else 0.0
        z = 1.0 + 4.5 * cov + (1.4 if head else -1.4) - 0.9 * min(sd, 4.5) - form - 0.55 * min(len(extra), 3) - comp
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            z -= 3.5
        return float(1.0 / (1.0 + math.exp(-(z - 3.0) / 1.5)))
    except Exception:
        return 0.0
