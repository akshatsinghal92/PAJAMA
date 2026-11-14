import re
import math

# Approximate per-100g macro vectors: (kcal, protein g, carb g, fat g)
_MACRO_TABLE = [
    # pure fats
    (("oil",), (884, 0, 0, 100)),
    (("butter",), (717, 1, 0, 81)),
    (("lard", "shortening", "ghee", "tallow"), (900, 0, 0, 100)),
    (("margarine",), (717, 0, 1, 80)),
    # nuts and seeds
    (("nut", "nuts", "almond", "almonds", "pecan", "pecans", "walnut", "walnuts",
      "cashew", "cashews", "pistachio", "pistachios", "hazelnut", "hazelnuts",
      "pinyon", "pinon", "macadamia"), (620, 15, 15, 58)),
    (("peanut", "peanuts"), (570, 26, 16, 49)),
    (("seed", "seeds", "sesame", "flax", "chia", "sunflower", "pumpkinseed"), (550, 20, 25, 45)),
    # dairy
    (("cheese", "cheddar", "mozzarella", "parmesan", "feta", "brie", "gouda", "swiss"), (380, 24, 3, 31)),
    (("cream",), (250, 2.5, 4, 25)),
    (("half",), (130, 3, 4.5, 11.5)),
    (("milk",), (60, 3.3, 4.8, 3.2)),
    (("kefir",), (55, 3.5, 4.5, 2.5)),
    (("yogurt", "yoghurt"), (80, 4, 10, 2.5)),
    (("ice", "gelato", "sherbet"), (210, 3.5, 24, 11)),
    (("egg", "eggs"), (143, 12.6, 0.7, 9.5)),
    # meats / proteins
    (("chicken", "turkey", "poultry"), (150, 24, 0, 6)),
    (("beef", "steak", "veal"), (230, 24, 0, 15)),
    (("pork", "ham", "bacon", "sausage", "salami", "pepperoni"), (290, 18, 1, 24)),
    (("lamb", "mutton"), (280, 22, 0, 21)),
    (("fish", "salmon", "tuna", "cod", "tilapia", "trout", "halibut"), (140, 22, 0, 5)),
    (("shrimp", "crab", "lobster", "scallop", "scallops", "clam", "clams", "mussels"), (95, 20, 1, 1.5)),
    (("tofu", "tempeh"), (110, 12, 3, 6)),
    (("luncheon", "deli"), (120, 17, 3, 4)),
    # starches / grains
    (("flour",), (360, 10, 76, 1.5)),
    (("wheat", "barley", "rye", "oats", "oat", "quinoa", "millet", "grain"), (340, 12, 72, 2)),
    (("rice",), (360, 7, 79, 0.6)),
    (("pasta", "spaghetti", "noodle", "noodles", "macaroni"), (370, 13, 75, 1.5)),
    (("bread", "bun", "roll", "bagel", "tortilla", "pita"), (265, 9, 49, 3.5)),
    (("cereal", "cereals"), (380, 7, 84, 3)),
    (("cracker", "crackers", "cookie", "cookies", "cake", "pastry", "muffin"), (440, 6, 65, 18)),
    (("potato", "potatoes"), (77, 2, 17, 0.1)),
    (("bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "pea", "peas"), (120, 8, 21, 0.5)),
    # sweeteners
    (("sugar", "syrup", "honey", "molasses"), (390, 0, 98, 0)),
    (("chocolate", "cocoa"), (540, 6, 58, 31)),
    (("jam", "jelly", "preserves"), (270, 0.4, 69, 0.1)),
    # produce
    (("spinach", "lettuce", "kale", "arugula", "chard", "greens", "cabbage", "collards"), (23, 2.5, 4, 0.4)),
    (("onion", "onions", "garlic", "shallot", "leek", "scallion"), (45, 1.5, 10, 0.1)),
    (("tomato", "tomatoes", "pepper", "peppers", "cucumber", "zucchini", "squash",
      "celery", "carrot", "carrots", "broccoli", "cauliflower", "mushroom", "mushrooms",
      "eggplant", "asparagus"), (30, 1.5, 6, 0.3)),
    (("apple", "banana", "orange", "berry", "berries", "grape", "grapes", "pear",
      "peach", "mango", "pomegranate", "cherry", "cherries", "lemon", "lime",
      "strawberries", "blueberries", "pineapple", "melon"), (60, 0.8, 15, 0.3)),
    (("avocado",), (160, 2, 9, 15)),
    (("raisin", "raisins", "date", "dates", "prune", "prunes", "fig", "figs"), (290, 2.5, 75, 0.5)),
    # condiments / sauces / spices
    (("spice", "spices", "cumin", "paprika", "cinnamon", "oregano", "thyme",
      "basil", "ginger", "turmeric", "nutmeg", "clove", "cloves", "coriander"), (300, 10, 60, 8)),
    (("salt",), (0, 0, 0, 0)),
    (("seasoning", "blend", "rub"), (250, 8, 50, 5)),
    (("sauce", "ketchup", "salsa", "gravy"), (80, 1.5, 15, 1.5)),
    (("mayonnaise", "mayo", "dressing"), (550, 1, 3, 60)),
    (("vinegar",), (20, 0, 1, 0)),
    (("broth", "stock", "bouillon", "soup"), (15, 1.5, 1.5, 0.5)),
    (("souffle", "casserole", "pie", "pizza", "sandwich", "burrito"), (220, 9, 20, 12)),
    (("juice",), (45, 0.5, 11, 0.1)),
    (("water",), (0, 0, 0, 0)),
]

_KEY_INDEX = {}
for _keys, _vec in _MACRO_TABLE:
    for _k in _keys:
        _KEY_INDEX.setdefault(_k, _vec)

# Modifiers: (word set) -> multiplicative vector on (kcal, protein, carb, fat)
_MODIFIERS = [
    (("reduced", "lowfat", "light", "lite", "skim", "nonfat", "fat-free", "lean"), (0.7, 1.05, 1.0, 0.5)),
    (("dried", "dehydrated", "powder", "powdered"), (1.6, 1.6, 1.6, 1.3)),
    (("frozen",), (1.0, 1.0, 1.0, 1.0)),
    (("fried", "breaded", "battered"), (1.45, 0.9, 1.6, 2.2)),
    (("toasted", "roasted"), (1.05, 1.05, 1.05, 1.08)),
    (("sweetened", "candied", "frosted", "glazed"), (1.2, 0.9, 1.5, 1.0)),
    (("cooked", "boiled", "steamed"), (0.9, 0.95, 0.85, 1.0)),
    (("whole", "full"), (1.1, 1.0, 1.0, 1.25)),
    (("patty", "patties", "nuggets"), (1.5, 0.7, 2.0, 2.2)),
]

_DESSERT_FORMS = {"frozen yogurt": (160, 4, 25, 5), "ice cream": (210, 3.5, 24, 11)}

_STOP = {"g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "and", "or",
         "of", "the", "a", "with", "from", "in", "for", "fresh", "chopped", "sliced",
         "diced", "minced", "shredded", "grated", "ground", "thawed", "to", "taste",
         "large", "small", "medium", "tube", "raw", "plain", "uncooked", "prepackaged",
         "ready-to-eat", "brand"}


def _tokens(text):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|oz|lb)?\b", " ", text)
    text = text.replace("low fat", "lowfat").replace("fat free", "fat-free")
    return [t for t in re.findall(r"[a-z][a-z\-]*", text)]


def _singular(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _lookup(tok):
    if tok in _KEY_INDEX:
        return _KEY_INDEX[tok]
    s = _singular(tok)
    if s in _KEY_INDEX:
        return _KEY_INDEX[s]
    return None


def _profile(text, primary_weight):
    """Return (macro vector, confidence, modifier-set) estimated from text."""
    low = (text or "").lower()
    toks = _tokens(text)
    if not toks:
        return None, 0.0, set()
    # composite dessert forms override
    for phrase, vec in _DESSERT_FORMS.items():
        if phrase in low:
            base = list(vec)
            break
    else:
        base = None
    hits = []
    if primary_weight and "," in low:
        # USDA style: primary food first, descriptors after
        segs = [s for s in re.split(r",", low) if s.strip()]
        for si, seg in enumerate(segs):
            w = 1.0 / (1.0 + 0.6 * si)
            for t in _tokens(seg):
                v = _lookup(t)
                if v is not None:
                    hits.append((w, v))
    else:
        n = len(toks)
        for i, t in enumerate(toks):
            v = _lookup(t)
            if v is not None:
                # recipe text: head noun tends to be last
                w = 0.5 + 0.5 * ((i + 1) / float(n))
                hits.append((w, v))
    if base is None:
        if not hits:
            return None, 0.0, set(toks)
        tot = sum(w for w, _ in hits)
        base = [sum(w * v[k] for w, v in hits) / tot for k in range(4)]
        conf = min(1.0, 0.5 + 0.25 * len(hits))
    else:
        conf = 1.0
    mods = set()
    tokset = set(toks)
    for words, mult in _MODIFIERS:
        if tokset.intersection(words):
            mods.add(words[0])
            base = [base[k] * mult[k] for k in range(4)]
    return base, conf, mods


def _macro_distance(a, b):
    # log-ratio distance per macro, with energy share comparison
    d = 0.0
    weights = (1.2, 1.0, 1.0, 1.1)
    for k in range(4):
        x, y = a[k], b[k]
        d += weights[k] * abs(math.log((x + 2.0) / (y + 2.0)))
    # energy composition (share of kcal from P/C/F)
    def shares(v):
        e = 4 * v[1] + 4 * v[2] + 9 * v[3]
        if e <= 0:
            return (0.0, 0.0, 0.0)
        return (4 * v[1] / e, 4 * v[2] / e, 9 * v[3] / e)
    sa, sb = shares(a), shares(b)
    d += 2.0 * sum(abs(sa[i] - sb[i]) for i in range(3))
    return d


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").strip()
        usda = str(usda_match or "").strip()
        if not ing or not usda:
            return 0.0
        pa, ca, ma = _profile(ing, False)
        pb, cb, mb = _profile(usda, True)

        ta = set(_singular(t) for t in _tokens(ing)) - _STOP
        tb = set(_singular(t) for t in _tokens(usda)) - _STOP
        overlap = len(ta & tb) / float(max(1, len(ta | tb)))

        if pa is None or pb is None:
            # no macro knowledge: fall back to weak lexical estimate, capped low-mid
            return round(2.0 + 4.0 * overlap, 3)

        dist = _macro_distance(pa, pb)
        proximity = math.exp(-dist / 1.8)  # 0..1
        conf = math.sqrt(ca * cb)
        score = 10.0 * (conf * proximity + (1 - conf) * 0.4)

        # modifier mismatch: a profile-changing qualifier present on one side only
        shifting = {"reduced", "dried", "fried", "sweetened", "patty"}
        asym = (ma ^ mb) & shifting
        score -= 1.2 * len(asym)
        if ("frozen" in mb) != ("frozen" in ma) and ("yogurt" in tb or "cream" in tb):
            score -= 1.5
        # small bonus for lexical agreement (same food likely same macros)
        score += 1.5 * overlap
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
