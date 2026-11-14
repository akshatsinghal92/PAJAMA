import re

_PREP = {"fresh", "chopped", "diced", "sliced", "minced", "cubed", "optional", "thawed", "boneless",
         "skinless", "large", "small", "medium", "whole", "finely", "roughly", "grated", "peeled",
         "crushed", "ripe", "organic", "plain", "pure", "of", "and", "or", "the", "a", "with", "from",
         "to", "taste", "for", "in", "raw", "regular", "g", "kg", "ml", "oz", "lb", "soft", "style"}

_STATE = {"cooked": "cook", "boiled": "cook", "baked": "cook", "roasted": "cook", "fried": "cook",
          "canned": "can", "dried": "dry", "dehydrated": "dry", "frozen": "froz", "smoked": "smok",
          "pickled": "pick", "powder": "powd", "ground": "grnd", "juice": "juic", "nectar": "juic",
          "chips": "chip", "cookies": "cook2", "cookie": "cook2", "candy": "cand", "babyfood": "baby"}

_ROLES = {
    "meat": {"beef", "pork", "chicken", "turkey", "lamb", "veal", "duck", "goat", "venison", "bacon", "ham", "sausage"},
    "fish": {"fish", "salmon", "tuna", "cod", "whitefish", "trout", "shrimp", "crab", "tilapia", "herring", "sardine"},
    "dairy": {"cheese", "milk", "yogurt", "cream", "butter", "yoghurt", "cottage"},
    "nut": {"peanut", "pecan", "almond", "walnut", "cashew", "hazelnut", "pistachio", "macadamia"},
    "starch": {"flour", "starch", "wheat", "rice", "corn", "oat", "barley", "tortilla", "bread", "pasta"},
    "sweet": {"sugar", "syrup", "honey", "molasses", "sweetener"},
    "oil": {"oil", "shortening", "lard", "margarine"},
    "squash": {"squash", "pumpkin", "zucchini", "butternut", "hubbard", "acorn"},
}

_JUNK = {"cookies", "cookie", "chips", "candy", "snack", "snacks", "cereal", "pizza", "soup", "baby", "babyfood", "bar", "bars"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tok(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"\d+(\.\d+)?\s*(g|kg|ml|oz|lb|l|tbsp|tsp|cup|cups)?\b", " ", ing)
        ing_main, _, ing_post = ing.partition(",")
        usda = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", usda)
        parts = [p.strip() for p in usda.split(",")]
        head, rest = parts[0], parts[1:]

        itoks = [t for t in _tok(ing_main) if t not in {_stem(p) for p in _PREP}]
        ipost = _tok(ing_post)
        htoks = _tok(head)
        rtoks = _tok(" ".join(rest))
        if not itoks:
            return 1.0
        utoks_all = set(htoks) | set(rtoks)

        # 1. coverage of ingredient words by the USDA description (head words weigh more)
        cov = 0.0
        for i, t in enumerate(itoks):
            wgt = 2.0 if i == len(itoks) - 1 else 1.0  # last word is the head noun
            if t in htoks:
                cov += wgt
            elif t in utoks_all:
                cov += wgt * 0.7
        tot = sum(2.0 if i == len(itoks) - 1 else 1.0 for i in range(len(itoks)))
        score = 6.0 * cov / tot

        # 2. culinary role: head noun of USDA should share role class with ingredient
        def roles(toks):
            return {r for r, ws in _ROLES.items() if any(_stem(w) in toks for w in ws)}
        ir, hr = roles(set(itoks)), roles(set(htoks))
        if ir and hr:
            if ir & hr:
                score += 1.0
                # same role, but different member of the class (pork vs beef)
                imem = {t for r in ir for t in itoks if t in {_stem(w) for w in _ROLES[r]}}
                umem = {t for r in ir for t in set(htoks) | set(rtoks) if t in {_stem(w) for w in _ROLES[r]}}
                if imem and umem and not (imem & umem):
                    score -= 3.5
            else:
                score -= 3.0

        # 3. extra unrelated words in primary food name (different product)
        extra = [t for t in htoks if t not in itoks and t not in _PREP]
        score -= 0.4 * min(len(extra), 4)
        if set(htoks) & _JUNK and not (set(itoks) & _JUNK):
            score -= 3.0

        # 4. state/behaviour mismatch: texture and prep would change
        def states(toks):
            return {_STATE[t] for t in toks if t in _STATE}
        s_ing = states(itoks) | states(ipost) | states(_tok(" ".join(re.findall(r"[a-z]+", ing))))
        s_usda = states(htoks) | states(rtoks)
        for s in s_usda - s_ing:
            score -= 1.5
        for s in s_ing - s_usda:
            score -= 1.0 if s != "froz" else 0.3
        if "raw" in rtoks and not s_ing:
            score += 0.5

        # 5. long specific cuts / odd descriptors suggest different item
        if len(rest) > 3:
            score -= 0.3 * (len(rest) - 3)

        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
