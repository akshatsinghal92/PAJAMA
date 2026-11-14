import re
import math

# Polarity lexicon: word -> (attribute, sign). Sign -1 = absence / reduced, +1 = presence.
_LEX = {}
def _add(attr, neg, pos):
    for w in neg:
        _LEX[w] = (attr, -1)
    for w in pos:
        _LEX[w] = (attr, 1)

_add("salt", ["unsalted", "saltfree", "unsalt"], ["salted", "brined", "cured", "saltwater"])
_add("sugar", ["unsweetened", "sugarless", "unsugared"], ["sweetened", "sweet", "syrup", "candied", "glazed", "sugared", "honey"])
_add("skin", ["skinless", "peeled"], ["skin", "skinon", "unpeeled"])
_add("bone", ["boneless", "deboned"], ["bone", "bones", "bonein"])
_add("seed", ["seedless", "pitted", "deseeded"], ["seeds", "seeded", "unpitted"])
_add("hull", ["hulled", "shelled", "dehulled"], ["unhulled", "inshell", "unshelled"])
_add("fat", ["nonfat", "fatfree", "skim", "lowfat", "lean", "reduced", "light", "lite", "diet"], ["whole", "regular", "fatty", "fat", "full"])
_add("caf", ["decaffeinated", "decaf", "caffeinefree"], ["caffeinated"])
_add("gluten", ["glutenfree"], ["gluten"])
_add("dairy", ["dairyfree", "nondairy", "vegan"], ["dairy", "milk"])
_add("heat", ["raw", "uncooked", "fresh", "unprepared", "frozen"], ["cooked", "boiled", "roasted", "fried", "baked", "toasted", "steamed", "canned", "dried", "dehydrated"])
_add("flavor", ["plain", "unflavored", "unseasoned"], ["flavored", "seasoned", "vanilla", "chocolate", "smoked", "spiced"])
_add("bleach", ["unbleached", "unenriched"], ["bleached", "enriched"])

_WEIGHT = {"salt": 1.0, "sugar": 1.0, "skin": 1.0, "bone": 1.0, "seed": 1.0, "hull": 1.0,
           "fat": 0.9, "caf": 1.0, "gluten": 0.8, "dairy": 0.6, "heat": 0.45, "flavor": 0.55, "bleach": 0.6}

_NEGATORS = ("no", "without", "non", "free", "not", "zero")
_FILLER = {"and", "or", "the", "of", "with", "in", "a", "an", "for", "from", "to", "nfs", "style", "type", "added", "pack"}


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|oz|lb|lbs)?\b", " ", s)
    return s


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _state(text):
    """Scan left to right with a negation window; return {attr: signed evidence}."""
    toks = re.findall(r"[a-z]+", text)
    ev = {}
    window = 0
    for i, t in enumerate(toks):
        if t in _NEGATORS:
            window = 2
            continue
        sign_flip = 1
        if window > 0:
            sign_flip = -1
        if i + 1 < len(toks) and toks[i + 1] == "free":
            sign_flip = -1
        hit = _LEX.get(t)
        if hit is None and t == "salt":
            hit = ("salt", 1)
        if hit is None and t == "sugar":
            hit = ("sugar", 1)
        if hit is None and t == "caffeine":
            hit = ("caf", 1)
        if hit is None and t == "gluten":
            hit = ("gluten", 1)
        if hit:
            attr, sg = hit
            ev[attr] = ev.get(attr, 0.0) + sg * sign_flip
        if window > 0:
            window -= 1
    return ev


def _bigrams(s):
    s = re.sub(r"[^a-z]", "", s)
    return set(s[i:i + 3] for i in range(len(s) - 2))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usd = _clean(usda_match)
        if not ing.strip() or not usd.strip():
            return 0.0
        ev_i = _state(ing)
        ev_u = _state(usd)

        # probability-like product: each contradiction multiplies survival
        survive = 1.0
        support = 0.0
        for attr in ev_i:
            if attr in ev_u and ev_i[attr] != 0 and ev_u[attr] != 0:
                w = _WEIGHT.get(attr, 0.5)
                if (ev_i[attr] > 0) != (ev_u[attr] > 0):
                    survive *= (1.0 - 0.85 * w)
                else:
                    support += 0.15 * w

        # identity: character trigram Dice of primary food chunks
        ing_main = re.split(r",|\(", ing)[0]
        usd_main = usd.split(",")[0]
        a = _bigrams(ing_main)
        b = _bigrams(usd_main)
        dice = 2.0 * len(a & b) / (len(a) + len(b)) if (a and b) else 0.0

        wi = set(_stem(w) for w in re.findall(r"[a-z]+", ing) if w not in _FILLER)
        wu = set(_stem(w) for w in re.findall(r"[a-z]+", usd) if w not in _FILLER)
        recall = len(wi & wu) / float(len(wi)) if wi else 0.0
        identity = 0.5 * dice + 0.5 * recall
        identity = min(1.0, identity + support)

        # soft gate on identity so a polarity-clean but unrelated food is still low
        gate = 1.0 / (1.0 + math.exp(-8.0 * (identity - 0.35)))
        return round(100.0 * gate * survive, 3)
    except Exception:
        return 0.0
