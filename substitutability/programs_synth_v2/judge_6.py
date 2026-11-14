import re
import math

# Variant 6: weighted cosine similarity over a "food identity vector".
# Each token is weighted by an a-priori specificity estimate: words that
# frequently appear as descriptors in USDA entries (cooked, raw, low fat,
# NFS...) carry little identity, while rarer content nouns carry a lot.
# Order-insensitive word pairs are added so that "cottage cheese" matches
# "Cheese, cottage" as a unit and outweighs single overlapping words.

_COMMON_DESCRIPTOR_FREQ = {
    # rough relative frequencies of descriptor words in a USDA-like corpus
    "raw": 0.30, "cooked": 0.25, "boiled": 0.10, "drained": 0.08,
    "without": 0.12, "with": 0.15, "salt": 0.10, "fat": 0.12, "low": 0.08,
    "reduced": 0.05, "frozen": 0.07, "canned": 0.07, "solids": 0.05,
    "liquids": 0.05, "prepared": 0.06, "nfs": 0.06, "ns": 0.04,
    "added": 0.06, "regular": 0.05, "roasted": 0.05, "baked": 0.05,
    "fried": 0.04, "dry": 0.05, "heat": 0.04, "meat": 0.05, "only": 0.04,
    "lean": 0.04, "made": 0.04, "commercial": 0.04, "fresh": 0.06,
    "whole": 0.05, "skin": 0.03, "eaten": 0.03, "not": 0.05, "sweetened": 0.03,
    "unsweetened": 0.03, "calorie": 0.02, "sodium": 0.03, "lowfat": 0.02,
}
_DROP = {"and", "or", "of", "the", "a", "an", "to", "in", "for", "from", "g",
         "ml", "kg", "oz", "chopped", "diced", "sliced", "minced", "large",
         "small", "medium", "thawed", "peeled", "uncooked"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and w[-3] not in "sxzho":
                return w[:-1]
            return w[: -len(suf)]
    return w


def _weight(w):
    f = _COMMON_DESCRIPTOR_FREQ.get(w)
    if f is not None:
        return -math.log(f) / 4.0     # roughly 0.3 .. 1.0
    # unseen word: treated as a content noun, longer => more specific
    return 1.6 + 0.05 * min(len(w), 10)


def _vector(words, head_index):
    vec = {}
    for i, w in enumerate(words):
        wt = _weight(w)
        if i == head_index:
            wt *= 1.8
        vec[w] = vec.get(w, 0.0) + wt
    for i in range(len(words) - 1):
        pair = "|".join(sorted((words[i], words[i + 1])))
        vec[pair] = vec.get(pair, 0.0) + 1.2
    return vec


def _ingredient_vec(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower()).split(",")[0]
    t = re.sub(r"\d+(\.\d+)?", " ", t)
    words = [_stem(w) for w in re.findall(r"[a-z]+", t) if w not in _DROP]
    return _vector(words, len(words) - 1), words


def _usda_vec(text):
    t = re.sub(r"\([^)]*\)", " ", text.lower())
    segs = [s for s in t.split(",") if s.strip()]
    words = []
    for k, s in enumerate(segs[:3]):
        ws = [_stem(w) for w in re.findall(r"[a-z]+", s) if w not in _DROP]
        if k == 1 and words:
            # rotate qualifier before primary: "cheese, cottage" -> cottage cheese
            words = ws + words
        else:
            words.extend(ws)
    head = 0
    if segs:
        first = [w for w in re.findall(r"[a-z]+", segs[0]) if w not in _DROP]
        head = len(words) - 1 if not first else words.index(_stem(first[-1])) if _stem(first[-1]) in words else 0
    return _vector(words, head), words


def _cos(a, b):
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def judging_function(ingredient, usda_match):
    try:
        vi, wi = _ingredient_vec(str(ingredient or ""))
        vu, wu = _usda_vec(str(usda_match or ""))
        if not wi or not wu:
            return 0.0
        c = _cos(vi, vu)
        # identity gate: ingredient head noun must be in the USDA identity words
        gate = 1.0 if wi[-1] in wu else 0.55
        return round(100.0 * c * gate, 2)
    except Exception:
        return 0.0
