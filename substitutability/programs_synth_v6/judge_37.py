import re

# qualifier axes: axis -> {value: [surface words]}
_AXES = {
    "color": {"red": ["red"], "green": ["green"], "yellow": ["yellow", "golden"], "white": ["white"], "black": ["black"], "brown": ["brown"], "orange": ["orange"], "purple": ["purple", "blue"]},
    "fat": {"whole": ["whole", "full"], "low": ["lowfat", "low", "reduced", "light", "lite", "lean", "skim", "nonfat", "fat-free", "free"]},
    "sweet": {"sweet": ["sweetened", "sweet", "candied"], "unsweet": ["unsweetened", "plain"]},
    "salt": {"salted": ["salted", "salt"], "unsalted": ["unsalted", "without"]},
    "part": {"breast": ["breast"], "thigh": ["thigh", "leg", "drumstick"], "wing": ["wing", "flat"], "liver": ["liver"], "heart": ["heart"], "tongue": ["tongue"], "kidney": ["kidney"], "neck": ["neck"], "skin": ["skin"], "bone": ["bone"], "leaf": ["leaf", "leave", "green"], "seed": ["seed"], "root": ["root", "bulb"], "stalk": ["stalk", "stem"]},
    "texture": {"ground": ["ground", "minced", "crumble", "powder", "powdered"], "whole": ["whole"], "sliced": ["sliced", "slice"], "shredded": ["shredded", "grated"], "chunk": ["chunk", "cube", "diced", "chopped"]},
    "age": {"fresh": ["fresh", "raw"], "aged": ["aged", "ripened"], "dried": ["dried", "dehydrated"], "smoked": ["smoked", "cured"]},
    "variety": {"greek": ["greek"], "italian": ["italian"], "mexican": ["mexican"], "wild": ["wild"], "dutch": ["dutch"], "french": ["french"], "swiss": ["swiss"]},
    "flavor": {"vanilla": ["vanilla"], "chocolate": ["chocolate", "cocoa"], "strawberry": ["strawberry"], "peach": ["peach"], "butter": ["butter", "buttered", "buttery"], "garlic": ["garlic"], "cinnamon": ["cinnamon"], "honey": ["honey"], "lemon": ["lemon"], "banana": ["banana"]},
}
_WORD2AX = {}
for _ax, _vals in _AXES.items():
    for _v, _ws in _vals.items():
        for _w0 in _ws:
            _WORD2AX.setdefault(_w0, []).append((_ax, _v))
_AX_WEIGHT = {"color": 1.6, "fat": 1.5, "sweet": 1.4, "salt": 0.8, "part": 2.2, "texture": 1.1, "age": 1.8, "variety": 1.0, "flavor": 1.5}
_SYN = {"clementine": "tangerine", "mandarin": "tangerine", "filbert": "hazelnut", "linseed": "flaxseed", "crawfish": "crayfish", "prawn": "shrimp", "garbanzo": "chickpea", "yoghurt": "yogurt", "bison": "buffalo", "cilantro": "coriander", "maize": "corn", "dehydrated": "dried", "uncooked": "raw", "poultry": "chicken", "cos": "romaine", "pinyon": "pine", "purée": "puree"}
_QUALWORDS = set(_WORD2AX)
_BENIGN = set("thawed chopped diced minced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless cold hot and of the a in for from or with nfs regular type separable trimmed choice select grade only mature variety flavor other than not eaten free range farmed wild mixed species commercial all strong brewed round atlantic pacific alaska american bing navel meat by product added dry heat moist steak chop fillet tail wing breast thigh shank loin roast rib segment floret piece strip wedge chunk cube rind kernel cooked boiled baked braised simmered broiled roasted steamed toasted grilled sauteed poached stewed canned frozen fried pickled".split())
_FORMNOUN = set("oil juice flour jerky nectar soup stew candy cake pudding snack spice sandwich taco entree cookie syrup sauce frankfurter loaf".split())

def _w(s):
    out = []
    for t in re.findall(r"[a-zé\-]+", s):
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(_SYN.get(t, t))
    return out

def _nobrand(raw):
    return " ".join(t for t in raw.split() if not (len(re.sub(r"[^A-Za-z]", "", t)) >= 3 and re.sub(r"[^A-Za-z]", "", t).isupper()))

def _profile(tokens):
    prof = {}
    for t in tokens:
        for ax, v in _WORD2AX.get(t, []):
            prof.setdefault(ax, set()).add(v)
    return prof

def judging_function(ingredient, usda_match):
    try:
        raw_u = _nobrand(str(usda_match or ""))
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", raw_u.lower())
        main = _w(ing.split(",")[0])
        it = _w(ing)
        ut = _w(u)
        segs = [_w(s) for s in u.split(",") if s.strip()]
        if not main or not segs:
            return 0.0
        iall, uset = set(it), set(ut)
        pi, pu = _profile(it), _profile(ut)
        # qualifier consistency
        qpen = 0.0
        qbonus = 0.0
        for ax in set(pi) | set(pu):
            a, b = pi.get(ax, set()), pu.get(ax, set())
            w = _AX_WEIGHT.get(ax, 1.0)
            if a and b:
                if a & b:
                    qbonus += 0.4 * w
                else:
                    qpen += w * 1.5
            elif a and not b:
                qpen += 0.45 * w      # ingredient states a qualifier USDA drops
            elif b and not a:
                qpen += 0.7 * w       # USDA adds a qualifier the ingredient did not ask for
        # identity: head and non-qualifier content tokens
        core = [t for t in main if t not in _BENIGN and t not in _QUALWORDS]
        if not core:
            core = [t for t in main if t not in _BENIGN] or main
        cov = sum(1 for t in core if t in uset) / float(len(core))
        head = 1.6 if core[-1] in uset else -1.2
        first = segs[0]
        # heavy: form noun swap and brand
        heavy = 0.0
        if (set(first) & _FORMNOUN) - iall:
            heavy += 3.0
        if (iall & _FORMNOUN) - uset:
            heavy += 1.5
        if first and first[0] in ("frozen", "dried", "canned", "smoked") and first[0] not in iall:
            heavy += 2.3
        cook = {"cooked", "boiled", "baked", "braised", "simmered", "broiled", "roasted", "steamed", "toasted", "grilled"}
        ic, uc = bool(iall & cook), bool(uset & cook) or "heat" in uset
        if uc and not ic and "raw" not in uset:
            heavy += 1.8
        if ic and not uc:
            heavy += 1.3
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            heavy += 3.5
        # extra unexplained nouns in first segment
        extra = [t for t in first if t not in iall and t not in _BENIGN and t not in _QUALWORDS and t not in core and t not in ("fish", "beef", "pork", "lamb", "chicken", "turkey", "nut", "cheese", "lettuce", "crustacean", "cereal", "fruit", "vegetable", "sausage")]
        score = 4.5 * cov + head + qbonus - min(qpen, 5.0) - heavy - 0.6 * min(len(extra), 3)
        return float(score + 2.0)
    except Exception:
        return 0.0
