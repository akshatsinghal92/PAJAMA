import re
import math

# Approximate per-100g macro prototypes: (kcal, protein, carb, fat)
_PROTO = {
    "oil":        (884, 0, 0, 100),
    "butter":     (717, 1, 0, 81),
    "lard":       (900, 0, 0, 100),
    "nutbutter":  (590, 22, 20, 50),
    "nut":        (600, 18, 20, 52),
    "sugar":      (387, 0, 100, 0),
    "syrup":      (290, 0, 75, 0),
    "flour":      (364, 10, 76, 1),
    "bread":      (270, 9, 50, 3),
    "pasta":      (360, 12, 72, 2),
    "rice":       (130, 3, 28, 0.3),
    "cereal":     (380, 8, 80, 3),
    "baked":      (450, 5, 65, 20),
    "leanmeat":   (165, 30, 0, 4),
    "fatmeat":    (260, 25, 0, 18),
    "organ":      (135, 20, 4, 4),
    "sausage":    (300, 13, 2, 27),
    "fish":       (140, 22, 0, 5),
    "egg":        (143, 13, 1, 10),
    "milk":       (60, 3.3, 5, 3.3),
    "cream":      (200, 2.5, 4, 20),
    "yogurt":     (70, 6, 6, 3),
    "cheese":     (380, 25, 2, 31),
    "freshcheese": (98, 11, 3.4, 4.3),
    "leafy":      (23, 2.5, 3.5, 0.4),
    "vegetable":  (35, 1.5, 7, 0.3),
    "starchveg":  (80, 2, 18, 0.1),
    "legume":     (340, 22, 60, 1.5),
    "fruit":      (55, 0.5, 14, 0.2),
    "driedfruit": (300, 2, 78, 0.5),
    "juice":      (40, 0.5, 9, 0.1),
    "spice":      (300, 10, 60, 8),
    "herb":       (40, 3, 7, 0.6),
    "sauce":      (90, 2, 15, 3),
    "condiment":  (150, 1, 20, 8),
    "beverage":   (2, 0, 0.5, 0),
    "alcohol":    (230, 0, 3, 0),
    "chocolate":  (540, 6, 58, 31),
    "soup":       (50, 3, 6, 1.5),
}

# keyword -> class, ordered by specificity (multi-word first)
_KEYWORDS = [
    ("peanut butter", "nutbutter"), ("almond butter", "nutbutter"), ("pecan butter", "nutbutter"),
    ("cashew butter", "nutbutter"), ("cocoa butter", "oil"), ("apple butter", "condiment"),
    ("half and half", "cream"), ("milk and cream", "cream"), ("sour cream", "cream"),
    ("cream cheese", "cheese"), ("cottage", "freshcheese"), ("ricotta", "freshcheese"),
    ("pie filling", "baked"), ("stew meat", "fatmeat"), ("ground beef", "fatmeat"),
    ("glass noodle", "pasta"), ("cellophane", "pasta"),
    ("oil", "oil"), ("shortening", "oil"), ("ghee", "butter"), ("lard", "lard"),
    ("butter", "butter"), ("margarine", "butter"),
    ("sugar", "sugar"), ("honey", "syrup"), ("syrup", "syrup"), ("molasses", "syrup"),
    ("flour", "flour"), ("bread", "bread"), ("toast", "bread"), ("bun", "bread"), ("roll", "bread"),
    ("tortilla", "bread"), ("noodle", "pasta"), ("pasta", "pasta"), ("spaghetti", "pasta"),
    ("macaroni", "pasta"), ("rice", "rice"), ("oat", "cereal"), ("cereal", "cereal"),
    ("cookie", "baked"), ("cake", "baked"), ("pie", "baked"), ("muffin", "baked"),
    ("cracker", "baked"), ("pastry", "baked"), ("brownie", "baked"),
    ("liver", "organ"), ("gizzard", "organ"), ("kidney", "organ"), ("heart", "organ"),
    ("feet", "organ"), ("tripe", "organ"), ("tongue", "organ"),
    ("sausage", "sausage"), ("bacon", "sausage"), ("salami", "sausage"), ("hot dog", "sausage"),
    ("frankfurter", "sausage"), ("pepperoni", "sausage"),
    ("chicken", "leanmeat"), ("turkey", "leanmeat"), ("breast", "leanmeat"),
    ("beef", "fatmeat"), ("pork", "fatmeat"), ("lamb", "fatmeat"), ("veal", "leanmeat"),
    ("chuck", "fatmeat"), ("roast", "fatmeat"), ("chop", "fatmeat"), ("steak", "fatmeat"),
    ("rib", "fatmeat"), ("duck", "fatmeat"), ("neck", "fatmeat"),
    ("fish", "fish"), ("salmon", "fish"), ("tuna", "fish"), ("cod", "fish"), ("shrimp", "fish"),
    ("crab", "fish"), ("tilapia", "fish"),
    ("egg", "egg"),
    ("yogurt", "yogurt"), ("cream", "cream"), ("milk", "milk"), ("cheese", "cheese"),
    ("chocolate", "chocolate"), ("cocoa", "chocolate"),
    ("juice", "juice"),
    ("almond", "nut"), ("pecan", "nut"), ("walnut", "nut"), ("peanut", "nut"), ("cashew", "nut"),
    ("seed", "nut"),
    ("bean", "legume"), ("lentil", "legume"), ("chickpea", "legume"),
    ("raisin", "driedfruit"),
    ("spinach", "leafy"), ("lettuce", "leafy"), ("kale", "leafy"), ("chrysanthemum", "leafy"),
    ("chard", "leafy"), ("cabbage", "leafy"), ("arugula", "leafy"), ("greens", "leafy"),
    ("potato", "starchveg"), ("corn", "starchveg"), ("yam", "starchveg"), ("plantain", "starchveg"),
    ("pepper", "vegetable"), ("tomato", "vegetable"), ("onion", "vegetable"), ("carrot", "vegetable"),
    ("celery", "vegetable"), ("broccoli", "vegetable"), ("mushroom", "vegetable"),
    ("zucchini", "vegetable"), ("squash", "vegetable"), ("cucumber", "vegetable"),
    ("vegetable", "vegetable"), ("garlic", "vegetable"),
    ("apple", "fruit"), ("banana", "fruit"), ("berry", "fruit"), ("berries", "fruit"),
    ("orange", "fruit"), ("lemon", "fruit"), ("grape", "fruit"), ("peach", "fruit"), ("pear", "fruit"),
    ("mango", "fruit"), ("melon", "fruit"),
    ("ginger", "spice"), ("cinnamon", "spice"), ("cumin", "spice"), ("paprika", "spice"),
    ("spice", "spice"), ("seasoning", "spice"), ("powder", "spice"),
    ("basil", "herb"), ("parsley", "herb"), ("cilantro", "herb"), ("oregano", "herb"),
    ("thyme", "herb"), ("mint", "herb"),
    ("sauce", "sauce"), ("salsa", "sauce"), ("gravy", "sauce"), ("paste", "sauce"),
    ("ketchup", "condiment"), ("mayonnaise", "condiment"), ("dressing", "condiment"),
    ("applesauce", "fruit"),
    ("soup", "soup"), ("broth", "soup"), ("stock", "soup"),
    ("wine", "alcohol"), ("beer", "alcohol"), ("rum", "alcohol"), ("vodka", "alcohol"),
    ("water", "beverage"), ("coffee", "beverage"), ("tea", "beverage"),
]

# modifiers that scale (kcal, protein, carb, fat)
_MODS = [
    (r"\bnon ?fat\b|\bfat free\b|\bskim\b", (0.55, 1.15, 1.1, 0.05)),
    (r"\blow ?fat\b|\breduced fat\b|\blight\b|\blite\b", (0.75, 1.05, 1.05, 0.5)),
    (r"\bdried\b|\bdehydrated\b|\blow moisture\b", (3.5, 3.5, 3.5, 3.5)),
    (r"\bfried\b|\bbreaded\b", (1.4, 1.0, 1.3, 1.8)),
    (r"\bsweetened\b|\bcandied\b|\bglazed\b|\bheavy syrup\b", (1.4, 1.0, 1.6, 1.0)),
    (r"\bunsweetened\b", (0.9, 1.0, 0.85, 1.0)),
    (r"\bcooked\b|\broasted\b|\bbraised\b|\bsimmered\b|\bgrilled\b", (1.15, 1.2, 1.0, 1.1)),
    (r"\blean\b|\btrimmed\b|\bmeat only\b", (0.85, 1.05, 1.0, 0.6)),
]

_PHRASE_CLASS_OVERRIDE = [
    (r"\bwith vegetables\b", "vegetable", 0.3),
    (r"\bwith (?:fruit|berries)\b", "fruit", 0.3),
    (r"\bwith sauce\b|\bin sauce\b", "sauce", 0.3),
]


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|grams?|kg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = t.replace("-", " ")
    t = re.sub(r"[^a-z,%\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _find_classes(text):
    """Return list of (position, class) for keyword hits, specific phrases consume text."""
    hits = []
    work = " " + text + " "
    for kw, cls in _KEYWORDS:
        pat = r"\b" + re.escape(kw) + r"s?\b"
        for m in re.finditer(pat, work):
            hits.append((m.start(), cls))
        work = re.sub(pat, lambda m: "#" * len(m.group(0)), work)
    hits.sort()
    return hits


def _profile(text, is_usda):
    if not text:
        return None, []
    hits = _find_classes(text)
    if not hits:
        return None, []
    if is_usda:
        # primary food (first comma segment) dominates USDA descriptions
        first_seg_end = text.find(",")
        if first_seg_end < 0:
            first_seg_end = len(text) + 1
        weights = []
        for pos, cls in hits:
            w = 1.0 if pos <= first_seg_end else 0.6
            weights.append((cls, w))
    else:
        # recipe text: head noun is usually last; "and" combos average
        weights = []
        n = len(hits)
        for i, (pos, cls) in enumerate(hits):
            w = 0.5 + 0.5 * (i + 1) / n
            weights.append((cls, w))
    # Collapse: use max weight per class
    agg = {}
    for cls, w in weights:
        agg[cls] = max(agg.get(cls, 0.0), w)
    for pat, cls, w in _PHRASE_CLASS_OVERRIDE:
        if re.search(pat, text):
            agg[cls] = max(agg.get(cls, 0.0), w)
    total = sum(agg.values())
    vec = [0.0, 0.0, 0.0, 0.0]
    for cls, w in agg.items():
        p = _PROTO[cls]
        for k in range(4):
            vec[k] += p[k] * w / total
    for pat, mult in _MODS:
        if re.search(pat, text):
            # don't apply dried multiplier to already-dense classes
            if mult[0] > 3 and any(c in agg for c in ("oil", "sugar", "flour", "spice", "nut",
                                                           "driedfruit", "legume", "pasta")):
                continue
            vec = [min(v * m, 900) for v, m in zip(vec, mult)]
    return vec, sorted(agg, key=lambda c: -agg[c])


def _macro_distance(a, b):
    # log-ratio distance on energy plus composition distance on energy fractions
    ka, kb = max(a[0], 1.0), max(b[0], 1.0)
    energy = abs(math.log(ka / kb))

    def frac(v):
        p, c, f = v[1] * 4, v[2] * 4, v[3] * 9
        s = p + c + f
        if s <= 0:
            return (1 / 3, 1 / 3, 1 / 3)
        return (p / s, c / s, f / s)

    fa, fb = frac(a), frac(b)
    comp = math.sqrt(sum((x - y) ** 2 for x, y in zip(fa, fb)))
    return energy, comp


def _token_set(text):
    stop = {"and", "or", "with", "of", "the", "a", "in", "ns", "as", "to", "raw", "fresh",
            "plain", "major", "type", "salad", "cooking", "uncooked", "warmed", "melted",
            "toasted", "chopped", "sliced", "diced", "minced", "frozen", "thawed"}
    return {w.rstrip("s") for w in re.findall(r"[a-z]+", text) if len(w) > 2 and w not in stop}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0
        # recipe ingredient: drop post-comma state text
        ing_main = ing.split(",")[0].strip() or ing

        va, ca = _profile(ing_main, False)
        vb, cb = _profile(usda, True)

        # identity overlap acts as a weak tiebreaker for macro estimation confidence
        ta, tb = _token_set(ing_main), _token_set(usda)
        overlap = len(ta & tb) / max(1, len(ta)) if ta else 0.0

        if va is None or vb is None:
            # unknown foods: macro estimate unavailable; fall back to overlap-based guess
            return round(15.0 + 45.0 * overlap, 3)

        energy, comp = _macro_distance(va, vb)
        # convert to proximity in [0,1]
        prox = math.exp(-1.6 * energy) * math.exp(-3.0 * comp)

        score = 70.0 * prox

        # same dominant macro class bonus
        if ca and cb and ca[0] == cb[0]:
            score += 15.0
        elif set(ca[:2]) & set(cb[:2]):
            score += 6.0
        else:
            score -= 10.0

        # composite ingredient (X and Y) matched to a single-class entry swings macros
        if len(ca) >= 2 and len(cb) == 1 and " and " in ing_main and "half and half" not in ing_main \
                and "milk and cream" not in ing_main:
            score -= 12.0

        # fat-level qualifier asymmetry: reduced/low fat on one side only
        fat_pat = r"\b(non ?fat|low ?fat|reduced fat|fat free|skim|light)\b"
        if bool(re.search(fat_pat, usda)) != bool(re.search(fat_pat, ing_main)):
            score -= 8.0

        # sodium / additive variants change profile perceptibly
        if re.search(r"\blow sodium\b|\bno salt\b", usda) and not re.search(r"sodium|salt", ing_main):
            score -= 5.0

        score += 15.0 * overlap
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
