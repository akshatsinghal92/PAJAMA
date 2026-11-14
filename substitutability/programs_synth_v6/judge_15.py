import re

# canonical food lexicon: canonical -> aliases. Compare canonical identities, not raw strings.
_LEX = {
    "tangerine": ["clementine", "mandarin", "tangerine"],
    "hazelnut": ["filbert", "hazelnut"],
    "brazilnut": ["para", "brazil"],
    "pinenut": ["pinyon", "pinon", "pine"],
    "flaxseed": ["linseed", "flaxseed", "flax"],
    "broadbean": ["fava", "broadbean"],
    "buffalo": ["bison", "buffalo"],
    "crayfish": ["crawfish", "crayfish", "crawdad"],
    "pomegranate": ["granada", "pomegranate"],
    "chickpea": ["garbanzo", "chickpea"],
    "shrimp": ["prawn", "shrimp"],
    "yogurt": ["yoghurt", "yogurt"],
    "corn": ["maize", "corn"],
    "romaine": ["romaine", "cos"],
    "coriander": ["cilantro", "coriander"],
    "applesauce": ["applesauce"],
    "vegan": ["vegan", "plant"],
}
_ALIAS = {}
for _c, _al in _LEX.items():
    for _a in _al:
        _ALIAS[_a] = _c

_MACRO = {
    "fat": ("oil", "butter", "shortening", "lard", "margarine", "mayonnaise", "ghee"),
    "sugar": ("sugar", "syrup", "honey", "molasses", "candy", "jam", "jelly"),
    "starch": ("flour", "bread", "pasta", "noodle", "rice", "cereal", "oat", "cracker", "tortilla", "cornbread", "granola", "bran", "cookie", "cake", "potato", "yam"),
    "nutseed": ("nut", "almond", "walnut", "pecan", "hazelnut", "pistachio", "cashew", "peanut", "seed", "flaxseed", "sesame", "chia", "tahini", "pinenut", "brazilnut"),
    "dairy": ("cheese", "cream", "milk", "yogurt", "kefir", "butter"),
    "meat": ("beef", "pork", "lamb", "veal", "sausage", "bacon", "ham", "chicken", "turkey", "duck", "buffalo", "liver", "tongue", "kidney", "heart", "giblet", "steak", "roast"),
    "seafood": ("fish", "salmon", "tuna", "cod", "swordfish", "herring", "pollock", "bass", "shrimp", "crab", "lobster", "crayfish", "squid", "oyster", "clam", "mussel", "scallop", "lox", "whitefish", "trout"),
    "legume": ("bean", "lentil", "pea", "chickpea", "tofu", "soy", "broadbean", "hummus", "tempeh"),
    "produce": ("lettuce", "spinach", "kale", "chard", "cabbage", "greens", "romaine", "escarole", "chrysanthemum", "herb", "parsley", "basil", "celery", "broccoli", "cauliflower", "asparagus", "cucumber", "zucchini", "squash", "tomato", "pepper", "radish", "mushroom", "eggplant", "onion", "garlic", "carrot", "beet", "artichoke", "olive"),
    "fruit": ("apple", "pear", "peach", "plum", "cherry", "grape", "berry", "orange", "tangerine", "lemon", "lime", "melon", "watermelon", "papaya", "mango", "pineapple", "banana", "pomegranate", "apricot", "fig", "date", "tamarind", "coconut", "applesauce", "fruit"),
    "liquid": ("juice", "tea", "coffee", "wine", "beer", "broth", "stock", "water", "drink", "beverage", "vinegar", "nectar"),
}
_NEAR = {frozenset(a) for a in [("meat", "seafood"), ("produce", "fruit"), ("starch", "legume"), ("fruit", "sugar"), ("nutseed", "fat"), ("dairy", "fat"), ("produce", "legume")]}
_FILL = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed crushed peeled halved torn crumbled shelled rinsed warmed melted softened ripe large small medium finely optional boneless skinless lean drained of and or the a with in for from to into steak fillet seed segment floret slice piece raw cooked dried canned toasted cold hot nfs whole".split())

def _canon(s):
    out = []
    for w in re.findall(r"[a-zé]+", s):
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(_ALIAS.get(w, w))
    return out

def _macro(tokens):
    for k in range(len(tokens) - 1, -1, -1):
        for m, kws in _MACRO.items():
            if tokens[k] in kws:
                return m
    return None

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        it = _canon(ing.split(",")[0])
        ut = _canon(u.split(",")[0])
        uall = _canon(u)
        if not it or not uall:
            return 0.0
        core = [w for w in it if w not in _FILL] or it
        uset = set(uall)
        cov = sum(1 for w in core if w in uset) / float(len(core))
        head = 1.0 if core[-1] in uset else 0.0
        mi = _macro(core)
        mu = _macro(ut) or _macro(uall)
        if mi and mu:
            if mi == mu:
                mscore = 2.0
            elif frozenset((mi, mu)) in _NEAR:
                mscore = 0.5
            else:
                mscore = -2.0
        else:
            mscore = 0.0
        # energy-density shifters present on only one side
        dens = ["dried", "dehydrated", "powder", "fried", "oil", "syrup", "concentrate", "jerky", "juice", "nonfat", "lowfat", "reduced"]
        dpen = 0.0
        for d in dens:
            if (d in uset) != (d in set(_canon(ing))):
                dpen += 1.0 if d in ("dried", "dehydrated", "powder", "fried", "oil", "syrup", "jerky", "juice") else 0.6
        dpen = min(dpen, 3.0)
        score = 4.5 * cov + 1.8 * head + mscore - dpen
        # cooked vs fresh
        cooked = {"cooked", "boiled", "baked", "roasted", "braised", "fried", "steamed", "simmered", "broiled"}
        ic = bool(set(_canon(ing)) & cooked)
        uc = bool(uset & cooked)
        if ic != uc and not ("raw" in uset and not ic):
            score -= 1.3
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|fast food", u):
            score -= 3.0
        return float(score + 2.0)
    except Exception:
        return 0.0
