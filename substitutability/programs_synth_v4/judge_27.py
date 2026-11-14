import re
from collections import defaultdict

# Hierarchical taxonomy: (category, subcategory) -> keywords
_TAXONOMY = {
    ("dairy", "cheese"): ["cheese", "cheddar", "mozzarella", "parmesan", "ricotta", "feta", "brie", "gouda", "cottage", "swiss", "provolone"],
    ("dairy", "milk"): ["milk", "cream", "buttermilk", "half-and-half", "kefir"],
    ("dairy", "yogurt"): ["yogurt", "yoghurt"],
    ("dairy", "butter"): ["butter", "ghee"],
    ("meat", "poultry"): ["chicken", "turkey", "duck", "goose", "hen", "quail", "broilers", "fryers", "giblets"],
    ("meat", "red"): ["beef", "pork", "lamb", "veal", "mutton", "goat", "venison", "bison", "steak"],
    ("meat", "cured"): ["ham", "bacon", "sausage", "salami", "merguez", "chorizo", "pepperoni", "prosciutto", "frankfurter", "bologna"],
    ("meat", "offal"): ["liver", "kidney", "kidneys", "heart", "tongue", "innards", "tripe", "gizzard", "neck"],
    ("fish", "fish"): ["fish", "salmon", "tuna", "cod", "whitefish", "trout", "halibut", "tilapia", "sardine", "anchovy", "mackerel"],
    ("fish", "shellfish"): ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop", "squid"],
    ("produce", "vegetable"): ["broccoli", "carrot", "onion", "garlic", "potato", "yam", "spinach", "lettuce", "cabbage", "artichoke", "artichokes",
                               "tomato", "pepper", "celery", "zucchini", "squash", "eggplant", "kale", "mushroom", "cucumber", "pea", "peas", "corn", "beet", "leek"],
    ("produce", "fruit"): ["apple", "apples", "orange", "mandarin", "clementine", "tangerine", "banana", "watermelon", "melon", "berry", "strawberry",
                           "blueberry", "grape", "lemon", "lime", "peach", "pear", "plum", "mango", "pineapple", "cherry", "raisin"],
    ("grain", "cereal"): ["cereal", "cereals", "oat", "oats", "granola", "muesli", "flakes"],
    ("grain", "flour_bread"): ["flour", "bread", "rice", "pasta", "spaghetti", "noodle", "noodles", "wheat", "barley", "quinoa", "couscous", "tortilla"],
    ("legume", "legume"): ["bean", "beans", "lentil", "lentils", "chickpea", "chickpeas", "pinto", "soybean", "tofu", "edamame"],
    ("nut_seed", "nut_seed"): ["seed", "seeds", "kernels", "almond", "almonds", "walnut", "pecan", "cashew", "peanut", "sesame", "pistachio", "hazelnut"],
    ("spice", "spice"): ["spice", "spices", "cinnamon", "cumin", "paprika", "ginger", "nutmeg", "clove", "turmeric", "oregano", "basil", "thyme",
                         "rosemary", "parsley", "cilantro", "dill", "sage", "salt"],
    ("fat", "oil"): ["oil", "shortening", "lard", "margarine"],
    ("sweet", "sugar"): ["sugar", "honey", "syrup", "syrups", "molasses", "agave", "sweetener"],
    ("condiment", "sauce"): ["sauce", "ketchup", "mustard", "mayonnaise", "dressing", "salsa", "vinegar", "barbecue", "relish", "spread", "paste"],
    ("beverage", "drink"): ["tea", "coffee", "juice", "soda", "beverage", "wine", "beer", "drink", "lemonade"],
    ("egg", "egg"): ["egg", "eggs"],
}

_KW = {}
for _key, _words in _TAXONOMY.items():
    for _w in _words:
        _KW.setdefault(_w, _key)

# Category affinities (cross-category but related)
_RELATED = {
    frozenset(["meat", "fish"]): 0.25,
    frozenset(["produce", "legume"]): 0.3,
    frozenset(["nut_seed", "legume"]): 0.25,
    frozenset(["fat", "dairy"]): 0.15,
    frozenset(["grain", "legume"]): 0.15,
    frozenset(["sweet", "condiment"]): 0.1,
}

# Form-shifting descriptors that move an item into a different functional category
_FORM_SHIFTERS = {
    "juice": ("beverage", "drink"), "sauce": ("condiment", "sauce"), "spread": ("condiment", "sauce"),
    "salad": ("condiment", "sauce"), "substitute": ("sweet", "substitute"), "patty": ("meat", "processed"),
    "soup": ("condiment", "soup"), "oil": ("fat", "oil"),
}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", t)
    return t


def _tokens(text):
    return re.findall(r"[a-z][a-z\-]*", text)


def _profile(tokens, head_index_fn):
    """Return weighted distribution over (category, subcategory)."""
    prof = defaultdict(float)
    n = len(tokens)
    for i, tok in enumerate(tokens):
        key = _KW.get(tok)
        if key is None and tok.endswith("s"):
            key = _KW.get(tok[:-1])
        if key is None:
            continue
        prof[key] += head_index_fn(i, n)
    total = sum(prof.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in prof.items()}


def _pair_sim(a, b):
    if a == b:
        return 1.0
    if a[0] == b[0]:
        return 0.55
    return _RELATED.get(frozenset([a[0], b[0]]), 0.0)


def _dist_sim(pa, pb):
    if not pa or not pb:
        return None
    s = 0.0
    for ka, va in pa.items():
        best = max(_pair_sim(ka, kb) for kb in pb)
        s += va * best
    r = 0.0
    for kb, vb in pb.items():
        best = max(_pair_sim(kb, ka) for ka in pa)
        r += vb * best
    return 0.5 * (s + r)


def _dominant(prof):
    if not prof:
        return None
    return max(prof.items(), key=lambda kv: kv[1])[0]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_main = ing.split(",")[0]
        ing_toks = _tokens(ing_main)
        usda_segments = [s.strip() for s in usda.split(",") if s.strip()]
        usda_toks = _tokens(usda)
        head_toks = _tokens(usda_segments[0]) if usda_segments else []

        # Ingredient: head noun is near the end of the phrase
        ing_prof = _profile(ing_toks, lambda i, n: 1.0 + 2.0 * (i + 1) / max(n, 1))
        # USDA: primary food first; earlier segments weigh more
        seg_weighted = []
        for si, seg in enumerate(usda_segments):
            for t in _tokens(seg):
                seg_weighted.append((t, 3.0 / (1 + si)))
        usda_prof = defaultdict(float)
        for t, w in seg_weighted:
            key = _KW.get(t) or (_KW.get(t[:-1]) if t.endswith("s") else None)
            if key:
                usda_prof[key] += w
        tot = sum(usda_prof.values())
        usda_prof = {k: v / tot for k, v in usda_prof.items()} if tot > 0 else {}

        sim = _dist_sim(ing_prof, usda_prof)
        if sim is None:
            # Unknown category: fall back on head-term agreement
            common = set(ing_toks) & set(usda_toks)
            sim = 0.4 * min(1.0, len(common) / max(1, len(set(ing_toks))))
        score = 10.0 * sim

        ing_dom = _dominant(ing_prof)
        usda_dom = _dominant(usda_prof)
        if ing_dom and usda_dom:
            if ing_dom == usda_dom:
                score += 1.5
            elif ing_dom[0] != usda_dom[0]:
                score -= 3.0

        # Form shifters present in USDA but not in ingredient -> category drift
        ing_set = set(ing_toks)
        for t in usda_toks:
            base = t[:-1] if t.endswith("s") and t[:-1] in _FORM_SHIFTERS else t
            if base in _FORM_SHIFTERS and base not in ing_set:
                score -= 2.5
                break

        # Compound/mixed ingredients span multiple categories or items
        if re.search(r"\band\b|\bmixed\b|&", ing_main):
            score -= 2.0

        # Substitutes / imitations cross into a different category
        if re.search(r"\b(substitute|imitation|analog)\b", usda) and not re.search(r"\b(substitute|imitation)\b", ing):
            score -= 3.0

        # Same primary food: head of USDA appears in ingredient
        head_set = set(head_toks) | {t[:-1] for t in head_toks if t.endswith("s")}
        if head_set & (ing_set | {t[:-1] for t in ing_set if t.endswith("s")}):
            score += 1.0

        return round(max(0.0, min(15.0, score)), 4)
    except Exception:
        return 0.0
