import re

_VARIANT_CUES = {
    "flavored", "flavoured", "chocolate", "vanilla", "strawberry", "honey", "cinnamon",
    "maple", "caramel", "mint", "lemon", "orange", "berry", "plant", "vegan", "soy",
    "soymilk", "almond", "oat", "coconut", "veggie", "meatless", "imitation", "substitute",
    "light", "lite", "diet", "sugar-free", "reduced", "fat-free", "lowfat", "nonfat",
    "spicy", "bbq", "barbecue", "ranch", "frosted", "glazed", "fudge", "mocha",
}

_BRAND_WORDS = {
    "kraft", "nabisco", "kellogg", "kellogg's", "heinz", "hormel", "campbell's", "pillsbury",
    "oreo", "kfc", "mcdonald's", "starbucks", "quaker", "hershey's", "nestle", "tyson",
    "banquet", "stouffer's", "morningstar", "boca", "gardenburger", "silk", "lactaid",
    "smucker's", "jif", "skippy", "pete", "tabasco", "nutella", "jell-o", "reese's",
}

_EXEMPLARS = [
    ({"sandwich", "cookies"}, "oreo"), ({"sandwich", "cookie"}, "oreo"),
    ({"hazelnut"}, "nutella"), ({"hot", "sauce"}, "tabasco"), ({"sriracha"}, "pete"),
    ({"chile", "sauce"}, "pete"), ({"ketchup"}, "heinz"), ({"gelatin"}, "jell-o"),
]

_STOP = {
    "chopped", "sliced", "diced", "minced", "fresh", "frozen", "thawed", "warmed", "toasted",
    "cooked", "drained", "peeled", "grated", "shredded", "crushed", "whole", "large",
    "small", "medium", "to", "taste", "and", "or", "of", "the", "a", "with", "for", "from",
    "cut", "pieces", "finely", "roughly", "lightly", "tube", "raw",
}


def _toks(s):
    return re.findall(r"[a-z0-9][a-z0-9']*", (s or "").lower())


def _stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _match(a, b):
    a, b = _stem(a), _stem(b)
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.8
    return 0.0


def _is_brand(seg):
    s = seg.strip()
    if not s:
        return False
    if re.search(r"[™®]", s):
        return True
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) >= 3 and letters.isupper():
        return True
    if any(t in _BRAND_WORDS for t in _toks(s)):
        return True
    return False


def judging_function(ingredient, usda_match):
    try:
        ing = ingredient if isinstance(ingredient, str) else ""
        usda = usda_match if isinstance(usda_match, str) else ""
        if not ing.strip() or not usda.strip():
            return 0.0

        ing = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|oz|lb)\b", " ", ing, flags=re.I)
        ing = re.sub(r"\([^)]*\)", " ", ing)
        ing_head = ing.split(",")[0]
        ing_all = set(_toks(ing))
        core = [t for t in _toks(ing_head) if t not in _STOP and not t.isdigit()]
        if not core:
            core = _toks(ing_head) or list(ing_all)
        if not core:
            return 0.0

        # Segment the USDA description; separate branded segments
        parens = re.findall(r"\(([^)]*)\)", usda)
        body = re.sub(r"\([^)]*\)", " ", usda)
        segs = [s for s in body.split(",") if s.strip()]
        brand_segs = [s for s in segs if _is_brand(s)] + [p for p in parens if _is_brand(p)]
        gen_segs = [s for s in segs if not _is_brand(s)]
        gen_tokens = [t for s in gen_segs for t in _toks(s)]
        brand_tokens = set(t for s in brand_segs for t in _toks(s))
        all_usda = set(_toks(usda))

        # Recall of ingredient core in generic part
        hits = [max([_match(c, g) for g in gen_tokens] or [0.0]) for c in core]
        recall = sum(hits) / len(hits)
        # Is the head food (last core word, usually the noun) in the primary segment?
        primary = _toks(gen_segs[0]) if gen_segs else []
        head_noun = core[-1]
        head_hit = max([_match(head_noun, p) for p in primary] or [0.0])
        any_primary = max([_match(c, p) for c in core for p in primary] or [0.0])

        score = 20.0 + 45.0 * recall + 15.0 * head_hit + 10.0 * any_primary

        # Brand handling
        unreq_generic = {t for t in gen_tokens if t in _VARIANT_CUES and t not in ing_all}
        if brand_segs:
            exemplar = any(key <= ing_all and b in brand_tokens | all_usda for key, b in _EXEMPLARS)
            brand_variant = {t for t in brand_tokens if t in _VARIANT_CUES and t not in ing_all}
            if exemplar:
                score += 10.0
            elif recall >= 0.99 and not brand_variant and not unreq_generic:
                score += 3.0  # brand is just a label on the right product
            else:
                score -= 5.0  # brand without full identity match: likely a different product
            score -= 12.0 * len(brand_variant)
            score -= 8.0 * len(unreq_generic)
        else:
            score -= 6.0 * len(unreq_generic)

        # Mild precision term: many unrelated generic segments suggest a composite dish
        unrelated = 0
        for s in gen_segs[1:]:
            st = [t for t in _toks(s) if len(t) > 2]
            if st and max(_match(t, i) for t in st for i in ing_all) == 0.0:
                unrelated += 1
        score -= 1.5 * max(0, unrelated - 2)

        return round(max(0.0, min(100.0, score)), 3)
    except Exception:
        return 0.0
