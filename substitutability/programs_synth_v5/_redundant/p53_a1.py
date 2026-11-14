import re

# attribute -> (negative-pole words, positive-pole words)
_PAIRS = {
    "salt": ({"unsalted", "saltfree", "nosalt", "withoutsalt", "lowsodium", "nosaltadded", "unsalt"},
             {"salted", "withsalt", "saltadded", "saltedsalt"}),
    "sweet": ({"unsweetened", "nosugar", "sugarfree", "withoutsugar", "nosugaradded", "noaddedsugar"},
              {"sweetened", "syrup", "candied", "glazed", "sugared", "honeyed"}),
    "skin": ({"skinless", "peeled", "withoutskin"}, {"skin", "withskin", "skinon", "unpeeled"}),
    "bone": ({"boneless", "deboned", "withoutbone"}, {"bone", "bonein", "withbone", "boneon"}),
    "seed": ({"seedless", "pitted", "withoutseeds", "deseeded"}, {"seeds", "seeded", "withseeds", "unpitted"}),
    "hull": ({"hulled", "shelled", "dehulled"}, {"unhulled", "unshelled", "inshell", "inshell"}),
    "fat": ({"fatfree", "nonfat", "skim", "lowfat", "reducedfat", "lean", "nofat", "lite", "light", "defatted"},
            {"whole", "fatadded", "regular", "highfat", "fullfat", "fatty", "withfat", "separablefat"}),
    "caff": ({"decaffeinated", "decaf", "caffeinefree"}, {"caffeinated", "regular"}),
    "cook": ({"raw", "uncooked", "fresh", "unprepared"}, {"cooked", "boiled", "roasted", "baked", "fried", "toasted", "steamed", "grilled"}),
    "sugarcal": ({"diet", "sugarfree"}, {"sugar"}),
    "gluten": ({"glutenfree"}, {"gluten", "wheat"}),
    "drain": ({"drained"}, {"liquids", "juice"}),
    "bleach": ({"unbleached", "unenriched"}, {"bleached", "enriched"}),
}

_NEG = {"no", "without", "free", "non", "not"}
_STOP = {"and", "or", "the", "of", "with", "in", "a", "an", "for", "from", "to", "nfs", "g", "style",
         "type", "pack", "added", "raw", "fresh", "cooked", "chopped", "diced", "sliced", "minced", "ground"}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)?\b\s*", "", s)
    s = re.sub(r"[\(\)\[\]]", " , ", s)
    return s


def _tokens(s):
    return re.findall(r"[a-z]+", s)


def _poles(text):
    """Return dict attribute -> set of poles (-1 / +1) stated in the text."""
    toks = _tokens(text)
    out = {}
    joined = [t for t in toks]
    # build negation-merged tokens
    merged = []
    i = 0
    while i < len(joined):
        t = joined[i]
        if t in _NEG and i + 1 < len(joined):
            merged.append(t + joined[i + 1])
            if i + 2 < len(joined) and joined[i + 1] in ("added",):
                pass
            i += 1
            # also keep bigram with following token for "without salt"
            if i + 1 < len(joined) and joined[i] in ("added",):
                merged.append(joined[i - 1] + joined[i + 1])
            merged.append(joined[i])
            # mark negated word
            if i == len(joined) - 1:
                pass
        else:
            merged.append(t)
        i += 1
    # also form "xfree" compounds ("salt free")
    for j in range(len(joined) - 1):
        if joined[j + 1] == "free":
            merged.append(joined[j] + "free")
    negated = set()
    for j, t in enumerate(joined):
        if t in _NEG and j + 1 < len(joined):
            negated.add(joined[j + 1])
            if j + 2 < len(joined):
                negated.add(joined[j + 2])
    for j, t in enumerate(joined):
        if j + 1 < len(joined) and joined[j + 1] == "free":
            negated.add(t)
    mset = set(merged)
    for attr, (neg, pos) in _PAIRS.items():
        hit = set()
        if mset & neg:
            hit.add(-1)
        for p in pos:
            if p in mset:
                # positive word, but not if it is itself negated
                if p in negated:
                    hit.add(-1)
                else:
                    hit.add(1)
        if attr == "sweet" and ("sweet" in mset or "sugar" in mset) and not (mset & neg):
            if "sugar" in negated or "sweet" in negated:
                hit.add(-1)
        if hit:
            out[attr] = hit
    # prefix-style negation: un-/non- forms
    for t in joined:
        if t.startswith("un") and t[2:] in ("salted", "sweetened", "bleached", "hulled", "peeled", "cooked", "flavored", "seasoned"):
            attr = {"salted": "salt", "sweetened": "sweet", "bleached": "bleach", "hulled": "hull",
                    "peeled": "skin", "cooked": "cook", "flavored": "flav", "seasoned": "flav"}[t[2:]]
            out.setdefault(attr, set()).add(-1)
            out[attr].discard(1)
    return out


def _core(text):
    first = text.split(",")[0]
    toks = [t for t in _tokens(first) if t not in _STOP]
    return [t.rstrip("s") if len(t) > 3 else t for t in toks]


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usd = _norm(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        score = 5.0

        # lexical anchor so non-contradiction does not mean match
        ing_all = set(t.rstrip("s") if len(t) > 3 else t for t in _tokens(ing) if t not in _STOP)
        usd_all = set(t.rstrip("s") if len(t) > 3 else t for t in _tokens(usd) if t not in _STOP)
        ing_core = set(_core(ing.split(",")[0]))
        usd_core = set(_core(usd))
        if ing_all:
            cover = len(ing_all & usd_all) / float(len(ing_all))
        else:
            cover = 0.0
        if ing_core:
            head = len(ing_core & usd_all) / float(len(ing_core))
        else:
            head = 0.0
        score += 3.0 * head + 2.0 * cover
        if not (ing_all & usd_all):
            score -= 4.0
        extra = usd_all - ing_all
        score -= min(1.5, 0.25 * len(extra))

        pi = _poles(ing)
        pu = _poles(usd)
        conflicts = 0
        agrees = 0
        for attr in set(pi) & set(pu):
            a, b = pi[attr], pu[attr]
            if a.isdisjoint(b):
                w = 1.0
                if attr in ("cook",):
                    w = 0.6
                if attr in ("salt", "sweet", "skin", "bone", "seed", "hull", "caff", "gluten", "fat"):
                    w = 2.5
                conflicts += w
            else:
                agrees += 1
        score -= 3.0 * conflicts
        score += 0.5 * agrees
        # one-sided mention: neutral
        return max(-10.0, min(15.0, score))
    except Exception:
        return 0.0
