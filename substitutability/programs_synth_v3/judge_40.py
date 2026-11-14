import re

# Qualifier ledger: each qualifier belongs to a "facet". A diner notices a change
# when the USDA entry asserts a different value on a facet than the ingredient,
# or asserts a noticeable value the ingredient never implied.
_FACETS = {
    "flavor_variant": ({"maple", "brown", "powdered", "confectioners", "honey", "molasses",
                        "smoked", "spicy", "hot", "sweetened", "unsweetened", "salted",
                        "unsalted", "flavored", "vanilla", "chocolate", "cinnamon",
                        "garlic", "lemon", "barbecue", "bbq", "teriyaki", "sour", "sweet",
                        "tart", "extra", "virgin", "light", "dark", "white", "red",
                        "yellow", "green", "black"}, 3.0),
    "fat_level": ({"lowfat", "nonfat", "skim", "reduced", "lite", "whole", "fat",
                   "added", "lean", "fatfree"}, 2.5),
    "form": ({"seeds", "seed", "juice", "peel", "powder", "paste", "dried", "dehydrated",
              "canned", "concentrate", "flakes", "syrup", "extract", "oil", "sauce",
              "puree", "patty", "nuggets", "breaded", "fried", "sticks", "chips"}, 3.5),
    "cooking": ({"cooked", "boiled", "baked", "roasted", "grilled", "braised", "stewed",
                 "steamed", "microwaved", "broiled", "sauteed", "fried"}, 1.5),
    "diet": ({"vegan", "tofu", "soy", "vegetarian", "imitation", "meatless", "gluten",
              "glutenfree", "dairy", "almond", "oat", "coconut", "rice"}, 2.0),
}

# Words that never change what a diner perceives (USDA bookkeeping / prep).
_NEUTRAL = {
    "raw", "fresh", "frozen", "thawed", "cold", "chilled", "uncooked", "cubed", "diced",
    "chopped", "sliced", "minced", "grated", "shredded", "peeled", "trimmed", "boneless",
    "skinless", "separable", "and", "with", "without", "of", "the", "a", "in", "for",
    "from", "made", "only", "all", "varieties", "commercial", "prepared", "imported",
    "domestic", "new", "zealand", "usda", "commodity", "ns", "as", "to", "or", "nfs",
    "includes", "serving", "garnish", "optional", "tube", "large", "small", "medium",
    "granulated", "regular", "plain", "drained", "solids", "liquids", "packed", "pack",
    "type", "style", "mature", "kernels", "top", "loin", "chops", "chop", "cut", "pieces",
    "piece", "ground", "bone", "skin", "meat", "edible", "portion", "retail", "choice",
    "select", "grade", "cuts", "trimmed", "inch", "approx", "about", "taste",
}

_FORM_FACET = "form"


def _stem(w):
    try:
        for suf, rep in (("ies", "y"), ("oes", "o"), ("ses", "s"), ("es", "e"), ("s", "")):
            if len(w) > 4 and w.endswith(suf):
                cand = w[: -len(suf)] + rep
                return cand
        return w
    except Exception:
        return w


def _clean_ingredient(text):
    t = text.lower()
    paren = " ".join(re.findall(r"\(([^)]*)\)", t))
    t = re.sub(r"\([^)]*\)", " ", t)
    parts = t.split(",", 1)
    main = parts[0]
    state = parts[1] if len(parts) > 1 else ""
    main = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", main)
    return main, state + " " + paren


def _tokens(text):
    return [_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 1]


def _facet_map(tokens):
    out = {}
    for t in tokens:
        for name, (vocab, _w) in _FACETS.items():
            if t in vocab or _stem(t) in {_stem(v) for v in vocab}:
                out.setdefault(name, set()).add(t)
    return out


def _core(tokens):
    facet_words = set()
    for vocab, _w in _FACETS.values():
        facet_words |= {_stem(v) for v in vocab}
    return [t for t in tokens if t not in _NEUTRAL and t not in facet_words]


def _fuzzy_in(word, pool):
    for p in pool:
        if word == p:
            return 1.0
        if len(word) >= 4 and len(p) >= 4 and (word.startswith(p[:4]) and p.startswith(word[:4])):
            return 0.8
        if len(word) >= 5 and (word in p or p in word):
            return 0.7
    return 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing_main, ing_extra = _clean_ingredient(str(ingredient))
        ing_tok = _tokens(ing_main)
        ing_extra_tok = _tokens(ing_extra)
        usda_tok = _tokens(str(usda_match))
        if not ing_tok or not usda_tok:
            return 0.0

        # Step 1: identity anchor -- the USDA primary food (first segment) must be
        # recognised in the ingredient head.
        usda_primary = _tokens(str(usda_match).split(",")[0])
        ing_core = _core(ing_tok) or ing_tok
        usda_core = _core(usda_tok)
        primary_core = [t for t in usda_primary if t not in _NEUTRAL] or usda_primary

        anchor = max([_fuzzy_in(t, ing_tok) for t in primary_core] + [0.0])
        if anchor == 0.0:
            # maybe the head noun sits later in USDA (e.g. "Pork, fresh, loin")
            anchor = 0.5 * max([_fuzzy_in(t, usda_tok) for t in ing_core] + [0.0])

        # Step 2: core coverage both ways (dropped vs added substantive words).
        covered = sum(_fuzzy_in(t, usda_tok) for t in ing_core) / max(len(ing_core), 1)
        extra_core = [t for t in usda_core if _fuzzy_in(t, ing_tok + ing_extra_tok) == 0.0]

        # Step 3: facet ledger comparison.
        ing_f = _facet_map(ing_tok)
        ing_f_extra = _facet_map(ing_extra_tok)
        usda_f = _facet_map(usda_tok)
        penalty = 0.0
        bonus = 0.0
        for name, (_vocab, weight) in _FACETS.items():
            a = ing_f.get(name, set())
            b = usda_f.get(name, set())
            soft = ing_f_extra.get(name, set())
            if a and b:
                if {_stem(x) for x in a} & {_stem(x) for x in b}:
                    bonus += weight * 0.6  # ingredient specified a variant and USDA honours it
                else:
                    penalty += weight * 1.2  # conflicting variant
            elif b and not a:
                if soft & b:
                    continue
                # USDA adds a qualifier the ingredient did not imply
                if name == "diet" and "vegan" in a:
                    continue
                penalty += weight * (0.9 if name != "cooking" else 0.5)
            elif a and not b:
                # ingredient demanded a variant, USDA is generic
                if name == "diet" and ("tofu" in usda_tok or "soy" in usda_tok):
                    continue
                penalty += weight * 0.7

        # Form in a parenthetical / post-comma that is not in USDA ("papaya seeds")
        # is already captured by core coverage; nothing extra here.

        # Step 4: generic-ness reward. An unqualified ingredient matched by a short,
        # qualifier-light USDA entry is ideal.
        n_ing_qual = sum(len(v) for v in ing_f.values())
        n_usda_qual = sum(len(v) for v in usda_f.values())
        if n_ing_qual == 0 and n_usda_qual == 0:
            bonus += 1.5

        score = 3.0 * anchor + 4.0 * covered + bonus
        score -= penalty
        score -= 0.6 * min(len(extra_core), 4)
        score = max(0.0, min(10.0, score))
        return round(score, 3)
    except Exception:
        return 0.0
