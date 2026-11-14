import re
import math

# Approximate per-100g macro prototypes: (kcal, protein, carb, fat, water_fraction)
_PROTOTYPES = {
    "leafy":      (20, 1.8, 3.5, 0.3, 0.93),
    "vegetable":  (35, 1.5, 7.0, 0.3, 0.90),
    "fruit":      (55, 0.7, 14.0, 0.2, 0.85),
    "lean_meat":  (130, 22.0, 0.0, 4.0, 0.72),
    "fatty_meat": (260, 17.0, 0.0, 21.0, 0.58),
    "cured_meat": (330, 16.0, 2.0, 29.0, 0.45),
    "organ":      (135, 20.0, 3.0, 4.5, 0.71),
    "fish":       (150, 19.0, 0.0, 8.0, 0.70),
    "shellfish":  (90, 18.0, 1.0, 1.2, 0.79),
    "egg":        (145, 12.5, 0.8, 10.0, 0.76),
    "dairy_milk": (60, 3.3, 4.8, 3.3, 0.88),
    "cheese":     (380, 24.0, 2.0, 31.0, 0.38),
    "pure_fat":   (880, 0.0, 0.0, 99.0, 0.01),
    "butter":     (717, 0.9, 0.1, 81.0, 0.16),
    "grain_dry":  (360, 11.0, 73.0, 2.0, 0.11),
    "flour":      (365, 11.0, 74.0, 2.0, 0.11),
    "bread":      (270, 9.0, 50.0, 3.5, 0.35),
    "grain_cooked": (130, 3.0, 28.0, 0.4, 0.68),
    "legume_dry": (340, 22.0, 60.0, 1.5, 0.10),
    "legume_cooked": (120, 8.0, 21.0, 0.5, 0.68),
    "nut_seed":   (580, 20.0, 22.0, 50.0, 0.05),
    "sugar":      (390, 0.0, 99.0, 0.0, 0.01),
    "sweet":      (480, 5.0, 60.0, 24.0, 0.05),
    "spice":      (300, 10.0, 60.0, 8.0, 0.09),
    "herb_fresh": (40, 3.0, 7.0, 0.7, 0.86),
    "sauce":      (90, 2.0, 15.0, 2.5, 0.78),
    "soup":       (70, 2.5, 8.0, 3.0, 0.85),
    "beverage":   (2, 0.1, 0.4, 0.0, 0.99),
    "sweet_drink": (45, 0.5, 11.0, 0.3, 0.88),
    "drink_mix":  (390, 6.0, 80.0, 4.0, 0.02),
    "alcohol":    (230, 0.0, 1.0, 0.0, 0.65),
    "condiment":  (150, 1.5, 20.0, 7.0, 0.65),
    "cocoa":      (230, 20.0, 58.0, 14.0, 0.03),
}

# Keyword -> prototype. Longer phrases are matched first.
_LEXICON = [
    ("cocoa butter", "pure_fat"), ("olive oil", "pure_fat"), ("oil", "pure_fat"),
    ("lard", "pure_fat"), ("shortening", "pure_fat"), ("ghee", "butter"),
    ("tallow", "pure_fat"), ("butter", "butter"), ("margarine", "butter"),
    ("dry mix", "drink_mix"), ("hot chocolate", "sweet_drink"), ("cocoa", "cocoa"),
    ("chocolate", "sweet"), ("candy", "sweet"), ("cookie", "sweet"), ("cake", "sweet"),
    ("soup", "soup"), ("broth", "beverage"), ("stock", "beverage"),
    ("sauce", "sauce"), ("gravy", "sauce"), ("salsa", "sauce"), ("pesto", "condiment"),
    ("ketchup", "condiment"), ("mayonnaise", "condiment"), ("dressing", "condiment"),
    ("mustard", "condiment"), ("paste", "condiment"),
    ("liver", "organ"), ("kidney", "organ"), ("heart", "organ"), ("tongue", "organ"),
    ("variety meats", "organ"), ("giblets", "organ"), ("tripe", "organ"),
    ("cervelat", "cured_meat"), ("salami", "cured_meat"), ("sausage", "cured_meat"),
    ("bologna", "cured_meat"), ("pepperoni", "cured_meat"), ("bacon", "cured_meat"),
    ("chorizo", "cured_meat"), ("frankfurter", "cured_meat"), ("hot dog", "cured_meat"),
    ("ham", "cured_meat"), ("prosciutto", "cured_meat"), ("pate", "cured_meat"),
    ("chicken breast", "lean_meat"), ("turkey breast", "lean_meat"),
    ("chicken", "lean_meat"), ("turkey", "lean_meat"), ("veal", "lean_meat"),
    ("venison", "lean_meat"), ("rabbit", "lean_meat"),
    ("beef", "fatty_meat"), ("pork", "fatty_meat"), ("lamb", "fatty_meat"),
    ("mutton", "fatty_meat"), ("duck", "fatty_meat"), ("goose", "fatty_meat"),
    ("patty", "fatty_meat"),
    ("lobster", "shellfish"), ("crayfish", "shellfish"), ("crab", "shellfish"),
    ("shrimp", "shellfish"), ("prawn", "shellfish"), ("scallop", "shellfish"),
    ("clam", "shellfish"), ("mussel", "shellfish"), ("oyster", "shellfish"),
    ("squid", "shellfish"), ("octopus", "shellfish"),
    ("herring", "fish"), ("salmon", "fish"), ("tuna", "fish"), ("cod", "fish"),
    ("mackerel", "fish"), ("sardine", "fish"), ("trout", "fish"), ("anchovy", "fish"),
    ("tilapia", "fish"), ("halibut", "fish"), ("fish", "fish"),
    ("egg", "egg"),
    ("cheese", "cheese"), ("parmesan", "cheese"), ("cheddar", "cheese"),
    ("mozzarella", "cheese"), ("milk", "dairy_milk"), ("yogurt", "dairy_milk"),
    ("cream", "dairy_milk"), ("kefir", "dairy_milk"),
    ("flour", "flour"), ("meal", "flour"), ("bread", "bread"), ("toast", "bread"),
    ("bagel", "bread"), ("roll", "bread"), ("tortilla", "bread"), ("pita", "bread"),
    ("cracker", "bread"),
    ("pasta", "grain_dry"), ("noodle", "grain_dry"), ("rice", "grain_dry"),
    ("oats", "grain_dry"), ("oat", "grain_dry"), ("quinoa", "grain_dry"),
    ("barley", "grain_dry"), ("amaranth", "grain_dry"), ("millet", "grain_dry"),
    ("couscous", "grain_dry"), ("cereal", "grain_dry"),
    ("lentil", "legume_dry"), ("chickpea", "legume_dry"), ("bean", "legume_dry"),
    ("peas", "legume_dry"), ("tofu", "egg"),
    ("flaxseed", "nut_seed"), ("flax", "nut_seed"), ("seed", "nut_seed"),
    ("almond", "nut_seed"), ("walnut", "nut_seed"), ("cashew", "nut_seed"),
    ("pecan", "nut_seed"), ("peanut", "nut_seed"), ("hazelnut", "nut_seed"),
    ("pistachio", "nut_seed"), ("nut", "nut_seed"), ("tahini", "nut_seed"),
    ("sugar", "sugar"), ("honey", "sugar"), ("syrup", "sugar"), ("molasses", "sugar"),
    ("jam", "sugar"),
    ("spices", "spice"), ("spice", "spice"), ("ground ginger", "spice"),
    ("cinnamon", "spice"), ("cumin", "spice"), ("paprika", "spice"),
    ("pepper, black", "spice"), ("black pepper", "spice"), ("nutmeg", "spice"),
    ("turmeric", "spice"), ("seasoning", "condiment"), ("salt", "spice"),
    ("basil", "herb_fresh"), ("parsley", "herb_fresh"), ("cilantro", "herb_fresh"),
    ("mint", "herb_fresh"), ("dill", "herb_fresh"), ("thyme", "herb_fresh"),
    ("rosemary", "herb_fresh"), ("garlic", "vegetable"), ("ginger", "vegetable"),
    ("escarole", "leafy"), ("lettuce", "leafy"), ("spinach", "leafy"),
    ("kale", "leafy"), ("arugula", "leafy"), ("chard", "leafy"), ("endive", "leafy"),
    ("cabbage", "leafy"), ("collard", "leafy"), ("greens", "leafy"),
    ("asparagus", "vegetable"), ("broccoli", "vegetable"), ("carrot", "vegetable"),
    ("onion", "vegetable"), ("tomato", "vegetable"), ("pepper", "vegetable"),
    ("zucchini", "vegetable"), ("squash", "vegetable"), ("celery", "vegetable"),
    ("cucumber", "vegetable"), ("mushroom", "vegetable"), ("eggplant", "vegetable"),
    ("potato", "vegetable"), ("corn", "vegetable"), ("cauliflower", "vegetable"),
    ("apple", "fruit"), ("banana", "fruit"), ("orange", "fruit"), ("berry", "fruit"),
    ("berries", "fruit"), ("grape", "fruit"), ("lemon", "fruit"), ("lime", "fruit"),
    ("mango", "fruit"), ("pear", "fruit"), ("peach", "fruit"), ("cherry", "fruit"),
    ("juice", "sweet_drink"), ("soda", "sweet_drink"),
    ("tea", "beverage"), ("coffee", "beverage"), ("water", "beverage"),
    ("wine", "alcohol"), ("beer", "alcohol"), ("vodka", "alcohol"), ("rum", "alcohol"),
    ("whiskey", "alcohol"),
]
_LEXICON.sort(key=lambda kv: -len(kv[0]))

_STOP = {"g", "of", "and", "or", "the", "a", "with", "to", "in", "from", "raw",
         "fresh", "chopped", "sliced", "diced", "whole", "large", "small", "medium",
         "ns", "as", "for", "type", "major", "nfs", "cut", "pieces", "minced"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|gram|grams|kg|ml|l|oz)\b", " ", t)
    t = re.sub(r"[^a-z,\s/'-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _classify(text, primary_weight=True):
    """Return list of (prototype, weight) hits; earlier segments weigh more for USDA."""
    hits = {}
    segments = [s.strip() for s in text.split(",") if s.strip()] or [text]
    for idx, seg in enumerate(segments):
        w = 1.0 / (1.0 + idx * (1.2 if primary_weight else 0.6))
        padded = " " + seg + " "
        consumed = padded
        for kw, proto in _LEXICON:
            pat = r"(?<![a-z])" + re.escape(kw) + r"(s|es)?(?![a-z])"
            if re.search(pat, consumed):
                hits[proto] = max(hits.get(proto, 0.0), w)
                consumed = re.sub(pat, " ", consumed)
    return hits


def _macro_vector(hits, text):
    if not hits:
        return None
    # Use dominant (top weighted) prototype as base; blend weaker ones a little.
    ranked = sorted(hits.items(), key=lambda kv: -kv[1])
    total = 0.0
    vec = [0.0] * 5
    for i, (proto, w) in enumerate(ranked[:3]):
        ww = w * (1.0 if i == 0 else 0.25)
        p = _PROTOTYPES[proto]
        for j in range(5):
            vec[j] += p[j] * ww
        total += ww
    vec = [v / total for v in vec]

    # Processing modifiers that shift macros per 100g.
    if re.search(r"\b(condensed|concentrate|concentrated)\b", text):
        vec = [vec[0] * 1.9, vec[1] * 1.9, vec[2] * 1.9, vec[3] * 1.9, max(0.0, vec[4] - 0.1)]
    if re.search(r"\b(dried|dehydrated|powder|powdered|dry)\b", text) and vec[4] > 0.5:
        f = (1.0 - 0.1) / max(0.05, 1.0 - vec[4])
        f = min(f, 8.0)
        vec = [vec[0] * f, vec[1] * f, vec[2] * f, vec[3] * f, 0.1]
    if re.search(r"\b(cooked|boiled|steamed)\b", text) and vec[4] < 0.2 and vec[2] > 40:
        vec = [vec[0] * 0.38, vec[1] * 0.38, vec[2] * 0.38, vec[3] * 0.38, 0.68]
    if re.search(r"\b(fried|breaded|battered)\b", text):
        vec = [vec[0] + 90, vec[1], vec[2] + 8, vec[3] + 9, max(0.0, vec[4] - 0.1)]
    if re.search(r"\b(lean only|separable lean|skinless|fat free|nonfat|lowfat|low fat|light)\b", text):
        vec = [vec[0] * 0.8, vec[1] * 1.05, vec[2], vec[3] * 0.55, vec[4]]
    if re.search(r"\b(sweetened|candied|glazed|syrup)\b", text):
        vec = [vec[0] + 60, vec[1], vec[2] + 15, vec[3], vec[4]]
    return vec


def _distance(a, b):
    # Log-scaled calorie gap plus macro share gap (energy fraction from P/C/F).
    kcal_gap = abs(math.log1p(a[0]) - math.log1p(b[0]))

    def shares(v):
        e = v[1] * 4 + v[2] * 4 + v[3] * 9
        if e <= 1e-6:
            return (0.0, 0.0, 0.0)
        return (v[1] * 4 / e, v[2] * 4 / e, v[3] * 9 / e)

    sa, sb = shares(a), shares(b)
    share_gap = math.sqrt(sum((x - y) ** 2 for x, y in zip(sa, sb)))
    water_gap = abs(a[4] - b[4])
    # Very low-calorie items (tea, water) have unstable shares; down-weight shares.
    low = min(a[0], b[0]) < 15
    return kcal_gap * 1.3 + share_gap * (0.6 if low else 2.2) + water_gap * 1.5


def _tokens(text):
    return {t for t in re.findall(r"[a-z]+", text) if len(t) > 2 and t not in _STOP}


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing or not usd:
            return 0.0

        ing_hits = _classify(ing, primary_weight=False)
        usd_hits = _classify(usd, primary_weight=True)
        va = _macro_vector(ing_hits, ing)
        vb = _macro_vector(usd_hits, usd)

        it, ut = _tokens(ing), _tokens(usd)
        lexical = 0.0
        if it and ut:
            stems_i = {t[:5] for t in it}
            stems_u = {t[:5] for t in ut}
            lexical = len(stems_i & stems_u) / max(1, len(stems_i))

        if va is None or vb is None:
            # No macro knowledge: fall back to lexical proximity, centered low.
            return round(max(0.0, min(100.0, 20.0 + 45.0 * lexical)), 3)

        d = _distance(va, vb)
        macro_score = 100.0 * math.exp(-0.9 * d)

        # Same dominant class bonus, cross-class penalty.
        top_a = max(ing_hits.items(), key=lambda kv: kv[1])[0]
        top_b = max(usd_hits.items(), key=lambda kv: kv[1])[0]
        if top_a == top_b:
            macro_score += 8.0
        else:
            macro_score -= 6.0

        # Specific food identity still matters for profile (lobster vs crayfish
        # share class but differ); scale by lexical agreement.
        score = 0.75 * macro_score + 25.0 * lexical

        # State mismatches that alter per-100g profile.
        ing_toasted = bool(re.search(r"\btoast(ed)?\b", ing))
        usd_toasted = bool(re.search(r"\btoast(ed)?\b", usd))
        if ing_toasted != usd_toasted and "bread" not in usd:
            score -= 8.0
        if re.search(r"\bwhole\b", str(ingredient).lower()) and re.search(r"\bground\b", usd):
            score -= 10.0
        if re.search(r"\b(canned)\b", ing) and not re.search(r"\b(canned)\b", usd):
            score -= 4.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
