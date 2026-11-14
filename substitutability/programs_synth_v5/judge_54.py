import re
import math

# Polarity lexicon: attribute -> (set of "absent/negative" cues, set of "present/positive" cues)
_POL = [
    ({"unsalted", "saltfree", "nosalt", "withoutsalt"}, {"salted"}),
    ({"unsweetened", "sugarfree", "nosugar", "withoutsugar"}, {"sweetened", "sugared"}),
    ({"skinless", "noskin", "withoutskin"}, {"skin", "skinon", "withskin"}),
    ({"boneless", "nobone", "withoutbone"}, {"bonein", "bone", "withbone"}),
    ({"seedless", "noseeds", "withoutseeds"}, {"seeds", "seeded", "withseeds"}),
    ({"hulled", "shelled", "dehulled"}, {"unhulled", "unshelled", "inshell"}),
    ({"decaffeinated", "decaf", "caffeinefree"}, {"caffeinated"}),
    ({"nonfat", "fatfree", "skim", "nofat", "lowfat", "reducedfat", "lite", "light"}, {"fullfat"}),
    ({"raw", "uncooked"}, {"cooked", "boiled", "fried", "baked"}),
    ({"drained"}, {"undrained"}),
]


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*[\d.]+\s*(g|kg|ml|oz|lb)?\s+", " ", s)
    s = s.replace("-", "")
    s = re.sub(r"\b(no|non|without)\s+(added\s+)?(\w+)", lambda m: "no" + m.group(3), s)
    s = re.sub(r"\b(\w+)\s+free\b", r"\1free", s)
    s = re.sub(r"\bwith\s+(\w+)", r"with\1", s)
    s = re.sub(r"\breduced\s+fat\b", "reducedfat", s)
    s = re.sub(r"\blow\s+fat\b", "lowfat", s)
    s = re.sub(r"\bfull\s+fat\b", "fullfat", s)
    s = re.sub(r"\bbone\s+in\b", "bonein", s)
    s = re.sub(r"\bin\s+shell\b", "inshell", s)
    s = re.sub(r"\bskin\s+on\b", "skinon", s)
    return s


def _w(s):
    return re.findall(r"[a-z]+", s)


def _sing(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _grams(w, n=3):
    w = "#" + w + "#"
    return {w[i:i + n] for i in range(max(1, len(w) - n + 1))}


def _word_sim(a, b):
    if a == b:
        return 1.0
    ga, gb = _grams(a), _grams(b)
    d = 2.0 * len(ga & gb) / (len(ga) + len(gb))
    return d if d >= 0.6 else 0.0


_FILL = {"and", "or", "of", "the", "a", "with", "in", "from", "for", "to", "nfs", "ns", "made", "style",
         "all", "type", "added", "pieces", "kinds", "brand", "usda"}


def judging_function(ingredient, usda_match):
    try:
        ing, usd = _clean(str(ingredient)), _clean(str(usda_match))
        iw, uw = _w(ing), _w(usd)
        if not iw or not uw:
            return 0.0

        # ---- polarity log-odds (primary feature) ----
        logit = 0.0
        iset, uset = set(iw), set(uw)
        for neg, pos in _POL:
            a_n, a_p = iset & neg, iset & pos
            b_n, b_p = uset & neg, uset & pos
            if (a_n and a_p) or (b_n and b_p):
                continue
            if (a_n and b_p) or (a_p and b_n):
                logit -= 3.0
            elif (a_n and b_n) or (a_p and b_p):
                logit += 0.4
        # un-prefix flip
        for w in iset:
            if w.startswith("un") and len(w) > 4 and w[2:] in uset:
                logit -= 2.0
        for w in uset:
            if w.startswith("un") and len(w) > 4 and w[2:] in iset:
                logit -= 2.0

        # ---- identity: best fuzzy alignment of every USDA content word to ingredient words ----
        ic = [_sing(w) for w in iw if w not in _FILL and len(w) > 2]
        uc = [_sing(w) for w in uw if w not in _FILL and len(w) > 2]
        if not ic or not uc:
            return 0.0
        # weights: first USDA word is the primary food, decays afterwards
        tot, got = 0.0, 0.0
        for k, u in enumerate(uc):
            wt = 1.0 / (1.0 + 0.5 * k)
            best = max(_word_sim(u, i) for i in ic)
            tot += wt
            got += wt * best
        fwd = got / tot
        tot2, got2 = 0.0, 0.0
        for k, i in enumerate(reversed(ic)):  # ingredient's final noun is its head
            wt = 1.0 / (1.0 + 0.5 * k)
            best = max(_word_sim(i, u) for u in uc)
            tot2 += wt
            got2 += wt * best
        bwd = got2 / tot2
        ident = math.sqrt(fwd * bwd)
        logit += 8.0 * (ident - 0.5)
        # primary-food guard: USDA's first word nowhere in ingredient
        if max(_word_sim(uc[0], i) for i in ic) == 0.0:
            logit -= 1.5

        return float(100.0 / (1.0 + math.exp(-logit)))
    except Exception:
        return 0.0
