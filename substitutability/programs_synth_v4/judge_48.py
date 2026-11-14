import re
import math

_UNITS = r"(?:g|kg|mg|ml|l|oz|lb|lbs|grams?|cups?|tbsp|tsp)"
_PREP = {
    "fresh", "frozen", "thawed", "chopped", "sliced", "slices", "diced", "minced", "grated",
    "large", "small", "medium", "finely", "roughly", "peeled", "trimmed", "boneless",
    "skinless", "optional", "garnish", "for", "and", "or", "of", "the", "a", "an", "to",
    "taste", "strong", "brewed", "whole", "raw", "plain", "about", "into", "pieces",
    "cut", "halved", "flaked", "cooked", "rinsed", "drained", "packed", "loosely",
}
_CATEGORY_HEADS = {
    "spices", "fish", "cheese", "nuts", "cereals", "beverages", "vegetables", "fruits",
    "beef", "pork", "lamb", "chicken", "turkey", "seeds", "oil", "vegetable", "soup",
    "sauce", "candies", "snacks", "baby", "infant", "mollusks", "crustaceans", "game",
    "meat", "alcoholic", "beverage", "sweeteners", "spreads", "legumes", "grains",
}
_DERIVED = {
    "milk", "butter", "soup", "pie", "sauce", "cookie", "cookies", "cake", "juice",
    "bread", "bar", "bars", "relish", "spread", "powder", "paste", "chips", "flavored",
    "flavor", "candy", "muffin", "muffins", "drink", "syrup", "jam", "jelly", "salad",
    "dressing", "pudding", "ice", "cream", "yogurt", "sandwich", "casserole", "filling",
    "crackers", "dip", "oil", "cereal", "puree", "concentrate", "extract",
}


def _stem(w):
    try:
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w
    except Exception:
        return w


def _tokens(text):
    return [_stem(t) for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 1]


def _clean_ingredient(text):
    t = (text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d./]+\s*" + _UNITS + r"?\b", " ", t)
    t = t.split(",")[0]
    toks = [w for w in _tokens(t) if w not in _PREP]
    return toks


def _trigrams(w):
    w = "  " + w + " "
    return {w[i:i + 3] for i in range(len(w) - 2)}


def _fuzzy(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.8
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ingredient(ingredient)
        if not ing:
            ing = _tokens(ingredient or "")
        segs = [s.strip() for s in str(usda_match or "").lower().split(",") if s.strip()]
        if not ing or not segs:
            return 0.0
        seg_toks = [_tokens(s) for s in segs]
        seg_toks = [s for s in seg_toks if s]
        if not seg_toks:
            return 0.0

        # Determine the "primary segment": skip a leading broad category header
        # (e.g. "Spices", "Fish", "Cheese") when the ingredient does not itself name it.
        primary_idx = 0
        first = seg_toks[0]
        if (len(first) == 1 and first[0] in _CATEGORY_HEADS and len(seg_toks) > 1
                and max(_fuzzy(first[0], w) for w in ing) < 0.75):
            primary_idx = 1
        primary = seg_toks[primary_idx]
        primary_head = primary[-1]
        primary_mods = primary[:-1]

        ing_head = ing[-1]
        ing_mods = ing[:-1]

        # Locate the ingredient head in the USDA description with a position-decay weight.
        best_role, best_sim = "absent", 0.0
        for si, st in enumerate(seg_toks):
            for ti, w in enumerate(st):
                s = _fuzzy(ing_head, w)
                if s < 0.7:
                    continue
                if si == primary_idx and ti == len(st) - 1:
                    role = "head"
                elif si == primary_idx:
                    role = "modifier"
                elif si < primary_idx:
                    role = "category"
                else:
                    role = "descriptor"
                rank = {"head": 4, "category": 3, "modifier": 2, "descriptor": 1}[role]
                cur = {"head": 4, "category": 3, "modifier": 2, "descriptor": 1, "absent": 0}[best_role]
                if rank > cur or (rank == cur and s > best_sim):
                    best_role, best_sim = role, s

        role_score = {"head": 6.0, "category": 4.0, "modifier": 2.0,
                      "descriptor": 2.5, "absent": 0.0}[best_role] * max(best_sim, 0.0)

        # Head-of-ingredient may be a generic word ("cheese", "fillet"); credit modifiers
        # that occupy the primary head slot (e.g. "brie cheese" vs "Cheese, brie").
        if best_role != "head" and ing_mods:
            m = max(_fuzzy(x, primary_head) for x in ing_mods)
            if m >= 0.8:
                role_score = max(role_score, 5.0 * m)

        # Demotion penalty: the USDA primary head is a derived product that the ingredient
        # does not name (applesauce -> cookie, almond -> almond milk).
        demotion = 0.0
        if primary_head in _DERIVED and max(_fuzzy(primary_head, w) for w in ing) < 0.7:
            demotion += 2.5
        if best_role in ("modifier", "descriptor") and primary_head not in ing:
            demotion += 1.0
        # Ingredient itself is a derived product but USDA primary is the bare base food.
        if ing_head in _DERIVED and best_role != "head" and \
                max(_fuzzy(ing_head, w) for st in seg_toks for w in st) < 0.7:
            demotion += 2.0

        # Coverage of ingredient modifiers in the whole USDA entry, decayed by position.
        cov = 0.0
        if ing_mods:
            for x in ing_mods:
                best = 0.0
                for si, st in enumerate(seg_toks):
                    decay = 1.0 / (1.0 + 0.4 * abs(si - primary_idx))
                    for w in st:
                        best = max(best, _fuzzy(x, w) * decay)
                cov += best
            cov = cov / len(ing_mods)
        else:
            cov = 0.6

        # Unmatched words in the primary segment signal a different food.
        extra = 0
        for w in primary_mods:
            if max(_fuzzy(w, x) for x in ing) < 0.7:
                extra += 1
        extra_pen = 0.6 * extra

        score = 2.0 + role_score + 2.0 * cov - demotion - extra_pen
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
