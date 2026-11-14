import re

_QUAL_WORDS = {
    "sodium", "salt", "salted", "unsalted", "lowfat", "nonfat", "skim", "light", "lite", "diet",
    "sweetened", "unsweetened", "sugar", "flavored", "flavoured", "enriched", "fortified",
    "imitation", "artificial", "decaffeinated", "seasoned", "vitamin", "reduced", "low", "free",
    "added", "substitute", "fat", "milkfat",
}
_NEUTRAL = {"raw", "plain", "regular", "whole", "fresh", "all", "types", "commercial", "ns", "nfs"}
_GLUE = {"and", "or", "of", "the", "with", "a", "in", "for", "from", "to", "without", "no", "g"}


def _norm(s):
    s = str(s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|oz|ml|grams?)\b", " ", s)
    s = re.sub(r"low[\s-]fat", "lowfat", s)
    s = re.sub(r"(non|fat)[\s-](fat|free)", "nonfat", s)
    return s


def _stem(w):
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(s):
    return [_stem(w) for w in re.findall(r"[a-z]+", s)]


def judging_function(ingredient, usda_match):
    try:
        ing = _norm(ingredient)
        usda = _norm(usda_match)
        itok = _tokens(ing)
        segs = [x for x in usda.split(",") if x.strip()]
        if not itok or not segs:
            return 0.0
        iset = set(itok)

        # Stage 1: head-noun gate. Primary USDA food word(s) must appear in the ingredient.
        head = [t for t in _tokens(segs[0]) if t not in _GLUE]
        if not head:
            return 0.0
        head_hit = sum(1 for t in head if t in iset) / float(len(head))
        # last word of ingredient phrase is typically the head noun
        last_noun = [t for t in itok if t not in _GLUE and t not in _QUAL_WORDS]
        tail_hit = 1.0 if (last_noun and last_noun[-1] in set(_tokens(usda))) else 0.0
        gate = 0.6 * head_hit + 0.4 * tail_hit

        # Stage 2: per-segment qualifier audit, walking the comma descriptors
        # each USDA descriptor segment is judged; a segment carrying a qualifier word
        # that the ingredient did not state costs points, scaled by how many qualifier words it has.
        cost = 0.0
        for seg in segs:
            toks = [t for t in _tokens(seg) if t not in _GLUE]
            if not toks:
                continue
            q = [t for t in toks if t in _QUAL_WORDS and t not in iset]
            if q:
                cost += 1.5 + 0.5 * (len(q) - 1)
        if re.search(r"\d\s*%", usda) and not re.search(r"\d\s*%", ing):
            cost += 1.0
        # reverse: ingredient states a qualifier that USDA lacks
        uset = set(_tokens(usda))
        cost += 0.5 * sum(1 for t in iset if t in _QUAL_WORDS and t not in uset and t not in ("fat", "free"))

        base = 10.0 - 2.2 * cost
        return max(0.0, base) * (0.1 + 0.9 * gate) if base > 0 else 0.0
    except Exception:
        return 0.0
