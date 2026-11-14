import re

NOTES = {"optional", "taste", "garnish", "serving", "serve", "needed", "divided", "from",
         "tube", "about", "approximately", "fresh", "large", "small", "medium", "whole",
         "of", "the", "a", "an", "and", "or", "for", "to", "with", "in", "into", "g", "kg",
         "ml", "oz", "lb", "cup", "cups", "tbsp", "tsp", "piece", "pieces", "style", "type",
         "extra", "good", "quality", "brand", "inch", "without", "no", "plus", "more", "such"}
PREP = {"chopped", "diced", "sliced", "minced", "cubed", "crumbled", "grated", "shredded",
        "thawed", "peeled", "crushed", "halved", "quartered", "trimmed", "softened", "melted",
        "mixed", "ripe", "drained", "rinsed", "washed", "cut", "finely", "roughly", "thinly"}
STATE = {"raw", "cooked", "frozen", "canned", "dried", "dry", "smoked", "fried", "boiled",
         "roasted", "baked", "pickled", "salted", "unsalted", "sweetened", "unsweetened",
         "ground", "powder", "powdered", "lowfat", "nonfat", "fat", "reduced", "low", "free",
         "plain", "flavored", "instant", "refined", "organic", "cured", "grilled", "steamed",
         "fresh", "juice", "paste", "sauce"}
STATE_PAIRS = [("raw", "cooked"), ("raw", "fried"), ("raw", "boiled"), ("raw", "roasted"),
               ("frozen", "canned"), ("dried", "raw"), ("sweetened", "unsweetened"),
               ("salted", "unsalted"), ("smoked", "raw")]
SYN = {"wrap": "tortilla", "granada": "pomegranate", "veggie": "vegetable", "veggies": "vegetable",
       "kidneys": "kidney", "cream": "cream", "shrimp": "shrimp", "prawn": "shrimp",
       "scallion": "onion", "aubergine": "eggplant", "courgette": "zucchini",
       "coriander": "cilantro", "garbanzo": "chickpea", "chickpeas": "chickpea"}


def _stem(w):
    w = SYN.get(w, w)
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ses", "s"), ("es", "e"), ("s", "")):
        if len(w) > 3 and w.endswith(suf) and not w.endswith("ss"):
            w = w[:-len(suf)] + rep
            break
    return SYN.get(w, w)


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        # split into segments with role weights
        parens = re.findall(r"\(([^)]*)\)", ing)
        ing_np = re.sub(r"\([^)]*\)", " ", ing)
        parts = ing_np.split(",")
        main = parts[0]
        post = " ".join(parts[1:])
        weighted = {}  # token -> weight
        mt = [t for t in _toks(main) if t not in NOTES]
        n = len(mt)
        for i, t in enumerate(mt):
            if t in PREP:
                w = 0.2
            elif i == n - 1:
                w = 3.0  # head noun usually last
            elif t in STATE:
                w = 1.5
            else:
                w = 2.0
            weighted[t] = max(weighted.get(t, 0), w)
        for seg, base in ((post, 0.8), (" ".join(parens), 0.8)):
            for t in _toks(seg):
                if t in NOTES or t in PREP:
                    continue
                weighted[t] = max(weighted.get(t, 0), base * (1.5 if t in STATE else 1.0))
        # drop notes in parens like 'optional'
        if not weighted:
            return 0.0
        ut_all = _toks(usda)
        uset = set(ut_all)
        usda_parts = usda.split(",")
        uprim = set(_toks(usda_parts[0])) - NOTES
        uprim_full = [t for t in _toks(usda_parts[0]) if t not in NOTES]

        total = sum(weighted.values())
        covered = sum(w for t, w in weighted.items() if t in uset)
        # partial credit by shared prefix
        for t, w in weighted.items():
            if t not in uset and len(t) >= 5:
                if any(len(u) >= 5 and (u[:5] == t[:5]) for u in uset):
                    covered += 0.5 * w
        cov = covered / total

        score = 10.0 * cov

        # head noun missing: heavy penalty
        head = mt[-1] if mt else None
        if head and head not in uset and head not in PREP:
            if not any(len(u) >= 5 and len(head) >= 5 and u[:5] == head[:5] for u in uset):
                score -= 3.0

        # USDA primary food terms that the ingredient does not mention: unaccounted extras
        itoks = set(weighted)
        extra = [t for t in uprim_full if t not in itoks and t not in STATE]
        score -= 1.2 * min(len(extra), 3)
        # extra USDA descriptors that add material qualifiers not in ingredient
        extra_desc = 0
        for t in set(ut_all):
            if t in ("vegetable", "meat", "flavored", "sweetened", "smoked", "fried", "frozen",
                     "canned", "dried", "cooked", "vegetables", "lowfat", "nonfat", "reduced") and t not in itoks:
                extra_desc += 1
        score -= 0.6 * min(extra_desc, 3)

        # state contradictions
        for a, b in STATE_PAIRS:
            if (a in itoks and b in uset and a not in uset) or (b in itoks and a in uset and b not in uset):
                score -= 2.0

        # compound ingredient ("X and Y") covered by a single food
        if re.search(r"\b(and|&)\b", ing_np.split(",")[0]):
            score -= 1.5

        # missing 'seed', 'leaf' etc. part words in ingredient but USDA gives whole fruit
        return max(-5.0, min(10.0, score))
    except Exception:
        return 0.0
