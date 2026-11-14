import re

_PREP = {
    "chopped", "sliced", "diced", "minced", "thawed", "frozen", "fresh", "raw", "cooked",
    "melted", "crumbled", "grated", "shredded", "peeled", "simmered", "boiled", "baked",
    "roasted", "toasted", "softened", "drained", "rinsed", "trimmed", "cubed", "halved",
    "large", "small", "medium", "lean", "whole", "finely", "roughly", "thinly", "for",
    "garnish", "to", "taste", "and", "or", "of", "the", "a", "an", "with", "in", "from",
    "skin", "on", "off", "optional", "about", "plus", "more", "extra", "dried", "dry",
}
_USDA_NOISE = {
    "nfs", "raw", "cooked", "unprepared", "prepared", "frozen", "canned", "fresh", "and",
    "or", "with", "without", "the", "of", "in", "from", "ns", "as", "to", "regular",
}


def _stem(w):
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _words(text):
    return [_stem(t) for t in re.findall(r"[a-zA-Z]+", text or "")]


def _ingredient_phrase(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.split(",")[0]
    s = re.sub(r"^\s*[\d./]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s, flags=re.I)
    toks = [w for w in _words(s) if w not in _PREP]
    return toks


def _usda_segments(usda):
    s = re.sub(r"\([^)]*\)", " ", str(usda or ""))
    segs = []
    for part in s.split(","):
        toks = [w for w in _words(part) if w not in _USDA_NOISE]
        if toks:
            segs.append(toks)
    return segs


def _compound_units(toks):
    """Return (head, modifiers): the last token is the head noun, the rest are modifiers
    that potentially form a compound with it."""
    if not toks:
        return None, []
    return toks[-1], toks[:-1]


def judging_function(ingredient, usda_match):
    try:
        ing = _ingredient_phrase(ingredient)
        segs = _usda_segments(usda_match)
        if not ing or not segs:
            return 0.0
        usda_all = [w for seg in segs for w in seg]
        usda_set = set(usda_all)
        primary = segs[0]
        head, mods = _compound_units(ing)

        score = 50.0

        # 1. Head noun integrity: the ingredient's head food must be in USDA.
        if head in usda_set:
            score += 20.0
            if head in primary:
                score += 8.0
        else:
            # head missing: maybe the compound collapsed (e.g. "zest" lost)
            score -= 30.0

        # 2. Modifier retention: each modifier forming part of the compound should appear.
        if mods:
            kept = sum(1 for m in mods if m in usda_set)
            frac = kept / float(len(mods))
            score += 22.0 * frac - 18.0 * (1.0 - frac)
            # bonus when the full compound appears adjacent in one segment
            for seg in segs:
                joined = " ".join(seg)
                if " ".join(ing[-2:]) in joined:
                    score += 8.0
                    break

        # 3. Compound hijack: ingredient head appears in USDA primary segment but as a
        # modifier of a different head (e.g. "kidney beans" for "beef kidney").
        if head in primary:
            idx = primary.index(head)
            following = [w for w in primary[idx + 1:] if w not in ing]
            if following:
                score -= 14.0 * min(2, len(following))
        # ingredient token used as modifier of a foreign head in primary
        if len(primary) >= 2:
            p_head = primary[-1]
            if p_head not in ing and any(w in ing for w in primary[:-1]):
                score -= 18.0

        # 4. Added modifiers in USDA that form a different food: extra words in the
        # primary segment not present in the ingredient.
        extra_primary = [w for w in primary if w not in ing]
        score -= 6.0 * len(extra_primary)

        # 5. Ingredient words entirely absent from USDA (lost parts of compound).
        missing = [w for w in ing if w not in usda_set]
        score -= 7.0 * len(missing)

        # 6. Generic catch-all USDA entries (NFS / lists of alternatives) dilute identity.
        raw_u = str(usda_match or "").lower()
        if re.search(r"\bnfs\b", raw_u):
            score -= 8.0
        if re.search(r"\bor\b", raw_u) and len(segs) >= 4:
            score -= 10.0

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
