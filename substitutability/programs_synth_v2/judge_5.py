import re
from difflib import SequenceMatcher

# Variant 5: "identity-bearing token" resolution.
# Many food heads are generic form nouns (paste, oil, seed, juice, sauce ...).
# For those, the identity of the food is carried by the modifier
# ("garlic paste" -> garlic, "chia seed" -> chia). We resolve an identity
# key (substance, form) for each side and compare substance first, form
# second, using a sequence matcher only as a tie-breaker for spellings.

_FORM_NOUNS = {
    "paste", "oil", "seed", "seeds", "juice", "sauce", "powder", "flour",
    "butter", "milk", "cream", "syrup", "extract", "puree", "jam", "jelly",
    "dressing", "meat", "breast", "thigh", "leg", "wing", "fillet", "filet",
    "patty", "nut", "nuts", "leaf", "leaves", "chip", "chips", "bar", "soup",
    "broth", "stock", "cheese", "yogurt", "bread", "cake", "pie", "salad",
}
_SKIP = {
    "fresh", "frozen", "canned", "raw", "cooked", "uncooked", "chopped",
    "diced", "sliced", "minced", "grated", "large", "small", "medium",
    "whole", "thawed", "drained", "peeled", "organic", "plain", "nfs", "ns",
    "and", "or", "of", "with", "the", "a", "in", "from", "sweet", "light",
    "dark", "low", "reduced", "fat", "lowfat", "nonfat", "calorie", "sodium",
}


def _words(seg):
    return [w for w in re.findall(r"[a-z]+", seg) if w not in _SKIP]


def _base(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxzh":
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _key_from_words(words):
    """Return (substance, form) from a head-final word list."""
    words = [_base(w) for w in words]
    if not words:
        return "", ""
    head = words[-1]
    if head in _FORM_NOUNS and len(words) > 1:
        return words[-2], head
    return head, ""


def _ingredient_key(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\d+(\.\d+)?\s*[a-z]{0,2}\b", " ", t)
    return _key_from_words(_words(t)), [_base(w) for w in _words(t)]


def _usda_key(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    segs = [_words(s) for s in t.split(",")]
    segs = [s for s in segs if s]
    if not segs:
        return ("", ""), []
    first = [_base(w) for w in segs[0]]
    allw = [_base(w) for s in segs for w in s]
    # "Cheese, cottage" / "Oil, olive" : single generic primary + qualifier
    if len(first) == 1 and len(segs) > 1:
        second = [_base(w) for w in segs[1]]
        if first[0] in _FORM_NOUNS or len(second) <= 2:
            return (second[-1], first[0]) if second else (first[0], ""), allw
    return _key_from_words(first), allw


def _spell(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def judging_function(ingredient, usda_match):
    try:
        (i_sub, i_form), i_all = _ingredient_key(str(ingredient or ""))
        (u_sub, u_form), u_all = _usda_key(str(usda_match or ""))
        if not i_sub or not u_sub:
            return 0.0

        # substance agreement (dominant)
        if i_sub == u_sub:
            sub = 1.0
        elif i_sub in u_all[:3]:
            sub = 0.75
        elif _spell(i_sub, u_sub) >= 0.85:
            sub = 0.8
        elif i_sub in u_all:
            sub = 0.35
        else:
            sub = 0.0

        # form agreement (secondary)
        if i_form == u_form:
            form = 1.0
        elif not i_form or not u_form:
            form = 0.6
        else:
            form = 0.2

        # does the USDA substance appear anywhere in the ingredient?
        back = 1.0 if u_sub in i_all else 0.0

        score = 6.0 * sub + 2.0 * form + 2.0 * back
        if sub == 0.0 and back == 0.0:
            score = min(score, 2.0)
        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
