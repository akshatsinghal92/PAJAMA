import re
import math

# Approximate per-100g macro estimates: (kcal, protein, carbs, fat)
_MACRO_LEXICON = [
    # pure fats
    (("oil", "lard", "shortening", "ghee", "tallow"), (884, 0, 0, 100)),
    (("butter", "margarine"), (717, 1, 0, 81)),
    # dairy
    (("cream",), (340, 2, 3, 36)),
    (("cheese", "brie", "camembert", "cheddar", "parmesan", "mozzarella", "feta"), (350, 23, 2, 28)),
    (("milk", "yogurt", "yoghurt", "kefir"), (60, 3.5, 5, 3)),
    # proteins
    (("skin",), (450, 13, 0, 44)),
    (("sausage", "bacon", "salami", "pepperoni", "chorizo"), (330, 14, 2, 29)),
    (("chicken", "turkey", "duck", "poultry", "neck", "breast", "thigh"), (190, 20, 0, 12)),
    (("beef", "pork", "lamb", "veal", "venison", "steak", "ground"), (230, 19, 0, 16)),
    (("fish", "bass", "salmon", "tuna", "cod", "trout", "shrimp", "prawn", "crab", "tilapia", "halibut", "anchovy", "sardine"), (120, 20, 0, 4)),
    (("egg", "eggs"), (143, 13, 1, 10)),
    (("tofu", "tempeh", "seitan"), (110, 12, 3, 6)),
    # nuts & seeds
    (("seed", "seeds", "linseed", "linseeds", "flaxseed", "chia", "sesame", "nut", "nuts", "almond", "almonds", "walnut", "peanut", "cashew", "pecan"), (570, 20, 25, 48)),
    (("germ", "bran"), (360, 23, 52, 10)),
    # grains & starch
    (("flour", "tortilla", "tortillas", "wrap", "bread", "bun", "roll", "pita", "naan"), (300, 9, 55, 5)),
    (("rice", "pasta", "noodle", "noodles", "spaghetti", "oats", "oat", "quinoa", "barley", "couscous", "cereal"), (360, 11, 72, 3)),
    (("bar", "cookie", "cake", "pie", "pastry", "muffin", "biscuit", "cracker", "granola"), (420, 6, 60, 17)),
    (("potato", "potatoes", "yam", "cassava"), (80, 2, 18, 0.1)),
    (("bean", "beans", "lentil", "lentils", "chickpea", "chickpeas"), (340, 22, 60, 1.5)),
    # sweet
    (("sugar", "honey", "syrup", "molasses", "jam", "jelly", "filling", "candy"), (300, 0.3, 75, 0.1)),
    (("chocolate", "cocoa"), (540, 6, 58, 31)),
    # fruit
    (("apple", "banana", "orange", "pear", "grape", "berry", "berries", "mango", "peach", "plum", "cherry", "lemon", "lime", "pineapple", "melon", "fruit", "apricot"), (55, 0.7, 14, 0.2)),
    # vegetables
    (("chrysanthemum", "spinach", "lettuce", "kale", "chard", "cabbage", "greens", "arugula", "leaves", "leaf", "bok", "choy", "shungiku", "watercress"), (22, 2.2, 3.5, 0.3)),
    (("onion", "garlic", "carrot", "pepper", "tomato", "celery", "cucumber", "zucchini", "squash", "broccoli", "cauliflower", "mushroom", "mushrooms", "eggplant", "vegetable", "vegetables"), (35, 1.5, 7, 0.3)),
    # condiments
    (("sauce", "ketchup", "dressing", "gravy", "salsa", "paste", "puree"), (110, 2, 18, 3)),
    (("mayonnaise", "mayo"), (680, 1, 1, 75)),
    (("spice", "spices", "ground", "powder", "seasoning", "cumin", "paprika", "cinnamon", "turmeric", "oregano", "basil", "thyme", "herb", "herbs"), (330, 12, 60, 8)),
    (("broth", "stock", "soup", "bouillon"), (15, 1.5, 1, 0.5)),
    (("juice",), (45, 0.5, 11, 0.1)),
    (("water", "tea", "coffee"), (1, 0, 0.2, 0)),
]

# Modifiers that shift macros in a direction
_MODIFIER_SHIFTS = {
    "fried": (1.35, 1.0, 1.1, 1.8),
    "breaded": (1.4, 0.9, 2.0, 1.5),
    "dried": (2.5, 2.5, 2.5, 2.0),
    "dehydrated": (2.5, 2.5, 2.5, 2.0),
    "lean": (0.8, 1.1, 1.0, 0.55),
    "skinless": (0.75, 1.1, 1.0, 0.4),
    "fat": (1.15, 0.95, 1.0, 1.35),
    "sweetened": (1.3, 1.0, 1.5, 1.0),
    "canned": (0.95, 1.0, 1.05, 1.0),
    "syrup": (1.5, 1.0, 2.0, 1.0),
    "pie": (1.6, 1.0, 1.6, 2.0),
    "filling": (1.6, 0.8, 1.7, 1.0),
    "nfs": (1.0, 1.0, 1.0, 1.0),
}

_NOISE = {"g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "and", "or", "of",
          "the", "a", "with", "from", "raw", "fresh", "frozen", "thawed", "chopped", "sliced",
          "diced", "minced", "whole", "large", "small", "medium", "tube", "inch", "uncooked",
          "nfs", "ns", "as", "to", "for", "in"}


def _tokens(text):
    try:
        t = str(text or "").lower()
        t = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)\b", " ", t)
        t = re.sub(r"[^a-z\s]", " ", t)
        return [w for w in t.split() if w]
    except Exception:
        return []


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and not w.endswith("ses"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _estimate_macros(tokens, is_usda):
    """Return (vector, n_hits). Weighted average; USDA head noun weighted higher."""
    acc = [0.0, 0.0, 0.0, 0.0]
    total_w = 0.0
    hits = 0
    n = len(tokens)
    token_set = set(tokens) | set(_stem(t) for t in tokens)
    for idx, tok in enumerate(tokens):
        cand = (tok, _stem(tok))
        for keys, vec in _MACRO_LEXICON:
            if cand[0] in keys or cand[1] in keys:
                if is_usda:
                    w = 3.0 if idx == 0 else 1.0 / (1 + 0.3 * idx)
                else:
                    # recipe text: last noun is usually the head
                    w = 1.0 + 2.0 * (idx / max(1, n - 1)) if n > 1 else 3.0
                for i in range(4):
                    acc[i] += w * vec[i]
                total_w += w
                hits += 1
                break
    if total_w <= 0:
        return None, 0
    vec = [a / total_w for a in acc]
    for mod, shift in _MODIFIER_SHIFTS.items():
        if mod in token_set:
            vec = [vec[i] * shift[i] for i in range(4)]
    vec[3] = min(vec[3], 100.0)
    return vec, hits


def _macro_distance(a, b):
    # Energy-share representation plus log-calorie distance
    def shares(v):
        kcal_p = 4 * v[1]
        kcal_c = 4 * v[2]
        kcal_f = 9 * v[3]
        tot = kcal_p + kcal_c + kcal_f
        if tot <= 0:
            return (1 / 3.0, 1 / 3.0, 1 / 3.0)
        return (kcal_p / tot, kcal_c / tot, kcal_f / tot)

    sa, sb = shares(a), shares(b)
    share_dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(sa, sb))) / math.sqrt(2)
    kcal_dist = abs(math.log((a[0] + 10) / (b[0] + 10))) / math.log(10)
    gram_dist = 0.0
    for i in (1, 2, 3):
        gram_dist += abs(math.log((a[i] + 1) / (b[i] + 1)))
    gram_dist /= 3 * math.log(20)
    return 0.4 * share_dist + 0.3 * min(1.0, kcal_dist) + 0.3 * min(1.0, gram_dist)


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0

        # strip parentheticals from ingredient but keep their words as weak evidence
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        ing_main = re.sub(r"\([^)]*\)", " ", ing)
        ing_core = ing_main.split(",")[0]

        ing_tokens = _tokens(ing_core)
        ing_state = _tokens(" ".join(ing_main.split(",")[1:]))
        usda_tokens = _tokens(usda)

        ing_vec, ih = _estimate_macros(ing_tokens + ing_state, False)
        if ing_vec is None and paren:
            ing_vec, ih = _estimate_macros(_tokens(paren), False)
        usda_vec, uh = _estimate_macros(usda_tokens, True)

        ing_content = set(_stem(t) for t in ing_tokens + _tokens(paren) if t not in _NOISE)
        usda_content = set(_stem(t) for t in usda_tokens if t not in _NOISE)
        overlap = 0.0
        if ing_content and usda_content:
            overlap = len(ing_content & usda_content) / float(len(ing_content | usda_content))

        if ing_vec is None or usda_vec is None:
            # No macro evidence: fall back to identity overlap, compressed toward middle
            return round(2.0 + 5.0 * overlap, 3)

        dist = _macro_distance(ing_vec, usda_vec)
        proximity = math.exp(-4.0 * dist)  # 1.0 identical, ~0.02 far

        # confidence in estimate grows with lexicon hits
        conf = 1.0 - 0.5 ** min(ih, uh)
        score = 10.0 * (conf * proximity + (1 - conf) * 0.5)

        # small bonus for shared content words (same food likely same macros)
        score += 2.0 * overlap

        # penalize processed-form swings: ingredient raw-ish but USDA composite product
        composite = {"pie", "filling", "bar", "sauce", "patty", "patties", "breaded", "nfs", "mix", "blend"}
        ing_set = set(ing_tokens)
        usda_set = set(usda_tokens)
        swing = len((usda_set & composite) - ing_set) + 0.5 * len((ing_set & composite) - usda_set)
        score -= 1.5 * swing

        return round(max(0.0, min(12.0, score)), 3)
    except Exception:
        return 0.0
