import re
import math

# Lexical and Token Overlap, variant 3: BM25 retrieval score, self-normalised.
# The USDA description is treated as a document and the cleaned ingredient
# tokens as a query. Term IDF comes from built-in pseudo document
# frequencies typical of a USDA-like collection (descriptor words such as
# raw / cooked / fat are very common, specific food names are rare), so
# overlap on modifiers is automatically discounted. BM25 length
# normalisation penalises long, descriptor-heavy entries. The raw score is
# divided by the query's ideal score (the ingredient matched against
# itself) to land in 0..1, then scaled to 0..10.

_N_DOCS = 8000.0
_DF = {
    "raw": 2600, "cooked": 2100, "boiled": 900, "drained": 700, "with": 1800,
    "without": 1100, "salt": 1000, "fat": 1300, "low": 700, "reduced": 400,
    "frozen": 650, "canned": 700, "prepared": 600, "regular": 450, "plain": 300,
    "fresh": 300, "dry": 450, "heat": 380, "meat": 900, "only": 700, "lean": 500,
    "nfs": 900, "roasted": 600, "baked": 500, "fried": 400, "beef": 900, "chicken": 600,
    "pork": 500, "cheese": 350, "juice": 220, "fruit": 300, "sauce": 300, "soup": 300,
    "oil": 180, "milk": 400, "cereal": 450, "spice": 90, "fish": 300, "turkey": 250,
    "bread": 250, "salad": 200, "dressing": 120, "beverage": 500, "sweetened": 250,
    "skin": 350, "eaten": 300, "not": 600, "made": 400, "from": 700, "and": 1500,
    "or": 900, "in": 800, "light": 200, "calorie": 150, "sodium": 250, "vegetable": 400,
}
_DEFAULT_DF = 25.0
_K1, _B, _AVGDL = 1.2, 0.75, 6.0
_NOISE = set("""g gram grams kg ml oz lb cup cups tbsp tsp to taste tube jar can optional
about divided the a an of as chopped diced minced sliced shredded grated thawed
segmented peeled rinsed cubed finely roughly large small medium""".split())


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _toks(text, is_ing):
    t = text.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    if is_ing:
        t = t.split(",")[0]
        t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", t)
    return [_sing(w) for w in re.findall(r"[a-z]+", t) if w not in _NOISE and len(w) > 1]


def _idf(t):
    df = _DF.get(t, _DEFAULT_DF)
    return math.log(1.0 + (_N_DOCS - df + 0.5) / (df + 0.5))


def _bm25(query, doc):
    tf = {}
    for t in doc:
        tf[t] = tf.get(t, 0) + 1
    dl = float(len(doc))
    s = 0.0
    for q in set(query):
        f = tf.get(q, 0)
        if f == 0:
            continue
        s += _idf(q) * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * dl / _AVGDL))
    return s


def judging_function(ingredient, usda_match):
    try:
        q = _toks(str(ingredient or ""), True)
        d = _toks(str(usda_match or ""), False)
        if not q or not d:
            return 0.0
        raw = _bm25(q, d)
        ideal = _bm25(q, q)
        if ideal <= 0:
            return 0.0
        rel = raw / ideal
        # symmetric check: how much of the document is explained by the query
        back = _bm25(d, q) / max(_bm25(d, d), 1e-9)
        score = 10.0 * (0.7 * rel + 0.3 * back)
        return round(max(0.0, min(10.0, score)), 3)
    except Exception:
        return 0.0
