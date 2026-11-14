import re
import math

# Variant 3: logistic "dish-ness" probability per side + component-graph comparison.
# Each side is mapped to a probability of being a composite dish via a weighted
# log-odds sum over cue classes. Score combines (a) agreement of these
# probabilities (Bernoulli similarity), (b) agreement in counted components when
# both are dishes, and (c) whether a single ingredient is merely a component of
# the other side's dish.

_CUE_WEIGHTS = {
    # strong dish cues
    "casserole": 3.0, "sandwich": 3.0, "soup": 2.8, "salad": 2.6, "stew": 2.6,
    "dinner": 2.8, "entree": 2.6, "stuffed": 2.6, "pizza": 2.4, "burrito": 2.4,
    "lasagna": 2.4, "pie": 1.6, "chili": 1.8, "curry": 1.8, "stir": 1.6,
    "fried rice": 2.4, "potpie": 2.6, "meal": 2.2, "platter": 2.2, "omelet": 1.8,
    "taco": 1.4, "quiche": 2.0, "dumpling": 1.6, "gravy": 1.4,
    # mixture cues
    "mix": 1.8, "blend": 1.4, "mixture": 2.0, "medley": 2.2, "combo": 2.0,
    "assorted": 1.4, "mixed": 1.4, "prepared": 1.6, "recipe": 1.6,
    "homemade": 1.0, "frozen meal": 2.6, "kit": 1.6,
    # sauce/preparation cues
    "in sauce": 2.2, "with sauce": 2.2, "in gravy": 2.2, "in syrup": 0.6,
    "in oil": 0.4, "in water": 0.2, "breaded": 0.8, "battered": 0.8,
}

# connectors which, between two food words, signal combination
_CONNECTORS = ("with", "and", "&", "plus", "topped", "filled", "w/")

# phrases with 'and'/'with' that are NOT composites (descriptor noise)
_BENIGN = [
    r"separable lean and fat", r"lean and fat", r"with salt", r"without salt",
    r"with added", r"without added", r"boiled,? drained,? (?:or|and)", r"drained,? or",
    r"skin and bones", r"with skin", r"without skin", r"with bone", r"meat and skin",
    r"cheddar or american", r"fryers and", r"broilers or fryers", r"salt and pepper",
    r"made with", r"fortified with", r"enriched with", r"with vitamin", r"with calcium",
    r"heads and", r"solids and liquids", r"with liquid", r"juice pack", r"and liquids",
]

_STOP = set("""a an the of or to for from fresh raw cooked dried dry frozen canned
chopped diced sliced minced shredded grated cubed whole large small medium
boiled baked roasted drained simmered heat uncooked ready serve unprepared
reduced low fat sodium salt without added style type regular plain
g kg mg ml l oz lb tbsp tsp cup cups piece pieces into paste thawed""".split())


def _norm(s):
    s = "" if s is None else str(s)
    s = s.lower()
    s = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb|lbs)?\b\.?", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9&/%,\s-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_benign(s):
    for pat in _BENIGN:
        s = re.sub(pat, " ", s)
    return re.sub(r"\s+", " ", s)


def _dish_logodds(text, is_usda):
    s = _strip_benign(text)
    lo = -2.2  # prior: most items are single ingredients
    hits = []
    for cue, w in _CUE_WEIGHTS.items():
        if re.search(r"\b" + re.escape(cue) + r"\b", s):
            lo += w
            hits.append(cue)
    # connectors joining two content words
    conn = 0
    for c in _CONNECTORS:
        pat = r"[a-z]{3,}\s+" + re.escape(c) + r"\s+[a-z]{3,}"
        conn += len(re.findall(pat, s))
    lo += 1.5 * min(conn, 3)
    # USDA: many comma segments with nouns is common for single foods,
    # so do not reward segment count; ingredient text: comma after is a state.
    if is_usda:
        segs = [x.strip() for x in s.split(",") if x.strip()]
        if segs and len(segs[0].split()) >= 4:
            lo += 0.6
    return lo, hits, conn


def _sigmoid(x):
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _components(text):
    s = _strip_benign(text)
    s = s.replace(",", " ")
    parts = re.split(r"\b(?:and|with|&|plus|w/|in)\b", s)
    comps = []
    for p in parts:
        toks = [t for t in re.findall(r"[a-z]+", p) if t not in _STOP and len(t) > 2]
        if toks:
            comps.append(set(_stem(t) for t in toks))
    return comps


def _stem(t):
    for suf in ("ies", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def _tokens(text):
    return set(_stem(t) for t in re.findall(r"[a-z]+", text)
               if t not in _STOP and len(t) > 2)


def judging_function(ingredient, usda_match):
    try:
        a = _norm(ingredient)
        b = _norm(usda_match)
        if not a or not b:
            return 0.0

        la, ha, ca = _dish_logodds(a, False)
        lb, hb, cb = _dish_logodds(b, True)
        pa, pb = _sigmoid(la), _sigmoid(lb)

        # (a) Bernoulli agreement: probability both sides fall in the same class
        agree = pa * pb + (1 - pa) * (1 - pb)

        ta, tb = _tokens(a), _tokens(b)
        overlap = len(ta & tb) / float(max(1, min(len(ta), len(tb)))) if ta and tb else 0.0

        # (b) dish-for-dish: compare component structure
        struct = 0.5
        if pa > 0.5 and pb > 0.5:
            comps_a, comps_b = _components(a), _components(b)
            matched = 0
            for c in comps_a:
                if any(c & d for d in comps_b):
                    matched += 1
            denom = max(len(comps_a), len(comps_b), 1)
            struct = matched / float(denom)
            cue_overlap = len(set(ha) & set(hb)) / float(max(1, len(set(ha) | set(hb))))
            struct = 0.7 * struct + 0.3 * cue_overlap

        # (c) containment penalty: single side is just a component of the dish side
        contain_pen = 0.0
        diff = abs(pa - pb)
        if diff > 0.4:
            single, dish = (ta, tb) if pa < pb else (tb, ta)
            if single and len(single & dish) > 0:
                contain_pen = 1.0 + 0.5 * (len(single & dish) / float(len(single)))
            else:
                contain_pen = 0.6

        score = 10.0 * agree                 # up to 10
        score += 3.0 * (struct - 0.5)        # -1.5..+1.5
        score += 2.0 * overlap               # up to 2
        score -= 4.0 * contain_pen * diff    # up to ~6
        score = max(0.0, min(12.0, score))
        return round(score / 12.0 * 10.0, 4)
    except Exception:
        return 5.0
