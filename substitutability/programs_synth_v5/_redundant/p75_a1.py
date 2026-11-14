import re

_NOISE = {"optional", "taste", "garnish", "for", "to", "of", "the", "a", "an", "and", "or", "with",
          "from", "in", "g", "kg", "oz", "ml", "tube", "fresh", "large", "small", "medium", "about",
          "nfs", "all", "varieties", "type", "made", "style", "serving", "warmed", "chopped",
          "sliced", "diced", "minced", "thawed", "melted", "softened", "crushed", "grated", "shelled"}
_FORM = {"dried", "dry", "frozen", "raw", "cooked", "roasted", "canned", "smoked", "powdered",
         "ground", "paste", "butter", "juice", "oil", "chips", "slices", "flour", "starch", "sauce",
         "pickled", "fermented", "boiled", "baked", "fried", "broiled", "salted", "unsalted",
         "sweetened", "unsweetened", "whole", "stewed", "steamed", "condensed", "evaporated",
         "instant", "refined", "pearls", "bran", "milk", "cream", "powder", "patties", "dehydrated"}
_ANTONYMS = [({"fat", "free", "lowfat", "low", "reduced", "nonfat"}, {"regular", "full", "whole"}),
             ({"salted"}, {"unsalted"}), ({"sweetened"}, {"unsweetened"}),
             ({"raw"}, {"cooked", "roasted", "boiled", "baked", "fried"}),
             ({"dried", "dry", "dehydrated"}, {"raw", "fresh"})]


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _tokens(s):
    s = s.lower()
    s = re.sub(r"\d+(\.\d+)?\s*(g|kg|oz|ml|lb|lbs|cups?|tbsp|tsp)\b", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?%?", " ", s)
    return [_stem(w) for w in re.findall(r"[a-z]+", s)]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "")
        usda = str(usda_match or "")
        ti = [t for t in _tokens(ing) if t not in _NOISE and _stem(t) not in _NOISE]
        tu_all = _tokens(usda)
        tu = set(tu_all)
        if not ti or not tu:
            return 0.0
        forms = {_stem(f) for f in _FORM}
        # first-segment head words of usda
        head = set(_tokens(usda.split(",")[0]))
        # split ingredient into core food tokens vs qualifiers
        core = [t for t in ti if t not in forms]
        qual = [t for t in ti if t in forms]
        # position weighting: later words in the main phrase (head noun) matter more
        total = 0.0
        got = 0.0
        n = len(core)
        for i, t in enumerate(core):
            w = 1.0 + 1.5 * (i + 1) / max(n, 1)
            total += w
            if t in tu:
                got += w * (1.0 if t in head else 0.8)
            else:
                # partial prefix credit
                if any(len(t) > 4 and (u.startswith(t[:5]) or t.startswith(u[:5])) for u in tu if len(u) > 4):
                    got += w * 0.5
        core_cov = got / total if total else 0.5
        # qualifier coverage
        if qual:
            qhit = sum(1 for q in qual if q in tu)
            qual_cov = qhit / len(qual)
        else:
            qual_cov = 1.0
        # extra usda content not in ingredient: head words extra
        extra_head = [t for t in head if t not in set(ti) and t not in _NOISE]
        extra_pen = min(len(extra_head), 3) * 0.12
        # extra usda descriptors that are material forms and absent from ingredient
        extra_forms = [t for t in tu if t in forms and t not in set(ti)]
        # raw/cooked defaults are mild
        mild = {_stem(x) for x in ("raw", "cooked", "boiled", "whole", "salted")}
        ef_pen = 0.05 * sum(1 for t in extra_forms if t in mild) + 0.12 * sum(1 for t in extra_forms if t not in mild)
        ef_pen = min(ef_pen, 0.4)
        # contradictions
        contra = 0
        sti = set(ti)
        for a, b in _ANTONYMS:
            a2 = {_stem(x) for x in a}
            b2 = {_stem(x) for x in b}
            if (sti & a2 and tu & b2 and not (tu & a2)) or (sti & b2 and tu & a2 and not (tu & b2)):
                contra += 1
        # low/fat-free in usda but not in ingredient
        if ({"free", "lowfat", "nonfat", "reduced", "low"} & tu) and not ({"free", "lowfat", "nonfat", "reduced", "low"} & sti):
            contra += 1
        score = 10.0 * (0.65 * core_cov + 0.35 * qual_cov)
        score *= (1.0 - extra_pen) * (1.0 - ef_pen)
        score -= 1.5 * contra
        if core_cov < 0.4:
            score *= 0.4
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
