import re
import math
from collections import Counter

# Variant 8: character-trigram category profiling.
# Each side is converted into a soft distribution over food categories by
# comparing its character-trigram profile with prototype lexicons; the score is
# derived from the Jensen-Shannon similarity between the two distributions,
# sharpened by agreement of the dominant category and of the head food token.

_CATEGORY_LEXICON = {
    "dairy": "milk cheese yogurt yoghurt cream butter buttermilk kefir curd whey ghee "
             "cheddar mozzarella parmesan ricotta feta brie custard dairy",
    "produce": "apple banana berry orange lemon lime grape peach pear plum mango melon "
               "tomato onion garlic carrot potato pepper lettuce spinach cabbage kale "
               "broccoli cucumber celery squash zucchini mushroom fruit vegetable leek "
               "radish beet avocado cherry pineapple eggplant",
    "meat": "beef pork lamb veal chicken turkey duck goose poultry broiler fryer bacon "
            "ham sausage salami cervelat steak chop loin shank rib brisket mince "
            "venison bison liver meat skin breast thigh wing drumstick",
    "seafood": "fish salmon tuna cod whiting haddock trout tilapia shrimp prawn crab "
               "lobster clam mussel oyster scallop squid octopus anchovy sardine fillet",
    "grain": "flour wheat rice oat oats barley corn maize rye bread pasta noodle cereal "
             "amaranth quinoa millet couscous semolina bran cracker tortilla",
    "legume": "bean beans lentil lentils chickpea pea peas soy soybean tofu tempeh "
              "edamame peanut legume hummus",
    "nut_seed": "almond walnut cashew pecan hazelnut pistachio macadamia seed seeds "
                "sesame sunflower pumpkin chia flax coconut nut nuts",
    "spice_herb": "spice spices ginger cinnamon cumin paprika turmeric oregano basil "
                  "thyme rosemary parsley cilantro coriander nutmeg clove pepper ground "
                  "dried herb herbs vanilla cardamom saffron mint dill",
    "oil_fat": "oil oils olive canola vegetable avocado sunflower shortening lard "
               "margarine fat tallow",
    "sweetener": "sugar honey syrup molasses maple agave sweetener stevia carob "
                 "chocolate cocoa candy jam jelly",
    "condiment": "sauce ketchup mustard mayonnaise vinegar soy salsa dressing relish "
                 "paste broth stock gravy marinade",
}

_STOP = set("g kg mg ml l oz lb cup cups tbsp tsp and or with of the a an in to for "
            "from raw cooked fresh frozen thawed chopped sliced diced minced trimmed "
            "large small medium nfs ns imported style plain".split())


def _trigrams(word):
    w = "^" + word + "$"
    if len(w) < 3:
        return [w]
    return [w[i:i + 3] for i in range(len(w) - 2)]


def _profile(words, weights=None):
    c = Counter()
    for idx, w in enumerate(words):
        wt = 1.0 if weights is None else weights[idx]
        for t in _trigrams(w):
            c[t] += wt
    return c


def _cos(a, b):
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


_PROTO = {}
_PROTO_WORDS = {}
for _cat, _txt in _CATEGORY_LEXICON.items():
    _ws = _txt.split()
    _PROTO_WORDS[_cat] = set(_ws)


def _clean(text, is_usda):
    s = str(text or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)?\b", " ", s)
    if not is_usda and "," in s:
        s = s.split(",")[0]
    return s


def _tokens(s):
    toks = re.findall(r"[a-z]+", s)
    out = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("es") and t[:-2] in _ALL_WORDS:
            t = t[:-2]
        elif len(t) > 3 and t.endswith("s") and t[:-1] in _ALL_WORDS:
            t = t[:-1]
        out.append(t)
    return out


_ALL_WORDS = set()
for _ws in _PROTO_WORDS.values():
    _ALL_WORDS |= _ws


def _word_category_scores(word):
    # best trigram cosine of word against each category's lexicon words
    prof = _profile([word])
    res = {}
    for cat, ws in _PROTO_WORDS.items():
        if word in ws:
            res[cat] = 1.0
            continue
        best = 0.0
        for lw in ws:
            if abs(len(lw) - len(word)) > 4:
                continue
            c = _cos(prof, _profile([lw]))
            if c > best:
                best = c
        res[cat] = best if best >= 0.55 else 0.0
    return res


def _distribution(tokens, is_usda):
    n = len(tokens)
    if n == 0:
        return None
    mass = {c: 0.0 for c in _PROTO_WORDS}
    for i, tok in enumerate(tokens):
        if is_usda:
            # primary food first: decay by position
            w = 1.0 / (1.0 + 0.6 * i)
        else:
            # head noun usually last in recipe text
            w = 1.0 / (1.0 + 0.6 * (n - 1 - i))
        sc = _word_category_scores(tok)
        for c, v in sc.items():
            mass[c] += w * (v ** 2)
    total = sum(mass.values())
    if total <= 1e-9:
        return None
    return {c: v / total for c, v in mass.items()}


def _js_similarity(p, q):
    keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a, b):
        s = 0.0
        for k in keys:
            av = a.get(k, 0.0)
            if av > 0 and b[k] > 0:
                s += av * math.log(av / b[k], 2)
        return s

    js = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    return max(0.0, 1.0 - js)


def _argmax(d):
    return max(d.items(), key=lambda kv: kv[1])[0]


def judging_function(ingredient, usda_match):
    try:
        ing_s = _clean(ingredient, False)
        usd_s = _clean(usda_match, True)
        ing_t = _tokens(ing_s)
        usd_t = _tokens(usd_s)
        if not ing_t or not usd_t:
            return 0.0

        p = _distribution(ing_t, False)
        q = _distribution(usd_t, True)

        # Head-token agreement (primary USDA food vs any ingredient token, trigram-fuzzy)
        primary = usd_t[0]
        head_sim = 0.0
        prim_prof = _profile([primary])
        for t in ing_t:
            head_sim = max(head_sim, _cos(prim_prof, _profile([t])))

        if p is None or q is None:
            # no category evidence: fall back to lexical overlap only
            return round(2.0 + 4.0 * head_sim, 3)

        sim = _js_similarity(p, q)
        same_top = _argmax(p) == _argmax(q)
        conf = min(max(p.values()), max(q.values()))

        score = 10.0 * sim ** 2
        if same_top:
            score += 2.0 + 1.5 * conf
        else:
            score -= 3.0 * conf
        score += 2.5 * head_sim

        # Ingredient words that the USDA side does not cover at all hint that the
        # ingredient is a composite or a different subtype within the category.
        usd_prof = _profile(usd_t)
        uncovered = 0
        for t in ing_t:
            if _cos(_profile([t]), usd_prof) < 0.2:
                uncovered += 1
        score -= 0.8 * uncovered

        return round(max(0.0, min(16.0, score)), 3)
    except Exception:
        return 0.0
