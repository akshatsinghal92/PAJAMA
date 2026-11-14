import re

_NOTES = re.compile(
    r"\b(optional|to taste|for (?:garnish|serving|decoration|dusting|frying|greasing)|"
    r"as needed|if desired|divided|or more|plus extra|approximately|about|roughly)\b", re.I)
_WEIGHT = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|grams?|kg|ml|l)\b\.?\s*", re.I)

_STOP = {"a", "an", "the", "of", "and", "or", "with", "in", "for", "from", "to", "on",
         "into", "some", "each", "per", "inch", "tube", "jar", "can", "pack", "package",
         "bag", "box", "piece", "pieces", "large", "small", "medium", "good", "quality",
         "store", "bought", "homemade", "brand", "style", "type", "any", "kind"}

# prep words that change neither identity nor what a USDA entry would carry
_PREP = {"chopped", "diced", "minced", "sliced", "cubed", "crumbled", "shredded", "grated",
         "thawed", "rinsed", "drained", "trimmed", "peeled", "halved", "quartered",
         "julienned", "torn", "crushed", "beaten", "softened", "separated", "cut",
         "finely", "roughly", "coarsely", "thinly", "thickly", "freshly", "lightly",
         "washed", "pitted", "cored", "deseeded", "seeded", "stemmed", "ripe", "patted",
         "dry", "room", "temperature", "mixed", "combined", "packed", "heaping", "level"}

# mutually exclusive qualifier families: (family, members)
_FAMILIES = [
    ("heat", {"raw", "fresh", "uncooked"}, {"cooked", "boiled", "fried", "roasted", "baked",
                                            "grilled", "steamed", "braised", "broiled",
                                            "stewed", "smoked", "toasted", "sauteed"}),
    ("fat", {"whole", "full", "regular", "plain"}, {"lowfat", "low", "reduced", "nonfat",
                                                    "skim", "light", "lite", "fat-free",
                                                    "skinless"}),
    ("sweet", {"unsweetened", "plain"}, {"sweetened", "sugar", "honey", "flavored"}),
    ("salt", {"unsalted", "salt-free"}, {"salted", "salt"}),
    ("form", {"fresh"}, {"dried", "dehydrated", "powder", "powdered", "canned", "frozen"}),
]

_EXTRA_MATERIAL = {"lowfat", "nonfat", "reduced", "with", "sweetened", "flavored",
                   "imitation", "substitute", "breaded", "battered", "kernel", "souffle",
                   "stew", "soup", "salad", "sandwich", "pie", "dip", "spread", "mix",
                   "blend"}


def _stem(w):
    w = w.lower()
    for suf, rep in (("ies", "y"), ("oes", "o"), ("ves", "f"), ("ses", "s"),
                     ("es", "e"), ("s", "")):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


def _grams(w):
    w = "^" + w + "$"
    return {w[i:i + 3] for i in range(max(1, len(w) - 2))}


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.85
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / float(len(ga | gb))


def _tokens(text):
    return [t for t in re.findall(r"[a-z][a-z%\-]*", text.lower())]


def _clean_ingredient(s):
    s = _WEIGHT.sub("", s or "")
    s = _NOTES.sub(" ", s)
    s = re.sub(r"\(\s*\)", " ", s)
    return s


def _ingredient_slots(s):
    """Return list of (token, weight, role) for the whole ingredient string."""
    main = re.split(r"[,(]", s, 1)[0]
    rest = s[len(main):]
    main_t = [t for t in _tokens(main) if t not in _STOP]
    rest_t = [t for t in _tokens(rest) if t not in _STOP]
    slots = []
    content_main = [t for t in main_t if t not in _PREP]
    for i, t in enumerate(content_main):
        if i == len(content_main) - 1:
            slots.append((t, 3.0, "head"))
        else:
            slots.append((t, 1.6, "qual"))
    for t in rest_t:
        if t in _PREP:
            continue
        slots.append((t, 1.0, "tail"))
    return slots, main


def _family_of(tok):
    for name, a, b in _FAMILIES:
        if tok in a:
            return name, 0
        if tok in b:
            return name, 1
    return None, None


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ing = _clean_ingredient(str(ingredient))
        usda = str(usda_match)
        slots, main = _ingredient_slots(ing)
        if not slots:
            return 0.0
        u_tokens = [t for t in _tokens(usda) if t not in _STOP]
        u_stems = [_stem(t) for t in u_tokens]
        if not u_stems:
            return 0.0

        # 1) weighted coverage of each ingredient slot by its best USDA token
        total_w = 0.0
        covered = 0.0
        head_cov = 0.0
        used = set()
        for tok, w, role in slots:
            st = _stem(tok)
            best, bi = 0.0, -1
            for j, us in enumerate(u_stems):
                v = _sim(st, us)
                if v > best:
                    best, bi = v, j
            if best < 0.45:
                best = 0.0
            else:
                used.add(bi)
            total_w += w
            covered += w * best
            if role == "head":
                head_cov = best
        coverage = covered / total_w if total_w else 0.0

        # 2) contradictions between qualifier families
        ing_fams = {}
        for tok, _, _ in slots:
            f, side = _family_of(tok)
            if f:
                ing_fams.setdefault(f, set()).add(side)
        contra = 0
        u_fams = {}
        for t in u_tokens:
            f, side = _family_of(t)
            if f:
                u_fams.setdefault(f, set()).add(side)
        for f, sides in ing_fams.items():
            if f in u_fams and not (sides & u_fams[f]):
                contra += 1

        # 3) material USDA qualifiers absent from the ingredient
        ing_stems = {_stem(t) for t, _, _ in slots} | {_stem(t) for t in _tokens(ing)}
        extra = 0
        for j, t in enumerate(u_tokens):
            if j in used:
                continue
            if t in _EXTRA_MATERIAL and _stem(t) not in ing_stems:
                extra += 1
        extra = min(extra, 3)

        # 4) compound ingredient ("X and Y") where only one side is covered
        compound_pen = 0.0
        parts = re.split(r"\band\b|&", main)
        if len(parts) > 1:
            part_cov = []
            for p in parts:
                pt = [_stem(t) for t in _tokens(p) if t not in _STOP and t not in _PREP]
                if not pt:
                    continue
                hit = sum(1 for t in pt if any(_sim(t, u) >= 0.45 for u in u_stems))
                part_cov.append(hit / float(len(pt)))
            if part_cov and min(part_cov) < 0.34:
                compound_pen = 2.0

        # 5) leftover USDA content noise (mild)
        unused = len([j for j in range(len(u_tokens)) if j not in used])
        noise = min(unused, 8) * 0.08

        score = 10.0 * (0.55 * coverage + 0.45 * head_cov)
        if head_cov == 0.0:
            score *= 0.45
        score -= 1.8 * contra
        score -= 1.3 * extra
        score -= compound_pen
        score -= noise
        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
