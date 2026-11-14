import re

_FORMS = {
    "frozen": ["frozen", "freezer", "thawed", "thaw"],
    "canned": ["canned", "can", "tinned", "drained"],
    "dried": ["dried", "dry", "dehydrated", "dessicated", "desiccated"],
    "powder": ["powder", "powdered", "ground", "flour", "granulated", "meal"],
    "paste": ["paste", "puree", "pureed", "concentrate", "concentrated"],
    "juice": ["juice", "nectar", "drink", "beverage"],
    "cooked": ["cooked", "braised", "roasted", "baked", "boiled", "fried", "grilled",
               "steamed", "broiled", "stewed", "pan", "sauteed", "toasted", "simmered"],
    "raw": ["raw", "fresh_"],
    "prepared": ["soup", "sauce", "mixture", "mix", "ready", "prepared", "substitute",
                 "imitation", "nfs", "dressing", "patty", "formed", "snacks"],
    "pickled": ["pickled", "jarred", "brined", "marinated", "pickles"],
}
_STOP = set("""a an the of and or with without in for to from as on at by style type nfs
raw fresh whole large small medium fine chopped diced sliced minced cubed crumbled trimmed
skin lean fat separable choice all grade nonfat g kg oz lb cup tbsp tsp pieces piece
equal parts part into cut""".split())


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)\b", " ", s)
    s = re.sub(r"\d+%?", " ", s)
    return s


def _forms(text):
    toks = set(re.findall(r"[a-z]+", text))
    out = set()
    for f, ws in _FORMS.items():
        for w in ws:
            if w in toks:
                out.add(f)
                break
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    ws = [_stem(w) for w in re.findall(r"[a-z]+", text)]
    return [w for w in ws if w not in _STOP and len(w) > 2 and w not in
            {f for l in _FORMS.values() for f in l}]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(ingredient)
        usda = _clean(usda_match)
        if not ing.strip() or not usda.strip():
            return 0.0
        ing_main = ing.split(",")[0]
        ing_state = ing[len(ing_main):]
        usda_parts = usda.split(",")
        usda_main = usda_parts[0]

        ci = _content(ing)
        cu = _content(usda)
        if not ci or not cu:
            return 1.0
        si, su = set(ci), set(cu)
        inter = si & su
        # coverage of ingredient food words by usda, and vice versa
        cov_i = len(inter) / len(si)
        cov_u = len(inter) / len(su)
        # head noun: last word of ingredient main vs usda primary food
        head_i = _content(ing_main)
        head_u = _content(usda_main)
        head_hit = 1.0 if (head_i and (head_i[-1] in su or (head_u and head_u[0] in si))) else 0.0

        fi = _forms(ing)
        fu = _forms(usda)
        # implicit raw: no form word means plain/raw
        proc = {"frozen", "canned", "dried", "powder", "paste", "juice", "cooked",
                "prepared", "pickled"}
        pi = fi & proc
        pu = fu & proc
        score = 0.0
        score += 4.0 * head_hit + 3.0 * cov_i + 1.5 * cov_u
        # form agreement
        shared = pi & pu
        score += 1.5 * len(shared)
        only_u = pu - pi
        only_i = pi - pu
        weights = {"frozen": 1.0, "canned": 1.5, "dried": 2.0, "powder": 1.2,
                   "paste": 1.5, "juice": 3.0, "cooked": 1.8, "prepared": 3.0,
                   "pickled": 1.5}
        for f in only_u:
            w = weights.get(f, 1.0)
            if f == "powder" and "ground" in usda and "ground" not in ing:
                w *= 0.4
            score -= w
        for f in only_i:
            score -= 0.7 * weights.get(f, 1.0)
        if not pi and not pu:
            score += 1.0
        # ingredient explicitly "fresh" vs usda processed
        if "fresh" in ing and (pu - {"frozen"} and "raw" not in fu):
            score -= 1.0
        # extra unmatched usda descriptors reduce the match mildly
        extra = len(su - si)
        score -= 0.25 * min(extra, 6)
        return float(score)
    except Exception:
        return 0.0
