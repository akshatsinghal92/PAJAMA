import re

_PREP = set("""fresh frozen thawed melted shredded sliced diced chopped minced grated ground crushed
whole lean skin skinless boneless trimmed dried dry canned cooked raw large small medium
organic sweetened unsweetened plain of and or with in the a for to from tube pieces piece
cut cubed peeled fine finely roughly packed optional divided softened chilled cold hot warm
g kg ml oz lb tbsp tsp cup cups""".split())

_SYN = {
    "maize": "corn", "granada": "pomegranate", "pomegranates": "pomegranate",
    "chicken": "chicken", "chickens": "chicken", "broilers": "chicken",
}


def _stem(w):
    w = _SYN.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    return [_stem(t) for t in re.findall(r"[a-z]+", s)]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\s*", "", ing.lower())
        ing_main = ing.split(",")[0]
        ing_t = [t for t in _tokens(ing_main) if t not in _PREP]
        if not ing_t:
            ing_t = _tokens(ing_main)
        parts = [p.strip() for p in usda.lower().split(",")]
        head_t = [t for t in _tokens(parts[0]) if t not in _PREP]
        all_t = set(t for p in parts for t in _tokens(p) if t not in _PREP)
        # head words of USDA: first part; also second part when first is a category
        cats = {"fish", "beef", "pork", "nuts", "cheese", "cereal", "snack", "oil", "spice",
                "chicken", "turkey", "cream", "yogurt", "ham", "lamb"}
        cand = set(head_t)
        if len(parts) > 1 and (not head_t or head_t[0] in cats or len(head_t) == 1):
            cand |= set(t for t in _tokens(parts[1]) if t not in _PREP)
        if not ing_t or not all_t:
            return 0.0
        ing_set = set(ing_t)
        ing_head = ing_t[-1]
        # 1. head noun of ingredient present in USDA head
        score = 0.0
        if ing_head in cand:
            score += 4.0
        elif ing_head in all_t:
            score += 2.5
        # 2. coverage of ingredient words by USDA words
        cov = len(ing_set & all_t) / float(len(ing_set))
        score += 3.0 * cov
        # 3. precision: USDA head words explained by ingredient
        if head_t:
            prec = len(set(head_t) & ing_set) / float(len(set(head_t)))
            score += 2.0 * prec
        # 4. penalty when USDA head contains foreign words (e.g. guava paste vs garlic paste)
        foreign = [t for t in head_t if t not in ing_set and t not in cats]
        score -= 1.0 * len(foreign)
        # 5. word-order: ingredient head is the last word; USDA head first word equal -> bonus
        if head_t and head_t[0] == ing_head:
            score += 1.0
        # 6. penalty for conflicting product forms
        forms = {"juice", "bean", "powder", "oil", "paste", "sauce", "flour", "butter", "milk", "seed"}
        for f in forms:
            if (f in cand) != (f in ing_set):
                score -= 1.5
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
