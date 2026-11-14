import re
import math

_UNITS = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "ounce", "ounces", "lb", "lbs",
    "pound", "pounds", "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pinch", "dash", "clove", "cloves", "slice", "slices",
    "piece", "pieces", "can", "cans", "package", "pkg", "inch",
}
_NOISE = {
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "trimmed", "flaked",
    "peeled", "thawed", "drained", "rinsed", "crushed", "cut", "into", "to", "taste",
    "from", "tube", "fresh", "freshly", "finely", "roughly", "thinly", "large", "small",
    "medium", "a", "an", "the", "of", "for", "with", "or", "optional", "about", "approx",
    "plus", "more", "extra", "divided", "packed", "loosely", "lightly", "whole", "halved",
    "quartered", "softened", "melted", "room", "temperature", "beaten", "nfs", "ns",
    "raw", "uncooked", "prepared", "ready", "eat", "type", "style", "brand", "inch",
    "serving", "servings", "if", "needed", "as", "such", "in", "on", "at", "and",
}
# Category / grouping heads frequently used by USDA that do not define a specific food.
_CATEGORY = {
    "spices", "spice", "cereals", "cereal", "beverages", "snacks", "sweets", "soups",
    "fast", "foods", "food", "restaurant", "babyfood", "candies", "sauces", "dressings",
    "products", "product", "mission", "post", "great",
}
# Modifier-ish words: overlap on these counts for little.
_MODIFIERS = {
    "ground", "smoked", "frozen", "dried", "dry", "canned", "cooked", "boiled", "baked",
    "fried", "roasted", "grilled", "steamed", "crude", "soft", "hard", "sweet", "salted",
    "unsalted", "low", "fat", "reduced", "sodium", "free", "plain", "red", "green",
    "white", "black", "yellow", "brown", "regular", "enriched", "fortified", "skinless",
    "boneless", "skin", "bone", "lean", "mature", "young", "crunch", "crunchy",
}


def _stem(w):
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ves", "f"), ("es", ""), ("s", "")):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            if suf == "es" and not re.search(r"(ch|sh|x|z|ss)es$", w):
                continue
            return w[: -len(suf)] + rep
    return w


def _clean_ingredient(text):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.split(",")[0]
    t = re.sub(r"^\s*[\d./]+\s*[a-z]*\b", " ", t)
    return t


def _tokens(text):
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in _UNITS or w in _NOISE or len(w) < 2:
            continue
        out.append(_stem(w))
    return out


def _trigrams(w):
    p = "#" + w + "#"
    return {p[i:i + 3] for i in range(len(p) - 2)}


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ta, tb = _trigrams(a), _trigrams(b)
    d = 2.0 * len(ta & tb) / (len(ta) + len(tb))
    return d if d >= 0.6 else 0.0


def _weight(tok):
    if tok in _CATEGORY:
        return 0.15
    if tok in _MODIFIERS:
        return 0.35
    return 1.0


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0

        ing_core = _clean_ingredient(ing_raw)
        ing_toks = _tokens(ing_core)
        if not ing_toks:
            ing_toks = _tokens(ing_raw)
        if not ing_toks:
            return 0.0

        # USDA tokens with segment-position decay: earlier segments define the food.
        segs = [s for s in usda_raw.lower().split(",") if s.strip()]
        usda = []  # (token, position_weight)
        for si, seg in enumerate(segs):
            pw = 1.0 / (1.0 + 0.45 * si)
            for tok in _tokens(seg):
                usda.append((tok, pw))
        if not usda:
            return 0.0

        # Head noun of the ingredient is its last content token (English head-final NP).
        content_ing = [t for t in ing_toks if _weight(t) >= 1.0] or ing_toks
        head = content_ing[-1]

        # Soft alignment: ingredient -> usda (recall of ingredient meaning).
        rec_num = rec_den = 0.0
        aligned = []
        for i, t in enumerate(ing_toks):
            w = _weight(t) * (1.6 if t == head else 1.0)
            best, bj = 0.0, -1
            for j, (u, pw) in enumerate(usda):
                s = _sim(t, u) * (0.6 + 0.4 * pw)
                if s > best:
                    best, bj = s, j
            rec_num += w * best
            rec_den += w
            if best > 0:
                aligned.append((i, bj))
        recall = rec_num / rec_den if rec_den else 0.0

        # Reverse: usda -> ingredient (precision; unmatched USDA food words = different food).
        pre_num = pre_den = 0.0
        unmatched_primary = 0.0
        for j, (u, pw) in enumerate(usda):
            w = _weight(u) * pw
            best = max(_sim(u, t) for t in ing_toks)
            pre_num += w * best
            pre_den += w
            if best == 0 and _weight(u) >= 1.0 and pw >= 0.99:
                unmatched_primary += 1.0
        precision = pre_num / pre_den if pre_den else 0.0

        # Head-noun match quality.
        head_sim = max(_sim(head, u) for u, _ in usda)

        # Order preservation: fraction of aligned pairs that are monotone (LIS-style).
        order = 0.5
        if len(aligned) >= 2:
            js = [j for _, j in aligned]
            lis = [1] * len(js)
            for a in range(len(js)):
                for b in range(a):
                    if js[b] <= js[a]:
                        lis[a] = max(lis[a], lis[b] + 1)
            order = max(lis) / len(js)
        elif len(aligned) == 1:
            order = 0.7

        # Content-word Jaccard (hard).
        si = set(t for t in ing_toks if _weight(t) >= 1.0)
        su = set(u for u, _ in usda if _weight(u) >= 1.0)
        jac = len(si & su) / len(si | su) if (si | su) else 0.0

        # F-measure weighted towards recall of ingredient meaning.
        beta2 = 1.5
        f = 0.0
        if recall + precision > 0:
            f = (1 + beta2) * recall * precision / (beta2 * precision + recall)

        score = 55.0 * f + 20.0 * head_sim + 10.0 * jac + 8.0 * order

        # Penalties.
        unmatched_ing_content = sum(
            1 for t in content_ing
            if max(_sim(t, u) for u, _ in usda) == 0
        )
        score -= 9.0 * unmatched_ing_content
        score -= 7.0 * unmatched_primary
        if re.search(r"\band\b|&|\bwith\b", ing_core):
            score -= 12.0  # compound/mixed ingredient rarely matched by one entry
        if head_sim == 0:
            score -= 15.0

        if score != score or math.isinf(score):
            return 0.0
        return round(max(0.0, min(100.0, score)), 4)
    except Exception:
        return 0.0
