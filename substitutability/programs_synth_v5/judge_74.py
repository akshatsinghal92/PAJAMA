import re
import math

STOP = set("""a an the and or of for to with in into from optional taste garnish serving serve needed
divided about approximately large small medium whole piece pieces tube style type brand quality good
extra g kg mg ml oz lb cup cups tbsp tsp plus more some few without no inch""".split())
PREPS = set("""chopped diced sliced minced cubed crumbled grated shredded thawed peeled crushed halved
quartered trimmed softened melted mixed ripe drained rinsed washed cut finely roughly thinly
fresh""".split())
ALIAS = {"wrap": "tortilla", "granada": "pomegranate", "veggie": "vegetable", "prawn": "shrimp",
         "aubergine": "eggplant", "courgette": "zucchini", "coriander": "cilantro"}


def _norm(w):
    w = ALIAS.get(w, w)
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("oes"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return ALIAS.get(w, w)


def _words(s):
    return [_norm(w) for w in re.findall(r"[a-z]+", s.lower())]


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4:
        k = 0
        while k < min(len(a), len(b)) and a[k] == b[k]:
            k += 1
        if k >= 4 and k >= 0.75 * min(len(a), len(b)):
            return 0.7
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|ml|oz|lb)?\b", " ", ing)
        if not ing.strip() or not usda.strip():
            return 0.0
        # ingredient: ordered list of content words with a "distance from end of head phrase"
        ing_head = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        extras = " ".join(re.findall(r"\(([^)]*)\)", ing) + re.sub(r"\([^)]*\)", " ", ing).split(",")[1:])
        head_words = [w for w in _words(ing_head) if w not in STOP]
        extra_words = [w for w in _words(extras) if w not in STOP]
        content_head = [w for w in head_words if w not in PREPS] or head_words
        content_extra = [w for w in extra_words if w not in PREPS]
        if not content_head:
            return 0.0

        u_parts = usda.split(",")
        u_first = [w for w in _words(u_parts[0]) if w not in STOP]
        u_rest = [w for w in _words(" ".join(u_parts[1:])) if w not in STOP]
        u_all = u_first + u_rest

        def best(w, pool):
            return max([_sim(w, u) for u in pool] or [0.0])

        # IDF-ish weight: longer, rarer words matter more
        def wt(w):
            return 1.0 + math.log(1 + len(w)) * 0.5

        # (a) head phrase coverage, weights biased to the last word (the noun)
        num = den = 0.0
        L = len(content_head)
        for i, w in enumerate(content_head):
            pos = 1.0 + 1.5 * (i == L - 1)
            c = best(w, u_all)
            num += pos * wt(w) * c
            den += pos * wt(w)
        head_cov = num / den

        # (b) extra qualifier coverage: matched or contradicted
        if content_extra:
            hits = sum(1 for w in content_extra if best(w, u_all) > 0)
            ex_cov = hits / len(content_extra)
        else:
            ex_cov = None

        # (c) reverse: USDA primary food words unexplained by ingredient
        ing_all = content_head + content_extra + [w for w in _words(ing) if w not in STOP]
        unexpl = [w for w in u_first if best(w, ing_all) == 0]
        rev_pen = min(1.0, len(unexpl) / max(1, len(u_first)))

        # (d) USDA qualifiers not in the ingredient (material ones only)
        MAT = {"cooked", "raw", "fried", "frozen", "canned", "dried", "smoked", "sweetened",
               "reduced", "lowfat", "nonfat", "vegetable", "flavored", "baked", "boiled",
               "roasted", "pickled", "kernel", "meat", "imitation", "substitute", "dehydrated"}
        ing_set = set(ing_all)
        mat_extra = [w for w in set(u_rest + u_first) if w in MAT and w not in ing_set]

        # multiplicative combination
        s = head_cov ** 1.5
        if ex_cov is not None:
            s *= 0.55 + 0.45 * ex_cov
        s *= 1.0 - 0.6 * rev_pen
        s *= 0.82 ** min(3, len(mat_extra))
        # explicit contradiction raw vs cooked etc.
        pairs = [("raw", "cooked"), ("raw", "fried"), ("raw", "boiled"), ("frozen", "canned"),
                 ("sweetened", "unsweetened"), ("dried", "raw")]
        for a, b in pairs:
            if (a in ing_set and b in u_all and a not in u_all) or (b in ing_set and a in u_all and b not in u_all):
                s *= 0.6
        # multi-food ingredient squeezed to one USDA food
        if re.search(r"\b(?:and|&)\b", ing_head) and len(content_head) >= 3:
            s *= 0.75
        return round(100.0 * max(0.0, min(1.0, s)), 3)
    except Exception:
        return 0.0
