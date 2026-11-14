import re

# attribute -> (positive cues, negative cues)
ATTRS = {
    "salt": ({"salted", "salt"}, {"unsalted", "saltfree", "nosalt", "lowsodium", "sodiumfree"}),
    "sweet": ({"sweetened", "sugared", "sugar", "sweet"}, {"unsweetened", "sugarfree", "nosugar", "sugarless"}),
    "skin": ({"skin", "skinon", "withskin"}, {"skinless", "noskin", "skinned", "skinnoteaten", "skinremoved"}),
    "bone": ({"bonein", "boneon", "withbone", "bone", "bones"}, {"boneless", "deboned", "nobone", "bonedremoved"}),
    "hull": ({"unhulled", "hull", "inshell", "shell"}, {"hulled", "shelled", "dehulled"}),
    "seed": ({"seeds", "seeded", "withseeds"}, {"seedless", "deseeded", "noseeds"}),
    "caf": ({"caffeinated", "regular"}, {"decaffeinated", "decaf", "caffeinefree"}),
    "fat": ({"fat", "oil", "buttered", "fried", "added"}, {"nonfat", "fatfree", "lowfat", "reducedfat", "lean", "nofat", "skim", "light"}),
    "gluten": ({"gluten"}, {"glutenfree", "nogluten"}),
    "drain": ({"liquid", "undrained"}, {"drained", "solids"}),
    "cook": ({"cooked", "roasted", "boiled", "baked"}, {"raw", "uncooked", "fresh"}),
    "pit": ({"pits", "pitted"}, {"unpitted"}),
}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb|grams?)?\b", " ", s)
    s = re.sub(r"[-_/]", " ", s)
    s = re.sub(r"[^a-z0-9 ,]", " ", s)
    return s


def _tokens(s):
    toks = [t for t in re.split(r"[ ,]+", s) if t]
    out = list(toks)
    # fuse negation words with the following word
    for i, t in enumerate(toks):
        if t in ("no", "not", "without", "non", "free") and i + 1 < len(toks):
            out.append(t + toks[i + 1])
            out.append(toks[i + 1] + t)
        if i + 1 < len(toks):
            out.append(t + toks[i + 1])
    return out


def _state(toks, attr):
    pos, neg = ATTRS[attr]
    ts = set(toks)
    hasneg = any(w in ts for w in neg)
    haspos = any(w in ts for w in pos)
    if hasneg:
        return -1
    if haspos:
        return 1
    # generic negation of the positive cue
    for p in pos:
        for n in ("no", "non", "not", "without"):
            if (n + p) in ts or (p + "free") in ts:
                return -1
    return 0


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


STOP = {"and", "or", "of", "the", "a", "with", "in", "for", "from", "to", "style", "type", "all", "varieties",
        "raw", "fresh", "canned", "frozen", "cooked", "chopped", "sliced", "diced", "g", "drained", "store", "bought"}


def judging_function(ingredient, usda_match):
    try:
        a = _norm(ingredient)
        b = _norm(usda_match)
        if not a.strip() or not b.strip():
            return 0.0
        ta, tb = _tokens(a), _tokens(b)

        # --- polarity layer ---
        conflicts = 0
        agrees = 0
        for attr in ATTRS:
            sa, sb = _state(ta, attr), _state(tb, attr)
            if sa != 0 and sb != 0:
                if sa != sb:
                    conflicts += 1
                else:
                    agrees += 1
        # explicit negation asymmetry on generic words
        na = {t for t in re.split(r"[ ,]+", a) if t.startswith("un") and len(t) > 4}
        nb = {t for t in re.split(r"[ ,]+", b) if t.startswith("un") and len(t) > 4}
        for w in na:
            if w[2:] in b.split():
                conflicts += 1
        for w in nb:
            if w[2:] in a.split():
                conflicts += 1

        # --- content layer: weighted head overlap ---
        ca = [_stem(t) for t in re.split(r"[ ,]+", a) if t and t not in STOP]
        cb_list = [_stem(t) for t in re.split(r"[ ,]+", b) if t and t not in STOP]
        if not ca or not cb_list:
            content = 0.3
        else:
            sb_set = set(cb_list)
            sa_set = set(ca)
            inter = sa_set & sb_set
            # head noun of ingredient = last word; USDA primary = first segment words
            head_a = ca[-1]
            primary_b = set(_stem(t) for t in re.split(r"[ ]+", b.split(",")[0]) if t and t not in STOP)
            head_hit = 1.0 if (head_a in sb_set) else 0.0
            prim_hit = len(primary_b & sa_set) / max(1, len(primary_b))
            cov_a = len(inter) / max(1, len(sa_set))
            extra_b = len(primary_b - sa_set) / max(1, len(primary_b))
            content = 0.35 * head_hit + 0.3 * cov_a + 0.25 * prim_hit - 0.2 * extra_b
            content = max(0.0, min(1.0, content + 0.1))

        score = 10.0 * content + 0.5 * agrees - 4.0 * conflicts
        return float(score)
    except Exception:
        return 0.0
