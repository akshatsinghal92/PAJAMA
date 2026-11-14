import re
import math

# Food Category Consistency, variant 7: Jensen-Shannon divergence between
# category-evidence histograms.
# Every token contributes evidence to one or more categories (some words are
# ambiguous: "butter" -> dairy/fat, "pepper" -> produce/spice, "ginger" ->
# produce/spice, "corn" -> produce/grain, "peanut" -> legume/nut). Evidence is
# weighted by position (head noun, USDA primary field). Histograms are
# smoothed and normalised; the score is 1 - JSD (base 2), reduced when either
# histogram is very uncertain (high entropy) because the category is unclear.

_EVID = {
    # word: {category: weight}
    "butter": {"dairy": 0.6, "fat": 0.4}, "pepper": {"produce": 0.5, "spice": 0.5},
    "ginger": {"produce": 0.45, "spice": 0.55}, "corn": {"produce": 0.6, "grain": 0.4},
    "peanut": {"legume": 0.4, "nutseed": 0.6}, "garlic": {"produce": 0.75, "spice": 0.25},
    "onion": {"produce": 0.8, "spice": 0.2}, "coconut": {"produce": 0.5, "nutseed": 0.5},
    "egg": {"protein": 0.7, "dairy": 0.3}, "chocolate": {"sweet": 1.0}, "cream": {"dairy": 1.0},
    "yogurt": {"dairy": 1.0}, "milk": {"dairy": 1.0}, "cheese": {"dairy": 1.0},
    "cottage": {"dairy": 1.0}, "oil": {"fat": 1.0}, "lard": {"fat": 1.0}, "margarine": {"fat": 1.0},
    "sugar": {"sweet": 1.0}, "honey": {"sweet": 1.0}, "syrup": {"sweet": 1.0}, "jam": {"sweet": 1.0},
    "candy": {"sweet": 1.0}, "candies": {"sweet": 1.0},
    "sauce": {"condiment": 1.0}, "dressing": {"condiment": 1.0}, "pesto": {"condiment": 1.0},
    "ketchup": {"condiment": 1.0}, "mustard": {"condiment": 0.8, "spice": 0.2},
    "mayonnaise": {"condiment": 0.6, "fat": 0.4}, "vinegar": {"condiment": 1.0},
    "paste": {"condiment": 0.6, "produce": 0.4}, "juice": {"beverage": 0.8, "produce": 0.2},
    "beverage": {"beverage": 1.0}, "beverages": {"beverage": 1.0}, "soup": {"beverage": 0.5, "condiment": 0.5},
    "broth": {"beverage": 0.6, "condiment": 0.4}, "spices": {"spice": 1.0}, "spice": {"spice": 1.0},
    "seasoning": {"spice": 1.0}, "salt": {"spice": 1.0},
}
_SIMPLE = {
    "protein": "chicken turkey beef pork lamb veal ham bacon sausage steak duck meat patty fish swordfish salmon tuna cod shrimp crab lobster tofu",
    "produce": "tomato carrot broccoli spinach lettuce kale cabbage zucchini squash celery cucumber mushroom potato eggplant vegetable vegetables fruit apple banana orange lemon lime berry blueberry strawberry grape mango peach pear cherry pineapple melon guava ugli avocado",
    "grain": "rice pasta noodle spaghetti macaroni bread flour oat cereal cereals barley quinoa couscous wheat cracker tortilla gnocchi granola",
    "legume": "bean lentil chickpea soybean edamame hummus pea",
    "nutseed": "nut almond walnut pecan cashew pistachio hazelnut seed chia flaxseed sesame sunflower tahini",
    "spice": "cinnamon cumin paprika nutmeg turmeric oregano basil thyme rosemary parsley cilantro dill sage clove cardamom",
}
for _c, _ws in _SIMPLE.items():
    for _w in _ws.split():
        _EVID.setdefault(_w, {_c: 1.0})
_CATS = sorted({c for d in _EVID.values() for c in d})


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _hist(weighted):
    h = {c: 0.0 for c in _CATS}
    hit = False
    for w, wt in weighted:
        ev = _EVID.get(w) or _EVID.get(_sing(w))
        if not ev:
            continue
        hit = True
        for c, v in ev.items():
            h[c] += v * wt
    evidence = sum(h.values())
    # smoothing proportional to the evidence mass, so a clean single-category
    # histogram looks the same whether it came from one word or three
    for c in h:
        h[c] += 0.01 * max(evidence, 1e-6)
    tot = sum(h.values())
    return {c: v / tot for c, v in h.items()}, hit


def _kl(p, q):
    return sum(p[c] * math.log2(p[c] / q[c]) for c in p if p[c] > 0)


def _entropy(p):
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower()).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        iw = re.findall(r"[a-z]+", ing)
        fields = [re.findall(r"[a-z]+", f) for f in str(usda_match or "").lower().split(",")]
        fields = [f for f in fields if f]
        if not iw or not fields:
            return 0.0
        n = len(iw)
        wi = [(w, 3.0 if k == n - 1 else 1.0) for k, w in enumerate(iw)]
        wu = []
        for fi, f in enumerate(fields):
            base = 3.0 if fi == 0 else (2.0 if fi == 1 else 0.4)
            for k, w in enumerate(f):
                wu.append((w, base * (1.2 if k == len(f) - 1 else 0.8)))
        p, hp = _hist(wi)
        q, hq = _hist(wu)
        # the very same food noun in the USDA identity fields: same category
        ident = {_sing(w) for f in fields[:2] for w in f}
        content = [w for w in iw if w not in ("fresh", "frozen", "raw", "chopped", "diced",
                                               "minced", "sliced", "canned", "cooked")]
        same_food = bool(content) and _sing(content[-1]) in ident
        if not hp or not hq:
            return 90.0 if same_food else 35.0
        m = {c: 0.5 * (p[c] + q[c]) for c in _CATS}
        jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
        sim = 1.0 - min(1.0, jsd)
        max_h = math.log2(len(_CATS))
        unclear = max(_entropy(p), _entropy(q)) / max_h
        score = 100.0 * sim * (1.0 - 0.3 * unclear)
        if same_food:
            score = max(score, 96.0)
        return round(max(0.0, min(100.0, score)), 2)
    except Exception:
        return 0.0
