import re

# Variant 3: slot-based coverage. The ingredient is decomposed into a HEAD
# (the core food, weighted heavily) and typed QUALIFIER slots (form, state,
# processing, variety). Each slot is resolved against the USDA description as
# covered / neutral / contradicted using stem matching and conflict groups.
# Score = weighted coverage ratio minus contradiction and unrequested-modifier
# penalties, mapped to 0-100.

_NOTES = {"optional", "taste", "garnish", "serving", "divided", "needed",
          "about", "approximately", "plus", "more", "extra", "for", "to",
          "of", "and", "or", "the", "a", "an", "with", "from", "in", "into",
          "some", "fresh", "freshly", "good", "quality", "large", "small",
          "medium", "pieces", "piece", "tube", "jar", "can", "pack", "package",
          "warmed", "warm", "chilled", "cold", "room", "temperature",
          "thawed", "drained", "rinsed", "trimmed", "patted", "dry_",
          "nfs", "ns", "all", "varieties", "type", "style", "made", "salad",
          "cooking", "only", "meat", "separable", "lean", "fat"}

_PREP_ONLY = {"chopped", "diced", "minced", "sliced", "cubed", "grated",
              "shredded", "peeled", "halved", "quartered", "crushed",
              "julienned", "torn", "cut", "finely", "roughly", "thinly",
              "coarsely", "beaten", "whisked", "softened", "melted", "packed",
              "leaves", "leaf", "shelled", "pitted", "seeded", "deveined"}

# qualifier type -> weight
_FORM = {"butter", "paste", "powder", "flour", "oil", "juice", "sauce",
         "chips", "chip", "flakes", "puree", "syrup", "jam", "jelly",
         "milk", "cream", "starch", "pearls", "meal", "extract", "concentrate",
         "patties", "patty", "bran", "seeds", "nuts", "ground", "whole",
         "mayonnaise", "spread", "broth", "stock", "soup"}
_STATE = {"raw", "cooked", "frozen", "dried", "dry", "canned", "fermented",
          "pickled", "smoked", "roasted", "toasted", "fried", "boiled",
          "steamed", "baked", "grilled", "broiled", "braised", "salted",
          "unsalted", "sweetened", "unsweetened", "cured", "fresh_"}
_SPECIAL = {"lowfat", "nonfat", "fatfree", "lowsodium", "light", "reduced",
            "diet", "organic", "oilroasted", "dryroasted", "skim"}

_CONFLICTS = [
    {"raw", "cooked", "roasted", "fried", "boiled", "baked", "grilled",
     "broiled", "steamed", "toasted", "braised", "smoked"},
    {"dried", "raw_fresh"},
    {"salted", "unsalted"},
    {"sweetened", "unsweetened"},
    {"oilroasted", "dryroasted"},
    {"lowfat", "nonfat", "fatfree", "whole_fat", "regular"},
    {"butter", "paste", "powder", "flour", "oil", "juice", "chips",
     "mayonnaise", "puree", "syrup", "flakes", "starch"},
]

# USDA-side modifiers the cook did not ask for that alter the food
_UNREQUESTED = {"lowfat", "nonfat", "fatfree", "lowsodium", "reduced",
                "light", "diet", "mountain", "hawaii", "made",
                "with", "mayonnaise", "imitation", "substitute", "skim"}

# loose equivalences between ingredient words and USDA words
_ALIASES = {
    "flats": {"wing", "wings"}, "drumettes": {"wing", "wings"},
    "pinyon": {"pine", "pinon"}, "pine": {"pinyon", "pinon"},
    "chard": {"swiss"}, "garbanzo": {"chickpea", "chickpeas"},
    "chickpea": {"garbanzo"}, "scallion": {"onion", "onions", "green"},
    "cilantro": {"coriander"}, "coriander": {"cilantro"},
    "shank": {"leg"}, "patties": {"patty"}, "patty": {"patties"},
    "frozen": {"raw"},
}


def _stem(w):
    w = w.lower()
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and w[-3] in "sxz":
                return w[:-2]
            if suf == "s" and not w.endswith("ss"):
                return w[:-1]
    return w


def _normalize(text):
    t = (text or "").lower()
    t = t.replace("low fat", "lowfat").replace("low-fat", "lowfat")
    t = t.replace("non-fat", "nonfat").replace("non fat", "nonfat")
    t = t.replace("fat free", "fatfree").replace("fat-free", "fatfree")
    t = t.replace("low sodium", "lowsodium").replace("low-sodium", "lowsodium")
    t = t.replace("reduced sodium", "lowsodium")
    t = t.replace("oil-roasted", "oilroasted").replace("oil roasted", "oilroasted")
    t = t.replace("dry roasted", "dryroasted").replace("dry-roasted", "dryroasted")
    t = t.replace("raw or frozen", "raw")
    return t


def _clean_ingredient(text):
    t = _normalize(text)
    t = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)\b\.?", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|oz|lb)\b", " ", t)
    t = re.sub(r"\bto taste\b|\bfor garnish\b|\bfor serving\b|\boptional\b", " ", t)
    return t


def _tokens(text):
    return [w for w in re.findall(r"[a-z]+", text) if len(w) > 1]


def _classify(w):
    if w in _SPECIAL:
        return "special", 1.4
    if w in _FORM:
        return "form", 1.5
    if w in _STATE:
        return "state", 1.1
    return "variety", 1.0


def _present(word, ustems, uwords):
    s = _stem(word)
    if s in ustems or word in uwords:
        return True
    for a in _ALIASES.get(word, ()):
        if a in uwords or _stem(a) in ustems:
            return True
    for u in ustems:
        if len(s) >= 5 and len(u) >= 5 and (u.startswith(s[:5]) or s.startswith(u[:5])):
            return True
    return False


def _group_of(w):
    for i, g in enumerate(_CONFLICTS):
        if w in g:
            return i
    return None


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        usda = _normalize(str(usda_match))

        # split ingredient: main phrase vs post-comma / parenthetical details
        paren = " ".join(re.findall(r"\(([^)]*)\)", ing))
        main = re.sub(r"\([^)]*\)", " ", ing)
        parts = main.split(",")
        main_phrase = parts[0]
        tail = " ".join(parts[1:]) + " " + paren

        main_toks = [w for w in _tokens(main_phrase) if w not in _NOTES]
        tail_toks = [w for w in _tokens(tail)
                     if w not in _NOTES and w not in _PREP_ONLY]
        if not main_toks:
            main_toks = _tokens(main_phrase) or _tokens(ing)
        if not main_toks:
            return 0.0

        utoks = _tokens(usda)
        uwords = set(utoks)
        ustems = {_stem(w) for w in utoks}
        uhead = utoks[0] if utoks else ""

        # head is the final non-prep word of the main phrase; for compounds
        # joined by "and" every food noun counts as a head.
        segments = re.split(r"\band\b|&", main_phrase)
        heads = []
        for seg in segments:
            st = [w for w in _tokens(seg) if w not in _NOTES and w not in _PREP_ONLY]
            if st:
                heads.append(st[-1])
        if not heads:
            heads = [main_toks[-1]]
        head_set = set(heads)

        quals = [w for w in main_toks if w not in head_set and w not in _PREP_ONLY]
        quals += [w for w in tail_toks if w not in head_set]

        # A form word acting as head (e.g. "pecan butter") makes the
        # preceding word a required food slot as well.
        for h in list(heads):
            if h in _FORM:
                idx = main_toks.index(h) if h in main_toks else -1
                if idx > 0:
                    prev = main_toks[idx - 1]
                    if prev not in head_set:
                        head_set.add(prev)
                        if prev in quals:
                            quals.remove(prev)

        total_w = 0.0
        got_w = 0.0
        contradictions = 0.0
        head_hits = 0
        for h in head_set:
            hw = 4.0 if h not in _FORM else 3.0
            total_w += hw
            if _present(h, ustems, uwords):
                got_w += hw
                head_hits += 1

        ing_set = set(main_toks) | set(tail_toks)
        for q in dict.fromkeys(quals):
            kind, w = _classify(q)
            total_w += w
            if _present(q, ustems, uwords):
                got_w += w
                continue
            g = _group_of(q)
            if g is not None and any(_group_of(u) == g and u != q for u in uwords):
                contradictions += w * 1.6
            elif kind == "variety" and q.endswith("ed"):
                got_w += w * 0.3  # likely a soft prep descriptor
            # else: unaccounted qualifier, no credit

        # USDA-side form words absent from the ingredient that conflict
        for u in uwords:
            g = _group_of(u)
            if g is not None and u not in ing_set:
                if any(_group_of(i) == g for i in ing_set):
                    contradictions += 0.6  # paired with ingredient conflict
                elif u in _FORM and g == len(_CONFLICTS) - 1:
                    contradictions += 1.5  # food turned into a different form

        unreq = sum(1 for u in uwords if u in _UNREQUESTED and u not in ing_set)

        coverage = got_w / total_w if total_w else 0.0
        head_ratio = head_hits / max(1, len(head_set))

        score = 100.0 * (0.35 * head_ratio + 0.65 * coverage)
        if head_hits == 0:
            score *= 0.25
        # primary USDA food should correspond to an ingredient food word
        if uhead and not any(_present(w, {_stem(uhead)}, {uhead}) for w in ing_set):
            score -= 8.0
        score -= 14.0 * contradictions
        score -= 12.0 * unreq
        # long USDA entries with many unmatched descriptors dilute a little
        unmatched_u = sum(1 for u in utoks if not _present(u, {_stem(x) for x in ing_set}, ing_set))
        score -= 1.2 * max(0, unmatched_u - 3)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
