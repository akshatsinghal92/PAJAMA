import re

_ATTRS = {
    "salt": ({"unsalted", "saltfree", "nosalt", "withoutsalt", "lowsodium", "sodiumfree"}, {"salted", "withsalt", "saltadded"}),
    "sweet": ({"unsweetened", "nosugar", "sugarfree", "nosugaradded", "withoutsugar"}, {"sweetened", "sugared", "sugaradded", "sugar"}),
    "skin": ({"skinless", "withoutskin", "noskin"}, {"skinon", "withskin", "skin"}),
    "bone": ({"boneless", "withoutbone", "nobone"}, {"bonein", "withbone", "bone", "bones"}),
    "seed": ({"seedless", "withoutseeds", "noseeds", "pitted"}, {"seeded", "withseeds", "seeds", "unpitted"}),
    "hull": ({"hulled", "shelled", "dehulled"}, {"unhulled", "unshelled", "inshell", "inshell"}),
    "caf": ({"decaffeinated", "decaf", "caffeinefree"}, {"caffeinated", "regular"}),
    "fat": ({"nonfat", "fatfree", "lowfat", "reducedfat", "skim", "lightfat", "lean", "nofat"}, {"wholefat", "fullfat", "regularfat", "wholemilk", "fatadded", "withfat", "whole"}),
    "cook": ({"raw", "uncooked", "fresh"}, {"cooked", "boiled", "roasted", "fried", "baked", "steamed", "grilled"}),
    "dry": ({"fresh", "raw"}, {"dried", "dehydrated"}),
    "froz": ({"fresh", "canned"}, {"frozen"}),
    "alc": ({"nonalcoholic", "alcoholfree"}, {"alcoholic"}),
    "gluten": ({"glutenfree"}, {"wheat"}),
    "drain": ({"drained"}, {"undrained", "liquidsincluded"}),
}
_STOP = {"and", "or", "of", "the", "a", "with", "in", "from", "for", "to", "style", "type", "nfs", "ns", "made",
         "g", "kg", "oz", "ml", "cup", "cups", "tbsp", "tsp", "added", "all", "kinds", "brand", "pieces", "piece"}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", s)
    s = s.replace("-", "").replace("’", "").replace("'", "")
    s = re.sub(r"\bno\s+added\s+(\w+)", r"no\1", s)
    s = re.sub(r"\b(no|without|non)\s+(\w+)", r"\1\2", s)
    s = re.sub(r"\b(\w+)\s+free\b", r"\1free", s)
    s = re.sub(r"\b(\w+)\s+added\b", r"\1added", s)
    s = re.sub(r"\bwith\s+(\w+)", r"with\1", s)
    s = re.sub(r"\breduced\s+fat\b", "reducedfat", s)
    s = re.sub(r"\blow\s+fat\b", "lowfat", s)
    s = re.sub(r"\bfat\s+free\b", "fatfree", s)
    s = re.sub(r"\bsalt\s+free\b", "saltfree", s)
    s = re.sub(r"\bin\s+shell\b", "inshell", s)
    s = re.sub(r"\bbone\s+in\b", "bonein", s)
    s = re.sub(r"\bskin\s+on\b", "skinon", s)
    return s


def _tokens(s):
    return re.findall(r"[a-z0-9]+", s)


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(str(ingredient))
        usd = _norm(str(usda_match))
        it, ut = set(_tokens(ing)), set(_tokens(usd))
        if not it or not ut:
            return 0.0

        contradictions = 0.0
        agreements = 0.0
        for name, (neg, pos) in _ATTRS.items():
            in_neg, in_pos = bool(it & neg), bool(it & pos)
            us_neg, us_pos = bool(ut & neg), bool(ut & pos)
            # negation prefix generic detection handled via sets; resolve ambiguous
            if in_neg and in_pos:
                continue
            if us_neg and us_pos:
                continue
            if (in_neg and us_pos) or (in_pos and us_neg):
                w = 2.0 if name in ("salt", "sweet", "skin", "bone", "seed", "hull", "caf", "fat", "alc") else 0.8
                contradictions += w
            elif (in_neg and us_neg) or (in_pos and us_pos):
                agreements += 1.0

        # generic un-X / X mismatch
        for w in it:
            if w.startswith("un") and len(w) > 4 and w[2:] in ut:
                contradictions += 1.5
        for w in ut:
            if w.startswith("un") and len(w) > 4 and w[2:] in it:
                contradictions += 1.5

        # content overlap on food words (needed so unrelated foods do not score neutral-high)
        ic = {_stem(w) for w in it if w not in _STOP and not w.isdigit() and len(w) > 2}
        uc = {_stem(w) for w in ut if w not in _STOP and not w.isdigit() and len(w) > 2}
        if not ic or not uc:
            return 0.0
        inter = ic & uc
        recall = len(inter) / len(ic)
        precision = len(inter) / len(uc)
        # head noun: first USDA token vs any ingredient token
        utoks = [_stem(w) for w in _tokens(usd) if w not in _STOP and len(w) > 2]
        head = 1.0 if utoks and utoks[0] in ic else 0.0
        if head == 0.0 and utoks:
            head = 0.5 if any(t in ic for t in utoks[:2]) else 0.0

        overlap = 0.5 * recall + 0.25 * precision + 0.25 * head
        score = 10.0 * overlap + 1.0 * min(agreements, 3) - 4.0 * contradictions
        if not inter:
            score -= 3.0
        return float(max(-20.0, min(15.0, score)))
    except Exception:
        return 0.0
