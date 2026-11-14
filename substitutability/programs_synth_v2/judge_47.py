import re

# Lexical and Token Overlap, variant 7: synonym-canonicalised Tversky index.
# Recipe and USDA vocabularies differ (garbanzo / chickpea, scallion / green
# onion, prawn / shrimp, yoghurt / yogurt, courgette / zucchini). Tokens are
# first canonicalised through a synonym table (single and two-word forms).
# Then the asymmetric Tversky index is computed:
#     T = |I & U| / (|I & U| + alpha*|I - U| + beta*|U - I|)
# with alpha > beta: ingredient words the USDA entry lacks hurt more than
# extra USDA descriptor words. Each token's contribution is weighted (food
# nouns > other words > modifiers) so modifier-only overlap is discounted.

_SYN = {
    "garbanzo": "chickpea", "garbanzos": "chickpea", "scallion": "green onion",
    "scallions": "green onion", "spring onion": "green onion", "prawn": "shrimp",
    "prawns": "shrimp", "yoghurt": "yogurt", "courgette": "zucchini",
    "aubergine": "eggplant", "capsicum": "pepper", "bell pepper": "pepper",
    "cilantro": "coriander", "coriander leaves": "coriander", "maize": "corn",
    "sweetcorn": "corn", "beetroot": "beet", "rocket": "arugula", "mince": "ground",
    "minced meat": "ground meat", "caster sugar": "sugar", "icing sugar": "powdered sugar",
    "confectioners sugar": "powdered sugar", "double cream": "heavy cream",
    "single cream": "light cream", "plain flour": "all purpose flour", "flax": "flaxseed",
    "flax seed": "flaxseed", "linseed": "flaxseed", "chile": "chili", "chilli": "chili",
    "evoo": "olive oil", "porridge oats": "oats", "rolled oats": "oats",
    "ketchup": "catsup", "mayo": "mayonnaise", "tinned": "canned",
}
_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste from tube jar can
optional about divided and or of with without the a an in as for fresh chopped diced
minced sliced shredded grated thawed segmented peeled drained rinsed cubed finely
roughly large small medium nfs ns""".split())
_MODS = set("""raw cooked boiled baked roasted fried grilled steamed frozen canned dried
low fat lowfat nonfat reduced calorie sodium light lean salted sweetened unsweetened
whole plain regular prepared ready heat dry skin not eaten only style made sweet""".split())
_ALPHA, _BETA = 0.8, 0.35


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _canon(text):
    t = " " + re.sub(r"[^a-z ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    for k in sorted(_SYN, key=len, reverse=True):
        t = t.replace(" " + k + " ", " " + _SYN[k] + " ")
    return [_sing(w) for w in t.split() if w not in _NOISE and len(w) > 1]


def _w(tok, head):
    if tok == head:
        return 2.5
    if tok in _MODS:
        return 0.35
    return 1.0


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "")).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing, flags=re.I)
        I = _canon(ing)
        U = _canon(re.sub(r"\([^)]*\)", " ", str(usda_match or "")))
        if not I or not U:
            return 0.0
        content = [t for t in I if t not in _MODS] or I
        head = content[-1]
        si, su = set(I), set(U)
        common = sum(_w(t, head) for t in si & su)
        only_i = sum(_w(t, head) for t in si - su)
        only_u = sum(_w(t, head) for t in su - si)
        denom = common + _ALPHA * only_i + _BETA * only_u
        tv = common / denom if denom else 0.0
        return round(10.0 * tv, 3)
    except Exception:
        return 0.0
