import re
import math

# Processing and Additive Difference, variant 6: morphology of UNEXPLAINED
# USDA words fed to a logistic score.
# Words of the USDA description that the ingredient does not explain are
# inspected morphologically instead of via one big lexicon:
#   * past participles (-ed) usually denote processing that adds something
#     (breaded, sweetened, salted, glazed), unless they are known neutral
#     preparation words (cooked, drained, chopped, boiled, peeled ...)
#   * flavour adjectives (-y, -ish, -flavored, -style)
#   * condiment / seasoning nouns from a short list
#   * "with"/"and" joins that introduce a second component
#   * upper-case brand tokens (formulated commercial products)
# These counts form a feature vector; a logistic function with hand-set
# weights estimates P(the entry adds a taste-relevant component).
# Score = 10 * (1 - P).

_NEUTRAL_ED = {"cooked", "drained", "chopped", "boiled", "peeled", "sliced", "diced",
               "minced", "shredded", "grated", "thawed", "steamed", "unprepared",
               "unheated", "enriched", "fortified", "unenriched", "trimmed", "separated",
               "uncooked", "unsalted", "unsweetened", "frozen", "canned", "dried",
               "roasted", "baked", "broiled", "grilled", "braised", "stewed", "poached",
               "microwaved", "reduced", "added", "mixed", "prepared", "packed", "segmented"}
_STRONG_ED = {"breaded", "battered", "sweetened", "salted", "glazed", "candied", "frosted",
              "seasoned", "marinated", "smoked", "cured", "flavored", "flavoured", "creamed",
              "buttered", "stuffed", "coated", "pickled", "spiced", "fried", "sugared"}
_CONDIMENTS = {"sauce", "gravy", "dressing", "salt", "pepper", "sugar", "syrup", "honey",
               "seasoning", "spices", "herbs", "garlic", "onion", "cheese", "butter", "oil",
               "vinegar", "mustard", "ketchup", "mayonnaise", "soy", "teriyaki", "bbq",
               "barbecue", "chili", "pesto", "cream", "glaze", "marinade", "blend", "mix"}
_W = {"bias": -2.6, "strong_ed": 2.4, "other_ed": 0.6, "flav_adj": 1.2, "condiment": 1.7,
      "join": 1.0, "brand": 1.1, "plain": -1.2}


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def _sing(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)\b", " ", ing)
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        raw_u = re.sub(r"\([^)]*\)", " ", str(usda_match or ""))
        usda = raw_u.lower()
        iw = {_sing(w) for w in re.findall(r"[a-z]+", ing)}
        uw = re.findall(r"[a-z]+", usda)
        if not iw or not uw:
            return 0.0
        unexplained = [w for w in uw if _sing(w) not in iw and w not in iw]
        f = dict.fromkeys(_W, 0.0)
        f["bias"] = 1.0
        for i, w in enumerate(unexplained):
            prev = unexplained[i - 1] if i else ""
            if prev in ("without", "no", "un", "not"):
                continue
            if w in _STRONG_ED:
                f["strong_ed"] += 1
            elif w.endswith("ed") and len(w) > 4 and w not in _NEUTRAL_ED:
                f["other_ed"] += 1
            elif (w.endswith("y") and len(w) > 4 and w not in ("dry", "turkey", "celery", "barley", "honey", "parsley", "jelly", "candy", "berry", "cherry", "whiskey", "ready", "dairy")) or w.endswith("ish") or w in ("style", "flavor", "flavour"):
                f["flav_adj"] += 1
            if _sing(w) in _CONDIMENTS or w in _CONDIMENTS:
                f["condiment"] += 1
        f["join"] = len(re.findall(r"\b(with|and)\s+(?!skin|bone|liquids|solids|peel|not|without)[a-z]+", usda))
        if re.search(r"\b(with|and)\b", ing):
            f["join"] = max(0.0, f["join"] - 1)
        f["brand"] = 1.0 if re.search(r"\b[A-Z][A-Z'&]{2,}\b", raw_u) else 0.0
        f["plain"] = 1.0 if re.search(r"\b(plain|unsalted|unsweetened|without salt|no sugar added|raw)\b", usda) else 0.0
        z = sum(_W[k] * v for k, v in f.items())
        p = _sigmoid(z)
        return round(10.0 * (1.0 - p), 3)
    except Exception:
        return 0.0
