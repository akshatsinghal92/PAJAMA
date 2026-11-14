import re
import math

# Category lexicon: stem prefixes -> category. Matching is by token prefix so
# plurals and simple inflections ("tomatoes", "peas") resolve to the same stem.
_LEXICON = {
    "dairy": ["milk", "chees", "brie", "cheddar", "mozzarell", "parmesan", "feta", "ricott",
              "yogurt", "yoghurt", "cream", "butter", "ghee", "kefir", "curd", "mascarpone",
              "gouda", "camembert", "paneer", "whey"],
    "produce": ["apple", "orange", "tangerin", "mandarin", "clementin", "kumquat", "lemon",
                "lime", "grape", "pomegran", "granada", "berr", "strawberr", "banana", "mango",
                "pear", "peach", "plum", "cherr", "melon", "tomato", "potato", "onion", "garlic",
                "carrot", "celery", "lettuce", "spinach", "kale", "cabbage", "broccoli",
                "cauliflower", "pepper", "cucumber", "zucchini", "squash", "pumpkin", "eggplant",
                "aubergin", "mushroom", "leek", "shallot", "beet", "radish", "turnip", "fig",
                "date", "apricot", "avocado", "pineapple", "kiwi", "papaya", "seaweed", "agar",
                "kelp", "nori", "vegetabl", "fruit", "leaves", "leaf", "sprout", "artichok",
                "asparagus", "okra", "corn", "yam", "cassava", "juice"],
    "meat": ["chicken", "beef", "pork", "lamb", "mutton", "turkey", "duck", "veal", "bacon",
             "ham", "sausag", "salami", "fish", "salmon", "tuna", "cod", "shrimp", "prawn",
             "crab", "lobster", "anchov", "sardin", "trout", "goat", "venison", "steak",
             "mince", "egg", "clam", "mussel", "oyster", "squid", "patty"],
    "grain": ["flour", "rice", "wheat", "oat", "barley", "bread", "pasta", "noodl", "spaghett",
              "gnocchi", "tortilla", "wrap", "couscous", "quinoa", "bulgur", "rye", "millet",
              "cornmeal", "polenta", "cereal", "cracker", "bun", "roll", "bagel", "pita",
              "macaroni", "semolina", "cookie", "cake", "biscuit"],
    "legume": ["bean", "lentil", "chickpea", "pea", "split", "soy", "tofu", "tempeh",
               "edamame", "dal", "dhal", "peanut", "hummus"],
    "spice": ["sage", "basil", "oregano", "thyme", "rosemary", "parsley", "cilantro",
              "coriander", "cumin", "turmeric", "paprika", "cinnamon", "nutmeg", "clove",
              "ginger", "cardamom", "pepper", "chili", "chile", "mint", "dill", "tarragon",
              "fennel", "saffron", "vanilla", "spice", "herb", "salt", "bay", "allspice",
              "anise", "mustard", "seasoning"],
    "fat": ["oil", "lard", "shortening", "margarin", "tallow", "dripping", "fat"],
    "sweet": ["sugar", "honey", "syrup", "molasses", "jaggery", "agave", "stevia",
              "sweeten", "candy", "chocolate", "jam", "jelly"],
    "condiment": ["sauce", "ketchup", "mayonnais", "vinegar", "dressing", "paste", "salsa",
                  "relish", "chutney", "pesto", "gravy", "soup", "broth", "stock", "marinad"],
    "nutseed": ["almond", "walnut", "cashew", "pecan", "hazelnut", "pistachio", "seed",
                "sesame", "sunflower", "chia", "flax", "nut"],
}

# Partial compatibility between distinct categories (symmetric).
_AFFINITY = {
    frozenset(["produce", "legume"]): 0.45,
    frozenset(["produce", "spice"]): 0.2,
    frozenset(["legume", "nutseed"]): 0.4,
    frozenset(["dairy", "fat"]): 0.4,
    frozenset(["grain", "legume"]): 0.2,
    frozenset(["sweet", "condiment"]): 0.2,
    frozenset(["spice", "condiment"]): 0.25,
    frozenset(["nutseed", "fat"]): 0.2,
}

_CATS = list(_LEXICON.keys())

_PREP = set("""fresh frozen thawed dried dry chopped sliced diced minced grated drained
ground whole raw cooked boiled large small medium fine finely roughly peeled softened
melted segments pieces of and the a for from tube canned soft""".split())

# Words in USDA entries that signal a processed/prepared product (process shift)
_PROCESS_SIGNALS = ["fat added", "from restaurant", "prepared", "with ", "flavored",
                    "breaded", "fried", "sandwich", "ready-to-eat", "mix"]


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|tbsp|tsp|cups?)\b", " ", text)
    text = re.sub(r"[^a-z\s,]", " ", text)
    return text


def _match_stem(tok):
    hits = []
    for cat in _CATS:
        best = 0
        for stem in _LEXICON[cat]:
            if tok == stem or (len(stem) >= 3 and tok.startswith(stem) and len(tok) - len(stem) <= 3):
                best = max(best, len(stem))
        if best:
            hits.append((cat, best))
    return hits


def _profile(words, position_decay):
    """Build a category weight vector; earlier/later words weighted by decay."""
    vec = dict((c, 0.0) for c in _CATS)
    n = len(words)
    for i, w in enumerate(words):
        if w in _PREP or len(w) < 2:
            continue
        hits = _match_stem(w)
        if not hits:
            continue
        weight = position_decay(i, n)
        share = 1.0 / len(hits)
        for cat, slen in hits:
            vec[cat] += weight * share * (0.6 + 0.1 * min(slen, 4))
    return vec


def _affinity_matrix_product(a, b):
    num = 0.0
    for ca in _CATS:
        if a[ca] <= 0:
            continue
        for cb in _CATS:
            if b[cb] <= 0:
                continue
            if ca == cb:
                k = 1.0
            else:
                k = _AFFINITY.get(frozenset([ca, cb]), 0.0)
            num += a[ca] * b[cb] * k
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return None
    return num / (na * nb)


def _dominant(vec):
    best = max(vec.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else None


def judging_function(ingredient, usda_match):
    try:
        ing = _tokens(str(ingredient or ""))
        usda_raw = str(usda_match or "")
        usda = _tokens(usda_raw)
        if not ing.strip() or not usda.strip():
            return 0.0

        # Ingredient: head noun is usually last -> weight later words more.
        ing_main = ing.split(",")[0]
        ing_words = ing_main.split()
        ing_vec = _profile(ing_words, lambda i, n: 0.5 + 1.5 * ((i + 1) / float(n)))

        # USDA: primary food first -> weight first segment heavily, descriptors less.
        segs = [s.split() for s in usda.split(",") if s.strip()]
        usda_vec = dict((c, 0.0) for c in _CATS)
        for si, seg in enumerate(segs[:4]):
            seg_weight = [2.0, 1.0, 0.5, 0.3][si]
            pv = _profile(seg, lambda i, n: 1.0)
            for c in _CATS:
                usda_vec[c] += pv[c] * seg_weight

        sim = _affinity_matrix_product(ing_vec, usda_vec)

        ing_dom = _dominant(ing_vec)
        usda_dom = _dominant(usda_vec)

        if sim is None:
            # One side has no recognisable category: fall back to lexical overlap.
            iw = set(w for w in ing_words if w not in _PREP and len(w) > 2)
            uw = set(w for s in segs for w in s if len(w) > 2)
            if not iw or not uw:
                return 3.0
            ov = 0
            for a in iw:
                for b in uw:
                    if a[:4] == b[:4]:
                        ov += 1
                        break
            return round(2.0 + 4.0 * ov / float(len(iw)), 3)

        score = 10.0 * sim

        # Dominant-category agreement bonus / mismatch penalty.
        if ing_dom and usda_dom:
            if ing_dom == usda_dom:
                score += 1.5
            else:
                k = _AFFINITY.get(frozenset([ing_dom, usda_dom]), 0.0)
                score -= 3.0 * (1.0 - k)

        # Brand-like first segment with no category signal (e.g. "Sage Valley, ...")
        if segs:
            first_vec = _profile(segs[0], lambda i, n: 1.0)
            first_dom = _dominant(first_vec)
            if re.match(r"^\s*[A-Z][a-z]+(\s+[A-Z][a-z]+)+\s*,", usda_raw) and first_dom != ing_dom:
                score -= 2.0

        # Processing shift within the same category (e.g. "fat added").
        low = usda_raw.lower()
        ing_low = str(ingredient).lower()
        for sig in _PROCESS_SIGNALS:
            if sig in low and sig.strip() not in ing_low:
                score -= 1.0

        # Part mismatch: ingredient asks for leaves of a fruit
        if re.search(r"\bleaves?\b", ing_low) and not re.search(r"\bleaves?\b", low):
            score -= 2.5

        return round(max(0.0, min(12.0, score)), 3)
    except Exception:
        return 0.0
