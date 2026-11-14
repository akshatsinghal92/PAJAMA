import re

# Variant 7: deduction model. Start from a perfect identity score and subtract
# penalties for evidence that the two texts name DIFFERENT foods:
#  - the USDA primary noun is absent from the ingredient,
#  - the ingredient head noun is absent from the USDA primary/secondary field,
#  - known look-alike / confusable food pairs,
#  - USDA "compound" foods (frozen yogurt, fruit juice) whose head differs.
# Word comparison uses 5-character prefix keys to absorb plural/derivation noise.

_CONFUSABLE = [
    ("garlic", "guava"), ("chia", "flax"), ("yogurt", "frozen"),
    ("gnocchi", "potato"), ("corn", "cornmeal"), ("butter", "margarine"),
    ("cream", "creamer"), ("pea", "peanut"), ("rice", "ricotta"),
    ("lime", "lemon"), ("parsley", "cilantro"), ("ham", "hamburger"),
    ("oat", "oatmeal"), ("jam", "jelly"), ("sweet", "potato"),
]
_FILLER = set("""fresh frozen canned raw cooked uncooked chopped diced sliced minced
grated shredded large small medium whole thawed drained peeled plain regular
nfs ns and or of with without the a an in for from to style type baked boiled
roasted fried low fat reduced calorie lowfat nonfat sodium salt added""".split())


def _key(w):
    w = w.rstrip("s") if len(w) > 3 else w
    return w[:5]


def _content(seg):
    return [w for w in re.findall(r"[a-z]+", seg) if w not in _FILLER and len(w) > 1]


def _confusable(a, b):
    for x, y in _CONFUSABLE:
        if (a.startswith(x[:5]) and b.startswith(y[:5])) or (a.startswith(y[:5]) and b.startswith(x[:5])):
            return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing = str(ingredient or "").lower()
        usda = str(usda_match or "").lower()
        ing = re.sub(r"\([^)]*\)", " ", ing).split(",")[0]
        ing = re.sub(r"\b\d+(\.\d+)?\s*(g|kg|ml|oz|lb)?\b", " ", ing)
        usda = re.sub(r"\([^)]*\)", " ", usda)
        i_words = _content(ing)
        segs = [_content(s) for s in usda.split(",")]
        segs = [s for s in segs if s]
        if not i_words or not segs:
            return 0.0

        i_keys = [_key(w) for w in i_words]
        prim_keys = [_key(w) for w in segs[0]]
        sec_keys = [_key(w) for w in segs[1]] if len(segs) > 1 else []
        rest_keys = [_key(w) for s in segs[2:] for w in s]
        head = i_keys[-1]
        usda_head = prim_keys[-1]

        score = 10.0
        # 1. ingredient head must name the USDA identity
        if head in prim_keys:
            pass
        elif head in sec_keys:
            score -= 1.0
        elif head in rest_keys:
            score -= 4.0
        else:
            score -= 6.0

        # 2. USDA primary noun must be in the ingredient
        if usda_head not in i_keys:
            score -= 2.5
            # multi-word primary whose first word is in the ingredient ("frozen yogurt")
            if len(prim_keys) > 1 and prim_keys[0] not in i_keys:
                score -= 0.5

        # 3. unexplained ingredient modifiers that denote another food
        unexplained = [k for k in i_keys[:-1] if k not in prim_keys + sec_keys + rest_keys]
        score -= 0.8 * min(3, len(unexplained))

        # 4. known confusable pairs between heads
        for a in i_words:
            for b in segs[0] + (segs[1] if len(segs) > 1 else []):
                if a != b and _confusable(a, b):
                    score -= 2.0
                    break

        return round(max(0.0, min(10.0, score)), 2)
    except Exception:
        return 0.0
