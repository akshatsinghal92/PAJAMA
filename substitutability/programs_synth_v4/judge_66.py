import re
import math

# Each cooking state is embedded as a point in a 4-D "transformation space":
# (heat_applied, added_fat, surface_browning, moisture_change[-1 dry .. +1 wet])
_METHOD_SPACE = {
    "raw":        (0.0, 0.0, 0.0, 0.0),
    "fresh":      (0.0, 0.0, 0.0, 0.0),
    "uncooked":   (0.0, 0.0, 0.0, 0.0),
    "unroasted":  (0.0, 0.0, 0.0, 0.0),
    "untoasted":  (0.0, 0.0, 0.0, 0.0),
    "cooked":     (0.6, 0.1, 0.2, 0.2),
    "boiled":     (0.6, 0.0, 0.0, 0.6),
    "poached":    (0.5, 0.0, 0.0, 0.6),
    "simmered":   (0.6, 0.0, 0.0, 0.5),
    "stewed":     (0.7, 0.1, 0.1, 0.6),
    "braised":    (0.7, 0.2, 0.4, 0.5),
    "steamed":    (0.5, 0.0, 0.0, 0.4),
    "blanched":   (0.3, 0.0, 0.0, 0.3),
    "microwaved": (0.5, 0.0, 0.0, 0.1),
    "baked":      (0.8, 0.1, 0.5, -0.3),
    "roasted":    (0.9, 0.2, 0.7, -0.4),
    "grilled":    (0.9, 0.1, 0.8, -0.4),
    "broiled":    (0.9, 0.1, 0.8, -0.4),
    "pan-broiled":(0.8, 0.2, 0.7, -0.3),
    "barbecued":  (0.9, 0.2, 0.8, -0.4),
    "toasted":    (0.7, 0.0, 0.8, -0.7),
    "sauteed":    (0.7, 0.5, 0.5, -0.2),
    "stir-fried": (0.8, 0.5, 0.6, -0.2),
    "pan-fried":  (0.8, 0.6, 0.7, -0.3),
    "fried":      (0.9, 0.8, 0.8, -0.4),
    "deep-fried": (1.0, 1.0, 0.9, -0.5),
    "smoked":     (0.5, 0.0, 0.6, -0.5),
    "dried":      (0.1, 0.0, 0.1, -1.0),
    "dehydrated": (0.1, 0.0, 0.1, -1.0),
    "oil-roasted":(0.9, 0.5, 0.7, -0.4),
    "pickled":    (0.1, 0.0, 0.0, 0.5),
    "canned":     (0.6, 0.0, 0.0, 0.5),
}

_ALIASES = {
    "saute": "sauteed", "sautéed": "sauteed", "sauted": "sauteed",
    "deep fried": "deep-fried", "deepfried": "deep-fried",
    "pan fried": "pan-fried", "pan broiled": "pan-broiled",
    "stir fried": "stir-fried", "frying": "fried", "fry": "fried",
    "roast": "roasted", "toast": "toasted", "grill": "grilled",
    "bake": "baked", "boil": "boiled", "steam": "steamed",
    "broil": "broiled", "microwave": "microwaved", "bbq": "barbecued",
    "smoke": "smoked", "fries": "fried", "dry-roasted": "roasted",
    "dry roasted": "roasted", "oil roasted": "oil-roasted",
    "hard-boiled": "boiled", "hard boiled": "boiled", "crumbles": "cooked",
    "heated": "cooked", "prepared": "cooked", "ready-to-eat": "cooked",
}

# Words where the method token names a product rather than a process
_LEXICAL_EXCEPTIONS = {
    ("roast", "chuck"), ("roast", "beef"), ("roast", "pork"), ("roast", "rump"),
    ("dried", "herb"), ("toast", "french"),
}

_NEUTRAL_WORDS = {"nfs", "ns", "generic", "plain", "regular", "commercial", "frozen", "thawed"}


def _clean(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", t)
    t = t.replace("é", "e")
    t = re.sub(r"[^a-z0-9%\-\s,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_states(text):
    """Return list of canonical method names present in text, longest-match first."""
    found = []
    t = " " + text.replace(",", " , ") + " "
    # multi-word aliases first
    for alias in sorted(_ALIASES, key=len, reverse=True):
        pat = r"(?<![a-z\-])" + re.escape(alias) + r"(?![a-z\-])"
        if re.search(pat, t):
            canon = _ALIASES[alias]
            words = set(re.findall(r"[a-z]+", t))
            if any((alias == a and b in words) for a, b in _LEXICAL_EXCEPTIONS):
                continue
            found.append(canon)
            t = re.sub(pat, " ", t)
    for m in sorted(_METHOD_SPACE, key=len, reverse=True):
        pat = r"(?<![a-z\-])" + re.escape(m) + r"(?![a-z\-])"
        if re.search(pat, t):
            words = set(re.findall(r"[a-z]+", t))
            if any((m == a and b in words) for a, b in _LEXICAL_EXCEPTIONS):
                t = re.sub(pat, " ", t)
                continue
            found.append(m)
            t = re.sub(pat, " ", t)
    return found


def _centroid(states):
    if not states:
        return None
    dims = len(next(iter(_METHOD_SPACE.values())))
    acc = [0.0] * dims
    # weight more specific (higher-heat) states more strongly
    total_w = 0.0
    for s in states:
        vec = _METHOD_SPACE.get(s)
        if vec is None:
            continue
        w = 1.0 + vec[0]
        total_w += w
        for i in range(dims):
            acc[i] += w * vec[i]
    if total_w == 0:
        return None
    return tuple(a / total_w for a in acc)


_DIM_WEIGHTS = (1.0, 1.6, 1.3, 1.1)


def _distance(a, b):
    return math.sqrt(sum(w * (x - y) ** 2 for w, x, y in zip(_DIM_WEIGHTS, a, b)))


def _food_tokens(text):
    stop = set(_METHOD_SPACE) | set(_ALIASES) | _NEUTRAL_WORDS | {
        "and", "or", "with", "without", "the", "a", "of", "in", "for", "to",
        "fat", "lean", "choice", "select", "boneless", "skinless", "type",
    }
    toks = []
    for w in re.findall(r"[a-z]+", text):
        if len(w) < 3 or w in stop:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        toks.append(w)
    return toks


def _anchor_overlap(ing, usda):
    it = _food_tokens(ing)
    ut = _food_tokens(usda)
    if not it or not ut:
        return 0.0
    iset, uset = set(it), set(ut)
    hits = 0
    for a in iset:
        for b in uset:
            if a == b or (len(a) > 4 and len(b) > 4 and (a.startswith(b[:5]) or b.startswith(a[:5]))):
                hits += 1
                break
    # fraction of ingredient food words found in the USDA description
    return min(1.0, hits / float(len(iset)))


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing or not usda:
            return 0.0

        ing_states = _extract_states(ing)
        usda_states = _extract_states(usda)

        raw_vec = _METHOD_SPACE["raw"]
        i_vec = _centroid(ing_states)
        u_vec = _centroid(usda_states)

        # Method agreement score in [0, 1]
        if i_vec is None and u_vec is None:
            method = 0.85
        elif i_vec is None:
            # unstated ingredient method: compatible with raw / generic
            d = _distance(raw_vec, u_vec)
            method = max(0.55, 0.9 - 0.25 * d)
        elif u_vec is None:
            # generic USDA entry: mostly compatible, but strong transformations unrepresented
            d = _distance(i_vec, raw_vec)
            method = max(0.2, 0.85 - 0.3 * d)
        else:
            d = _distance(i_vec, u_vec)
            method = math.exp(-1.8 * d)
            if set(ing_states) & set(usda_states):
                method = min(1.0, method + 0.1)

        # Explicit raw vs heat-processed conflict (e.g. raw fillet vs cooked fish)
        i_raw = any(_METHOD_SPACE.get(s, (1,))[0] == 0.0 for s in ing_states)
        u_raw = any(_METHOD_SPACE.get(s, (1,))[0] == 0.0 for s in usda_states)
        i_hot = any(_METHOD_SPACE.get(s, (0,))[0] > 0.2 for s in ing_states)
        u_hot = any(_METHOD_SPACE.get(s, (0,))[0] > 0.2 for s in usda_states)
        if (i_raw and u_hot and not u_raw) or (u_raw and i_hot and not i_raw):
            method *= 0.45

        anchor = _anchor_overlap(ing, usda)

        # Same food is a prerequisite; method agreement then orders candidates
        score = 100.0 * (0.1 + 0.9 * anchor) * (0.4 + 0.6 * method)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
