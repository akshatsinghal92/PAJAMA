import re
import math

_STOP = {"optional", "taste", "garnish", "for", "to", "of", "the", "a", "an", "and", "or", "with", "from",
         "in", "g", "tube", "large", "small", "medium", "about", "nfs", "all", "varieties", "type", "made",
         "style", "chopped", "sliced", "diced", "minced", "thawed", "melted", "softened", "crushed",
         "grated", "shelled", "warmed", "fresh", "pieces", "piece", "salad", "cooking"}


def _norm(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", lambda m: " " + m.group(0)[1:-1] + " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|oz|ml|lb|lbs)\b", " ", s)
    s = re.sub(r"[^a-z ,]", " ", s)
    return s


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _grams(w, n=3):
    w = "#" + w + "#"
    return {w[i:i + n] for i in range(max(len(w) - n + 1, 1))}


def _tokset(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s) if w not in _STOP]


def _soft_match(t, pool):
    """best character-trigram Dice between token t and any word in pool"""
    best = 0.0
    gt = _grams(t)
    for u in pool:
        gu = _grams(u)
        d = 2.0 * len(gt & gu) / (len(gt) + len(gu))
        if d > best:
            best = d
    return best


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        ing_main = ing.split(",")[0]
        ing_rest = " ".join(ing.split(",")[1:])
        u_parts = [p for p in usd.split(",")]
        u_main = _tokset(u_parts[0]) if u_parts else []
        u_all = _tokset(usd)
        i_main = _tokset(ing_main)
        i_rest = _tokset(ing_rest)
        if not i_main or not u_all:
            return 0.0
        # main-phrase: how well do the ingredient words get explained (soft) by usda words
        def cover(tokens, pool):
            if not tokens:
                return 1.0
            vals = []
            for t in tokens:
                if t in pool:
                    vals.append(1.0)
                else:
                    s = _soft_match(t, pool)
                    vals.append(s if s >= 0.6 else 0.0)
            return sum(vals) / len(vals)

        c_main = cover(i_main, set(u_all))
        c_rest = cover(i_rest, set(u_all)) if i_rest else 1.0
        # reverse: how much of USDA headline is explained by the ingredient (precision)
        ip = set(i_main + i_rest)
        p_head = cover(u_main, ip) if u_main else 0.0
        # headline noun: last word of the ingredient main phrase should be present in usda headline
        last = i_main[-1]
        head_ok = 1.0 if last in set(u_all) else (0.5 if _soft_match(last, set(u_all)) > 0.75 else 0.0)
        first_ok = 1.0 if (u_main and u_main[0] in set(i_main + i_rest)) else 0.0
        # logistic-ish combination in log-odds space
        z = -3.0 + 2.5 * c_main + 1.0 * c_rest + 1.8 * p_head + 1.2 * head_ok + 0.8 * first_ok
        # material qualifier conflicts
        iset = set(i_main + i_rest)
        uset = set(u_all)
        conflicts = [
            ({"dried", "dry", "dehydrated"}, {"raw", "fresh", "frozen"}),
            ({"frozen"}, {"canned"}), ({"canned"}, {"frozen", "raw"}),
            ({"unsalted"}, {"salted"}), ({"salted"}, {"unsalted"}),
            ({"roasted"}, {"raw"}), ({"raw"}, {"cooked", "roasted"}),
            ({"cooked"}, {"raw"}), ({"sweetened"}, {"unsweetened"}),
            ({"smoked"}, {"raw"}), ({"fermented", "pickled"}, {"raw"}),
        ]
        for a, b in conflicts:
            if iset & a and uset & b and not (uset & a):
                z -= 1.2
        # USDA has diet/modified qualifiers the recipe doesn't mention
        mods = {"free", "low", "reduced", "nonfat", "lowfat", "imitation", "substitute", "flavored", "sweetened", "dried", "dehydrated", "canned", "powder"}
        for m in mods:
            if m in uset and m not in iset:
                z -= 0.7
        # extra descriptors beyond headline: mild length penalty
        extra = len([t for t in u_all if t not in iset])
        z -= 0.15 * math.log(1 + extra)
        return 100.0 / (1.0 + math.exp(-z))
    except Exception:
        return 0.0
