import re

# Form axes: each axis maps a canonical state to trigger words.
_AXES = {
    "temp": {
        "frozen": ["frozen", "freeze", "thawed", "thaw"],
        "canned": ["canned", "can", "tinned", "jarred", "bottled", "drained"],
        "dried": ["dried", "dry", "dehydrated", "powder", "powdered", "ground", "flakes", "freeze-dried"],
        "fresh": ["fresh", "raw", "uncooked"],
        "cooked": ["cooked", "boiled", "baked", "roasted", "fried", "toasted", "sauteed", "sautéed",
                   "steamed", "grilled", "braised", "prepared", "stewed", "simmered"],
    },
    "conc": {
        "paste": ["paste", "puree", "purée", "concentrate", "concentrated", "extract"],
        "juice": ["juice", "nectar", "drink", "beverage"],
        "soup": ["soup", "broth", "stock", "bouillon", "ready-to-serve", "condensed"],
        "sauce": ["sauce", "dressing", "gravy", "syrup", "spread"],
    },
    "proc": {
        "mix": ["mix", "instant", "ready-to-eat", "ready-to-bake", "ready-to-drink"],
        "whole": ["whole", "seeds", "leaves", "segments", "pieces"],
        "minced": ["minced", "chopped", "grated", "shredded", "sliced", "diced", "crushed"],
    },
}

_STOP = set("a an and of the with in from or for to on into without added nfs ns as s".split())
_PREP = set("fresh frozen canned dried dry raw cooked boiled baked roasted fried toasted thawed drained "
            "chopped minced sliced diced grated shredded whole fat small medium large extra skin lean "
            "only trimmed choice select prepared salt unsalted salted tube cup package pkg".split())


def _clean(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb|grams?)\b\s*", "", s)
    return s


def _forms(text):
    toks = set(re.findall(r"[a-zé\-]+", text))
    out = {}
    for axis, d in _AXES.items():
        found = set()
        for k, words in d.items():
            if any(w in toks for w in words):
                found.add(k)
        out[axis] = found
    return out


def _stem(w):
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _content(text):
    t = re.sub(r"\([^)]*\)", " ", text)
    return [_stem(w) for w in re.findall(r"[a-z]+", t) if w not in _STOP and w not in _PREP and len(w) > 1]


def judging_function(ingredient, usda_match):
    try:
        ing = _clean(str(ingredient))
        usda = (str(usda_match) or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0

        ing_main = ing.split(",")[0]
        fi, fu = _forms(ing), _forms(usda)

        # Ingredient content words vs USDA words (anchor so form score only matters for same food).
        ic = _content(ing_main)
        uc = set(_content(usda))
        if not ic:
            ic = _content(ing)
        cover = (sum(1 for w in ic if w in uc) / len(ic)) if ic else 0.0
        # Primary food of USDA (first comma segment) should appear in ingredient
        prim = set(_content(usda.split(",")[0]))
        icset = set(_content(ing))
        prim_hit = (len(prim & icset) / len(prim)) if prim else 0.0

        # Form agreement
        score = 0.0
        for axis, wt in (("temp", 3.0), ("conc", 3.5), ("proc", 1.5)):
            a, b = fi[axis], fu[axis]
            if a and b:
                if a & b:
                    score += wt
                elif axis == "temp" and (a | b) <= {"fresh", "cooked"} and "cooked" in a | b:
                    score -= wt * 1.2  # raw vs cooked changes texture
                else:
                    score -= wt
            elif a and not b:
                # ingredient states a form USDA does not state: mild
                score += 0.0 if axis != "conc" else -wt * 0.6
                if axis == "temp" and a == {"fresh"}:
                    score += wt * 0.3
            elif b and not a:
                # USDA imposes an unstated form: concentration / prepared forms are risky
                if axis == "conc":
                    score -= wt * 0.8
                elif axis == "temp" and "cooked" in b:
                    score -= wt * 0.6
                elif axis == "proc" and "mix" in b:
                    score -= wt * 0.8
                else:
                    score += wt * 0.15
            else:
                score += wt * 0.4  # both silent: forms recoverable

        total = score + 6.0 * cover + 4.0 * prim_hit
        if cover == 0 and prim_hit == 0:
            total -= 6.0
        return float(total)
    except Exception:
        return 0.0
