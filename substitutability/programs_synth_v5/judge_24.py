import re
import math

_NOISE = set("""g kg mg oz lb lbs ml l cup cups tbsp tsp tablespoon teaspoon piece pieces slice sliced
diced chopped minced grated shredded crushed fresh freshly large small medium thin thick fine finely roughly
to taste from tube optional of the a an and or with for in into cut halved quartered peeled thawed drained
rinsed divided softened melted packed whole inch nfs raw ready bake fry""".split())

_PREP_STRIP = set("sliced diced chopped minced grated shredded crushed thawed drained peeled".split())

def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ches", "shes", "oes", "sses")):
                return w[:-1]
            if suf == "es":
                return w[:-2]
            if w.endswith("ss"):
                return w
            return w[:-1]
    return w

def _tokens(text, drop_noise=True):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|lbs|ml|l)\b", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\b(?!%)", " ", text)
    words = re.findall(r"[a-z]+|\d+%", text)
    out = []
    for w in words:
        if drop_noise and w in _NOISE:
            continue
        out.append(_stem(w))
    return out

def _split_ing(ing):
    s = (ing or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    parts = s.split(",", 1)
    main = parts[0]
    return main

def judging_function(ingredient, usda_match):
    try:
        ing_main = _split_ing(ingredient)
        usda = (usda_match or "").lower()
        usda_parts = [p for p in usda.split(",")]
        ti = _tokens(ing_main)
        tu_all = _tokens(usda)
        if not ti or not tu_all:
            return 0.0
        # primary food segment of USDA (first comma segment) gets the highest weight
        primary = set(_tokens(usda_parts[0]))
        n_u = len(tu_all)
        # position weights for ingredient: later words in a noun phrase are more head-like
        wi = {}
        for k, t in enumerate(ti):
            wi[t] = max(wi.get(t, 0), 1.0 + 0.5 * (k / max(1, len(ti) - 1)) if len(ti) > 1 else 1.5)
        wu = {}
        for k, t in enumerate(tu_all):
            base = 1.5 if t in primary else 0.8
            wu[t] = max(wu.get(t, 0), base)
        # soft match: share prefix of 5+ chars counts as 0.8
        def sim(a, b):
            if a == b:
                return 1.0
            if len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5]:
                return 0.8
            return 0.0
        # weighted recall of ingredient tokens
        rec_num = rec_den = 0.0
        for t, w in wi.items():
            best = max((sim(t, u) for u in wu), default=0.0)
            rec_num += w * best
            rec_den += w
        recall = rec_num / rec_den if rec_den else 0.0
        # weighted precision of USDA tokens
        pre_num = pre_den = 0.0
        for u, w in wu.items():
            best = max((sim(u, t) for t in wi), default=0.0)
            pre_num += w * best
            pre_den += w
        precision = pre_num / pre_den if pre_den else 0.0
        if recall + precision == 0:
            return 0.0
        f = 2 * recall * precision / (recall + precision)
        # ordered bigram bonus (order-insensitive across comma reorder: check adjacency either way)
        bi_i = set(zip(ti, ti[1:]))
        bi_u = set(zip(tu_all, tu_all[1:]))
        bi_u |= set((b, a) for a, b in bi_u)
        bigram = (len(bi_i & bi_u) / len(bi_i)) if bi_i else 0.0
        # head noun: last content token of ingredient should appear in USDA primary or anywhere
        head = ti[-1]
        head_hit = 1.0 if head in primary else (0.6 if head in wu else 0.0)
        # qualifier conflicts: tokens in only one side that are known contrast words
        contrast = [("dark", "light"), ("low", "regular"), ("lean", "fat"), ("vegan", "regular"),
                    ("whole", "skim"), ("sweet", "unsweetened"), ("smoked", "raw"), ("canned", "raw"),
                    ("frozen", "fresh"), ("cooked", "raw")]
        sI, sU = set(ti) | set(_tokens(ingredient, False)), set(tu_all) | set(_tokens(usda_match, False))
        pen = 0.0
        for a, b in contrast:
            if (a in sI and b in sU and a not in sU) or (b in sI and a in sU and b not in sI):
                pen += 0.08
        extra = len([u for u in set(tu_all) if u not in wi and u not in primary])
        extra_pen = 0.03 * min(extra, 5)
        score = 10.0 * (0.5 * f + 0.2 * bigram + 0.3 * head_hit) - 10.0 * (pen + extra_pen)
        # all-ingredient-tokens-covered bonus
        if recall > 0.99:
            score += 1.0
        return max(0.0, round(score, 4))
    except Exception:
        return 0.0
