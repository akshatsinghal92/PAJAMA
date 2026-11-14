import re
import math

_UNITS = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "ounce", "ounces", "lb", "lbs",
    "pound", "pounds", "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pinch", "dash", "clove", "cloves", "piece", "pieces",
    "slice", "slices", "can", "cans", "pkg", "package", "inch",
}

_NOISE = {
    "diced", "chopped", "minced", "sliced", "grated", "shredded", "peeled", "crushed",
    "fresh", "freshly", "finely", "roughly", "coarsely", "thinly", "thawed", "drained",
    "rinsed", "trimmed", "halved", "quartered", "cubed", "to", "taste", "from", "tube",
    "of", "and", "or", "the", "a", "an", "for", "with", "without", "in", "into",
    "large", "small", "medium", "about", "optional", "plus", "more", "extra", "some",
    "softened", "melted", "room", "temperature", "divided", "packed", "lightly",
    "beaten", "whole", "cut", "pieces", "inch", "other", "eaten", "includes", "only",
    "nfs", "ns", "type", "style", "made", "prepared",
}

# Modifier-like tokens: overlap only on these counts for little.
_MODIFIERS = {
    "raw", "cooked", "frozen", "canned", "dried", "dry", "uncooked", "boiled", "baked",
    "roasted", "fried", "grilled", "steamed", "plain", "unsalted", "salted", "sweetened",
    "unsweetened", "enriched", "unenriched", "lean", "fat", "low", "reduced", "regular",
    "ground", "soft", "hard", "mix", "commercial", "homemade", "solids", "liquids",
    "flesh", "skin", "boneless", "skinless", "white", "red", "green", "yellow", "black",
    "light", "dark", "heavy", "instant", "brand", "foods", "by", "products", "variety",
    "meats", "fluid", "added", "salt", "sugar", "water", "pack", "packed",
}


def _stem(tok):
    t = tok
    for suf in ("ies", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            if suf == "ies":
                return t[:-3] + "y"
            if suf == "es" and t[-3] in "sxz":
                return t[:-2]
            if suf == "s" and not t.endswith("ss"):
                return t[:-1]
    return t


def _clean_ingredient(text):
    s = str(text or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"\d+(\.\d+)?\s*[a-z]{0,6}\b", lambda m: " " if re.sub(r"[\d.\s]", "", m.group(0)) in _UNITS or re.sub(r"[\d.\s]", "", m.group(0)) == "" else " " + re.sub(r"[\d.\s]", "", m.group(0)) + " ", s)
    toks = re.findall(r"[a-z]+", s)
    out = []
    for t in toks:
        if t in _UNITS or t in _NOISE or len(t) < 2:
            continue
        out.append(_stem(t))
    return out


def _segments_usda(text):
    s = str(text or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    segs = []
    for i, part in enumerate(s.split(",")):
        toks = []
        for t in re.findall(r"[a-z]+", part):
            if t in _NOISE or t in _UNITS or len(t) < 2:
                continue
            toks.append(_stem(t))
        if toks:
            segs.append(toks)
    return segs


def _bigrams(w):
    w = "^" + w + "$"
    return [w[i:i + 2] for i in range(len(w) - 1)]


def _dice(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    pool = list(bb)
    hit = 0
    for g in ba:
        if g in pool:
            pool.remove(g)
            hit += 1
    return 2.0 * hit / (len(ba) + len(bb))


def _weight(tok):
    return 0.25 if tok in _MODIFIERS else 1.0


def judging_function(ingredient, usda_match):
    try:
        ing = _clean_ingredient(ingredient)
        segs = _segments_usda(usda_match)
        if not ing or not segs:
            return 0.0

        # Positional weights for USDA tokens: earlier comma segments define the food.
        usda_tokens = []
        for si, seg in enumerate(segs):
            pos_w = 1.0 / (1.0 + 0.35 * si)
            for t in seg:
                usda_tokens.append((t, pos_w * _weight(t), si))

        # Ingredient token weights: head noun (last token) is the food-defining word.
        n = len(ing)
        ing_w = []
        for i, t in enumerate(ing):
            base = _weight(t)
            head = 1.6 if i == n - 1 else 1.0
            ing_w.append(base * head)

        # Greedy soft alignment (best pairs first, one-to-one).
        pairs = []
        for i, t in enumerate(ing):
            for j, (u, uw, si) in enumerate(usda_tokens):
                sim = _dice(t, u)
                if sim >= 0.6:
                    pairs.append((sim, i, j))
        pairs.sort(reverse=True)
        used_i, used_j = set(), set()
        matched_ing = 0.0
        matched_usda = 0.0
        head_hit = 0.0
        first_seg_hit = False
        for sim, i, j in pairs:
            if i in used_i or j in used_j:
                continue
            used_i.add(i)
            used_j.add(j)
            matched_ing += sim * ing_w[i]
            matched_usda += sim * usda_tokens[j][1]
            if i == n - 1:
                head_hit = max(head_hit, sim)
            if usda_tokens[j][2] == 0 and _weight(usda_tokens[j][0]) == 1.0:
                first_seg_hit = True

        total_ing = sum(ing_w) or 1.0
        total_usda = sum(w for _, w, _ in usda_tokens) or 1.0
        recall = matched_ing / total_ing
        precision = matched_usda / total_usda

        # Weighted F-beta favouring recall (ingredient coverage) with beta=1.5
        beta2 = 2.25
        if recall + precision > 0:
            f = (1 + beta2) * precision * recall / (beta2 * precision + recall)
        else:
            f = 0.0

        # Ordered bigram match bonus on contiguous content tokens.
        ing_bi = set(zip(ing, ing[1:]))
        flat = [t for t, _, _ in usda_tokens]
        usda_bi = set(zip(flat, flat[1:])) | set(zip(flat[1:], flat))
        bigram_bonus = 0.1 if ing_bi and (ing_bi & usda_bi) else 0.0

        # Unmatched content tokens in ingredient (non-modifier) are penalised.
        unmatched_content = sum(1 for i, t in enumerate(ing) if i not in used_i and _weight(t) == 1.0)

        score = 0.55 * f + 0.25 * head_hit + (0.12 if first_seg_hit else 0.0) + bigram_bonus
        score -= 0.06 * unmatched_content
        # Squash and scale to 0-100
        score = 1.0 / (1.0 + math.exp(-6.0 * (score - 0.45)))
        return round(100.0 * score, 3)
    except Exception:
        return 0.0
