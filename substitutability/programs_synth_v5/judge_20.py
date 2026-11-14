import re

_STATE = {"cooked", "raw", "dried", "dry", "frozen", "canned", "roasted", "boiled", "fried",
          "baked", "smoked", "pickled", "fresh", "toasted", "steamed", "simmered", "grilled",
          "broiled", "braised", "sweetened", "unsweetened", "salted", "unsalted", "powder",
          "ground", "mix", "juice", "leaves", "skin", "cured", "stewed"}
_NOISE = {"fat", "lean", "choice", "grade", "ns", "as", "to", "eaten", "includes", "include",
          "foods", "for", "usda", "usda's", "food", "distribution", "program", "separable",
          "trimmed", "inch", "imported", "new", "zealand", "enriched", "with", "and", "or",
          "of", "the", "a", "in", "from", "added", "no", "not", "without", "all", "grades",
          "mature", "seeds", "by", "products", "variety", "meats", "type", "style", "whole"}
_PREP = {"sliced", "diced", "chopped", "minced", "crumbled", "cubed", "thawed", "divided",
         "optional", "soaked", "overnight", "peeled", "grated", "shredded", "crushed",
         "finely", "roughly", "large", "small", "medium", "packed", "softened", "melted",
         "taste", "about", "plus", "extra", "more", "cut", "pieces", "piece", "halved",
         "rinsed", "drained", "washed", "trimmed", "visible"}
_FORM = {"cooked": "cook", "roasted": "cook", "boiled": "cook", "baked": "cook",
         "fried": "cook", "steamed": "cook", "simmered": "cook", "grilled": "cook",
         "broiled": "cook", "braised": "cook", "stewed": "cook",
         "dried": "dry", "dry": "dry", "raw": "raw", "fresh": "raw"}


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _toks(s):
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|oz|lb|ml|l)\b", " ", s)
    return [w for w in re.findall(r"[a-z]+", s) if w]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = str(ingredient or "")
        usda_raw = str(usda_match or "")
        ing_main = ing_raw.split(",")[0]
        ing_all = _toks(ing_raw)
        ing_main_t = _toks(ing_main)
        u_parts = usda_raw.split(",")
        u_all = _toks(usda_raw)
        if not ing_all or not u_all:
            return 0.0

        ing_core = [_stem(w) for w in ing_main_t if w not in _PREP and w not in _NOISE]
        ing_set = set(_stem(w) for w in ing_all if w not in _PREP and w not in _NOISE)
        u_set = set(_stem(w) for w in u_all if w not in _NOISE)
        u_head = set(_stem(w) for w in _toks(u_parts[0]) if w not in _NOISE)
        u_desc = set(_stem(w) for p in u_parts[1:] for w in _toks(p) if w not in _NOISE)

        if not ing_core:
            return 0.0

        # head noun: last core word of ingredient name
        head = ing_core[-1]
        head_hit = head in u_set
        head_first = head in u_head
        score = 5.0 if head_hit else 0.0
        if head_first:
            score += 1.0

        # dropped qualifiers: ingredient words missing in usda
        dropped = [w for w in ing_core if w not in u_set]
        dropped_w = 0.0
        for w in dropped:
            dropped_w += 1.5 if w in _STATE else 1.0
        if head_hit:
            dropped_w -= 0.0 if head not in dropped else 0.0

        # added qualifiers: usda descriptors/words not implied by ingredient
        added = [w for w in (u_desc | (u_head - set(ing_core))) if w not in ing_set]
        # trailing descriptors that are plain categories are less harmful
        added_w = 0.0
        for w in added:
            added_w += 1.2 if w in _STATE else 0.6
        added_w = min(added_w, 5.0)
        dropped_w = min(dropped_w, 5.0)

        # explicit processing-state conflict
        ing_states = {_FORM[w] for w in ing_all if w in _FORM}
        u_states = {_FORM[w] for w in u_all if w in _FORM}
        conflict = 0.0
        if ing_states and u_states and not (ing_states & u_states):
            conflict = 2.5
        elif u_states == {"cook"} and not ing_states:
            conflict = 1.0
        elif ing_states and not u_states and ing_states != {"raw"}:
            conflict = 1.0

        # generic-vs-specific alignment: ratio of usda specifics to ingredient specifics
        n_i, n_u = len(ing_set), len(u_set)
        balance = 1.0 - abs(n_i - n_u) / float(max(n_i, n_u, 1))

        score += 3.0 * balance - 0.9 * dropped_w - 0.8 * added_w - conflict
        return float(max(-10.0, min(12.0, score)))
    except Exception:
        return 0.0
