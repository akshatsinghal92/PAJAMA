import re

# (keywords) -> approx per 100g (kcal, protein, carb, fat)
_CLASSES = [
    (("oil", "shortening", "lard", "tallow", "butter", "margarine", "ghee"), (850, 0, 0, 95)),
    (("mayonnaise", "mayo"), (690, 1, 1, 75)),
    (("sugar", "syrup", "honey", "molasses", "candy", "jam", "jelly"), (350, 0, 90, 0)),
    (("flour", "bread", "pasta", "noodle", "rice", "cereal", "oat", "oatmeal", "cracker", "tortilla", "cornbread", "granola", "grain", "wheat", "barley", "quinoa", "amaranth", "cornmeal", "bran", "cookie", "cake"), (350, 10, 72, 3)),
    (("nut", "almond", "walnut", "pecan", "hazelnut", "pistachio", "cashew", "peanut", "seed", "flaxseed", "sesame", "chia", "sunflower", "tahini", "pine", "brazil"), (600, 18, 20, 52)),
    (("cheese", "cheddar", "brie", "camembert", "mozzarella", "parmesan", "cream cheese", "asadero", "queso"), (350, 22, 2, 28)),
    (("cream", "half"), (250, 3, 4, 25)),
    (("yogurt", "yoghurt", "kefir"), (65, 4, 8, 2)),
    (("milk", "buttermilk"), (55, 3, 5, 2)),
    (("beef", "pork", "lamb", "veal", "sausage", "bacon", "ham", "steak", "roast", "chuck", "sirloin", "brisket", "tongue", "jerky", "salami", "cervelat", "duck"), (230, 21, 0, 16)),
    (("chicken", "turkey", "poultry", "liver", "kidney", "heart", "giblet", "gizzard"), (170, 22, 0, 8)),
    (("fish", "salmon", "tuna", "cod", "swordfish", "herring", "pollock", "bass", "shrimp", "crab", "lobster", "crayfish", "crawfish", "squid", "oyster", "clam", "mussel", "scallop", "lox", "whitefish", "tilapia", "trout"), (110, 21, 0, 3)),
    (("egg",), (145, 12, 1, 10)),
    (("bean", "lentil", "pea", "chickpea", "tofu", "soy", "broadbean", "hummus", "tempeh", "fava", "lima"), (340, 22, 60, 2)),
    (("lettuce", "spinach", "kale", "chard", "arugula", "romaine", "escarole", "cabbage", "greens", "chrysanthemum", "watercress", "herb", "parsley", "basil", "cilantro", "mint", "sage", "thyme", "celery", "sprout", "broccoli", "cauliflower", "asparagus", "cucumber", "zucchini", "squash", "tomato", "pepper", "radish", "mushroom", "eggplant", "onion", "garlic", "carrot", "beet", "artichoke", "olive", "turnip", "leek", "okra"), (25, 2, 5, 0.3)),
    (("potato", "yam", "cassava", "plantain", "corn", "pumpkin", "taro", "sweet potato", "parsnip"), (85, 2, 20, 0.3)),
    (("apple", "pear", "peach", "plum", "cherry", "grape", "berry", "blueberry", "strawberry", "raspberry", "blackberry", "orange", "tangerine", "clementine", "mandarin", "lemon", "lime", "grapefruit", "melon", "watermelon", "papaya", "mango", "pineapple", "banana", "pomegranate", "apricot", "fig", "date", "tamarind", "coconut", "kiwi", "guava", "applesauce", "jamun", "fruit"), (55, 0.7, 14, 0.3)),
    (("juice", "tea", "coffee", "wine", "beer", "broth", "stock", "water", "drink", "beverage", "soda", "vinegar", "nectar", "brine"), (15, 0.3, 3, 0)),
    (("sauce", "ketchup", "salsa", "dressing", "gravy", "soup", "puree", "mustard", "paste"), (90, 2, 12, 4)),
    (("spice", "pepper", "cinnamon", "paprika", "cumin", "ginger", "turmeric", "oregano", "powder", "seasoning", "cocoa", "extract"), (280, 10, 55, 8)),
]
_FILL = set("fresh frozen thawed chopped diced minced sliced shredded grated cubed ripe large small medium raw cooked dried canned whole of and or the a with in for from nfs".split())

def _words(s):
    out = []
    for w in re.findall(r"[a-z]+", s):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out

def _profile(words):
    # head-first: later words in ingredient and earlier in USDA matter; find best class by scoring matches
    best = None
    best_score = 0.0
    n = len(words)
    for kws, prof in _CLASSES:
        sc = 0.0
        for i, w in enumerate(words):
            if w in kws:
                sc = max(sc, 1.0 + 0.1 * i)
        if sc > best_score:
            best_score, best = sc, prof
    return best

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        u = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        iw = _words(ing.split(",")[0])
        uw = _words(u.split(",")[0])
        uall = _words(u)
        pi = _profile(iw)
        pu = _profile(uw) or _profile(uall)
        # identity overlap
        core = [w for w in iw if w not in _FILL]
        uset = set(uall)
        ov = (sum(1 for w in core if w in uset) / float(len(core))) if core else 0.0
        if pi is None or pu is None:
            return 3.0 * ov
        # normalised macro distance (calories scaled)
        d = abs(pi[0] - pu[0]) / 300.0 + abs(pi[1] - pu[1]) / 20.0 + abs(pi[2] - pu[2]) / 40.0 + abs(pi[3] - pu[3]) / 25.0
        prox = max(0.0, 4.0 - 2.0 * d)
        # cooked / dried changes water content
        wet = {"dried", "dehydrated", "powder", "dry"}
        if (set(iw) & wet) != (set(_words(u)) & wet):
            prox -= 0.8
        score = prox + 5.0 * ov
        if core and core[-1] not in uset:
            score -= 1.5
        if re.search(r"taco bell|mcdonald|burger king|wendy|pizza hut|restaurant|entree|sandwich", u):
            score -= 2.0
        return float(score)
    except Exception:
        return 0.0
