import re
import math

# Qualifier "slots": each slot is a dimension a diner might notice.
# Neutral values are ones a USDA entry can carry without changing the food
# relative to an unqualified ingredient (e.g. "raw", "uncooked").
_SLOTS = {
    "state": {
        "values": {"dried", "dehydrated", "fried", "roasted", "toasted", "smoked",
                   "canned", "pickled", "cured", "boiled", "baked", "grilled",
                   "braised", "stewed", "steamed", "candied", "sweetened", "salted",
                   "frozen", "cooked", "breaded", "battered"},
        "neutral": {"raw", "uncooked", "fresh", "frozen", "unprepared", "plain"},
        "weight": 2.6,
    },
    "fat": {
        "values": {"nonfat", "lowfat", "reduced", "light", "lite", "skim", "whole",
                   "lean", "fat", "fatfree"},
        "neutral": set(),
        "weight": 1.2,
    },
    "flavor": {
        "values": {"peach", "strawberry", "vanilla", "chocolate", "honey", "garlic",
                   "lemon", "cherry", "blueberry", "raspberry", "maple", "spicy",
                   "barbecue", "bbq", "cinnamon", "mint", "orange", "apple"},
        "neutral": set(),
        "weight": 2.2,
    },
    "grade": {
        "values": {"extra", "virgin", "organic", "choice", "select", "prime",
                   "premium", "imported"},
        "neutral": {"choice", "select", "prime"},
        "weight": 0.9,
    },
    "form": {
        "values": {"ground", "powder", "powdered", "paste", "juice", "sauce", "flakes",
                   "slices", "chopped", "puree", "concentrate", "extract", "syrup",
                   "oil", "flour", "meal", "seeds", "seed", "kernels", "whole"},
        "neutral": {"whole", "seed", "seeds", "kernels"},
        "weight": 2.0,
    },
    "dish": {
        "values": {"salad", "soup", "stew", "casserole", "sandwich", "pie", "cake",
                   "patty", "nuggets", "made", "with", "mix", "dinner", "entree",
                   "prepared", "recipe", "dressing", "dip"},
        "neutral": set(),
        "weight": 3.2,
    },
}

_PREP = {"sliced", "diced", "cubed", "minced", "chopped", "thawed", "peeled",
         "ripe", "large", "small", "medium", "fresh", "trimmed", "rinsed",
         "drained", "halved", "quartered", "grated", "shredded", "crushed",
         "finely", "roughly", "thinly", "about", "into", "pieces", "cut",
         "for", "to", "taste", "optional", "from", "tube", "softened",
         "melted", "beaten", "room", "temperature", "packed", "a", "of", "the",
         "or", "and", "boneless", "skinless"}

_USDA_FILLER = {"or", "and", "with", "without", "broilers", "fryers", "includes",
                "usda", "commodity", "ns", "as", "to", "nfs", "meat", "skin",
                "only", "all", "varieties", "regular", "commercial", "type",
                "boneless"}

_SYN = {
    "pinyon": "pine", "pignoli": "pine", "seed": "grain", "seeds": "grain",
    "filbert": "hazelnut", "filberts": "hazelnut", "scallion": "onion",
    "cilantro": "coriander", "garbanzo": "chickpea", "courgette": "zucchini",
    "aubergine": "eggplant", "lowfat": "lowfat", "fatfree": "nonfat",
}


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _norm_word(w):
    w = w.lower().replace("-", "")
    return _SYN.get(w, w)


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"[^a-z\- ]", " ", t)
    return [_norm_word(w) for w in t.split() if w]


def _clean_usda(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    segs = [s.strip() for s in t.split(",") if s.strip()]
    out = []
    for i, s in enumerate(segs):
        words = [_norm_word(w) for w in re.sub(r"[^a-z\- ]", " ", s).split() if w]
        out.append(words)
    return out


def _slot_of(word):
    hits = []
    for name, spec in _SLOTS.items():
        if word in spec["values"] or word in spec["neutral"]:
            hits.append(name)
    return hits


def _trigrams(s):
    s = "  " + s + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _fuzzy(a, b):
    if a == b or _stem(a) == _stem(b):
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            ingredient, usda_match = str(ingredient), str(usda_match)

        ing_words = _clean_ingredient(ingredient)
        usda_segs = _clean_usda(usda_match)
        if not ing_words or not usda_segs:
            return 0.0

        # Compound-ingredient signal ("steak and sliced onion")
        compound_penalty = 0.0
        raw_head = re.sub(r"\([^)]*\)", " ", ingredient.lower()).split(",")[0]
        if re.search(r"\b(and|&|with)\b", raw_head):
            compound_penalty = 2.5

        ing_set = set(_stem(w) for w in ing_words)
        ing_core = [w for w in ing_words if w not in _PREP]
        if not ing_core:
            ing_core = ing_words

        usda_all = [w for seg in usda_segs for w in seg]
        usda_primary = usda_segs[0]

        # 1. Core identity: how well ingredient core nouns are covered by USDA
        cover = []
        for w in ing_core:
            if _slot_of(w):
                continue
            best = max((_fuzzy(w, u) for u in usda_all), default=0.0)
            # matches in primary segment count a bit more
            bprim = max((_fuzzy(w, u) for u in usda_primary), default=0.0)
            cover.append(max(best, min(1.0, bprim * 1.1)))
        if not cover:
            cover = [max((_fuzzy(w, u) for u in usda_all), default=0.0) for w in ing_core]
        # last noun of ingredient is typically the head; weight it double
        weights = [1.0] * len(cover)
        if weights:
            weights[-1] = 2.0
        identity = sum(c * wt for c, wt in zip(cover, weights)) / max(sum(weights), 1e-9)

        # 2. Slot alignment: compare qualifiers per slot
        ing_slots = {}
        for w in ing_words:
            for s in _slot_of(w):
                ing_slots.setdefault(s, set()).add(_stem(w))
        usda_slots = {}
        for idx, seg in enumerate(usda_segs):
            for w in seg:
                if w in _USDA_FILLER and w not in ("with",):
                    continue
                for s in _slot_of(w):
                    usda_slots.setdefault(s, []).append((_stem(w), idx))

        added_cost = 0.0
        matched_bonus = 0.0
        for slot, entries in usda_slots.items():
            spec = _SLOTS[slot]
            neutral = set(_stem(n) for n in spec["neutral"])
            ing_vals = ing_slots.get(slot, set())
            for val, idx in entries:
                if val in ing_vals or val in ing_set:
                    matched_bonus += spec["weight"] * 0.5
                    continue
                if val in neutral:
                    continue
                # A qualifier in the primary segment (e.g. "cucumber salad made")
                # is a bigger identity shift than a trailing descriptor.
                pos_factor = 1.3 if idx == 0 else 1.0 / (1.0 + 0.15 * idx)
                added_cost += spec["weight"] * pos_factor
        # Dish slot: count only once-ish to avoid exploding on "made with"
        dish_count = sum(1 for v, _ in usda_slots.get("dish", []) if v not in ing_set)
        if dish_count > 1:
            added_cost -= _SLOTS["dish"]["weight"] * 0.5 * (dish_count - 1)

        dropped_cost = 0.0
        for slot, vals in ing_slots.items():
            spec = _SLOTS[slot]
            neutral = set(_stem(n) for n in spec["neutral"])
            usda_vals = set(v for v, _ in usda_slots.get(slot, []))
            usda_stems = set(_stem(u) for u in usda_all)
            for v in vals:
                if v in usda_vals or v in usda_stems:
                    continue
                if v in neutral:
                    continue
                dropped_cost += spec["weight"]

        # 3. Specificity balance: count unexplained USDA content tokens
        explained = 0
        unexplained = 0
        for w in usda_all:
            if w in _USDA_FILLER:
                continue
            if any(_fuzzy(w, i) >= 0.6 for i in ing_words):
                explained += 1
            elif _slot_of(w):
                continue  # already handled by slot logic
            elif w.isupper() or len(w) <= 2:
                continue
            else:
                unexplained += 1
        extra_ratio = unexplained / float(explained + unexplained + 1)
        # Brand names (upper-case tokens in original) indicate specificity; neutral
        # if ingredient is itself qualified, small penalty otherwise.
        brand_pen = 0.0
        if re.search(r"\b[A-Z]{3,}\b", usda_match):
            brand_pen = 0.3 if len(ing_core) >= 2 else 0.8

        # Compose score on a 0..10 scale
        identity_score = 6.0 * (identity ** 1.5)
        spec_score = 4.0 * math.exp(-0.35 * (added_cost + dropped_cost))
        bonus = min(1.5, matched_bonus * 0.4)
        score = identity_score + spec_score + bonus
        score -= 2.0 * extra_ratio
        score -= brand_pen
        score -= compound_penalty
        # Primary food mismatch: head noun absent from primary segment entirely
        head = ing_core[-1]
        if max((_fuzzy(head, u) for u in usda_primary), default=0.0) < 0.4:
            score -= 1.2

        if score != score:  # NaN guard
            return 0.0
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
