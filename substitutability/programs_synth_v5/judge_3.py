import re
import math

_FAMILIES = {
    "dairy": "milk yogurt yoghurt cheese cream butter kefir whey curd",
    "oil": "oil shortening lard ghee margarine",
    "meat": "beef pork lamb veal ham bacon sausage chicken turkey duck goose venison giblets liver heart tongue gizzard steak ribs meat",
    "fish": "fish salmon tuna swordfish cod trout whitefish shrimp crab lobster sardine anchovy tilapia squid clam oyster mussel",
    "veg": "radish chard squash carrot onion garlic spinach kale lettuce tomato potato cabbage celery pepper cucumber zucchini broccoli cauliflower pumpkin beet turnip leek",
    "fruit": "apple applesauce banana orange lemon lime grape berry strawberry blueberry cherry peach pear mango pineapple olive coconut",
    "grain": "flour rice oat oats wheat corn bread pasta noodle cereal amaranth quinoa barley rye",
    "legume": "bean lentil pea chickpea soy tofu peanut",
    "nut": "almond walnut pecan cashew pistachio hazelnut seed sunflower flax flaxseed chia sesame",
    "herb": "sage basil thyme oregano parsley mint cilantro rosemary dill ginger cinnamon cumin paprika spice spices",
    "sauce": "sauce marinara ketchup mustard mayonnaise dressing salsa vinegar paste",
    "snack": "chips cracker cookie cake candy chocolate",
}
_W2F = {}
for _f, _ws in _FAMILIES.items():
    for _w in _ws.split():
        _W2F.setdefault(_w, set()).add(_f)

_NOISE = set("""fresh frozen canned dried raw cooked chopped sliced diced minced grated shredded cubed ground
crushed thawed drained optional garnish leftover store bought homemade toasted roasted smoked pickled
large small medium whole skin on for frying of and or with without the a an to taste from tube cup
slices boneless skinless peeled ready serve regular salt added low high fat lowfat nonfat""".split())

def _norm(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w

def _words(s):
    return [_norm(w) for w in re.findall(r"[a-z]+", s)]

def _tri(w):
    w = "#" + w + "#"
    return set(w[i:i + 3] for i in range(len(w) - 2)) if len(w) >= 3 else {w}

def _dice(a, b):
    x, y = _tri(a), _tri(b)
    return 2.0 * len(x & y) / (len(x) + len(y)) if x and y else 0.0

def _fams(ws):
    out = set()
    for w in ws:
        out |= _W2F.get(w, set())
    return out

def judging_function(ingredient, usda_match):
    try:
        ing = re.sub(r"\([^)]*\)", " ", str(ingredient or "").lower())
        ing = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)\b", " ", ing)
        usd = re.sub(r"\([^)]*\)", " ", str(usda_match or "").lower())
        ing_words = [w for w in _words(ing.split(",")[0]) if w not in _NOISE]
        segs = [s for s in usd.split(",") if s.strip()]
        if not ing_words or not segs:
            return 0.0
        usd_words = []
        for s in segs[:3]:
            usd_words += [w for w in _words(s) if w not in _NOISE]
        if not usd_words:
            return 0.0

        # best fuzzy alignment of the ingredient head noun against any USDA word
        head = ing_words[-1]
        best = 0.0
        for k, w in enumerate(usd_words):
            d = _dice(head, w)
            pos = 1.0 if k < 2 else 0.8
            best = max(best, d * pos)
        # family agreement
        fi, fu = _fams(ing_words), _fams(usd_words)
        if fi and fu:
            fam = 1.0 if (fi & fu) else 0.15
        else:
            fam = 0.6
        # secondary content words: harmonic agreement
        sec = ing_words[:-1]
        if sec:
            hit = sum(1 for w in sec if any(_dice(w, u) > 0.75 for u in usd_words))
            sec_score = hit / float(len(sec))
        else:
            sec_score = 1.0
        # reverse: USDA primary-segment words unexplained by ingredient
        prim = [w for w in _words(segs[0]) if w not in _NOISE]
        unexpl = [w for w in prim if not any(_dice(w, i) > 0.75 for i in ing_words)]
        pen = 1.0 / (1.0 + 0.5 * len(unexpl)) if prim else 1.0
        # geometric-style combine
        score = 100.0 * (best ** 1.5) * fam * (0.6 + 0.4 * sec_score) * (0.5 + 0.5 * pen)
        return max(0.0, min(100.0, score))
    except Exception:
        return 0.0
