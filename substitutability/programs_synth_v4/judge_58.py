import re

_UNITS_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*(?:g|kg|mg|ml|l|oz|lb|grams?)\b\.?\s*", re.I)
_PAREN_RE = re.compile(r"\(([^)]*)\)")

_PREP = {
    "fresh", "frozen", "thawed", "chopped", "diced", "sliced", "minced", "cubed", "cold",
    "warm", "warmed", "hot", "crumbled", "grated", "shredded", "peeled", "for", "serving",
    "to", "taste", "and", "or", "with", "of", "the", "a", "an", "in", "from", "tube",
    "optional", "divided", "packed", "softened", "melted", "room", "temperature", "strong",
    "brewed", "finely", "roughly", "large", "small", "medium", "whole", "plain",
}

_GENERIC_USDA = {
    "raw", "nfs", "ns", "commercial", "regular", "prepared", "ready", "eat", "ready-to-eat",
    "includes", "usda", "commodity", "fortified", "enriched", "packaged", "cereals", "cereal",
    "snacks", "snack", "nuts", "spices", "salad", "or", "and", "with", "without", "made",
    "type", "form", "style", "brand", "product", "products", "cooking", "leaf", "skin",
}

# Words that, when introduced by a branded entry but absent from the ingredient,
# signal a different variant / flavour / base.
_VARIANT_WORDS = {
    "chocolate", "vanilla", "strawberry", "blueberry", "cinnamon", "honey", "maple",
    "peanut", "almond", "soy", "oat", "rice", "coconut", "vegan", "plant", "plant-based",
    "meatless", "veggie", "vegetable", "frosted", "sugar", "sugared", "sweetened",
    "unsweetened", "light", "lite", "diet", "reduced", "fat", "free", "nonfat", "lowfat",
    "low", "sodium", "cheese", "cheddar", "bbq", "barbecue", "spicy", "hot", "ranch",
    "garlic", "onion", "lemon", "lime", "orange", "cherry", "raspberry", "apple", "banana",
    "mint", "caramel", "fudge", "marshmallow", "fruit", "flavored", "flavor", "glazed",
    "decaf", "decaffeinated", "gluten", "multigrain", "bran", "raisin", "nut", "nuts",
    "imitation", "substitute", "analog", "pumpkin", "spice", "berry", "berries",
}

_TM_HINTS = re.compile(r"(?:®|™|\(r\)|\(tm\)|'s\b)", re.I)


def _trigrams(word):
    w = "^" + word + "$"
    return {w[i:i + 3] for i in range(max(1, len(w) - 2))}


def _dice(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return 2.0 * len(ta & tb) / (len(ta) + len(tb))


def _words(text):
    return [w for w in re.findall(r"[a-z][a-z'\-]*", text.lower()) if len(w) > 1]


def _stem(w):
    w = w.strip("'-")
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxz":
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def _clean_ingredient(ing):
    s = ing or ""
    s = _UNITS_RE.sub("", s)
    parens = " ".join(_PAREN_RE.findall(s))
    s = _PAREN_RE.sub(" ", s)
    head = s.split(",")[0]
    return head, parens


def _segment_usda(usda):
    """Split USDA description into segments labelled 'brand' or 'generic'."""
    raw = usda or ""
    segs = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        letters = [c for c in p if c.isalpha()]
        upper_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0
        is_brand = False
        if len(letters) >= 3 and upper_ratio >= 0.85:
            is_brand = True
        elif _TM_HINTS.search(p):
            is_brand = True
        segs.append((p, is_brand))
    # Segments directly following a brand that use Title Case words are usually
    # the brand's product line name ("100% Natural Granola").
    labelled = []
    after_brand = False
    for p, is_brand in segs:
        kind = "brand" if is_brand else "generic"
        if not is_brand and after_brand:
            toks = p.split()
            caps = sum(1 for t in toks if t[:1].isupper())
            if toks and caps / len(toks) >= 0.6:
                kind = "product"
        labelled.append((p, kind))
        after_brand = after_brand or is_brand
    return labelled


def _best_match(word, pool):
    best = 0.0
    for p in pool:
        d = _dice(word, p)
        if d > best:
            best = d
            if best >= 1.0:
                break
    return best


def judging_function(ingredient, usda_match):
    try:
        if not isinstance(ingredient, str) or not isinstance(usda_match, str):
            return 0.0
        if not ingredient.strip() or not usda_match.strip():
            return 0.0

        head, parens = _clean_ingredient(ingredient)
        ing_words = [_stem(w) for w in _words(head) if w not in _PREP]
        if not ing_words:
            ing_words = [_stem(w) for w in _words(head)]
        if not ing_words:
            return 0.0
        ing_set = set(ing_words)
        paren_words = {_stem(w) for w in _words(parens)}

        segments = _segment_usda(usda_match)
        if not segments:
            return 0.0

        generic_words, brand_words, product_words = [], [], []
        for seg, kind in segments:
            ws = [_stem(w) for w in _words(seg)]
            if kind == "brand":
                brand_words.extend(ws)
            elif kind == "product":
                product_words.extend(ws)
            else:
                generic_words.extend(ws)

        has_brand = bool(brand_words)
        all_usda = generic_words + brand_words + product_words
        descriptive_pool = generic_words + product_words

        # 1. Coverage of ingredient words (fuzzy, weighted by position: the
        #    final word of the ingredient head is usually the core noun).
        n = len(ing_words)
        cov_num, cov_den = 0.0, 0.0
        for i, w in enumerate(ing_words):
            weight = 1.0 + (1.5 if i == n - 1 else 0.0)
            m_desc = _best_match(w, descriptive_pool) if descriptive_pool else 0.0
            m_brand = _best_match(w, brand_words) if brand_words else 0.0
            # Credit from a brand name only counts partially: the brand naming
            # a product (e.g. COCO-ROOS ~ chocolate) is weaker evidence.
            m = max(m_desc, 0.6 * m_brand)
            if m < 0.45:
                m = 0.0
            cov_num += weight * m
            cov_den += weight
        coverage = cov_num / cov_den if cov_den else 0.0

        # Primary-food alignment: first USDA segment vs ingredient core.
        first_seg_words = [_stem(w) for w in _words(segments[0][0])]
        core = ing_words[-1]
        primary_hit = max([_dice(core, f) for f in first_seg_words] + [0.0])
        primary_any = max([_dice(w, f) for w in ing_words for f in first_seg_words] + [0.0])

        # 2. Brand-implied variant drift: variant words carried by brand or
        #    product-line segments that the ingredient does not mention.
        brand_variant_drift = 0
        for w in set(brand_words + product_words):
            if w in _VARIANT_WORDS and w not in ing_set and w not in paren_words:
                if _best_match(w, ing_words) < 0.7:
                    brand_variant_drift += 1

        # Generic-segment variant drift (counts less; still a variant change).
        generic_variant_drift = 0
        for w in set(generic_words):
            if w in _VARIANT_WORDS and w not in ing_set and w not in _GENERIC_USDA:
                if _best_match(w, ing_words) < 0.7:
                    generic_variant_drift += 1

        # Plant-based / imitation markers are the strongest base change.
        base_shift = 0
        lowered = usda_match.lower()
        for marker in ("plant-based", "plant based", "meatless", "imitation", "substitute",
                       "vegan", "analog", "dairy-free", "non-dairy", "nondairy"):
            if marker in lowered and marker not in ingredient.lower():
                base_shift += 1

        # 3. Brand legitimacy: a brand is acceptable when the generic part of
        #    the entry already describes the ingredient well (standard example).
        if has_brand:
            generic_cover = 0.0
            if descriptive_pool:
                hits = [1.0 if _best_match(w, descriptive_pool) >= 0.6 else 0.0 for w in ing_words]
                generic_cover = sum(hits) / len(hits)
            brand_term = 1.2 * generic_cover - 0.6
        else:
            brand_term = 0.3

        # 4. Extra unexplained specificity in non-brand segments.
        extra = [w for w in set(generic_words)
                 if w not in _GENERIC_USDA and w not in _VARIANT_WORDS
                 and _best_match(w, ing_words) < 0.6]
        extra_pen = min(len(extra), 6) * 0.25

        score = 5.0
        score += 4.0 * (coverage - 0.5)
        score += 1.5 * primary_hit + 0.5 * primary_any - 1.0
        score += brand_term
        score -= 1.6 * brand_variant_drift
        score -= 0.7 * generic_variant_drift
        score -= 2.5 * base_shift
        score -= extra_pen

        if not any(_best_match(w, all_usda) >= 0.6 for w in ing_words):
            score -= 2.0

        return round(max(0.0, min(10.0, score)), 4)
    except Exception:
        return 0.0
