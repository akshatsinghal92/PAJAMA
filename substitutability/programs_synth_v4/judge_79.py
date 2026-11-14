import re

# Variant 3: "compound span coverage" via a modifier-head dependency model.
# Each ingredient is parsed into (modifier, head) dependency arcs. Arcs whose
# modifier is a known identity-changing modifier are "locked": the USDA entry must
# realise both ends (in any order, since USDA reorders words). Additionally USDA
# words that would lock onto the ingredient's head with a modifier absent from the
# ingredient create a "foreign compound" penalty. Multi-food ingredients joined
# by and/with are treated as compound dishes needing both components.

_IDENTITY_MODIFIERS = {
    "sweet", "coconut", "peanut", "almond", "soy", "soya", "oat", "rice", "cashew",
    "green", "black", "white", "red", "sea", "cream", "sour", "butter", "cottage",
    "corn", "maple", "brown", "ice", "egg", "goat", "sheep", "buttermilk", "apple",
    "tomato", "garlic", "onion", "chili", "chile", "hot", "bell", "wild", "jack",
    "pork", "beef", "chicken", "turkey", "lamb", "veal", "fish", "duck", "rock",
    "baking", "cake", "pastry", "bread", "corned", "cured", "smoked", "pickled",
    "evaporated", "condensed", "powdered", "dried", "dry", "kidney", "lima", "pinto",
    "navy", "string", "snap", "snow", "sugar", "cane", "palm", "sesame", "olive",
    "vegetable", "canola", "sunflower", "mustard", "spring", "napa", "bok", "swiss",
    "blue", "cream", "cheddar", "pumpkin", "squash", "water", "tofu", "vegan",
    "breakfast", "granola", "frozen", "instant", "whole", "skim", "jerky", "bone",
    "silk", "kiwi", "passion", "star", "dragon", "blood", "key", "concord",
}

_HEADS = {
    "potato", "milk", "butter", "tea", "bass", "oil", "cheese", "bean", "pepper",
    "sauce", "flour", "sugar", "cream", "bread", "cake", "juice", "water", "salt",
    "sausage", "pea", "nut", "seed", "corn", "rice", "fruit", "melon", "onion",
    "squash", "lettuce", "cabbage", "egg", "yogurt", "broth", "stock", "paste",
    "syrup", "vinegar", "meal", "flake", "chop", "steak", "roast", "loin", "fillet",
    "breast", "thigh", "wing", "skin", "kidney", "liver", "bone", "jerky", "cracker",
    "mayonnaise", "aioli", "grape", "raspberry", "berry", "orange", "lime", "lemon",
    "chocolate", "powder", "chip", "sprout", "green", "leaf", "root", "tip",
}

_SYNONYMS = {
    "maize": "corn", "clementine": "tangerine", "mandarin": "tangerine",
    "aubergine": "eggplant", "courgette": "zucchini", "prawn": "shrimp",
    "coriander": "cilantro", "garbanzo": "chickpea", "poultry": "chicken",
    "buttery": "butter", "buttered": "butter", "frank": "frankfurter",
    "hotdog": "frankfurter", "scallion": "onion", "capsicum": "pepper",
    "soya": "soy", "yoghurt": "yogurt", "chilli": "chili", "chile": "chili",
    "flaked": "flake", "flakes": "flake", "battered": "batter",
}

_NOISE = {
    "g", "kg", "mg", "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "of", "the", "a",
    "an", "for", "to", "from", "in", "on", "fresh", "chopped", "sliced", "diced",
    "minced", "cubed", "drained", "thawed", "cold", "warm", "hot", "raw", "cooked",
    "foraged", "bagged", "toasted", "crispy", "segments", "segment", "garnish",
    "round", "snack", "plain", "regular", "or", "made", "with", "and", "without",
    "large", "small", "medium", "fine", "finely", "roughly", "about", "tube",
    "microwave", "flavored", "flavor", "uncooked", "imported", "only", "pack",
}

_JOINERS = {"and", "with", "&", "plus"}


def _stem(w):
    try:
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]
        if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
    except Exception:
        pass
    return w


def _norm(w):
    w = _SYNONYMS.get(w, w)
    w = _stem(w)
    return _SYNONYMS.get(w, w)


def _words(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"\d+(\.\d+)?%?", " ", t)
    return re.findall(r"[a-z&]+", t)


def _ingredient_main(ingredient):
    t = str(ingredient or "")
    t = t.split(",")[0]
    return _words(t)


def _segments(ws):
    segs, cur = [], []
    for w in ws:
        if w in _JOINERS:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(w)
    if cur:
        segs.append(cur)
    return segs


def _content(ws):
    return [_norm(w) for w in ws if w not in _NOISE and len(w) > 1]


def _fuzzy_in(word, bag):
    if word in bag:
        return 1.0
    best = 0.0
    for b in bag:
        if len(word) >= 4 and len(b) >= 4 and (word.startswith(b) or b.startswith(word)):
            best = max(best, 0.8)
        elif len(word) >= 5 and len(b) >= 5 and word[:5] == b[:5]:
            best = max(best, 0.6)
    return best


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _ingredient_main(ingredient)
        usda_raw = _words(usda_match)
        if not ing_raw or not usda_raw:
            return 0.0

        usda_bag = set(_content(usda_raw))
        if not usda_bag:
            return 0.0
        usda_primary = set(_content(_words(str(usda_match).split(",")[0])))

        segments = [s for s in (_content(seg) for seg in _segments(ing_raw)) if s]
        if not segments:
            return 0.0

        # usda joined dish components
        usda_segments = _segments([w for w in usda_raw])
        usda_is_combo = len([s for s in usda_segments if _content(s)]) > 1 and any(
            w in _JOINERS for w in usda_raw)

        seg_scores = []
        for seg in segments:
            head = seg[-1]
            mods = seg[:-1]
            head_hit = _fuzzy_in(head, usda_bag)
            # locked arcs: identity modifier directly before head (or before
            # another modifier that precedes head)
            locked = []
            for i, m in enumerate(mods):
                nxt = seg[i + 1]
                if m in _IDENTITY_MODIFIERS or nxt in _HEADS or head in _HEADS:
                    locked.append(m)
            if locked:
                lock_cov = sum(_fuzzy_in(m, usda_bag) for m in locked) / len(locked)
            else:
                lock_cov = 1.0
            loose = [m for m in mods if m not in locked]
            loose_cov = (sum(_fuzzy_in(m, usda_bag) for m in loose) / len(loose)) if loose else 1.0

            s = 0.55 * head_hit + 0.35 * lock_cov + 0.10 * loose_cov
            # head missing but compound fused elsewhere (e.g. modifier is head)
            if head_hit == 0 and mods and _fuzzy_in(mods[-1], usda_primary) > 0:
                s = max(s, 0.25)
            seg_scores.append(s)

        # compound dish: all components must be covered
        if len(segments) > 1:
            core = min(seg_scores) * 0.7 + (sum(seg_scores) / len(seg_scores)) * 0.3
            if min(seg_scores) < 0.5:
                core *= 0.5
        else:
            core = seg_scores[0]
            if usda_is_combo:
                core *= 0.55

        # foreign compound penalty: USDA identity modifiers adjacent to a matched
        # ingredient head that the ingredient does not contain
        ing_all = set(w for seg in segments for w in seg)
        foreign = 0
        usda_seq = _content(usda_raw)
        for i, w in enumerate(usda_seq):
            if w in _IDENTITY_MODIFIERS and w not in ing_all and _fuzzy_in(w, ing_all) == 0:
                neighbours = usda_seq[max(0, i - 2):i + 3]
                if any(n in ing_all for n in neighbours if n != w):
                    foreign += 1
        penalty = min(0.45, 0.15 * foreign)

        # primary-food check: USDA primary should overlap ingredient
        prim_hit = max((_fuzzy_in(p, ing_all) for p in usda_primary), default=0.0)
        if prim_hit == 0:
            core *= 0.6

        score = max(0.0, min(1.0, core - penalty))
        return round(score * 100.0, 2)
    except Exception:
        return 0.0
