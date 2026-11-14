import re

_PREP = {"fresh", "frozen", "cooked", "raw", "chopped", "sliced", "diced", "minced", "warmed",
         "toasted", "sifted", "thawed", "optional", "large", "small", "medium", "dried", "ground",
         "lean", "strong", "brewed", "wild", "foraged", "lowfat", "and", "or", "of", "with", "the",
         "a", "from", "tube", "leaves", "leaf", "g", "kg", "oz", "ml", "whole", "boneless", "skinless"}
_GENERIC = {"nfs", "ns", "as", "to", "all", "varieties", "type", "commercial", "regular", "raw",
            "cooked", "mixed", "species", "major", "flour", "salad", "cooking"}


def _stem(w):
    try:
        for suf in ("ies",):
            if w.endswith(suf) and len(w) > 4:
                return w[:-3] + "y"
        if w.endswith("oes") and len(w) > 4:
            return w[:-2]
        if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            return w[:-1]
        return w
    except Exception:
        return w


def _toks(s):
    return [_stem(t) for t in re.findall(r"[a-z]+", s.lower())]


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        if not ing.strip() or not usda.strip():
            return 0.0
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing = re.sub(r"^\s*\d+(\.\d+)?\s*(g|kg|oz|ml|lb)?\b", " ", ing)
        main = ing.split(",")[0]
        itoks = [t for t in _toks(main) if t not in _PREP]
        if not itoks:
            itoks = _toks(main)
        if not itoks:
            return 0.0
        ihead = itoks[-1]

        segs = [s for s in usda.split(",")]
        segtoks = [_toks(re.sub(r"\([^)]*\)", " ", s)) for s in segs]
        alltoks = [t for st in segtoks for t in st]
        if not alltoks:
            return 0.0
        uset = set(alltoks)
        first = set(segtoks[0]) if segtoks else set()
        firsttwo = set(t for st in segtoks[:2] for t in st)

        # coverage of ingredient identity tokens
        cov = sum(1 for t in itoks if t in uset) / float(len(itoks))
        head_in_first = ihead in first
        head_anywhere = ihead in uset
        head_in_firsttwo = ihead in firsttwo

        score = 0.0
        score += 4.0 * cov
        if head_in_first:
            score += 3.0
        elif head_in_firsttwo:
            score += 2.0
        elif head_anywhere:
            score += 1.0
        else:
            score -= 1.0

        # extra identity tokens in USDA primary segment that ingredient lacks (e.g. taco, patty, sauce)
        itok_all = set(_toks(ing))
        extra = [t for t in first if t not in itok_all and t not in _GENERIC and t not in _PREP]
        score -= 1.5 * min(len(extra), 3)
        # USDA head noun differs from ingredient head (first token of USDA)
        ufirst = segtoks[0][-1] if segtoks and segtoks[0] else ""
        if ufirst and ufirst != ihead and ufirst in itok_all:
            score += 0.5
        # extra content words in later segments that are not ingredient-related and not generic
        later = [t for st in segtoks[1:3] for t in st
                 if t not in itok_all and t not in _GENERIC and t not in _PREP]
        score -= 0.3 * min(len(later), 4)
        # sibling-food conflict: token overlap exists only via a non-head word
        if cov > 0 and not head_anywhere:
            score -= 1.5
        return max(0.0, min(10.0, score + 1.0))
    except Exception:
        return 0.0
