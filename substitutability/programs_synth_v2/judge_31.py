import re
import math

# Nutritional Profile Proximity, variant 7: k-nearest reference foods.
# A small embedded reference set of foods with per-100g macros is used as a
# "nutrient memory". Each text is matched softly (character bigram overlap
# over the cleaned phrase) to the reference names; the macro estimate is the
# similarity-weighted average of the top-3 neighbours (kNN regression).
# The two estimates are compared with a Canberra distance, which treats
# relative differences evenly (2 g vs 4 g fat matters like 20 g vs 40 g).

_REF = [
    # name, kcal, protein, carb, fat
    ("olive oil", 884, 0, 0, 100), ("vegetable oil", 884, 0, 0, 100),
    ("butter salted", 717, 0.9, 0.1, 81), ("mayonnaise", 680, 1, 0.6, 75),
    ("chicken breast raw", 120, 22.5, 0, 2.6), ("chicken breast roasted", 165, 31, 0, 3.6),
    ("chicken patty breaded", 280, 14, 14, 18), ("chicken thigh", 177, 19.7, 0, 10.9),
    ("turkey light meat roasted", 147, 30, 0, 2), ("turkey skin", 380, 25, 0, 30),
    ("ground beef", 254, 17, 0, 20), ("beef steak lean", 160, 26, 0, 6),
    ("pork chop", 231, 26, 0, 14), ("bacon cooked", 541, 37, 1.4, 42),
    ("swordfish raw", 125, 19.8, 0, 4.4), ("salmon fillet", 208, 20, 0, 13),
    ("tuna canned in water", 116, 25.5, 0, 0.8), ("shrimp cooked", 99, 24, 0.2, 0.3),
    ("fried fish breaded", 232, 15, 15, 12), ("egg whole", 143, 12.6, 0.7, 9.5),
    ("tofu firm", 144, 17, 3, 9), ("cottage cheese", 98, 11, 3.4, 4.3),
    ("cottage cheese low fat", 72, 12.4, 2.7, 1), ("cheddar cheese", 403, 24.9, 1.3, 33),
    ("parmesan cheese", 431, 38, 4, 29), ("cream cheese", 342, 6, 4, 34),
    ("vanilla yogurt", 95, 5, 15, 1.3), ("plain yogurt whole milk", 61, 3.5, 4.7, 3.3),
    ("frozen yogurt vanilla", 159, 4, 24, 5.6), ("ice cream vanilla", 207, 3.5, 24, 11),
    ("whole milk", 61, 3.2, 4.8, 3.3), ("heavy cream", 340, 2.8, 2.7, 36),
    ("white rice cooked", 130, 2.7, 28, 0.3), ("pasta cooked", 158, 5.8, 31, 0.9),
    ("potato gnocchi", 133, 3, 30, 0.3), ("baked potato", 93, 2.5, 21, 0.1),
    ("bread whole wheat", 252, 12, 43, 3.5), ("rolled oats", 389, 16.9, 66, 6.9),
    ("breakfast cereal flakes", 357, 7, 84, 0.4), ("granola cereal nut", 471, 10, 64, 20),
    ("wheat flour", 364, 10, 76, 1), ("sweet corn raw", 86, 3.3, 19, 1.4),
    ("creamed corn canned", 72, 1.7, 18, 0.4), ("black beans", 132, 8.9, 24, 0.5),
    ("lentils cooked", 116, 9, 20, 0.4), ("green peas", 81, 5.4, 14.5, 0.4),
    ("tomato raw", 18, 0.9, 3.9, 0.2), ("tomato paste", 82, 4.3, 19, 0.5),
    ("tomato sauce", 24, 1.2, 5.3, 0.3), ("onion raw", 40, 1.1, 9.3, 0.1),
    ("garlic raw", 149, 6.4, 33, 0.5), ("spinach raw", 23, 2.9, 3.6, 0.4),
    ("broccoli raw", 34, 2.8, 6.6, 0.4), ("carrot raw", 41, 0.9, 9.6, 0.2),
    ("lettuce", 15, 1.4, 2.9, 0.2), ("mushroom", 22, 3.1, 3.3, 0.3),
    ("banana", 89, 1.1, 23, 0.3), ("apple", 52, 0.3, 14, 0.2),
    ("blueberries", 57, 0.7, 14.5, 0.3), ("orange grapefruit citrus", 42, 0.8, 10.7, 0.1),
    ("fruit juice", 46, 0.5, 11, 0.1), ("guava paste", 300, 0.4, 75, 0.1),
    ("raisins dried fruit", 299, 3.1, 79, 0.5), ("avocado", 160, 2, 8.5, 14.7),
    ("almonds nuts", 579, 21, 22, 50), ("peanut butter", 588, 25, 20, 50),
    ("chia seeds", 486, 16.5, 42, 30.7), ("flaxseed", 534, 18.3, 29, 42),
    ("sugar granulated", 387, 0, 100, 0), ("honey", 304, 0.3, 82, 0),
    ("maple syrup", 260, 0, 67, 0.1), ("milk chocolate candy", 535, 7.7, 59, 30),
    ("italian dressing", 240, 0.4, 10, 22), ("italian dressing reduced calorie", 50, 0.3, 6, 2.5),
    ("pesto sauce", 418, 5, 6, 40), ("ketchup", 101, 1, 27, 0.1),
    ("chicken broth", 6, 0.6, 0.4, 0.2), ("vegetable soup", 30, 1.3, 5, 0.6),
    ("cream soup condensed", 110, 2, 10, 7), ("ground ginger spice", 335, 9, 72, 4.2),
    ("fresh ginger root", 80, 1.8, 18, 0.8), ("ground cinnamon", 247, 4, 81, 1.2),
    ("seasoning blend", 230, 9, 45, 3), ("garlic powder", 331, 16.6, 73, 0.7),
    ("salt", 0, 0, 0, 0), ("black pepper", 251, 10.4, 64, 3.3),
]


def _clean(text, is_ing):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    if is_ing:
        t = t.split(",")[0]
        t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"\b(nfs|ns|fresh|chopped|diced|sliced|minced|thawed|uncooked|segmented)\b", " ", t)
    words = re.findall(r"[a-z]+", t)
    return " ".join(words)


def _bigrams(s):
    out = set()
    for w in s.split():
        w = "^" + w + "$"
        for i in range(len(w) - 1):
            out.add(w[i:i + 2])
    return out


_REF_GRAMS = [(_bigrams(r[0]), r[1:]) for r in _REF]


def _knn(text, k=3):
    g = _bigrams(text)
    if not g:
        return None, 0.0
    sims = []
    for rg, macros in _REF_GRAMS:
        inter = len(g & rg)
        if inter == 0:
            continue
        # containment of the reference name in the text (asymmetric overlap)
        s = inter / float(len(rg)) * (inter / float(len(g))) ** 0.3
        sims.append((s, macros))
    if not sims:
        return None, 0.0
    sims.sort(key=lambda x: -x[0])
    top = sims[:k]
    # sharpen weights so the best neighbour dominates
    w = [s ** 4 for s, _ in top]
    tot = sum(w)
    est = [sum(wi * m[j] for wi, (_, m) in zip(w, top)) / tot for j in range(4)]
    return est, top[0][0]


def _canberra(a, b):
    d = 0.0
    for x, y, eps in zip(a, b, (20.0, 1.0, 1.0, 1.0)):
        d += abs(x - y) / (abs(x) + abs(y) + eps)
    return d / 4.0


def judging_function(ingredient, usda_match):
    try:
        ti = _clean(str(ingredient or ""), True)
        tu = _clean(str(usda_match or ""), False)
        if not ti or not tu:
            return 0.0
        ei, ci = _knn(ti)
        eu, cu = _knn(tu)
        if ei is None or eu is None:
            return 3.0
        d = _canberra(ei, eu)
        score = 10.0 * (1.0 - d) ** 2
        # low-confidence neighbour matches shrink toward the neutral middle
        conf = min(ci, cu)
        if conf < 0.5:
            score = 5.0 + (score - 5.0) * (conf / 0.5)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
