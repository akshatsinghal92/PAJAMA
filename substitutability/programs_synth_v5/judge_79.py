import re
import math

_NOISE = set("""fresh frozen thawed chopped sliced diced minced cubed grated shredded crushed cooked raw drained
rinsed peeled cold hot warm toasted roasted large small medium whole boneless skinless organic canned dried
baked boiled steamed melted softened garnish taste for the of or without a an to from plain extra finely
thinly foraged crispy flaked segments pieces regular g kg oz lb ml tsp tbsp cup not nfs ns""".split())
_CATEGORY = set("""nuts fish cereal cereals spices beverages candies snacks sauce sauces soup soups oil oils
fruit fruits vegetables vegetable meat meats seeds cheese bread crackers cookies cake""".split())
_SYN = {"maize": "corn", "poultry": "chicken", "clementine": "tangerine", "mandarin": "tangerine",
        "capsicum": "pepper", "prawn": "shrimp", "aubergine": "eggplant", "scallion": "onion"}


def _key(w):
    w = _SYN.get(w, w)
    return w[:5] if len(w) > 5 else (w[:-1] if len(w) > 3 and w.endswith("s") else w)


def _clean(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    s = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\b", " ", s)
    return s


def _seq(s):
    return [_key(t) for t in re.findall(r"[a-z]+", s) if t not in _NOISE]


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean(str(ingredient)).split(",")[0]
        usda_raw = _clean(str(usda_match))
        segs = [x for x in usda_raw.split(",")]
        iseq = _seq(ing)
        useq_all = _seq(usda_raw)
        if not iseq or not useq_all:
            return 0.0

        uset = set(useq_all)
        # -- head: last content word of the ingredient phrase (the food noun)
        head = iseq[-1]
        head_hit = head in uset
        # position of head in USDA: primary segment (strong) vs descriptor (weak)
        prim = set(_seq(segs[0]))
        head_w = 1.0 if head in prim else (0.7 if head_hit else 0.0)

        # -- modifiers: all words before head; each must survive
        mods = iseq[:-1]
        if mods:
            kept = sum(1 for m in mods if m in uset)
            mod_w = kept / float(len(mods))
        else:
            mod_w = 1.0

        # -- additions: USDA primary-segment words that are neither in ingredient nor category labels
        iset = set(iseq)
        added = [w for w in _seq(segs[0]) if w not in iset and w not in {_key(c) for c in _CATEGORY}]
        add_w = math.exp(-0.9 * len(added))

        # -- trailing extra foods ("X and Y") not mentioned in ingredient
        raw_i = ing
        i_multi = bool(re.search(r"\b(and|with)\b", raw_i))
        u_multi = bool(re.search(r"\b(and|with)\b", usda_raw))
        multi_w = 1.0 if i_multi == u_multi else 0.45

        # -- descriptor bloat: descriptors in USDA beyond ingredient, mild
        extra = [w for w in useq_all if w not in iset]
        bloat_w = 1.0 / (1.0 + 0.08 * len(extra))

        # multiplicative blend: any hard failure drags the score
        score = 10.0 * (0.15 + 0.85 * head_w) * (0.25 + 0.75 * mod_w) * (0.4 + 0.6 * add_w) \
            * multi_w * (0.6 + 0.4 * bloat_w)
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
