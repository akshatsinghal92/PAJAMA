import re

_PREP = {
    "fresh", "frozen", "thawed", "melted", "shredded", "chopped", "diced", "sliced",
    "minced", "grated", "ground", "lean", "sweetened", "unsweetened", "canned", "dried",
    "cooked", "raw", "skin-on", "skinless", "boneless", "large", "small", "medium",
    "whole", "fine", "finely", "roughly", "crushed", "peeled", "toasted", "roasted",
    "softened", "cold", "warm", "hot", "plain", "organic", "extra", "virgin", "light",
    "of", "and", "or", "the", "a", "an", "with", "from", "for", "into", "to", "in",
    "leaves", "pieces", "piece", "parts", "equal", "tube", "jar", "can", "pack",
    "nfs", "ns", "uncooked", "prepared", "type", "style", "made", "regular",
}

_SYN = {
    "maize": "corn", "courgette": "zucchini", "aubergine": "eggplant",
    "coriander": "cilantro", "prawn": "shrimp", "prawns": "shrimp", "rocket": "arugula",
    "scallion": "onion", "scallions": "onion", "garbanzo": "chickpea",
    "chickpeas": "chickpea", "capsicum": "pepper", "mince": "ground",
    "yoghurt": "yogurt", "icing": "powdered", "caster": "sugar",
}


def _singular(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|l|oz|lb|grams?)\b", " ", text)
    text = re.sub(r"\d+", " ", text)
    words = re.findall(r"[a-z][a-z\-]*", text)
    out = []
    for w in words:
        w = _SYN.get(w, w)
        w = _singular(w)
        if w not in _PREP and len(w) > 1:
            out.append(w)
    return out


def _ingredient_core(ing):
    main = ing.split(",")[0]
    toks = _tokens(main)
    return toks


def _usda_core(usda):
    parts = [p.strip() for p in usda.split(",") if p.strip()]
    if not parts:
        return [], []
    primary = _tokens(parts[0])
    secondary = []
    for p in parts[1:3]:
        secondary.extend(_tokens(p))
    return primary, secondary


def _trigrams(s):
    s = "  " + s + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _char_sim(a, b):
    if not a or not b:
        return 0.0
    ta, tb = _trigrams(a), _trigrams(b)
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _best_match(word, cands):
    best = 0.0
    for c in cands:
        if c == word:
            return 1.0
        if len(word) >= 4 and len(c) >= 4 and (word.startswith(c) or c.startswith(word)):
            best = max(best, 0.85)
        best = max(best, _char_sim(word, c))
    return best


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _ingredient_core(str(ingredient))
        prim, sec = _usda_core(str(usda_match))
        if not ing or not (prim or sec):
            return 5.0
        usda_all = prim + sec

        # Head noun: last content token of the ingredient phrase.
        head = ing[-1]
        head_vs_primary = _best_match(head, prim) if prim else 0.0
        head_vs_any = _best_match(head, usda_all)
        head_score = max(head_vs_primary, 0.9 * head_vs_any)

        # Modifier tokens: how many of the ingredient's qualifiers identify the same food.
        mods = ing[:-1]
        if mods:
            mod_cov = sum(_best_match(m, usda_all) for m in mods) / len(mods)
        else:
            mod_cov = 1.0

        # Reverse direction: does the USDA primary phrase introduce a different food?
        if prim:
            prim_cov = sum(_best_match(p, ing) for p in prim) / len(prim)
        else:
            prim_cov = 0.5

        # Whole-phrase character similarity as a soft tie-breaker.
        phrase = _char_sim(" ".join(ing), " ".join(usda_all))

        score = 10.0 * (0.5 * head_score + 0.2 * mod_cov + 0.2 * prim_cov + 0.1 * phrase)

        # Penalize when heads clearly differ (different core substance).
        if head_score < 0.4:
            score *= 0.5
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
