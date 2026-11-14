import re

# Taste-impact ledger: every USDA token that the ingredient does not "pay for"
# is charged against a flavor budget. Additives cost most, processing states less,
# neutral catalog descriptors cost nothing.
_ADDITIVE_COST = {
    "salt": 2.5, "salted": 2.5, "sugar": 3.0, "sweetened": 3.0, "sweet": 1.5,
    "syrup": 3.0, "honey": 2.5, "sauce": 3.5, "gravy": 3.5, "breaded": 3.5,
    "batter": 3.0, "battered": 3.5, "seasoned": 3.0, "seasoning": 3.0,
    "flavored": 3.0, "flavor": 2.5, "pepper": 2.0, "butter": 2.5, "cheese": 2.5,
    "cream": 2.0, "creamed": 2.5, "glazed": 3.0, "candied": 3.0, "marinated": 3.0,
    "smoked": 2.5, "cured": 2.5, "pickled": 3.0, "brine": 2.0, "spiced": 2.5,
    "chocolate": 2.5, "vanilla": 2.0, "oil": 2.0, "fat": 1.0, "added": 2.0,
    "contains": 1.5, "mix": 2.5, "mixture": 3.0, "blend": 1.0, "souffle": 4.0,
    "cookies": 4.0, "cookie": 4.0, "sandwich": 3.0, "frozen": 1.0, "dessert": 3.0,
    "stuffed": 3.0, "filling": 3.0, "dressing": 3.0, "soup": 3.5, "stew": 3.5,
    "casserole": 3.5, "pie": 3.5, "cake": 3.5, "bread": 2.5,
}
_PROCESS_COST = {
    "cooked": 1.2, "boiled": 1.0, "simmered": 1.2, "roasted": 1.5, "toasted": 1.5,
    "fried": 2.0, "baked": 1.5, "broiled": 1.2, "grilled": 1.5, "braised": 1.5,
    "stewed": 1.5, "steamed": 0.8, "canned": 1.2, "dried": 0.8, "dehydrated": 1.2,
    "ground": 1.0, "powder": 1.5, "powdered": 1.5, "reduced": 1.5, "lowfat": 1.0,
    "nonfat": 1.5, "light": 1.0, "low": 0.8, "sodium": 1.0, "free": 1.0,
    "gluten": 1.5, "drained": 0.3, "microwaved": 1.0, "concentrate": 2.0,
    "juice": 2.0, "instant": 1.5,
}
_NEUTRAL = {
    "raw", "fresh", "unprepared", "plain", "regular", "whole", "meat", "only",
    "and", "or", "with", "without", "of", "the", "a", "in", "by", "products",
    "variety", "meats", "broilers", "fryers", "prepackaged", "deli", "luncheon",
    "ready", "to", "eat", "solids", "liquids", "all", "types", "commercial",
    "fortified", "vitamin", "d", "skin", "not", "includes", "type", "style",
    "globe", "french", "no", "nfs", "usda", "cereals", "spices", "nuts", "ns",
}
_PREP = {
    "chopped", "sliced", "diced", "minced", "shredded", "grated", "thawed",
    "peeled", "crushed", "halved", "cubed", "trimmed", "rinsed", "washed",
    "segments", "pulp", "seeds", "large", "small", "medium", "pieces", "piece",
    "fine", "finely", "thin", "thinly", "lunch", "tube", "from",
}
# Ingredient words that pre-authorize particular charges.
_IMPLIES = {
    "toasted": {"roasted", "toasted", "dried"},
    "roasted": {"roasted", "toasted"},
    "fried": {"fried", "oil"},
    "cooked": {"cooked", "boiled", "simmered", "drained", "steamed"},
    "deli": {"deli", "luncheon", "prepackaged", "cured", "smoked"},
    "lunch": {"deli", "luncheon", "prepackaged", "cured"},
    "sliced": set(),
    "ground": {"ground", "powder", "powdered"},
    "frozen": {"frozen"},
    "lowfat": {"lowfat", "low", "fat", "reduced"},
    "dried": {"dried", "dehydrated"},
}


def _stem(w):
    try:
        w = w.lower()
        for suf in ("ies", "es", "s"):
            if len(w) > 4 and w.endswith(suf):
                if suf == "ies":
                    return w[:-3] + "y"
                if suf == "es" and w[-3:-2] in ("s", "x", "h"):
                    return w[:-2]
                if suf == "s" and not w.endswith("ss"):
                    return w[:-1]
        return w
    except Exception:
        return w


def _clean_ingredient(text):
    t = str(text or "").lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", t)
    t = re.sub(r"[^a-z\s,-]", " ", t)
    t = t.replace("-", " ")
    return t


def _words(text):
    return [w for w in re.split(r"[\s,]+", text) if w]


def judging_function(ingredient, usda_match):
    try:
        ing_raw = _clean_ingredient(ingredient)
        usda_raw = re.sub(r"[^a-z\s,-]", " ", str(usda_match or "").lower()).replace("-", " ")
        ing_words = _words(ing_raw)
        if not ing_words or not usda_raw.strip():
            return 0.0

        ing_stems = {_stem(w) for w in ing_words}
        ing_set = set(ing_words)
        allowed = set()
        for w in ing_words:
            allowed |= _IMPLIES.get(w, set())

        segments = [s.strip() for s in usda_raw.split(",") if s.strip()]
        if not segments:
            return 0.0
        usda_words = _words(usda_raw)

        # ---- Identity: does the primary food (first segment, or first two) match?
        content_ing = [_stem(w) for w in ing_words
                       if w not in _PREP and w not in _NEUTRAL
                       and w not in _PROCESS_COST and w not in _ADDITIVE_COST]
        if not content_ing:
            content_ing = [_stem(w) for w in ing_words if w not in _NEUTRAL] or [_stem(ing_words[-1])]
        head_words = set()
        for seg in segments[:2]:
            head_words |= {_stem(w) for w in _words(seg)}
        all_usda_stems = {_stem(w) for w in usda_words}

        def _hit(s, pool):
            if s in pool:
                return True
            for p in pool:
                if len(s) >= 4 and len(p) >= 4 and (p.startswith(s[:4]) and s.startswith(p[:4])):
                    if abs(len(s) - len(p)) <= 3:
                        return True
            return False

        head_hits = sum(1 for s in content_ing if _hit(s, head_words))
        any_hits = sum(1 for s in content_ing if _hit(s, all_usda_stems))
        identity = (0.65 * head_hits + 0.35 * any_hits) / float(len(content_ing))
        first_seg_hit = any(_hit(_stem(w), set(content_ing)) for w in _words(segments[0]))

        # ---- Charge ledger for unpaid USDA tokens
        charge = 0.0
        unknown = 0
        for w in usda_words:
            s = _stem(w)
            if w in ing_set or s in ing_stems or w in allowed:
                continue
            if w in _NEUTRAL:
                continue
            if w in _ADDITIVE_COST:
                charge += _ADDITIVE_COST[w]
            elif s in _ADDITIVE_COST:
                charge += _ADDITIVE_COST[s]
            elif w in _PROCESS_COST:
                charge += _PROCESS_COST[w]
            elif len(w) > 2:
                unknown += 1
        # Unknown extra words: brand names, other foods => compound risk
        charge += 0.9 * min(unknown, 5)

        # "with X" / "and X" in the USDA that ingredient lacks: compound food
        for m in re.finditer(r"\b(with|and)\s+([a-z]+)", usda_raw):
            tgt = m.group(2)
            if _stem(tgt) not in ing_stems and tgt not in _NEUTRAL and tgt != "salt":
                charge += 1.0

        # Ingredient specifies a state the USDA contradicts (e.g. fresh vs frozen/cooked)
        if "fresh" in ing_set and any(w in usda_words for w in ("frozen", "canned", "cooked", "dried")):
            charge += 1.5

        # Ingredient asks for a modifier that USDA lacks (toasted, flavored...) - mild penalty
        missing_mod = 0.0
        for w in ing_words:
            if w in _ADDITIVE_COST or w in ("toasted", "roasted", "smoked", "fried"):
                if w not in usda_words and _stem(w) not in all_usda_stems:
                    if not (allowed & set(usda_words)):
                        missing_mod += 1.0
        charge += missing_mod

        # ---- Combine: identity gates everything; flavor budget decays the score
        budget = 1.0 / (1.0 + 0.22 * charge)
        score = 100.0 * (0.25 + 0.75 * identity) * budget
        if not first_seg_hit:
            score *= 0.6
        if identity == 0:
            score = min(score, 8.0)
        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
