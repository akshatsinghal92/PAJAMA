import re
import math

# alias -> canonical food id (family lexicon)
_FAM = {
    "chickpea": ["chickpea", "chickpeas", "garbanzo", "garbanzos"],
    "eggplant": ["eggplant", "aubergine", "brinjal"],
    "zucchini": ["zucchini", "courgette"],
    "scallion": ["scallion", "scallions", "spring onion", "green onion"],
    "flax": ["flaxseed", "flaxseeds", "linseed", "linseeds", "flax"],
    "corn": ["corn", "maize", "sweetcorn"],
    "pinenut": ["pine nut", "pine nuts", "pinyon", "pignolia"],
    "cilantro": ["cilantro", "coriander leaf", "coriander leaves"],
    "arugula": ["arugula", "rocket"],
    "bellpepper": ["bell pepper", "capsicum", "sweet pepper"],
    "shrimp": ["shrimp", "prawn", "prawns"],
    "beet": ["beet", "beets", "beetroot"],
    "hazelnut": ["hazelnut", "hazelnuts", "filbert", "filberts"],
    "yogurt": ["yogurt", "yoghurt", "yogurts"],
    "lox": ["lox", "smoked salmon"],
    "cornstarch": ["cornstarch", "cornflour", "corn starch"],
    "powsugar": ["powdered sugar", "icing sugar", "confectioners sugar"],
    "bakingsoda": ["baking soda", "bicarbonate of soda", "sodium bicarbonate"],
    "cookie": ["cookie", "cookies", "biscuit", "biscuits"],
    "fries": ["french fries", "fries", "chips"],
    "potato": ["potato", "potatoes"],
    "tomato": ["tomato", "tomatoes"],
    "peanut": ["peanut", "peanuts", "groundnut"],
    "grape": ["grape", "grapes"],
    "radish": ["radish", "radishes"],
}
_A2F = {}
for _f, _l in _FAM.items():
    for _a in _l:
        _A2F[_a] = _f
_PHR = sorted([a for a in _A2F if " " in a], key=lambda x: -len(x))

_NOISE = set("""a an the of and or with without in on for to from fresh large small medium optional garnish
thawed peeled chopped sliced diced minced grated shredded crushed finely roughly pieces piece slices slice cut
g kg ml oz lb cup cups tbsp tsp style prepared ready about each more taste whole""".split())
_STATE = set("raw cooked fried baked boiled dried dry frozen canned toasted roasted smoked braised steamed pickled powder ground".split())
# words that define a different product when they differ
_CLASS = set("""oil cheese yogurt milk butter sugar vinegar bread flour tea cereal seaweed beef pork chicken lamb
turkey fish salmon cream sauce dressing juice egg rice pasta cake soup wine beer souffle soymilk bone liver heart
kefir ball patty avocado coconut peanut cashew almond walnut pecan balsamic brown white red green black""".split())


def _toks(s):
    s = s.lower()
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb|l)\b", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    s = " " + re.sub(r"\s+", " ", s).strip() + " "
    for p in _PHR:
        s = s.replace(" " + p + " ", " " + _A2F[p] + " ")
    out = []
    for w in s.split():
        if w in _A2F:
            w = _A2F[w]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def _grams(w, n=3):
    w = "^" + w + "$"
    return set(w[i:i + n] for i in range(max(1, len(w) - n + 1)))


def _wsim(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    d = 2.0 * len(ga & gb) / float(len(ga) + len(gb))
    return d if d >= 0.6 else 0.0


def _best(w, pool):
    return max([_wsim(w, p) for p in pool] or [0.0])


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        if not ing.strip() or not usda.strip():
            return 0.0
        core = ing.split(",")[0]
        it = [w for w in _toks(core) if w not in _NOISE and len(w) > 1]
        ist = set(_toks(ing)) & _STATE
        segs = usda.split(",")
        ut_primary = [w for w in _toks(segs[0]) if w not in _NOISE and len(w) > 1]
        ut_rest = [w for w in _toks(" ".join(segs[1:])) if w not in _NOISE and len(w) > 1]
        if not it or not (ut_primary or ut_rest):
            return 0.0
        ut_all = ut_primary + ut_rest
        ust = set(ut_all) & _STATE
        it_c = [w for w in it if w not in _STATE]
        ut_c = [w for w in ut_all if w not in _STATE]
        if not it_c or not ut_c:
            return 1.0
        # soft alignment both directions (harmonic mean = symmetric F)
        rec = sum(_best(w, ut_c) for w in it_c) / float(len(it_c))
        prec_w = [(2.0 if w in ut_primary else 1.0) for w in ut_c]
        prec = sum(pw * _best(w, it_c) for pw, w in zip(prec_w, ut_c)) / sum(prec_w)
        f = 0.0 if rec + prec == 0 else 2 * rec * prec / (rec + prec)
        # same-food gate: does the ingredient's head resolve to something in the USDA primary?
        head = it_c[-1]
        gate = 1.0
        gpool = ut_primary + [w for w in _toks(segs[1] if len(segs) > 1 else "") if w not in _NOISE and len(w) > 1]
        if gpool:
            pm = max(_best(head, gpool), max(_best(w, gpool) for w in it_c))
            gate = 0.35 + 0.65 * pm
        # class conflicts
        ci = set(w for w in it_c if w in _CLASS)
        cu = set(w for w in ut_c if w in _CLASS)
        miss = len(cu - ci) + len(ci - cu)
        conf = math.exp(-0.45 * miss)
        # state agreement
        sm = 1.0
        if ist and ust and not (ist & ust):
            sm = 0.8
        score = 10.0 * f * gate * conf * sm
        return round(score, 3)
    except Exception:
        return 0.0
