import re

_AXES = {
    "color": ["red", "green", "yellow", "white", "black", "brown", "purple", "orange", "golden", "blue", "pink"],
    "fat": ["whole", "skim", "nonfat", "non-fat", "lowfat", "low-fat", "reduced", "fat-free", "lean", "full-fat", "light"],
    "sweet": ["sweet", "unsweetened", "sweetened", "sour", "bitter", "salted", "unsalted"],
    "state": ["raw", "cooked", "dried", "dehydrated", "frozen", "canned", "fresh", "smoked", "roasted", "fried", "boiled", "pickled", "baked"],
    "part": ["breast", "thigh", "leg", "wing", "loin", "rib", "shoulder", "belly", "heart", "liver", "kidney", "tail", "seeds", "seed", "leaves", "root", "skin", "bone", "bones", "flour", "oil", "starch", "juice", "powder", "paste", "sauce", "syrup"],
    "form": ["ground", "minced", "whole", "chopped", "sliced", "diced", "paste", "powder", "flakes", "chips"],
    "diet": ["vegan", "plant-based", "tofu", "soy", "almond", "coconut", "oat", "rice", "dairy", "nut"],
    "type": ["greek", "wild", "brown", "basmati", "jasmine", "cheddar", "mozzarella", "parmesan", "olive", "maple", "cane", "granulated", "powdered", "confectioners", "vanilla", "chocolate", "lemon", "lime"],
}
_SYN = {"non-fat": "nonfat", "fat-free": "nonfat", "skim": "nonfat", "low-fat": "lowfat", "plant-based": "vegan",
        "seed": "seeds", "bones": "bone", "dehydrated": "dried", "linseeds": "flaxseed", "linseed": "flaxseed"}
_STOP = set("a an and or of the with in for from to into as at by on fresh large small medium thin thick pieces piece cold hot warm chilled thawed serving serve optional taste about extra nfs".split())


def _clean(s, drop_paren=True):
    s = (s or "").lower()
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|ml|l|oz|lb|grams?)?\b\s*", "", s)
    if drop_paren:
        s = re.sub(r"\([^)]*\)", " ", s)
    return s


def _toks(s):
    out = []
    for t in re.findall(r"[a-z][a-z\-]*", s):
        t = _SYN.get(t, t)
        if len(t) > 3 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def _axis_values(toks):
    res = {}
    tset = set(toks)
    for ax, vals in _AXES.items():
        found = set()
        for v in vals:
            v = _SYN.get(v, v)
            if len(v) > 3 and v.endswith("s") and not v.endswith("ss"):
                v = v[:-1]
            if v in tset:
                found.add(v)
        if found:
            res[ax] = found
    return res


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean(ingredient)
        usda_raw = _clean(usda_match)
        if not ing_raw.strip() or not usda_raw.strip():
            return 0.0
        parts = ing_raw.split(",")
        ing_main = _toks(parts[0])
        ing_post = _toks(" ".join(parts[1:]))
        ing_all = ing_main + ing_post
        usda_parts = usda_raw.split(",")
        usda_head = _toks(usda_parts[0])
        usda_all = _toks(usda_raw)

        ing_c = [t for t in ing_all if t not in _STOP]
        usda_c = [t for t in usda_all if t not in _STOP]
        if not ing_c or not usda_c:
            return 0.0

        # 1. head noun agreement: last content word of ingredient main phrase vs usda tokens
        main_c = [t for t in ing_main if t not in _STOP] or ing_c
        head = main_c[-1]
        us = set(usda_c)
        score = 0.0
        head_hit = head in us
        score += 4.0 if head_hit else 0.0
        if head_hit and usda_head and head in usda_head:
            score += 1.0
        # 2. coverage of ingredient content words in usda
        cov = sum(1 for t in set(main_c) if t in us) / float(len(set(main_c)))
        score += 3.0 * cov
        # 3. qualifier-axis agreement
        ia = _axis_values(ing_all)
        ua = _axis_values(usda_all)
        pen = 0.0
        bonus = 0.0
        for ax, vals in ia.items():
            if ax in ua:
                if vals & ua[ax]:
                    bonus += 1.0
                else:
                    pen += {"color": 2.5, "fat": 2.0, "sweet": 2.5, "part": 3.0, "diet": 2.5, "type": 2.0}.get(ax, 1.5)
            else:
                if ax in ("part", "diet", "color"):
                    pen += 0.8
        for ax, vals in ua.items():
            if ax not in ia:
                # usda adds a qualifier the recipe never mentioned
                if ax in ("diet", "part", "sweet"):
                    pen += 1.2
                elif ax == "state" and vals & {"dried", "smoked", "pickled", "canned"}:
                    pen += 1.0
        # added ingredients in usda description
        extra_flags = ["fat added", "added", "imported", "made with", "nfs"]
        for f in extra_flags:
            if f in usda_raw and f not in ing_raw:
                pen += 0.8 if f != "nfs" else 1.2
        # 4. unmatched content words of usda main phrase (different food)
        u_head_c = [t for t in usda_head if t not in _STOP]
        if u_head_c and not (set(u_head_c) & set(ing_c)):
            pen += 2.0
        # parenthetical hints of non-food-use (seeds for serving etc.)
        score += min(bonus, 3.0) * 0.5 - pen
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
