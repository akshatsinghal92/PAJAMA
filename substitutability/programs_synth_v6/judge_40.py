import re

_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "bison": "buffalo", "cilantro": "coriander", "maize": "corn", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine", "pinyon": "pine", "purée": "puree", "ox": "beef", "calf": "veal", "mutton": "lamb", "aubergine": "eggplant", "courgette": "zucchini", "rocket": "arugula", "scallion": "onion", "capsicum": "pepper", "innard": "giblet", "flat": "wing", "battered": "batter", "buttered": "butter", "golden": "yellow", "puree": "sauce"}
_COOK = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing navel meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious".split())
_FORMS = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())
_INEDIBLE = {"leaf", "leave", "bone", "peel", "stem", "shell", "rind"}
_DIETW = set("lowfat nonfat reduced light lite skim lactose sodium decaffeinated diet sweetened unsweetened flavored fortified hydrogenated".split())
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut cheese lettuce crustacean cereal fruit vegetable sausage game mollusk seed".split())
_COLORS = {"red", "green", "yellow", "white", "black", "brown", "orange", "purple"}

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

class _Ctx:
    pass

# ---------- mini judges: each returns a vote (positive = substitutable) ----------
def _j_identity(c):
    v = 5.0 * c.cov + (1.6 if c.head in c.uset else -1.0)
    if len(c.core) >= 2 and c.cov < 0.6:
        v -= 2.0          # modifier+head ingredient whose USDA matches only a fragment
    return v

def _j_form(c):
    v = 0.0
    if (set(c.first) & _FORMS) - c.iset:
        v -= 3.3
    if (c.iset & _FORMS) - c.uset:
        v -= 1.4
    if c.first and c.first[0] in ("frozen", "dried", "canned", "smoked") and c.first[0] not in c.iset:
        v -= 2.6
    return v

def _j_part(c):
    d = (c.iset & _INEDIBLE) ^ (c.uset & _INEDIBLE)
    v = -2.8 if d else 0.0
    if ("seed" in c.iset) != ("seed" in c.uset) and (c.core and c.core[-1] in c.uset) and "seed" not in c.core:
        v -= 1.0
    return v

def _j_state(c):
    v = 0.0
    ic, uc = bool(c.iset & _COOK), bool(c.uset & _COOK)
    if uc and not ic and "raw" not in c.uset:
        v -= 2.0
    if ic and not uc:
        v -= 1.0 if c.is_dish else 1.5
    ing_dried = "dried" in c.iset and not ic
    usda_dried = "dried" in c.uset and "from" not in c.uset
    if ing_dried != usda_dried:
        v -= 2.6
    for st, p in (("pickled", 2.6), ("smoked", 2.6), ("canned", 1.1)):
        if (st in c.iset) != (st in c.uset):
            v -= p
    if ("fried" in c.iset) != ("fried" in c.uset) and not (ic and uc):
        v -= 1.4
    if ("ground" in c.iset) != ("ground" in c.uset) or ("powdered" in c.iset) != ("powdered" in c.uset):
        v -= 1.3
    if "ground" in c.iset and "ground" in c.uset and ("lean" in c.uset) != ("lean" in c.iset):
        v -= 0.8
    return v

def _j_diet(c):
    d = len((c.uset & _DIETW) - c.iset) + 0.5 * len((c.iset & _DIETW) - c.uset)
    return -1.0 * min(d, 3.0)

def _j_color(c):
    ci, cu = c.iset & _COLORS, c.uset & _COLORS
    if ci and cu and not (ci & cu):
        return -1.8
    return 0.0

def _j_spec(c):
    extra = [t for t in c.first if t not in c.iset and t not in _BENIGN and t not in _DIETW and t not in c.core and t not in _TAXA and t not in _COOK and t not in _COLORS and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground")]
    v = -0.6 * min(len(extra), 3)
    n_and_i = len(re.findall(r"\band\b", c.main_text))
    n_and_u = len(re.findall(r"\band\b", c.u_first_text))
    if n_and_i and not n_and_u and len(c.core) >= 2 and c.cov < 1.0:
        v -= 0.8
    return v

def _j_brand(c):
    return -3.5 if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", c.u) else 0.0

_JUDGES = [_j_identity, _j_form, _j_part, _j_state, _j_diet, _j_color, _j_spec, _j_brand]

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        c = _Ctx()
        c.u = u
        c.main_text = ing.split(",")[0]
        c.u_first_text = u.split(",")[0]
        main = _w(c.main_text)
        it = _w(ing)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        ut = [t for s in segs for t in s]
        c.iset, c.uset, c.first = set(it), set(ut), segs[0]
        core = [t for t in main if t not in _BENIGN and t not in _COOK and t not in _DIETW and t not in ("dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter", "butter") and t not in _INEDIBLE]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        c.core = core
        c.head = core[-1]
        c.cov = sum(1 for t in core if t in c.uset) / float(len(core))
        c.is_dish = len(segs) == 1 and "and" in ut
        total = sum(j(c) for j in _JUDGES)
        # continuous tie-breaker: shorter, more generic USDA names are slightly better
        total -= 0.03 * max(0, len(segs) - 2)
        return float(total + 1.0 + 0.02 * c.cov)
    except Exception:
        return 0.0
