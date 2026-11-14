import re
import math

_UNITS = {
    "g", "gram", "grams", "kg", "mg", "ml", "l", "oz", "ounce", "ounces", "lb", "lbs",
    "pound", "pounds", "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pinch", "dash", "clove", "cloves", "piece", "pieces",
}

_NOISE = {
    "diced", "chopped", "minced", "sliced", "to", "taste", "from", "tube", "for",
    "garnish", "fresh", "freshly", "finely", "roughly", "coarsely", "thawed", "drained",
    "rinsed", "peeled", "trimmed", "cut", "into", "about", "of", "the", "a", "an",
    "optional", "or", "as", "needed", "large", "small", "medium", "whole", "with",
    "without", "plus", "more", "divided", "packed", "loosely", "firmly", "softened",
    "melted", "room", "temperature", "halved", "quartered", "cubed", "shredded",
    "grated", "crushed", "beaten", "lightly", "well", "in", "on", "at", "by",
}

# Words that describe state/quality rather than food identity.
_MODIFIERS = {
    "raw", "cooked", "boiled", "frozen", "canned", "dried", "dry", "lean", "fat",
    "ground", "roasted", "baked", "fried", "grilled", "smoked", "salted", "unsalted",
    "salt", "sweetened", "unsweetened", "powder", "powdered", "plain", "regular",
    "lowfat", "low", "reduced", "nonfat", "light", "all", "grades", "separable",
    "uncooked", "prepared", "ready", "commercial", "homemade", "made", "added",
    "heated", "stewed", "steamed", "broiled", "braised", "simmered", "pan", "solids",
    "liquids", "and", "only", "skinless", "boneless", "skin", "bone", "flesh",
    "halves", "pieces", "variety", "meats", "products", "by", "mature", "seeds",
    "type", "style", "brand", "fluid", "whole", "trimmed", "inch", "level",
    "choice", "select", "prime", "usda", "stick", "sticks", "spread", "mix",
}

# Words whose mismatch strongly signals a different food form.
_FORM_WORDS = {
    "powder", "canned", "spread", "salad", "patty", "sauce", "soup", "juice", "cookie",
    "cookies", "cake", "bar", "bars", "chips", "candy", "drink", "beverage", "syrup",
    "cereal", "crackers", "sandwich", "pie", "frozen", "dried", "liquid", "paste",
}


def _stem(w):
    try:
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]
        if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
            return w[:-2]
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w
    except Exception:
        return w


def _tokens(text):
    text = text.lower()
    text = re.sub(r"\d+(\.\d+)?\s*(g|kg|mg|ml|l|oz|lb)\b", " ", text)
    text = re.sub(r"[0-9/\"'%.]+", " ", text)
    return [t for t in re.findall(r"[a-z]+", text) if t]


def _ingredient_parts(ing):
    """Return (core tokens list, aside tokens list, is_compound)."""
    s = ing.lower()
    paren = " ".join(re.findall(r"\(([^)]*)\)", s))
    s = re.sub(r"\([^)]*\)", " ", s)
    main, _, post = s.partition(",")
    core_raw = _tokens(main)
    core_raw = [t for t in core_raw if t not in _UNITS]
    compound = "and" in core_raw or "&" in main or " with " in (" " + main + " ")
    core = [_stem(t) for t in core_raw if t not in _NOISE and t != "and"]
    aside = [_stem(t) for t in _tokens(post + " " + paren)
             if t not in _NOISE and t not in _UNITS]
    return core, aside, compound


def _usda_parts(desc):
    segs = [seg.strip() for seg in re.sub(r"\([^)]*\)", " ", desc.lower()).split(",")]
    segs = [seg for seg in segs if seg]
    out = []
    for seg in segs:
        toks = [_stem(t) for t in _tokens(seg) if t not in _NOISE or t == "and"]
        if toks:
            out.append(toks)
    return out


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.8
    # character bigram dice
    if len(a) < 3 or len(b) < 3:
        return 0.0
    ba = {a[i:i + 2] for i in range(len(a) - 1)}
    bb = {b[i:i + 2] for i in range(len(b) - 1)}
    d = 2.0 * len(ba & bb) / (len(ba) + len(bb))
    return d if d >= 0.75 else 0.0


def _weight(tok, idx, n):
    # Head-noun weighting: in English noun phrases the last word is the head.
    base = 0.35 if tok in _MODIFIERS else 1.0
    pos = 1.0 + 0.8 * (idx + 1) / max(n, 1)
    return base * pos


def judging_function(ingredient, usda_match):
    try:
        if not ingredient or not usda_match:
            return 0.0
        ingredient = str(ingredient)
        usda_match = str(usda_match)
        core, aside, compound = _ingredient_parts(ingredient)
        segs = _usda_parts(usda_match)
        if not core or not segs:
            return 0.0

        # Position weight of USDA tokens: earlier segments define the food.
        usda_tokens = []
        for si, seg in enumerate(segs):
            seg_w = 1.0 / (1.0 + 0.45 * si)
            for t in seg:
                if t == "and":
                    continue
                usda_tokens.append((t, si, seg_w))
        if not usda_tokens:
            return 0.0

        # 1. Weighted soft coverage of ingredient core tokens (recall).
        n = len(core)
        total_w = 0.0
        cov_w = 0.0
        head_hit = 0.0
        matched_usda = set()
        for i, tok in enumerate(core):
            w = _weight(tok, i, n)
            total_w += w
            best, best_j = 0.0, -1
            for j, (ut, si, sw) in enumerate(usda_tokens):
                s = _sim(tok, ut) * (0.6 + 0.4 * sw)
                if s > best:
                    best, best_j = s, j
            cov_w += w * best
            if best_j >= 0 and best > 0:
                matched_usda.add(best_j)
            if i == n - 1:
                head_hit = best
        recall = cov_w / total_w if total_w else 0.0

        # Aside tokens (post-comma, parentheticals) give a small bonus only.
        aside_bonus = 0.0
        if aside:
            hits = sum(1 for a in aside if any(_sim(a, ut) >= 0.8 for ut, _, _ in usda_tokens))
            aside_bonus = 0.05 * hits / len(aside)

        # 2. Precision on the USDA primary segment: unmatched content words there are
        #    usually a different product (brand names, salads, spreads).
        primary = [j for j, (ut, si, sw) in enumerate(usda_tokens) if si == 0]
        prim_content = [j for j in primary if usda_tokens[j][0] not in _MODIFIERS]
        if prim_content:
            prim_matched = sum(1 for j in prim_content if j in matched_usda or
                               any(_sim(usda_tokens[j][0], c) >= 0.75 for c in core))
            precision = prim_matched / len(prim_content)
        else:
            precision = 0.5

        # 3. Ordered bigram agreement between core and the flattened USDA text.
        core_bi = {(core[k], core[k + 1]) for k in range(len(core) - 1)}
        flat = [t for seg in segs for t in seg if t != "and"]
        usda_bi = {(flat[k], flat[k + 1]) for k in range(len(flat) - 1)}
        bigram = len(core_bi & usda_bi) / len(core_bi) if core_bi else 0.0

        # 4. Form-word conflicts: USDA has a product form word absent from ingredient.
        ing_all = set(core) | set(aside) | {_stem(t) for t in _tokens(ingredient)}
        usda_all = {t for t, _, _ in usda_tokens}
        form_conf = len({_stem(f) for f in _FORM_WORDS} & (usda_all - ing_all))
        form_conf_rev = len({_stem(f) for f in _FORM_WORDS} & ({_stem(t) for t in core} - usda_all))

        # Combine
        score = (
            0.45 * recall
            + 0.25 * precision
            + 0.15 * head_hit
            + 0.10 * bigram
            + aside_bonus
        )
        score -= 0.12 * form_conf + 0.10 * form_conf_rev
        if compound and not (bigram > 0.5 and precision > 0.8):
            score -= 0.2
        if head_hit == 0:
            score *= 0.6

        score = max(0.0, min(1.0, score))
        return round(10.0 * score, 4)
    except Exception:
        return 0.0
