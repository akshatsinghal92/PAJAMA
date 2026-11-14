import re
import unicodedata

_ALIAS = {"aubergine": "eggplant", "courgette": "zucchini", "garbanzo": "chickpea", "scallion": "onion", "cilantro": "coriander", "rocket": "arugula", "capsicum": "pepper", "swede": "rutabaga", "beetroot": "beet", "maize": "corn", "prawn": "shrimp", "crawfish": "crayfish", "filbert": "hazelnut", "linseed": "flaxseed", "clementine": "tangerine", "mandarin": "tangerine", "satsuma": "tangerine", "yoghurt": "yogurt", "bison": "buffalo", "pinyon": "pine", "pinon": "pine", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "battered": "batter", "buttered": "butter", "golden": "yellow", "cos": "romaine", "ox": "beef", "calf": "veal", "fava": "broadbean", "innard": "giblet", "flat": "wing", "para": "brazil", "concord": "grape", "bing": "cherry", "navel": "orange", "gala": "apple", "fuji": "apple", "russet": "potato", "roma": "tomato", "portobello": "mushroom", "cremini": "mushroom", "shiitake": "mushroom"}
_COOKV = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled", "sauteed", "poached", "stewed", "heat"}
_NOISE = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american meat by product added moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel without salt fat fresh raw whole heart seed delicious style lean domesticated imported zealand new fluid".split())
_TRANSFORM = set("milk juice oil sauce soup pie cake cookie candy syrup pudding jam jelly muffin cracker chip flour salad dressing sandwich taco entree stew loaf drink beverage extract vinegar seasoning nectar pretzel bar snack frankfurter gravy dip spread icecream puree paste powder".split())
_STATE = {"dried", "canned", "frozen", "smoked", "pickled", "fried", "ground", "powdered", "batter", "lowfat", "nonfat", "reduced", "light", "lite", "skim", "lactose", "sodium", "decaffeinated", "diet", "sweetened", "unsweetened", "flavored", "fortified", "hydrogenated", "leaf", "leave", "bone", "peel", "stem", "shell"} | _COOKV
_TAXA = set("fish beef pork lamb veal chicken turkey duck nut seed cheese lettuce crustacean fruit vegetable game mollusk organ sausage".split())

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
    s = re.sub(r"\bapple ?sauce\b", "applesauce", s)
    s = re.sub(r"\bapple puree\b", "applesauce", s)
    return [_ALIAS.get(_stem(t), _stem(t)) for t in re.findall(r"[a-z]+", s)]

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _cost(t, role):
    """cost of an unmatched token; role 'i' = ingredient token missing from USDA, 'u' = USDA token not in ingredient"""
    if t in _NOISE:
        return 0.05
    if t in _TRANSFORM:
        return 3.2 if role == "u" else 1.6
    if t in _COOKV:
        return 2.2 if role == "u" else 1.3
    if t in ("dried", "pickled", "smoked"):
        return 2.5
    if t in _STATE:
        return 1.2 if role == "u" else 0.8
    if t in _TAXA:
        return 0.15 if role == "u" else 1.5
    return 1.7 if role == "u" else 2.6

def _edit(a, b, ing_set, usda_set):
    """weighted Levenshtein with free reordering of adjacent tokens handled by trying several orderings outside"""
    n, m = len(a), len(b)
    INF = 1e9
    d = [[INF] * (m + 1) for _ in range(n + 1)]
    d[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if d[i][j] >= INF:
                continue
            if i < n:
                c = d[i][j] + _cost(a[i], "i") * (0.4 if a[i] in usda_set else 1.0)
                if c < d[i + 1][j]:
                    d[i + 1][j] = c
            if j < m:
                c = d[i][j] + _cost(b[j], "u") * (0.4 if b[j] in ing_set else 1.0)
                if c < d[i][j + 1]:
                    d[i][j + 1] = c
            if i < n and j < m and a[i] == b[j]:
                if d[i][j] < d[i + 1][j + 1]:
                    d[i + 1][j + 1] = d[i][j]
    return d[n][m]

def judging_function(ingredient, usda_match):
    try:
        u_nb = _nobrand(str(usda_match or ""))
        paren = _w(" ".join(re.findall(r"\(([^)]*)\)", u_nb)))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u_clean = re.sub(r"\([^)]*\)", " ", u_nb.lower())
        itoks = _w(ing.split(",")[0])
        tail = _w(",".join(ing.split(",")[1:]))
        segs = [_w(s) for s in u_clean.split(",") if s.strip()]
        if not itoks or not segs:
            return 0.0
        a = [t for t in itoks + [x for x in tail if x in _STATE]]
        iset = set(a) | set(itoks)
        uflat = [t for s in segs for t in s]
        uset = set(uflat) | set(paren)
        # candidate orderings of the USDA text: as written, hierarchy reversed (category last), and
        # 'natural phrase' order where segment 0 moves behind its modifiers
        orders = [uflat]
        orders.append([t for s in reversed(segs) for t in s])
        if len(segs) > 1:
            orders.append([t for s in (segs[1:] + segs[:1]) for t in s])
        best = min(_edit(a, [t for t in o], iset, uset) for o in orders)
        # head-position check: the ingredient head must be reachable without being demoted to a modifier
        core = [t for t in itoks if t not in _NOISE and t not in _STATE] or itoks
        head = core[-1]
        demote = 0.0
        for si, s in enumerate(segs):
            if head in s:
                k = s.index(head)
                if any(x in _TRANSFORM and x not in iset for x in s[k + 1:]):
                    demote = 3.0
                elif si > 0 and segs[0][0] in _TRANSFORM and segs[0][0] not in iset:
                    demote = 3.0
                break
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u_clean):
            demote += 3.5
        # one-sided dried default-state exemption (dried nuts/fruit sold dried) and reconstituted
        if "dried" in uset and "dried" not in iset and (set(core) & {"nut", "pine", "raisin", "fig", "date", "apricot", "prune", "mushroom", "bean", "pea", "lentil"}):
            best = max(0.0, best - 1.6)
        return float(10.0 - best - demote)
    except Exception:
        return 0.0
