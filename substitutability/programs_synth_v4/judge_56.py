import re
import math


# Polarity ledger approach: each side is converted into a dict mapping an
# attribute "root" to a signed polarity (+1 present / -1 negated).  Two sources
# feed the ledger: (a) a curated table of attribute axes with explicit
# positive/negative surface forms, and (b) a generic negation-scope parser that
# catches "no X", "without X", "X-free", "un-X", "non-X" against "with X",
# "X added", plain "X".  Contradictions are aggregated with a soft-OR
# (probabilistic union) instead of a sum, and agreements give a small bonus.

_AXES = {
    # root: (weight, negative patterns, positive patterns)
    "salt": (1.0,
             [r"\bunsalted\b", r"\bno salt\b", r"\bsalt[- ]free\b", r"\bwithout salt\b",
              r"\bno added salt\b", r"\bsodium[- ]free\b", r"\bno sodium\b"],
             [r"\bsalted\b", r"\bwith salt\b", r"\bsalt added\b", r"\badded salt\b"]),
    "sugar": (1.0,
              [r"\bunsweetened\b", r"\bno sugar\b", r"\bsugar[- ]free\b", r"\bwithout sugar\b",
               r"\bno added sugar\b", r"\bsugarless\b"],
              [r"\bsweetened\b", r"\bwith sugar\b", r"\bsugar added\b", r"\badded sugar\b",
               r"\bheavy syrup\b", r"\blight syrup\b", r"\bsyrup pack\b"]),
    "fat_added": (0.9,
                  [r"\bno (?:added )?fat\b", r"\bwithout (?:added )?fat\b", r"\bfat not added\b",
                   r"\bfat[- ]free\b", r"\bnonfat\b", r"\bnon[- ]fat\b"],
                  [r"\bfat added\b", r"\bwith (?:added )?fat\b", r"\bwith butter\b",
                   r"\bwith oil\b", r"\bwith margarine\b"]),
    "skin": (1.0,
             [r"\bskinless\b", r"\bwithout skin\b", r"\bno skin\b", r"\bskin removed\b",
              r"\bmeat only\b", r"\bpeeled\b"],
             [r"\bwith skin\b", r"\bskin[- ]on\b", r"\bskin only\b", r"\bmeat and skin\b",
              r"\bunpeeled\b", r"\bnot peeled\b"]),
    "bone": (1.0,
             [r"\bboneless\b", r"\bdeboned\b", r"\bbone removed\b", r"\bwithout bones?\b",
              r"\bno bones?\b", r"\bfillets?\b"],
             [r"\bbone[- ]in\b", r"\bwith bones?\b", r"\bon the bone\b", r"\bbones? included\b"]),
    "hull": (0.9,
             [r"\bhulled\b", r"\bshelled\b", r"\bdehulled\b", r"\bkernels?\b"],
             [r"\bunhulled\b", r"\bin shell\b", r"\bin[- ]shell\b", r"\bwith hulls?\b",
              r"\bunshelled\b"]),
    "seed": (0.9,
             [r"\bseedless\b", r"\bseeded\b(?! bread| rye| bun)", r"\bwithout seeds\b",
              r"\bno seeds\b", r"\bpitted\b"],
             [r"\bwith seeds\b", r"\bseeds? included\b", r"\bunpitted\b", r"\bwith pits?\b"]),
    "caffeine": (1.0,
                 [r"\bdecaf(?:feinated)?\b", r"\bcaffeine[- ]free\b", r"\bno caffeine\b",
                  r"\bwithout caffeine\b"],
                 [r"\bcaffeinated\b", r"\bwith caffeine\b", r"\bregular\b(?= coffee| tea| cola)"]),
    "alcohol": (0.9,
                [r"\bnon[- ]?alcoholic\b", r"\balcohol[- ]free\b", r"\bdealcoholized\b"],
                [r"\balcoholic\b", r"\bwith alcohol\b"]),
    "gluten": (0.6,
               [r"\bgluten[- ]free\b", r"\bwithout gluten\b"],
               [r"\bwith gluten\b", r"\bvital wheat gluten\b"]),
    "lactose": (0.6,
                [r"\blactose[- ]free\b", r"\blactose reduced\b"],
                [r"\bwith lactose\b"]),
    "cook": (0.7,
             [r"\braw\b", r"\buncooked\b", r"\bunbaked\b", r"\bfresh\b(?! frozen)"],
             [r"\bcooked\b", r"\bbaked\b", r"\broasted\b", r"\bfried\b", r"\bboiled\b",
              r"\bgrilled\b", r"\bbraised\b", r"\bsteamed\b", r"\btoasted\b", r"\bdry heat\b",
              r"\bpan[- ]fried\b", r"\bbroiled\b", r"\bstewed\b"]),
    "drain": (0.5,
              [r"\bundrained\b", r"\bwith liquid\b", r"\bsolids and liquids?\b"],
              [r"\bdrained\b", r"\bdrained solids\b"]),
    "bleach": (0.4,
               [r"\bunbleached\b"],
               [r"\bbleached\b"]),
    "enrich": (0.3,
               [r"\bunenriched\b"],
               [r"\benriched\b"]),
    "cure": (0.5,
             [r"\buncured\b", r"\bunsmoked\b"],
             [r"\bcured\b", r"\bsmoked\b"]),
    "sweet_type": (0.6,
                   [r"\bdry\b(?= wine| sherry| vermouth)", r"\bsavory\b", r"\bsavoury\b"],
                   [r"\bsweet\b"]),
}

_COMPILED = {}
for _root, (_w, _neg, _pos) in _AXES.items():
    _COMPILED[_root] = (_w, [re.compile(p) for p in _neg], [re.compile(p) for p in _pos])

_GENERIC_NEG = [
    (re.compile(r"\b(?:no|without|minus|zero)\s+(?:added\s+)?([a-z]{3,})"), -1),
    (re.compile(r"\b([a-z]{3,})[- ]free\b"), -1),
    (re.compile(r"\b([a-z]{3,})less\b"), -1),
    (re.compile(r"\bnon[- ]?([a-z]{3,})\b"), -1),
    (re.compile(r"\bwith\s+(?:added\s+)?([a-z]{3,})"), 1),
    (re.compile(r"\b([a-z]{3,})\s+added\b"), 1),
    (re.compile(r"\badded\s+([a-z]{3,})"), 1),
]

_GENERIC_STOP = {"the", "and", "fat", "salt", "sugar", "skin", "bone", "bones", "seed",
                 "seeds", "caffeine", "alcohol", "gluten", "lactose", "vitamin", "less",
                 "more", "regular", "unless", "dressing", "liquid", "water", "added",
                 "blend", "species", "type", "grades"}


def _clean(text):
    try:
        t = str(text or "").lower()
    except Exception:
        return ""
    t = re.sub(r"^\s*[\d.,/]+\s*(?:g|grams?|kg|ml|l|oz|lb|lbs|cups?|tbsp|tsp)?\b", " ", t)
    t = t.replace("(", " ( ").replace(")", " ) ")
    t = re.sub(r"[^a-z0-9%\-/ ()']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip_word(word):
    w = word
    for suf in ("ness", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _ledger(text):
    led = {}
    weights = {}
    for root, (w, negs, poss) in _COMPILED.items():
        neg_hits = sum(1 for p in negs if p.search(text))
        pos_hits = sum(1 for p in poss if p.search(text))
        # "unhulled" contains "hulled" etc. -- resolve via precedence of
        # longer/explicit forms: if both fire, use the stronger count, ties -> skip
        if neg_hits and pos_hits:
            if root == "hull" and re.search(r"\bunhulled\b|\bunshelled\b", text):
                led[root] = 1
            elif neg_hits > pos_hits:
                led[root] = -1
            elif pos_hits > neg_hits:
                led[root] = 1
            else:
                continue
        elif neg_hits:
            led[root] = -1
        elif pos_hits:
            led[root] = 1
        else:
            continue
        weights[root] = w
    for rx, sign in _GENERIC_NEG:
        for m in rx.finditer(text):
            word = m.group(1)
            if word in _GENERIC_STOP:
                continue
            key = "g:" + _strip_word(word)
            if key in led and led[key] != sign:
                led.pop(key, None)
                weights.pop(key, None)
                continue
            led[key] = sign
            weights[key] = 0.5
    # un-prefixed adjectives as negation of their base form
    for m in re.finditer(r"\bun([a-z]{4,}ed)\b", text):
        base = m.group(1)
        key = "u:" + _strip_word(base)
        led[key] = -1
        weights[key] = 0.6
    for m in re.finditer(r"\b([a-z]{4,}ed)\b", text):
        base = m.group(1)
        if text[max(0, m.start() - 2):m.start()] == "un":
            continue
        key = "u:" + _strip_word(base)
        if key not in led:
            led.setdefault("pending:" + key, 1)
    return led, weights


def _resolve_pending(led_a, led_b):
    # A bare "salted"/"peeled" only counts as positive when the other side
    # carries the negated "un-" form; otherwise it is ignored.
    out_a = {k: v for k, v in led_a.items() if not k.startswith("pending:")}
    out_b = {k: v for k, v in led_b.items() if not k.startswith("pending:")}
    for k in led_a:
        if k.startswith("pending:") and k[8:] in out_b:
            out_a[k[8:]] = 1
    for k in led_b:
        if k.startswith("pending:") and k[8:] in out_a:
            out_b[k[8:]] = 1
    return out_a, out_b


def _head_affinity(a, b):
    # weak topical anchor so unrelated pairs are not identical to related ones
    def grams(s):
        s = re.sub(r"\([^)]*\)", " ", s)
        s = re.sub(r"[^a-z ]", " ", s)
        words = [w for w in s.split() if len(w) > 2]
        g = set()
        for w in words:
            w = "#" + w[:7] + "#"
            for i in range(len(w) - 2):
                g.add(w[i:i + 3])
        return g
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / math.sqrt(len(ga) * len(gb))


def judging_function(ingredient, usda_match):
    try:
        a = _clean(ingredient)
        b = _clean(usda_match)
        if not a or not b:
            return 0.0

        led_a, w_a = _ledger(a)
        led_b, w_b = _ledger(b)
        led_a, led_b = _resolve_pending(led_a, led_b)

        conflict_union = 0.0  # soft-OR of contradiction probabilities
        agree_mass = 0.0
        conflicts = 0
        for key in set(led_a) & set(led_b):
            w = max(w_a.get(key, 0.6), w_b.get(key, 0.6))
            if led_a[key] != led_b[key]:
                conflicts += 1
                conflict_union = 1.0 - (1.0 - conflict_union) * (1.0 - 0.85 * w)
            else:
                agree_mass += w

        affinity = _head_affinity(a, b)  # 0..1

        # base: neutral 55, shifted by topical affinity (+/-15)
        score = 55.0 + 30.0 * (affinity - 0.5)
        # agreement bonus with diminishing returns
        score += 12.0 * (1.0 - math.exp(-agree_mass))
        # contradiction penalty: multiplicative collapse
        score *= (1.0 - 0.8 * conflict_union)
        if conflicts >= 2:
            score -= 5.0 * (conflicts - 1)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
