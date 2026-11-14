import re


_PREP = {
    "fresh", "frozen", "thawed", "chopped", "minced", "diced", "sliced", "shredded",
    "grated", "toasted", "roasted", "fried", "leftover", "optional", "trimmed",
    "cooked", "raw", "large", "small", "medium", "whole", "ground", "crushed",
    "finely", "roughly", "for", "frying", "the", "and", "or", "of", "a", "an",
    "to", "taste", "peeled", "drained", "rinsed", "softened", "melted", "cut",
    "into", "pieces", "plus", "more", "extra", "about", "boneless", "skinless",
    "uncooked", "regular", "prepared", "packed", "from", "tube", "with", "without",
    "salad", "cooking", "style", "ns", "nfs", "as", "ingredient", "in", "on",
}

_ALIASES = {
    "sufu": "fermented tofu", "fuyu": "fermented tofu", "puree": "sauce",
    "purée": "sauce", "applesauce": "apple sauce", "queso": "cheese",
    "chiles": "chili", "chilies": "chili", "chile": "chili", "scallion": "green onion",
    "scallions": "green onion", "cilantro": "coriander", "garbanzo": "chickpea",
    "aubergine": "eggplant", "courgette": "zucchini", "prawn": "shrimp",
    "prawns": "shrimp", "flaxseed": "flax seed", "flaxseeds": "flax seed",
}

# Mutually exclusive "kind" groups: two different members => different core food.
_KINDS = [
    {"chicken", "turkey", "beef", "pork", "lamb", "veal", "duck", "goat", "fish",
     "salmon", "tuna", "cod", "shrimp", "crab", "venison", "bison"},
    {"kidney", "kidneys", "liver", "livers", "gizzard", "gizzards", "heart", "skin",
     "tongue", "breast", "thigh", "wing", "leg", "giblets"},
    {"olive", "sunflower", "canola", "coconut", "sesame", "peanut", "corn", "soybean",
     "avocado", "palm", "safflower"},
    {"garlic", "guava", "ginger", "tomato", "onion", "apple", "pear", "sage",
     "basil", "thyme", "durian", "mango", "banana", "lemon", "lime", "orange"},
    {"chia", "flax", "sesame", "pumpkin", "hemp", "poppy"},
    {"white", "wheat", "rye", "sourdough", "multigrain"},
    {"cheddar", "mozzarella", "asadero", "parmesan", "feta", "brie", "gouda", "swiss"},
]


def _norm_word(w):
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def _expand(words):
    out = []
    for w in words:
        a = _ALIASES.get(w)
        if a:
            out.extend(a.split())
        else:
            out.append(w)
    return out


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|ml|l|oz|lb|grams?)?\b", " ", t)
    words = re.findall(r"[a-zà-ÿ]+", t)
    words = [w for w in words if w not in _PREP]
    return _expand(words)


def _usda_segments(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    segs = [s.strip() for s in t.split(",") if s.strip()]
    res = []
    for s in segs:
        ws = [w for w in re.findall(r"[a-zà-ÿ]+", s) if w not in _PREP]
        res.append(_expand(ws))
    return [s for s in res if s]


def _trigrams(s):
    s = "  " + s + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _dice(a, b):
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _kind_conflict(ing_set, usda_set):
    conflicts = 0
    for group in _KINDS:
        a = ing_set & group
        b = usda_set & group
        if a and b and not (a & b):
            conflicts += 1
    return conflicts


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_words = [_norm_word(w) for w in _clean_ingredient(str(ingredient))]
        segs = [[_norm_word(w) for w in s] for s in _usda_segments(str(usda_match))]
        if not ing_words or not segs:
            return 0.0

        head = ing_words[-1]
        ing_set = set(ing_words)

        # Build USDA core: primary segment + first two descriptors, reordered as
        # natural phrase ("oil, sunflower" -> "sunflower oil").
        primary = segs[0]
        descriptors = [w for s in segs[1:3] for w in s]
        usda_core_words = descriptors + primary
        usda_set = set(w for s in segs for w in s)

        # 1. Head noun identity: does ingredient head appear in USDA core?
        if head in primary:
            head_score = 1.0
        elif head in usda_set:
            head_score = 0.75
        else:
            head_score = max((_dice(head, w) for w in usda_set), default=0.0)
            if head_score < 0.5:
                head_score *= 0.5

        # 2. Primary coverage: how much of the USDA primary food is explained.
        prim_hits = 0.0
        for w in primary:
            best = max((_dice(w, iw) for iw in ing_words), default=0.0)
            prim_hits += 1.0 if best >= 0.8 else (best if best >= 0.5 else 0.0)
        prim_cov = prim_hits / len(primary)

        # 3. Ingredient coverage by USDA core words.
        ing_hits = sum(1 for w in ing_words if w in usda_set)
        ing_cov = ing_hits / len(ing_words)

        # 4. Phrase-level character similarity.
        phrase_sim = _dice(" ".join(ing_words), " ".join(usda_core_words))

        # 5. Kind conflicts (different species / oils / fruits ...).
        conflicts = _kind_conflict(ing_set, usda_set)

        score = (
            40.0 * head_score
            + 25.0 * prim_cov
            + 20.0 * ing_cov
            + 15.0 * phrase_sim
        )
        score -= 30.0 * conflicts

        # Strong signal when there is zero lexical connection at all.
        if head_score < 0.3 and prim_cov == 0.0 and ing_cov == 0.0:
            score = min(score, 8.0)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
