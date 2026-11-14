import re

# Qualifier categories with "noticeability" weights: how much a diner would notice
# if this qualifier were added or dropped relative to the ingredient.
_QUALIFIER_CLASSES = {
    "flavor": (3.0, {"sweetened", "unsweetened", "salted", "unsalted", "spicy", "smoked",
                      "flavored", "honey", "sugar", "sugared", "cinnamon", "vanilla",
                      "chocolate", "barbecue", "bbq", "teriyaki", "garlic", "lemon",
                      "seasoned", "plain", "sour", "sweet", "hot", "mild", "nonfat",
                      "lowfat", "reduced", "light", "diet", "decaffeinated"}),
    "species": (4.0, {"beef", "pork", "lamb", "veal", "chicken", "turkey", "duck", "goat",
                       "salmon", "tuna", "cod", "kidney", "pinto", "navy", "black", "white",
                       "red", "green", "yellow", "brown", "wild", "basmati", "jasmine"}),
    "form": (2.5, {"ground", "powder", "powdered", "dried", "dehydrated", "paste", "sauce",
                    "juice", "crackers", "cracker", "chips", "flakes", "flour", "starch",
                    "relish", "puree", "concentrate", "syrup", "ball", "patty", "spread",
                    "canned", "frozen", "bottled", "instant", "whole", "sliced", "crushed"}),
    "processing": (1.5, {"toasted", "roasted", "fried", "baked", "boiled", "cooked",
                          "crude", "refined", "raw", "fresh", "cured", "pickled",
                          "fermented", "virgin", "extra", "pasteurized"}),
    "grade": (0.3, {"choice", "select", "prime", "commercial", "retail", "imported",
                     "domestic", "separable", "lean", "fat", "trimmed", "mature", "seeds",
                     "includes", "usda", "commodity", "regular", "prepared", "ns", "nfs",
                     "made", "from", "with", "without", "added", "only", "and", "or"}),
}

_PREP_NOISE = {"chopped", "diced", "minced", "divided", "optional", "thawed", "soaked",
               "overnight", "rinsed", "drained", "peeled", "to", "taste", "of", "visible",
               "for", "garnish", "large", "small", "medium", "about", "cup", "cups", "tbsp",
               "tsp", "the", "a", "an", "tube", "room", "temperature", "softened", "melted",
               "beaten", "halved", "quartered", "packed", "freshly", "finely", "roughly"}

# Processing words that are honoured if they appear in the ingredient's text (any part).
_STATE_WORDS = {"raw", "cooked", "fresh", "frozen", "canned", "dried", "toasted",
                "roasted", "bottled", "smoked"}


def _norm(word):
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text):
    return [_norm(t) for t in re.findall(r"[a-zA-Z]+", text or "")]


def _qual_class(tok):
    for name, (weight, words) in _QUALIFIER_CLASSES.items():
        if tok in words or tok + "s" in words or tok + "ed" in words:
            return name, weight
    return None, 0.0


def _clean_ingredient(ingredient):
    s = str(ingredient or "")
    s = re.sub(r"^\s*[\d.,/]+\s*(g|kg|mg|ml|l|oz|lb|grams?)?\b", " ", s, flags=re.I)
    parens = " ".join(re.findall(r"\(([^)]*)\)", s))
    s = re.sub(r"\([^)]*\)", " ", s)
    main, _, post = s.partition(",")
    return main, post + " " + parens


def _bigram_dice(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ga = {a[i:i + 2] for i in range(len(a) - 1)} or {a}
    gb = {b[i:i + 2] for i in range(len(b) - 1)} or {b}
    return 2.0 * len(ga & gb) / (len(ga) + len(gb))


def _soft_in(tok, pool, thr=0.8):
    best = 0.0
    for p in pool:
        d = _bigram_dice(tok, p)
        if d > best:
            best = d
    return best if best >= thr else 0.0


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        main, extra = _clean_ingredient(ingredient)
        ing_core = [t for t in _tokens(main) if t not in _PREP_NOISE and len(t) > 1]
        ing_extra = set(_tokens(extra))
        ing_all = set(ing_core) | ing_extra
        if not ing_core:
            ing_core = [t for t in _tokens(ingredient) if len(t) > 1]
            if not ing_core:
                return 0.0

        # USDA description as a specificity hierarchy: segment 0 = primary food,
        # later segments = progressively narrower qualifiers.
        segments = [seg.strip() for seg in str(usda_match).split(",") if seg.strip()]
        if not segments:
            return 0.0
        seg_tokens = [[t for t in _tokens(seg) if len(t) > 1] for seg in segments]
        usda_all = set(t for st in seg_tokens for t in st)

        # 1. Identity of the ingredient: content (non-qualifier) tokens must be found.
        ing_heads = [t for t in ing_core if _qual_class(t)[0] not in ("flavor", "processing", "grade")]
        if not ing_heads:
            ing_heads = ing_core
        head_hits = [(_soft_in(t, usda_all, 0.75)) for t in ing_heads]
        head_cov = sum(head_hits) / len(head_hits)
        # last token of the ingredient phrase is usually the head noun
        last_head = ing_heads[-1]
        last_hit = _soft_in(last_head, usda_all, 0.75)
        primary_hit = max([_soft_in(t, seg_tokens[0], 0.75) for t in ing_heads] + [0.0])

        # 2. Qualifiers the ingredient specified that the USDA entry drops.
        dropped = 0.0
        for t in ing_core:
            cls, w = _qual_class(t)
            if cls in ("flavor", "species", "form", "processing") and not _soft_in(t, usda_all, 0.85):
                # species words that are head-ish are already covered by head_cov
                dropped += w if cls != "species" else w * 0.6

        # 3. Qualifiers the USDA entry adds that the ingredient did not imply.
        #    Deeper segments are narrower; added qualifiers there cost a little more
        #    unless they are grade/boilerplate.
        added = 0.0
        unknown_added = 0
        for depth, st in enumerate(seg_tokens):
            depth_factor = 1.0 + 0.12 * min(depth, 5)
            for t in st:
                if _soft_in(t, ing_all, 0.85):
                    continue
                cls, w = _qual_class(t)
                if cls is None:
                    if depth == 0:
                        # an unrelated primary food word: strong sign of a different food
                        added += 2.0
                    else:
                        unknown_added += 1
                    continue
                if cls == "processing" and t in ("raw", "fresh") and not (ing_extra & _STATE_WORDS) and not (set(ing_core) & {"cooked", "toasted", "roasted", "fried", "baked"}):
                    continue  # raw/fresh is the default state of an unqualified ingredient
                if cls == "processing" and t in ("raw",) and (set(ing_core) & {"toasted", "roasted", "fried", "baked", "cooked"}):
                    added += 2.0
                    continue
                added += w * depth_factor * (0.5 if cls == "grade" else 1.0)
        added += 0.35 * min(unknown_added, 6)

        # 4. Generality preference: unqualified ingredient should map to a short entry.
        ing_qual_count = sum(1 for t in ing_core if _qual_class(t)[0] in ("flavor", "form", "processing"))
        usda_depth = len(segments)
        if ing_qual_count == 0:
            depth_pen = max(0, usda_depth - 2) * 0.4
        else:
            # specified variant: reward entries deep enough to carry the variant
            depth_pen = max(0, ing_qual_count + 1 - usda_depth) * 0.5

        score = 10.0
        score *= (0.25 + 0.75 * head_cov)
        score *= (0.55 + 0.45 * last_hit)
        score *= (0.75 + 0.25 * primary_hit)
        score -= 0.9 * dropped
        score -= 0.6 * added
        score -= depth_pen

        # Exact-name bonus for generic-to-generic matches.
        if " ".join(ing_core) == " ".join(seg_tokens[0]) and usda_depth <= 2:
            score += 2.0
        return round(max(0.0, min(12.0, score)), 4)
    except Exception:
        return 0.0
