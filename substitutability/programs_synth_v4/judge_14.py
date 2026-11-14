import re
import math

# Approximate per-100g macro vectors: (kcal/100, protein, carbs, fat, water-ish)
_CLASS_MACROS = {
    "pure_fat":     (8.8, 0.0, 0.0, 99.0, 0.0),
    "lean_meat":    (1.4, 24.0, 0.0, 4.0, 70.0),
    "fatty_meat":   (2.8, 18.0, 0.0, 22.0, 58.0),
    "organ":        (1.2, 18.0, 2.0, 4.0, 74.0),
    "processed_meat": (3.0, 14.0, 3.0, 26.0, 52.0),
    "fish":         (1.1, 21.0, 0.0, 3.0, 75.0),
    "dried_fish":   (3.0, 62.0, 0.0, 3.0, 18.0),
    "leafy":        (0.2, 1.5, 3.5, 0.3, 94.0),
    "vegetable":    (0.35, 2.0, 7.0, 0.3, 89.0),
    "fruit":        (0.55, 0.8, 14.0, 0.3, 84.0),
    "juice":        (0.5, 0.3, 12.5, 0.1, 86.0),
    "dried_fruit":  (2.9, 2.5, 72.0, 0.5, 20.0),
    "sugar":        (3.9, 0.0, 99.0, 0.0, 0.5),
    "grain":        (3.7, 11.0, 70.0, 4.0, 11.0),
    "cereal":       (3.8, 8.0, 80.0, 4.0, 3.0),
    "bran":         (3.2, 13.0, 50.0, 20.0, 6.0),
    "legume":       (1.3, 8.0, 23.0, 0.6, 66.0),
    "dairy_liquid": (0.6, 3.3, 4.8, 3.3, 88.0),
    "yogurt":       (0.9, 6.0, 12.0, 2.0, 79.0),
    "cheese_soft":  (1.0, 11.0, 3.5, 4.5, 79.0),
    "cheese_hard":  (4.0, 25.0, 1.5, 33.0, 37.0),
    "nut":          (6.0, 18.0, 20.0, 52.0, 4.0),
    "sweet_cream":  (3.5, 2.0, 50.0, 17.0, 30.0),
    "sauce":        (0.9, 2.0, 12.0, 2.5, 82.0),
    "spice_dry":    (3.2, 10.0, 60.0, 10.0, 8.0),
    "herb_fresh":   (0.5, 3.0, 8.0, 0.8, 85.0),
    "egg":          (1.45, 12.5, 0.7, 10.0, 76.0),
    "baked":        (3.4, 8.0, 55.0, 10.0, 28.0),
    "beverage":     (0.4, 0.2, 10.0, 0.0, 89.0),
}

# keyword -> class, ordered by priority (first hit with highest weight wins)
_KEYWORDS = [
    ("juice", "juice", 5), ("nectar", "juice", 4), ("soda", "beverage", 4),
    ("oil", "pure_fat", 5), ("lard", "pure_fat", 5), ("shortening", "pure_fat", 5),
    ("butter", "pure_fat", 3), ("ghee", "pure_fat", 5),
    ("sauce", "sauce", 4), ("marinara", "sauce", 4), ("salsa", "sauce", 4),
    ("gravy", "sauce", 4), ("ketchup", "sauce", 4), ("dressing", "sauce", 3),
    ("spices", "spice_dry", 5), ("ground", "spice_dry", 1), ("powder", "spice_dry", 2),
    ("seasoning", "spice_dry", 3),
    ("sage", "herb_fresh", 2), ("basil", "herb_fresh", 2), ("parsley", "herb_fresh", 2),
    ("cilantro", "herb_fresh", 2), ("thyme", "herb_fresh", 2), ("rosemary", "herb_fresh", 2),
    ("mint", "herb_fresh", 2), ("dill", "herb_fresh", 2), ("oregano", "herb_fresh", 2),
    ("sugar", "sugar", 4), ("honey", "sugar", 2), ("syrup", "sugar", 3), ("molasses", "sugar", 3),
    ("cereal", "cereal", 4), ("cereals", "cereal", 4), ("oat", "grain", 2), ("oats", "grain", 2),
    ("granola", "cereal", 3),
    ("bran", "bran", 4), ("rice", "grain", 2), ("flour", "grain", 3), ("pasta", "grain", 2),
    ("bread", "baked", 3), ("cake", "baked", 3), ("cookie", "baked", 3), ("muffin", "baked", 3),
    ("beans", "legume", 3), ("lentils", "legume", 3), ("chickpeas", "legume", 3), ("peas", "legume", 2),
    ("yogurt", "yogurt", 5), ("milk", "dairy_liquid", 3), ("cream", "sweet_cream", 1),
    ("cottage", "cheese_soft", 4), ("ricotta", "cheese_soft", 4), ("cheese", "cheese_hard", 3),
    ("coconut", "nut", 2), ("nuts", "nut", 3), ("almond", "nut", 3), ("walnut", "nut", 3),
    ("peanut", "nut", 3), ("cashew", "nut", 3), ("pecan", "nut", 3),
    ("egg", "egg", 3), ("eggs", "egg", 3),
    ("lettuce", "leafy", 4), ("romaine", "leafy", 4), ("spinach", "leafy", 4), ("kale", "leafy", 4),
    ("cabbage", "leafy", 3), ("chard", "leafy", 4), ("arugula", "leafy", 4), ("greens", "leafy", 3),
    ("broccoli", "vegetable", 3), ("carrot", "vegetable", 3), ("onion", "vegetable", 3),
    ("pepper", "vegetable", 2), ("tomato", "vegetable", 2), ("squash", "vegetable", 3),
    ("potato", "vegetable", 2), ("celery", "vegetable", 3), ("mushroom", "vegetable", 3),
    ("fruit", "fruit", 3), ("apple", "fruit", 3), ("berry", "fruit", 2), ("blackberry", "fruit", 2),
    ("pomegranate", "fruit", 3), ("orange", "fruit", 3), ("banana", "fruit", 3), ("grape", "fruit", 3),
    ("mango", "fruit", 3), ("pear", "fruit", 3), ("peach", "fruit", 3), ("ugli", "fruit", 3),
    ("raisins", "dried_fruit", 4), ("prunes", "dried_fruit", 4), ("dates", "dried_fruit", 3),
    ("sausage", "processed_meat", 4), ("bacon", "processed_meat", 4), ("salami", "processed_meat", 4),
    ("ham", "processed_meat", 3), ("bologna", "processed_meat", 4), ("hot dog", "processed_meat", 4),
    ("patty", "processed_meat", 3),
    ("kidney", "organ", 4), ("kidneys", "organ", 4), ("liver", "organ", 4), ("giblets", "organ", 4),
    ("heart", "organ", 3), ("tripe", "organ", 4),
    ("fish", "fish", 3), ("cod", "fish", 3), ("salmon", "fish", 3), ("tuna", "fish", 3),
    ("shrimp", "fish", 3), ("tilapia", "fish", 3),
    ("chicken", "lean_meat", 2), ("turkey", "lean_meat", 2), ("poultry", "lean_meat", 2),
    ("breast", "lean_meat", 1), ("sirloin", "lean_meat", 2), ("loin", "lean_meat", 1),
    ("beef", "fatty_meat", 2), ("lamb", "fatty_meat", 2), ("pork", "fatty_meat", 2),
    ("veal", "lean_meat", 2), ("chop", "fatty_meat", 1), ("neck", "lean_meat", 1),
]

_PHRASE_RE = None


def _norm(text):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|l|oz|lb)\b", " ", text)
    text = re.sub(r"[^a-z\s,/-]", " ", text)
    return text


def _tokens(text):
    return [t for t in re.split(r"[\s,/-]+", text) if t]


def _class_votes(text, primary_bonus_tokens):
    votes = {}
    toks = _tokens(text)
    tokset = set(toks)
    joined = " " + " ".join(toks) + " "
    for kw, cls, w in _KEYWORDS:
        hit = (" " + kw + " ") in joined if " " in kw else kw in tokset
        if not hit:
            continue
        weight = float(w)
        if kw in primary_bonus_tokens:
            weight *= 1.6
        votes[cls] = votes.get(cls, 0.0) + weight
    return votes


def _profile(text, primary_tokens, is_usda):
    votes = _class_votes(text, primary_tokens)
    toks = set(_tokens(text))
    # state adjustments that move macros
    if "dried" in toks or "dehydrated" in toks or "salted" in toks:
        if "fish" in votes or "cod" in toks:
            votes["dried_fish"] = votes.get("dried_fish", 0) + 6
        if "fruit" in votes:
            votes["dried_fruit"] = votes.get("dried_fruit", 0) + 4
    if "fresh" in toks or "leaves" in toks:
        if "spice_dry" in votes:
            votes["spice_dry"] *= 0.4
    if is_usda and "spices" in toks:
        votes["spice_dry"] = votes.get("spice_dry", 0) + 6
    if "cream" in toks and "coconut" in toks:
        votes["sweet_cream"] = votes.get("sweet_cream", 0) + 3
    if not votes:
        return None
    total = sum(votes.values())
    vec = [0.0] * 5
    for cls, v in votes.items():
        m = _CLASS_MACROS[cls]
        for i in range(5):
            vec[i] += m[i] * v / total
    top = max(votes.items(), key=lambda kv: kv[1])[0]
    return vec, top, votes


def _macro_distance(a, b):
    # scale: kcal/100 (x8), protein, carbs, fat, water (x0.4)
    scales = (8.0, 1.0, 1.0, 1.0, 0.4)
    d = 0.0
    for i in range(5):
        d += (scales[i] * (a[i] - b[i])) ** 2
    return math.sqrt(d)


def _primary(text):
    head = text.split(",")[0]
    return set(_tokens(head))


def _stem(t):
    for suf in ("ies", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0

        ing_main = ing.split(",")[0]
        ing_prim = set(_tokens(ing_main))
        usd_prim = _primary(usd)

        p_ing = _profile(ing_main, ing_prim, False)
        p_usd = _profile(usd, usd_prim, True)

        # Food identity overlap (stemmed) as anchor for macro similarity
        stop = {"fresh", "raw", "cooked", "chopped", "sliced", "diced", "whole", "and",
                "with", "of", "the", "store", "bought", "trimmed", "drained", "nfs",
                "ready", "to", "serve", "for", "serving", "optional"}
        a = {_stem(t) for t in _tokens(ing_main) if t not in stop and len(t) > 2}
        b = {_stem(t) for t in _tokens(usd) if t not in stop and len(t) > 2}
        overlap = len(a & b) / float(len(a)) if a else 0.0

        if p_ing is None or p_usd is None:
            # no macro knowledge: fall back to identity overlap only
            return round(2.0 + 5.0 * overlap, 3)

        dist = _macro_distance(p_ing[0], p_usd[0])
        macro_sim = math.exp(-dist / 30.0)  # 1 when identical, ->0 when far

        same_class = 1.0 if p_ing[1] == p_usd[1] else 0.0

        score = 4.5 * macro_sim + 1.5 * same_class + 3.0 * overlap

        ing_t = set(_tokens(ing))
        usd_t = set(_tokens(usd))

        # Macro-swinging form changes
        if "juice" in usd_t and "juice" not in ing_t:
            score -= 3.0
        if ("mixture" in usd_t or "mixed" in usd_t) and "mix" not in ing_t and "mixed" not in ing_t:
            score -= 1.5
        if "canned" in ing_t and "raw" in usd_t:
            score -= 1.5
        if ("dried" in ing_t) != ("dried" in usd_t) and ("fish" in ing_t or "fruit" in ing_t):
            score -= 1.0
        if "salted" in usd_t and "salted" not in ing_t:
            score -= 1.0
        # Different animal species carry different fat/protein balance
        species = {"beef", "lamb", "pork", "chicken", "turkey", "veal", "duck", "goat"}
        si = ing_t & species
        su = usd_t & species
        if si and su and not (si & su):
            score -= 2.5
        # Leaner cut / imported variety vs unspecified (fat trim swings macros)
        if "lean" in usd_t and "only" in usd_t and "lean" not in ing_t:
            score -= 1.5
        # Different sugar refinements / brands of cereal
        if p_usd[1] == "cereal" and overlap < 0.5:
            score -= 1.5
        if "sugar" in ing_t and "sugar" in usd_t:
            refine = {"turbinado", "brown", "powdered", "raw", "demerara", "maple"}
            if (usd_t & refine) and not (ing_t & refine):
                score -= 2.0
        # Fresh herb vs dried ground spice: big density swing
        if "spices" in usd_t and not (ing_t & {"ground", "dried", "powder"}):
            score -= 2.0

        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
